"""Shared security helpers for gateway platform adapters."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

# Hostnames that bind only to the local machine.
LOOPBACK_HOSTS = frozenset({
    "127.0.0.1",
    "localhost",
    "::1",
    "ip6-localhost",
    "ip6-loopback",
})

DEFAULT_WEBHOOK_BIND_HOST = "127.0.0.1"
DEFAULT_MAX_WEBHOOK_BODY_BYTES = 1_048_576

# Markdown image/link destination metacharacters (CommonMark).
_MARKDOWN_DEST_ESCAPE_RE = re.compile(r"([\\\)])")


def is_loopback_host(host: str) -> bool:
    """True when host binds only to the local machine."""
    if not host:
        return False
    return host.strip().lower() in LOOPBACK_HOSTS


def is_production_deployment() -> bool:
    """Best-effort signal that webhook auth must be configured."""
    for key in ("HERMES_ENV", "NODE_ENV", "ENVIRONMENT"):
        val = os.getenv(key, "").strip().lower()
        if val in ("production", "prod"):
            return True
    return False


def env_bool(
    env_name: str,
    extra: Optional[Dict[str, Any]],
    key: str,
    *,
    default: bool = False,
    explicit_false: bool = False,
) -> bool:
    """Return a bool with environment variables overriding config.extra.

    When ``explicit_false`` is True (Slack-style gates), only explicit falsey
    strings disable the flag; the safe default is True.
    """
    env_val = os.getenv(env_name)
    if env_val is not None and str(env_val).strip() != "":
        lowered = str(env_val).strip().lower()
        if explicit_false:
            return lowered not in ("false", "0", "no", "off")
        return lowered in ("true", "1", "yes", "on")

    configured = (extra or {}).get(key)
    if configured is not None:
        if isinstance(configured, str):
            lowered = configured.strip().lower()
            if explicit_false:
                return lowered not in ("false", "0", "no", "off")
            return lowered in ("true", "1", "yes", "on")
        return bool(configured)
    return default


def env_csv_set(
    env_name: str,
    extra: Optional[Dict[str, Any]],
    key: str,
) -> Set[str]:
    """Parse a comma-separated allowlist with env overriding config.extra."""
    env_val = os.getenv(env_name)
    if env_val is not None and str(env_val).strip() != "":
        raw = env_val
    else:
        raw = (extra or {}).get(key)
    if raw is None:
        return set()
    if isinstance(raw, list):
        return {str(part).strip() for part in raw if str(part).strip()}
    return {part.strip() for part in str(raw).split(",") if part.strip()}


def parse_strict_boolean(value: Any, *, default: bool = False) -> bool:
    """Parse YAML/JSON booleans without treating ``\"false\"`` as true."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("false", "0", "no", "off"):
            return False
        if lowered in ("true", "1", "yes", "on"):
            return True
        return default
    return bool(value)


def escape_markdown_link_destination(url: str) -> str:
    """Escape characters that break ``![alt](url)`` markdown image syntax."""
    return _MARKDOWN_DEST_ESCAPE_RE.sub(r"\\\1", str(url or ""))


