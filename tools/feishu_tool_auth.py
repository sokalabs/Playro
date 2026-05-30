"""Authorization context for Feishu tools used by the comment agent.

The Feishu tool handlers are callable by an LLM, so every model-supplied
file/document token must be checked against the same comment access policy that
allowed the triggering event before any tenant-token API call is made.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from tools.registry import tool_error

logger = logging.getLogger(__name__)

_local = threading.local()


@dataclass(frozen=True)
class FeishuToolAuthContext:
    """Per-agent authorization scope for Feishu document/comment tools."""

    user_open_id: str
    current_file_type: str
    current_file_token: str
    current_wiki_token: str = ""


def set_authorization_context(
    *,
    user_open_id: str,
    current_file_type: str,
    current_file_token: str,
    current_wiki_token: str = "",
) -> None:
    """Install the current Feishu comment authorization scope for this thread."""
    _local.auth_context = FeishuToolAuthContext(
        user_open_id=(user_open_id or "").strip(),
        current_file_type=(current_file_type or "docx").strip() or "docx",
        current_file_token=(current_file_token or "").strip(),
        current_wiki_token=(current_wiki_token or "").strip(),
    )


def clear_authorization_context() -> None:
    """Clear the current thread's Feishu tool authorization scope."""
    _local.auth_context = None


def get_authorization_context() -> Optional[FeishuToolAuthContext]:
    """Return the current thread's Feishu tool authorization scope, if any."""
    return getattr(_local, "auth_context", None)


def _load_comment_rules_api():
    """Load Feishu comment rule helpers lazily."""
    from gateway.platforms.feishu_comment_rules import (
        is_user_allowed,
        load_config,
        resolve_rule,
    )

    return load_config, resolve_rule, is_user_allowed


def authorize_file_access(file_type: str, file_token: str, operation: str) -> Optional[str]:
    """Return ``None`` when access is allowed, otherwise a serialized tool error.

    This intentionally reloads the mtime-cached rules on every tool call so
    long-running agents observe hot-reloaded policy changes.  Wiki-token rule
    resolution is only reused for the already-verified triggering document;
    cross-document tool calls must match normal file-token/wildcard/top-level
    rules rather than inheriting the source document's wiki rule.
    """
    ctx = get_authorization_context()
    if ctx is None:
        logger.warning("[Feishu-Tool-Auth] Missing auth context for %s", operation)
        return tool_error("Feishu tool access denied: missing comment authorization context")

    target_type = (file_type or "docx").strip() or "docx"
    target_token = (file_token or "").strip()
    if not target_token:
        return tool_error("Feishu tool access denied: missing file token")
    if not ctx.user_open_id:
        logger.warning("[Feishu-Tool-Auth] Missing user for %s on %s:%s", operation, target_type, target_token)
        return tool_error("Feishu tool access denied: missing requesting user")

    try:
        load_config, resolve_rule, is_user_allowed = _load_comment_rules_api()
    except ImportError as exc:
        logger.exception("[Feishu-Tool-Auth] Failed to import comment rules: %s", exc)
        return tool_error("Feishu tool access denied: comment authorization unavailable")

    wiki_token = ""
    if target_type == ctx.current_file_type and target_token == ctx.current_file_token:
        wiki_token = ctx.current_wiki_token

    cfg = load_config()
    rule = resolve_rule(cfg, target_type, target_token, wiki_token=wiki_token)
    if not rule.enabled or not is_user_allowed(rule, ctx.user_open_id):
        logger.warning(
            "[Feishu-Tool-Auth] Denied %s for user=%s target=%s:%s rule=%s policy=%s enabled=%s",
            operation,
            ctx.user_open_id,
            target_type,
            target_token,
            rule.match_source,
            rule.policy,
            rule.enabled,
        )
        return tool_error("Feishu tool access denied by comment access policy")

    logger.debug(
        "[Feishu-Tool-Auth] Allowed %s for user=%s target=%s:%s rule=%s",
        operation,
        ctx.user_open_id,
        target_type,
        target_token,
        rule.match_source,
    )
    return None
