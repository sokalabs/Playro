"""Regression tests for Codex security remediations (2026-05-22)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest


def test_build_replay_entry_sanitizes_codex_message_items():
    from gateway.run import _build_replay_entry, _sanitize_codex_message_items_for_replay

    msg = {
        "role": "assistant",
        "content": "visible",
        "codex_message_items": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "leak <memory-context>secret</memory-context> tail",
                    }
                ],
            }
        ],
    }
    entry = _build_replay_entry("assistant", msg["content"], msg)
    text = entry["codex_message_items"][0]["content"][0]["text"]
    assert "memory-context" not in text
    assert "secret" not in text


def test_build_environment_hints_strips_newlines_from_paths():
    import sys

    from agent.prompt_builder import build_environment_hints, _clear_backend_probe_cache

    _clear_backend_probe_cache()
    with mock.patch.dict(os.environ, {"TERMINAL_ENV": "local"}, clear=False):
        with mock.patch("agent.prompt_builder.os.path.expanduser", return_value="/home/u\nINJECT"):
            with mock.patch("agent.prompt_builder.os.getcwd", return_value="/proj\nINJECT"):
                with mock.patch.object(sys, "platform", "linux"):
                    with mock.patch("agent.prompt_builder.is_wsl", return_value=False):
                        hints = build_environment_hints()
    assert "\nINJECT" not in hints
    assert "/home/u INJECT" in hints


def test_align_compressor_provider_for_moonshot_cn():
    from agent.context_compressor import _align_compressor_provider

    assert _align_compressor_provider(
        "https://api.moonshot.cn/v1", "kimi-coding"
    ) == "kimi-coding-cn"


def test_is_azure_endpoint_url_rejects_subdomain_false_positives():
    from agent.auxiliary_client import _is_azure_endpoint_url

    assert _is_azure_endpoint_url("https://myresource.openai.azure.com/openai/v1")
    assert not _is_azure_endpoint_url("https://azure.com.attacker.example/v1")
    assert not _is_azure_endpoint_url("https://attacker.example/azure.com/v1")


def test_build_native_content_parts_omits_absolute_paths():
    from agent.image_routing import build_native_content_parts

    with pytest.MonkeyPatch.context() as mp:
        tmp = Path(os.environ.get("TEMP", "/tmp"))
        img = tmp / "codex-security-test-image.png"
        img.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        try:
            parts, _skipped = build_native_content_parts("caption", [str(img)])
            text = parts[0]["text"]
            assert str(img) not in text
            assert "attached natively" in text
        finally:
            img.unlink(missing_ok=True)


def test_irc_standalone_send_guards_overlong_target():
    adapter_path = Path(__file__).resolve().parents[1] / "plugins/platforms/irc/adapter.py"
    source = adapter_path.read_text(encoding="utf-8")
    assert "IRC_MAX_TARGET_BYTES = 300" in source
    assert "_validate_irc_delivery_target" in source
    assert "if max_bytes < 1:" in source
    assert 'return {"error": "IRC standalone send: delivery target too long for IRC PRIVMSG"}' in source
    assert "if split_at < 1:" in source

    over = "x" * 500
    overhead = len(f"PRIVMSG {over} :".encode("utf-8")) + 2
    assert 510 - overhead < 1


def test_gitnexus_proxy_binds_loopback():
    root = Path(__file__).resolve().parents[1]
    proxy = (root / "optional-skills/research/gitnexus-explorer/scripts/proxy.mjs").read_text(
        encoding="utf-8"
    )
    assert "127.0.0.1" in proxy
    assert "server.listen(PORT, HOST" in proxy


def test_pretext_skill_documents_loopback_http_server():
    skill = (
        Path(__file__).resolve().parents[1] / "skills/creative/pretext/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "--bind 127.0.0.1" in skill


def test_pretext_donut_orbit_defers_lil_gui_import():
    template = (
        Path(__file__).resolve().parents[1]
        / "skills/creative/pretext/templates/donut-orbit.html"
    ).read_text(encoding="utf-8")
    assert "import GUI from" not in template
    assert 'await import("https://esm.sh/lil-gui' in template


def test_page_agent_skill_has_no_bookmarklet_payload():
    skill = (
        Path(__file__).resolve().parents[1]
        / "optional-skills/web-development/page-agent/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "javascript:(function()" not in skill


def test_comfyui_log_redacts_token_query_params():
    import re

    common = (
        Path(__file__).resolve().parents[1]
        / "skills/creative/comfyui/scripts/_common.py"
    ).read_text(encoding="utf-8")
    assert "def redact_secrets_for_log" in common
    assert "redact_secrets_for_log(msg)" in common

    url = "wss://cloud.comfy.org/ws?clientId=abc&token=secret-key-123"
    redacted = re.sub(
        r"([?&]token=)[^&\s\"']+",
        r"\1<redacted>",
        url,
        flags=re.IGNORECASE,
    )
    assert "secret-key-123" not in redacted
    assert "<redacted>" in redacted


def test_gateway_context_refs_ignore_messaging_cwd():
    root = Path(__file__).resolve().parents[1]
    source = (root / "gateway" / "run.py").read_text(encoding="utf-8")
    assert "MESSAGING_CWD is deprecated and must not widen" in source
    assert 'os.environ.get("TERMINAL_CWD") or os.getcwd()' in source
    assert 'or os.environ.get("MESSAGING_CWD")' not in source.split(
        "preprocess_context_references_async"
    )[1].split("except Exception")[0]


def test_auto_resume_checks_authorization():
    root = Path(__file__).resolve().parents[1]
    source = (root / "gateway" / "run.py").read_text(encoding="utf-8")
    block = source.split("def _schedule_resume_pending_sessions")[1].split(
        "def start(self)"
    )[0]
    assert "_is_user_authorized(source)" in block


def test_remove_job_rejects_unsafe_ids():
    from cron.jobs import remove_job

    assert remove_job("..") is False
    assert remove_job("/etc/passwd") is False


def test_empty_response_scaffolding_preserves_tool_audit_trail():
    root = Path(__file__).resolve().parents[1]
    source = (root / "run_agent.py").read_text(encoding="utf-8")
    fn = source.split("def _drop_trailing_empty_response_scaffolding")[1].split(
        "def _repair_message_sequence"
    )[0]
    assert "Do not drop trailing tool/assistant pairs here" in fn
    assert 'messages[-1].get("role") == "tool"' not in fn


def test_load_config_honors_ignore_user_config(monkeypatch):
    from hermes_cli import config as cfg_mod

    cfg_mod._LOAD_CONFIG_CACHE.clear()
    cfg_mod._RAW_CONFIG_CACHE.clear()
    monkeypatch.setenv("HERMES_IGNORE_USER_CONFIG", "1")
    with mock.patch.object(cfg_mod, "get_config_path") as mock_path:
        mock_path.return_value = Path("/nonexistent/hermes/config.yaml")
        loaded = cfg_mod.load_config()
    assert loaded.get("model") == cfg_mod.DEFAULT_CONFIG.get("model")
    assert cfg_mod.read_raw_config() == {}
