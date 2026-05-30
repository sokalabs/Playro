"""Safe formatting helpers for background process notifications.

Background process output is attacker-controlled (for example, from test suites,
package scripts, or repositories). These helpers intentionally keep raw process
output out of synthetic agent messages so completion notifications remain a
status signal instead of a prompt-injection channel.
"""

from __future__ import annotations

from typing import Any

from tools.ansi_strip import strip_ansi

_OUTPUT_OMITTED_NOTICE = (
    "Output omitted from this automatic notification because process output is "
    "untrusted. Inspect the process log explicitly with the terminal/process "
    "tools if you need the output."
)


def _safe_inline(value: Any, *, default: str = "unknown", max_len: int = 300) -> str:
    """Return a single-line, bounded representation for notification metadata."""
    if value is None:
        text = default
    else:
        text = strip_ansi(str(value))
    text = text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
    text = "".join(ch if ord(ch) >= 32 or ch == "\t" else "?" for ch in text)
    if not text:
        text = default
    if len(text) > max_len:
        text = text[: max_len - 15] + "...(truncated)"
    return text


def format_background_process_notification(evt: dict) -> str | None:
    """Format a queue event without embedding untrusted process output."""
    evt_type = evt.get("type", "completion")
    sid = _safe_inline(evt.get("session_id"))
    if evt_type == "watch_disabled":
        message = _safe_inline(evt.get("message", "Watch patterns disabled."), max_len=600)
        return f"[IMPORTANT: {message}]"

    if evt_type == "watch_match":
        pattern = _safe_inline(evt.get("pattern", "?"), default="?", max_len=200)
        suppressed = evt.get("suppressed", 0)
        text = (
            f"[IMPORTANT: Background process {sid} matched "
            f"watch pattern \"{pattern}\".\n"
            f"Command: omitted from this automatic notification.\n"
            f"Matched output: {_OUTPUT_OMITTED_NOTICE}"
        )
        if suppressed:
            text += f"\n({_safe_inline(suppressed, default='0')} earlier matches were suppressed by rate limit)"
        text += "]"
        return text

    if evt_type != "completion":
        return None

    exit_code = _safe_inline(evt.get("exit_code", "?"), default="?")
    return (
        f"[IMPORTANT: Background process {sid} completed "
        f"(exit code {exit_code}).\n"
        f"Command: omitted from this automatic notification.\n"
        f"Output: {_OUTPUT_OMITTED_NOTICE}]"
    )


__all__ = ["format_background_process_notification"]