def is_public_http_image_url(url: str) -> bool:
    """Return True when url is a safe public http(s) image URL."""
    raw = str(url or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return False
    from tools.url_safety import is_safe_url

    return is_safe_url(raw)


def compare_ascii_secrets(provided: str, expected: str) -> bool:
    """Timing-safe secret compare that rejects non-ASCII inputs."""
    if not isinstance(provided, str) or not isinstance(expected, str):
        return False
    try:
        provided.encode("ascii")
        expected.encode("ascii")
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(provided, expected)


def build_notification_receipt_key(notification: Dict[str, Any]) -> Optional[str]:
    """Stable dedupe key for webhook notifications with or without top-level id."""
    explicit_id = str(notification.get("id") or "").strip()
    if explicit_id:
        return f"id:{explicit_id}"
    payload = json.dumps(
        {
            "subscriptionId": notification.get("subscriptionId"),
            "changeType": notification.get("changeType"),
            "resource": notification.get("resource"),
            "resourceData": notification.get("resourceData"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def webhook_auth_required(*, client_state: Optional[str], bind_host: str) -> bool:
    """Return True when inbound webhooks must present client_state/HMAC."""
    if client_state:
        return False
    if is_production_deployment():
        return True
    return not is_loopback_host(bind_host)


_API_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_MAX_API_TOOL_OUTPUT_CHARS = 32_768
_MAX_API_TOOL_PREVIEW_CHARS = 160
_MCP_MAX_ENCODED_IMAGE_BYTES = 8 * 1024 * 1024
_MCP_MAX_DECODED_IMAGE_BYTES = 6 * 1024 * 1024

# Inline reasoning tags must not reach OpenAI-compatible SSE consumers.
_STREAM_SUPPRESS_TAG_RE = re.compile(
    r"<(?:REASONING_SCRATCHPAD|think|thinking|reasoning|thought|redacted_thinking)\b[^>]*>.*?</(?:REASONING_SCRATCHPAD|think|thinking|reasoning|thought|redacted_thinking)>",
    re.DOTALL | re.IGNORECASE,
)
_STREAM_SUPPRESS_OPEN_TAG_RE = re.compile(
    r"<(?:REASONING_SCRATCHPAD|think|thinking|reasoning|thought|redacted_thinking)\b[^>]*>.*$",
    re.DOTALL | re.IGNORECASE,
)
_DATA_IMAGE_URL_RE = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+", re.IGNORECASE)


def validate_api_session_id(session_id: str) -> Optional[str]:
    """Return a safe API session id or None when untrusted."""
    value = str(session_id or "").strip()
    if not value:
        return None
    if re.search(r"[\r\n\x00]", value):
        return None
    if "/" in value or "\\" in value or ".." in value:
        return None
    if len(value) > 256:
        return None
    if not _API_SESSION_ID_RE.match(value):
        return None
    return value


def sanitize_sandbox_task_id(task_id: Optional[str]) -> str:
    """Map external session/task ids to a safe single sandbox path segment."""
    from utils import sanitize_sandbox_task_id as _sanitize

    return _sanitize(task_id)


def truncate_api_text(text: str, *, max_chars: int = _MAX_API_TOOL_OUTPUT_CHARS) -> str:
    """Bound serialized tool/output payloads for API streaming and storage."""
    raw = str(text or "")
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars] + "\n…[truncated]"


def redact_api_tool_output(text: Any) -> str:
    """Strip vision base64 and redact secrets from tool results exposed via API."""
    if text is None:
        return ""
    if isinstance(text, list):
        parts = []
        for item in text:
            if isinstance(item, dict):
                part_text = item.get("text")
                if part_text is not None:
                    parts.append(redact_api_tool_output(part_text))
            else:
                parts.append(redact_api_tool_output(item))
        return "\n".join(p for p in parts if p)
    raw = str(text)
    raw = _DATA_IMAGE_URL_RE.sub("[image data omitted]", raw)
    try:
        from agent.redact import redact_sensitive_text

        raw = redact_sensitive_text(raw)
    except Exception:
        pass
    return truncate_api_text(raw)


def sanitize_stream_delta_for_api(delta: Optional[str]) -> Optional[str]:
    """Remove suppressed reasoning tags before OpenAI-compatible SSE emission."""
    if delta is None:
        return None
    text = str(delta)
    if not text:
        return text
    cleaned = _STREAM_SUPPRESS_TAG_RE.sub("", text)
    cleaned = _STREAM_SUPPRESS_OPEN_TAG_RE.sub("", cleaned)
    return cleaned or None


def safe_tool_preview_label(
    function_name: str,
    function_args: Any,
    *,
    max_len: int = _MAX_API_TOOL_PREVIEW_CHARS,
) -> str:
    """Build a short, redacted tool preview safe for streaming API clients."""
    try:
        from agent.display import build_tool_preview

        args = function_args if isinstance(function_args, dict) else {}
        label = build_tool_preview(function_name, args, max_len=max_len) or function_name
    except Exception:
        label = str(function_name or "tool")
    try:
        from agent.redact import redact_sensitive_text

        label = redact_sensitive_text(label)
    except Exception:
        pass
    return truncate_api_text(label, max_chars=max_len)


def cache_image_bytes_within_limit(data: bytes) -> bool:
    """Return True when raw image bytes are within the shared cache size cap."""
    return len(data) <= _MCP_MAX_DECODED_IMAGE_BYTES


def mcp_image_block_within_limits(encoded_data: str) -> bool:
    """Return True when an MCP image block is within encoded/decoded size caps."""
    if not encoded_data:
        return False
    if len(encoded_data) > _MCP_MAX_ENCODED_IMAGE_BYTES:
        return False
    import base64

    try:
        decoded = base64.b64decode(encoded_data, validate=True)
    except (TypeError, ValueError):
        return False
    return len(decoded) <= _MCP_MAX_DECODED_IMAGE_BYTES


def redact_response_store_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Redact sensitive tool outputs before persisting Responses API state."""
    redacted: List[Dict[str, Any]] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        item = dict(entry)
        content = item.get("content")
        if isinstance(content, str):
            item["content"] = redact_api_tool_output(content)
        redacted.append(item)
    return redacted
