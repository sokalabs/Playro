"""Security regressions for gateway API server and shared helpers."""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import patch

import pytest

from gateway.platforms import security
from gateway.platforms.api_server import APIServerAdapter, _IdempotencyCache, _make_request_fingerprint
from gateway.platforms.base import BasePlatformAdapter, cache_image_from_bytes


def test_validate_api_session_id_rejects_traversal():
    assert security.validate_api_session_id("../../etc/passwd") is None
    assert security.validate_api_session_id("good-session_1") == "good-session_1"


def test_redact_api_tool_output_strips_data_urls():
    payload = "prefix data:image/png;base64,QUJD suffix"
    redacted = security.redact_api_tool_output(payload)
    assert "base64" not in redacted
    assert "[image data omitted]" in redacted


def test_sanitize_stream_delta_for_api_removes_reasoning_tags():
    delta = "hello <think>secret</think> world"
    assert security.sanitize_stream_delta_for_api(delta) == "hello  world"


def test_mcp_image_block_within_limits():
    small = base64.b64encode(b"x" * 16).decode("ascii")
    assert security.mcp_image_block_within_limits(small) is True
    huge = "A" * (security._MCP_MAX_ENCODED_IMAGE_BYTES + 1)
    assert security.mcp_image_block_within_limits(huge) is False


def test_idempotency_fingerprint_includes_session_key_and_history():
    body = {"model": "hermes", "messages": [{"role": "user", "content": "hi"}]}
    history = [{"role": "user", "content": "hi"}]
    fp_a = _make_request_fingerprint(
        body,
        keys=["model", "messages"],
        session_key="scope-a",
        conversation_history=history,
    )
    fp_b = _make_request_fingerprint(
        body,
        keys=["model", "messages"],
        session_key="scope-b",
        conversation_history=history,
    )
    assert fp_a != fp_b


def test_idempotency_fingerprint_includes_gateway_context():
    body = {"model": "hermes", "messages": [{"role": "user", "content": "hi"}]}
    fp_a = _make_request_fingerprint(
        body,
        keys=["model", "messages"],
        gateway_context={"platform": "discord", "chat_id": "chat-a"},
    )
    fp_b = _make_request_fingerprint(
        body,
        keys=["model", "messages"],
        gateway_context={"platform": "discord", "chat_id": "chat-b"},
    )
    assert fp_a != fp_b


@pytest.mark.asyncio
async def test_idempotency_cache_shields_inflight_from_waiter_cancel():
    cache = _IdempotencyCache()
    compute_cancelled = False

    async def slow():
        nonlocal compute_cancelled
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            compute_cancelled = True
            raise
        return "ok"

    cancelled_waiter = asyncio.create_task(cache.get_or_set("k", "fp", slow))
    await asyncio.sleep(0.05)
    concurrent_waiter = asyncio.create_task(cache.get_or_set("k", "fp", slow))
    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter
    assert not compute_cancelled
    assert await concurrent_waiter == "ok"


def test_api_server_excludes_session_search_toolset():
    adapter = APIServerAdapter.__new__(APIServerAdapter)
    with patch(
        "hermes_cli.tools_config._get_platform_tools",
        return_value={"session_search", "terminal"},
    ):
        with patch("gateway.run._resolve_runtime_agent_kwargs", return_value={}):
            with patch("gateway.run._load_gateway_config", return_value={}):
                with patch("gateway.run._resolve_gateway_model", return_value="hermes"):
                    with patch(
                        "gateway.run.GatewayRunner._load_reasoning_config",
                        return_value={},
                    ):
                        with patch(
                            "gateway.run.GatewayRunner._load_fallback_model",
                            return_value=None,
                        ):
                            with patch("run_agent.AIAgent") as mock_agent:
                                adapter._ensure_session_db = lambda: None
                                adapter._create_agent(session_id="api-test")
    enabled = mock_agent.call_args.kwargs["enabled_toolsets"]
    assert "session_search" not in enabled


def test_gateway_context_without_toolsets_preserves_api_server_defaults():
    adapter = APIServerAdapter.__new__(APIServerAdapter)

    def platform_tools(_config, platform):
        if platform == "discord":
            return {"discord_only"}
        return {"terminal", "file", "session_search"}

    with patch("hermes_cli.tools_config._get_platform_tools", side_effect=platform_tools):
        with patch("gateway.run._resolve_runtime_agent_kwargs", return_value={}):
            with patch("gateway.run._load_gateway_config", return_value={}):
                with patch("gateway.run._resolve_gateway_model", return_value="hermes"):
                    with patch("gateway.run.GatewayRunner._load_reasoning_config", return_value={}):
                        with patch("gateway.run.GatewayRunner._load_fallback_model", return_value=None):
                            with patch("run_agent.AIAgent") as mock_agent:
                                adapter._ensure_session_db = lambda: None
                                adapter._create_agent(
                                    session_id="api-test",
                                    gateway_context={"platform": "discord", "chat_id": "123"},
                                )

    enabled = mock_agent.call_args.kwargs["enabled_toolsets"]
    assert enabled == ["file", "terminal"]


def test_cache_image_from_bytes_rejects_oversized_payload():
    with pytest.raises(ValueError, match="larger than allowed"):
        cache_image_from_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (7 * 1024 * 1024))


def test_extract_local_files_skips_untrusted_paths(tmp_path):
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"\x89PNG\r\n\x1a\n")
    content = f"See {secret}"
    paths, cleaned = BasePlatformAdapter.extract_local_files(content)
    assert paths == []
    assert str(secret) in cleaned or "See" in cleaned
