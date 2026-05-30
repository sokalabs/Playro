#!/usr/bin/env python3
"""
Chrome DevTools Protocol (CDP) helper tool.

Exposes a single tool, ``browser_cdp``, that sends a small allowlist of
low-risk CDP commands to an isolated managed CDP-backed browser session.
User-supplied live Chrome CDP overrides are disabled for safety; this tool
should only operate against managed sessions that already have a supervisor
attached.

This is a narrow escape hatch for browser operations not covered by the main
browser tool surface (``browser_navigate``, ``browser_click``,
``browser_console``, etc.). It intentionally blocks sensitive CDP domains such
as Runtime, Network, Storage, DOM, Target enumeration, and similar APIs that
can bypass browser origin and cookie protections.

Method reference: https://chromedevtools.github.io/devtools-protocol/
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

CDP_DOCS_URL = "https://chromedevtools.github.io/devtools-protocol/"

# Keep this list intentionally small. Raw CDP can bypass same-origin and
# HttpOnly cookie protections, so browser_cdp must not expose cookie/storage,
# network, DOM, JavaScript evaluation, target enumeration, or other broad
# browser-state APIs to prompt-injected page content.
SAFE_CDP_METHODS = frozenset(
    {
        "Browser.getVersion",
        "Emulation.clearDeviceMetricsOverride",
        "Emulation.setDeviceMetricsOverride",
        "Page.handleJavaScriptDialog",
        "Page.reload",
        "Page.stopLoading",
    }
)


def _cdp_method_error(method: str) -> Optional[str]:
    """Return an error string when ``method`` is not safe to expose."""
    if method in SAFE_CDP_METHODS:
        return None
    allowed = ", ".join(sorted(SAFE_CDP_METHODS))
    return (
        f"CDP method {method!r} is not allowed by browser_cdp. "
        "Raw CDP access is restricted because sensitive domains can expose "
        "cookies, storage, page contents, or arbitrary browser state. "
        f"Allowed methods: {allowed}."
    )

# ``websockets`` is a transitive dependency of hermes-agent (via fal_client
# and firecrawl-py) and is already imported by gateway/platforms/feishu.py.
# Wrap the import so a clean error surfaces if the package is ever absent.
try:
    import websockets
    from websockets.exceptions import WebSocketException

    _WS_AVAILABLE = True
except ImportError:
    websockets = None  # type: ignore[assignment]
    WebSocketException = Exception  # type: ignore[assignment,misc]
    _WS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Async-from-sync bridge (matches the pattern in homeassistant_tool.py)
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine from a sync handler, safe inside or outside a loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Endpoint resolution
# ---------------------------------------------------------------------------


def _resolve_cdp_endpoint() -> str:
    """Return the normalized CDP WebSocket URL, or empty string if unavailable.

    Delegates to ``tools.browser_tool._get_cdp_override``. Live Chrome CDP
    overrides are disabled there, so this only returns a value if a future
    isolated backend intentionally provides one.
    """
    try:
        from tools.browser_tool import _get_cdp_override  # type: ignore[import-not-found]

        return (_get_cdp_override() or "").strip()
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("browser_cdp: failed to resolve CDP endpoint: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Core CDP call
# ---------------------------------------------------------------------------


async def _cdp_call(
    ws_url: str,
    method: str,
    params: Dict[str, Any],
    target_id: Optional[str],
    timeout: float,
) -> Dict[str, Any]:
    """Make a single CDP call, optionally attaching to a target first.

    When ``target_id`` is provided, we call ``Target.attachToTarget`` with
    ``flatten=True`` to multiplex a page-level session over the same
    browser-level WebSocket, then send ``method`` with that ``sessionId``.
    When ``target_id`` is None, ``method`` is sent at browser level for
    allowlisted browser-scoped methods such as ``Browser.getVersion``.
    """
    assert websockets is not None  # guarded by _WS_AVAILABLE at call-site

    async with websockets.connect(
        ws_url,
        max_size=None,  # CDP responses (e.g. DOM.getDocument) can be large
        open_timeout=timeout,
        close_timeout=5,
        ping_interval=None,  # CDP server doesn't expect pings
    ) as ws:
        next_id = 1
        session_id: Optional[str] = None

        # --- Step 1: attach to target if requested ---
        if target_id:
            attach_id = next_id
            next_id += 1
            await ws.send(
                json.dumps(
                    {
                        "id": attach_id,
                        "method": "Target.attachToTarget",
                        "params": {"targetId": target_id, "flatten": True},
                    }
                )
            )
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Timed out attaching to target {target_id}"
                    )
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                msg = json.loads(raw)
                if msg.get("id") == attach_id:
                    if "error" in msg:
                        raise RuntimeError(
                            f"Target.attachToTarget failed: {msg['error']}"
                        )
                    session_id = msg.get("result", {}).get("sessionId")
                    if not session_id:
                        raise RuntimeError(
                            "Target.attachToTarget did not return a sessionId"
                        )
                    break
                # Ignore events (messages without "id") while waiting

        # --- Step 2: dispatch the real method ---
        call_id = next_id
        next_id += 1
        req: Dict[str, Any] = {
            "id": call_id,
            "method": method,
            "params": params or {},
        }
        if session_id:
            req["sessionId"] = session_id
        await ws.send(json.dumps(req))

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out waiting for response to {method}"
                )
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            msg = json.loads(raw)
            if msg.get("id") == call_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error: {msg['error']}")
                return msg.get("result", {})
            # Ignore events / out-of-order responses


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------


def _browser_cdp_via_supervisor(
    task_id: str,
    frame_id: str,
    method: str,
    params: Optional[Dict[str, Any]],
    timeout: float,
) -> str:
    """Route a CDP call through the live supervisor session for an OOPIF frame.

    Looks up the frame in the supervisor's snapshot, extracts its child
    ``cdp_session_id``, and dispatches ``method`` with that sessionId via
    the supervisor's already-connected WebSocket (using
    ``asyncio.run_coroutine_threadsafe`` onto the supervisor loop).
    """
    try:
        from tools.browser_supervisor import SUPERVISOR_REGISTRY  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover — defensive
        return tool_error(
            f"CDP supervisor is not available: {exc}. frame_id routing requires "
            f"a running supervisor attached to an active managed browser session."
        )

    supervisor = SUPERVISOR_REGISTRY.get(task_id)
    if supervisor is None:
        return tool_error(
            f"No CDP supervisor is attached for task={task_id!r}. Call "
            f"browser_navigate first so the supervisor can attach to a managed "
            f"browser session. Once attached, browser_snapshot will populate "
            f"frame_tree with frame_ids you can pass here."
        )

    snap = supervisor.snapshot()
    # Search both the top frame and the children for the requested id.
    top = snap.frame_tree.get("top")
    frame_info: Optional[Dict[str, Any]] = None
    if top and top.get("frame_id") == frame_id:
        frame_info = top
    else:
        for child in snap.frame_tree.get("children", []) or []:
            if child.get("frame_id") == frame_id:
                frame_info = child
                break
    if frame_info is None:
        # Check the raw frames dict too (frame_tree is capped at 30 entries)
        with supervisor._state_lock:  # type: ignore[attr-defined]
            raw = supervisor._frames.get(frame_id)  # type: ignore[attr-defined]
        if raw is not None:
            frame_info = raw.to_dict()

    if frame_info is None:
        return tool_error(
            f"frame_id {frame_id!r} not found in supervisor state. "
            f"Call browser_snapshot to see current frame_tree."
        )

    child_sid = frame_info.get("session_id")
    if not child_sid:
        # Same-origin iframes do not get their own sessionId; use the
        # standard browser tools rather than broad JavaScript evaluation via
        # raw CDP.
        return tool_error(
            f"frame_id {frame_id!r} is not an out-of-process iframe (no "
            f"dedicated CDP session). Use browser_snapshot or another "
            f"dedicated browser tool for same-origin iframe inspection."
        )

    # Dispatch onto the supervisor's loop.
    import asyncio as _asyncio
    loop = supervisor._loop  # type: ignore[attr-defined]
    if loop is None or not loop.is_running():
        return tool_error(
            "CDP supervisor loop is not running. Restart the managed browser session."
        )

    async def _do_cdp():
        return await supervisor._cdp(  # type: ignore[attr-defined]
            method,
            params or {},
            session_id=child_sid,
            timeout=timeout,
        )

    try:
        fut = _asyncio.run_coroutine_threadsafe(_do_cdp(), loop)
        result_msg = fut.result(timeout=timeout + 2)
    except Exception as exc:
        return tool_error(
            f"CDP call via supervisor failed: {type(exc).__name__}: {exc}",
            cdp_docs=CDP_DOCS_URL,
        )

    payload: Dict[str, Any] = {
        "success": True,
        "method": method,
        "frame_id": frame_id,
        "session_id": child_sid,
        "result": result_msg.get("result", {}),
    }
    return json.dumps(payload, ensure_ascii=False)


def browser_cdp(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    target_id: Optional[str] = None,
    frame_id: Optional[str] = None,
    timeout: float = 30.0,
    task_id: Optional[str] = None,
) -> str:
    """Send an allowlisted CDP command. See ``CDP_DOCS_URL`` for documentation.

    Args:
        method: Safe CDP method name, e.g. ``"Browser.getVersion"``.
        params: Method-specific parameters; defaults to ``{}``.
        target_id: Optional target/tab ID for page-level methods.  When set,
            we first attach to the target (``flatten=True``) and send
            ``method`` with the resulting ``sessionId``.  Uses a fresh
            stateless CDP connection.
        frame_id: Optional cross-origin (OOPIF) iframe ``frame_id`` from
            ``browser_snapshot.frame_tree.children[]``.  When set (and the
            frame is an OOPIF with a live session tracked by the CDP
            supervisor), routes the call through the supervisor's existing
            WebSocket for allowlisted frame-scoped methods on backends where
            per-call fresh CDP connections would hit signed-URL expiry
            (Browserbase) or expensive reattach.
        timeout: Seconds to wait for the call to complete.
        task_id: Task identifier for supervisor lookup.  When ``frame_id``
            is set, this identifies which task's supervisor to use; the
            handler will default to ``"default"`` otherwise.

    Returns:
        JSON string ``{"success": True, "method": ..., "result": {...}}`` on
        success, or ``{"error": "..."}`` on failure.
    """
    if not method or not isinstance(method, str):
        return tool_error(
            "'method' is required (e.g. 'Browser.getVersion')",
            cdp_docs=CDP_DOCS_URL,
        )

    call_params: Dict[str, Any] = params or {}
    if not isinstance(call_params, dict):
        return tool_error(
            f"'params' must be an object/dict, got {type(call_params).__name__}"
        )

    method_error = _cdp_method_error(method)
    if method_error:
        return tool_error(method_error, method=method, cdp_docs=CDP_DOCS_URL)

    # --- Route iframe-scoped calls through the supervisor ---------------
    if frame_id:
        return _browser_cdp_via_supervisor(
            task_id=task_id or "default",
            frame_id=frame_id,
            method=method,
            params=call_params,
            timeout=timeout,
        )
    del task_id  # stateless path below

    if not _WS_AVAILABLE:
        return tool_error(
            "The 'websockets' Python package is required but not installed. "
            "Install it with: pip install websockets"
        )

    endpoint = _resolve_cdp_endpoint()
    if not endpoint:
        return tool_error(
            "No managed CDP endpoint is available. Live Chrome CDP overrides "
            "are disabled for safety; use the standard isolated browser tools "
            "instead. The Camofox backend is REST-only and does not expose CDP.",
            cdp_docs=CDP_DOCS_URL,
        )

    if not endpoint.startswith(("ws://", "wss://")):
        return tool_error(
            f"CDP endpoint is not a WebSocket URL: {endpoint!r}. "
            "Expected ws://... or wss://... from an isolated managed browser "
            "backend."
        )

    try:
        safe_timeout = float(timeout) if timeout else 30.0
    except (TypeError, ValueError):
        safe_timeout = 30.0
    safe_timeout = max(1.0, min(safe_timeout, 300.0))

    try:
        result = _run_async(
            _cdp_call(endpoint, method, call_params, target_id, safe_timeout)
        )
    except asyncio.TimeoutError as exc:
        return tool_error(
            f"CDP call timed out after {safe_timeout}s: {exc}",
            method=method,
        )
    except TimeoutError as exc:
        return tool_error(str(exc), method=method)
    except RuntimeError as exc:
        return tool_error(str(exc), method=method)
    except WebSocketException as exc:
        return tool_error(
            f"WebSocket error talking to CDP at {endpoint}: {exc}. The "
            "managed browser may have disconnected — restart the browser session.",
            method=method,
        )
    except Exception as exc:  # pragma: no cover — unexpected
        logger.exception("browser_cdp unexpected error")
        return tool_error(
            f"Unexpected error: {type(exc).__name__}: {exc}",
            method=method,
        )

    payload: Dict[str, Any] = {
        "success": True,
        "method": method,
        "result": result,
    }
    if target_id:
        payload["target_id"] = target_id
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


BROWSER_CDP_SCHEMA: Dict[str, Any] = {
    "name": "browser_cdp",
    "description": (
        "Send a safe allowlisted Chrome DevTools Protocol (CDP) command. "
        "Narrow escape hatch for browser operations not covered by "
        "browser_navigate, browser_click, browser_console, etc. Sensitive "
        "CDP domains such as Runtime, Network, Storage, DOM, and Target "
        "enumeration are blocked.\n\n"
        "**Requires a reachable CDP endpoint.** Available when the user has "
        "an isolated managed browser exposes CDP, or when "
        "'browser.cdp_url' is set in config.yaml. Not currently wired up for "
        "cloud backends (Browserbase, Browser Use, Firecrawl) — those expose "
        "CDP per session but live-session routing is a follow-up. Camofox is "
        "REST-only and will never support CDP. If the tool is in your toolset "
        "at all, a CDP endpoint is already reachable.\n\n"
        f"**CDP method reference:** {CDP_DOCS_URL} — use web_extract on a "
        "method's URL (e.g. '/tot/Page/#method-handleJavaScriptDialog') "
        "to look up parameters and return shape.\n\n"
        "**Allowed methods:** Browser.getVersion, "
        "Emulation.clearDeviceMetricsOverride, "
        "Emulation.setDeviceMetricsOverride, Page.handleJavaScriptDialog, "
        "Page.reload, Page.stopLoading.\n\n"
        "**Common patterns:**\n"
        "- Handle a native JS dialog: method='Page.handleJavaScriptDialog', "
        "params={'accept': true, 'promptText': ''}, target_id=<tabId>\n"
        "- Set viewport for a tab: method='Emulation.setDeviceMetricsOverride', "
        "params={'width': 1280, 'height': 720, 'deviceScaleFactor': 1, "
        "'mobile': false}, target_id=<tabId>\n\n"
        "**Usage rules:**\n"
        "- Browser.getVersion omits target_id and frame_id.\n"
        "- Page.* and Emulation.* methods can pass target_id for top-level "
        "tab scope when needed.\n"
        "- **Cross-origin iframe scope** for allowlisted Page.* or "
        "Emulation.* methods: pass frame_id from the "
        "browser_snapshot frame_tree output. This routes through the CDP "
        "supervisor's live connection — the only reliable way on "
        "Browserbase where stateless CDP calls hit signed-URL expiry.\n"
        "- Each stateless call (without frame_id) is independent — sessions "
        "and event subscriptions do not persist between calls. For stateful "
        "workflows, prefer the dedicated browser tools or use frame_id "
        "routing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": (
                    "Allowed CDP method name, e.g. 'Browser.getVersion' "
                    "or 'Page.handleJavaScriptDialog'."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Method-specific parameters as a JSON object. Omit or "
                    "pass {} for methods that take no parameters."
                ),
                "properties": {},
                "additionalProperties": True,
            },
            "target_id": {
                "type": "string",
                "description": (
                    "Optional. Target/tab ID from browser_snapshot metadata "
                    "or another trusted source. Use for page-level methods "
                    "at the top-level tab scope. Mutually exclusive with "
                    "frame_id."
                ),
            },
            "frame_id": {
                "type": "string",
                "description": (
                    "Optional. Out-of-process iframe (OOPIF) frame_id from "
                    "browser_snapshot.frame_tree.children[] where "
                    "is_oopif=true. When set, routes the call through the "
                    "CDP supervisor's live session for that iframe. "
                    "Useful for allowed Page.* or Emulation.* calls inside "
                    "cross-origin iframes, especially on Browserbase where "
                    "fresh per-call CDP connections can't keep up with "
                    "signed URL rotation."
                ),
            },
            "timeout": {
                "type": "number",
                "description": (
                    "Timeout in seconds (default 30, max 300)."
                ),
                "default": 30,
            },
        },
        "required": ["method"],
    },
}


def _browser_cdp_check() -> bool:
    """Availability check for browser_cdp.

    The tool is only offered when the Python side can actually reach an
    isolated managed CDP endpoint right now. User-supplied live Chrome CDP
    overrides are disabled for safety.

    Backends that do *not* currently expose CDP to us — Camofox (REST-only),
    the default local agent-browser mode (Playwright hides its internal CDP
    port), and cloud providers whose per-session ``cdp_url`` is not yet
    surfaced — are gated out so the model doesn't see a tool that would
    reliably fail.  Cloud-provider CDP routing is a follow-up.

    Kept in a thin wrapper so the registration statement stays at module top
    level (the tool-discovery AST scan only picks up top-level
    ``registry.register(...)`` calls).
    """
    try:
        from tools.browser_tool import (  # type: ignore[import-not-found]
            _get_cdp_override,
            check_browser_requirements,
        )
    except ImportError as exc:  # pragma: no cover — defensive
        logger.debug("browser_cdp check: browser_tool import failed: %s", exc)
        return False
    if not check_browser_requirements():
        return False
    return bool(_get_cdp_override())


registry.register(
    name="browser_cdp",
    toolset="browser-cdp",
    schema=BROWSER_CDP_SCHEMA,
    handler=lambda args, **kw: browser_cdp(
        method=args.get("method", ""),
        params=args.get("params"),
        target_id=args.get("target_id"),
        frame_id=args.get("frame_id"),
        timeout=args.get("timeout", 30.0),
        task_id=kw.get("task_id"),
    ),
    check_fn=_browser_cdp_check,
    emoji="🧪",
)
