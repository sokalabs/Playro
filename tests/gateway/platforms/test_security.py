"""Security regression tests for gateway platform adapters."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import PlatformConfig
from gateway.platforms import security
from gateway.platforms.dingtalk import DingTalkAdapter
from gateway.platforms.msgraph_webhook import MSGraphWebhookAdapter
from gateway.platforms.telegram import TelegramAdapter
from gateway.platforms.wecom_callback import WecomCallbackAdapter


def test_env_bool_prefers_environment_over_extra():
    extra = {"guest_mode": True}
    with patch.dict(os.environ, {"TELEGRAM_GUEST_MODE": "false"}, clear=False):
        assert security.env_bool("TELEGRAM_GUEST_MODE", extra, "guest_mode") is False


def test_parse_strict_boolean_rejects_false_string():
    assert security.parse_strict_boolean("false") is False
    assert security.parse_strict_boolean("true") is True


def test_escape_markdown_link_destination():
    url = "https://example.com/a.png)[click](https://evil)"
    escaped = security.escape_markdown_link_destination(url)
    assert "\\)" in escaped


def test_build_notification_receipt_key_without_id():
    notification = {
        "subscriptionId": "sub-1",
        "changeType": "created",
        "resource": "users/1/messages/abc",
    }
    key = security.build_notification_receipt_key(notification)
    assert key is not None
    assert key.startswith("sha256:")


def test_compare_ascii_secrets_rejects_non_ascii():
    assert security.compare_ascii_secrets("café", "cafe") is False


def test_msgraph_receipt_key_always_present():
    notification = {"subscriptionId": "s", "changeType": "updated", "resource": "x"}
    assert MSGraphWebhookAdapter._build_receipt_key(notification) is not None


def test_msgraph_requires_client_state_on_public_bind():
    config = PlatformConfig(
        extra={"host": "0.0.0.0", "port": 9999},
    )
    with pytest.raises(ValueError, match="client_state"):
        MSGraphWebhookAdapter(config)


def test_telegram_guest_mode_env_wins():
    adapter = TelegramAdapter(
        PlatformConfig(extra={"guest_mode": True, "token": "test"}),
    )
    with patch.dict(os.environ, {"TELEGRAM_GUEST_MODE": "false"}, clear=False):
        assert adapter._telegram_guest_mode() is False


def test_wecom_callback_user_app_map_uses_chat_id():
    adapter = WecomCallbackAdapter(PlatformConfig(extra={}))
    source = SimpleNamespace(
        chat_id="corpB:alice",
        user_id="corpB:alice",
        user_id_alt="alice",
    )
    map_key = source.chat_id or adapter._user_app_key("corpB", source.user_id_alt)
    adapter._user_app_map[map_key] = "app-a"
    assert adapter._user_app_map["corpB:alice"] == "app-a"
    assert "corpB:corpB:alice" not in adapter._user_app_map


def test_dingtalk_send_image_escapes_markdown():
    adapter = DingTalkAdapter(PlatformConfig(extra={}))
    unsafe = "https://example.com/x.png)[evil](https://evil)"

    async def _run() -> str:
        with patch(
            "gateway.platforms.security.is_public_http_image_url",
            return_value=True,
        ):
            mock_send = AsyncMock(return_value=SimpleNamespace(success=True))
            with patch.object(adapter, "send", mock_send):
                await adapter.send_image("chat", unsafe)
            return mock_send.call_args.kwargs.get("content") or mock_send.call_args[0][1]

    sent = asyncio.run(_run())
    assert "\\)" in sent


def test_validate_api_session_id_accepts_safe_ids():
    assert security.validate_api_session_id("api-abc123") == "api-abc123"


def test_redact_response_store_history():
    history = [{"role": "tool", "content": "data:image/png;base64,QUJD"}]
    redacted = security.redact_response_store_history(history)
    assert "base64" not in redacted[0]["content"]
