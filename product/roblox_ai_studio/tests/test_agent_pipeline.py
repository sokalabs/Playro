import json
import os
from pathlib import Path

from product.roblox_ai_studio.hermes_backend import agent_pipeline as ap
from product.roblox_ai_studio.hermes_backend.agent_pipeline import _extract_json


def test_extract_json_ignores_braces_inside_strings():
    payload = _extract_json('prefix {"message": "keep {this} text", "ok": true} suffix')

    assert payload is not None
    assert json.loads(payload) == {"message": "keep {this} text", "ok": True}


def test_extract_json_handles_escaped_quotes_before_closing_object():
    raw = r'log {"message": "quoted \"brace } text\"", "ok": true} done'
    payload = _extract_json(raw)

    assert payload is not None
    assert json.loads(payload)["ok"] is True


def test_hermes_agent_uses_safe_default_toolsets_and_scrubbed_env(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, **kwargs})

        class Result:
            returncode = 0
            stdout = '{"title": "Test", "files": []}'

        return Result()

    monkeypatch.setattr(ap, "_resolve_hermes_bin", lambda: str(tmp_path / "hermes"))
    monkeypatch.setattr(ap.HermesRobloxSession, "local", lambda project_root: ap.HermesRobloxSession(project_root=project_root))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    inherited_home = tmp_path / "inherited-hermes"
    monkeypatch.setenv("HERMES_HOME", str(inherited_home))
    monkeypatch.setenv("PLAYRO_HERMES_TOOLSETS", "file,terminal,memory,skills,cronjob,session_search,custom")
    monkeypatch.setenv("UNRELATED_SECRET_TOKEN", "do-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-leak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "do-not-leak")
    monkeypatch.setenv("PLAYRO_RUNTIME_FLAG", "keep-me")
    monkeypatch.setenv("PLAYRO_API_TOKEN", "do-not-leak")
    monkeypatch.setenv("PLAYRO_OPENAI_API_KEY", "do-not-leak")
    monkeypatch.setenv("PLAYRO_CLIENT_SECRET", "do-not-leak")
    monkeypatch.setenv("PLAYRO_ALLOW_API_TOKEN", "do-not-leak")
    monkeypatch.setenv("PLAYRO_RUNTIME_SECRET", "do-not-leak")
    monkeypatch.setenv("PLAYRO_RUNTIME_AUTH_KEY", "do-not-leak")
    monkeypatch.setenv("PLAYRO_MEMORY_MODE", "keep-memory-mode")
    monkeypatch.setenv("PLAYRO_HERMES_HOME", "keep-hermes-home")
    monkeypatch.setenv("PLAYRO_HERMES_BIN", "keep-hermes-bin")
    monkeypatch.setenv("PLAYRO_ALLOW_PATH_HERMES", "1")
    monkeypatch.setenv("PLAYRO_ALLOW_TEST_FLAG", "1")
    monkeypatch.setenv("PLAYRO_RUNTIME_ENDPOINT", "keep-runtime-endpoint")
    monkeypatch.setenv("PATH", "runtime-path")
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("SYSTEMROOT", "C:\\Windows")
    monkeypatch.setenv("COMSPEC", "C:\\Windows\\System32\\cmd.exe")
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")

    result = ap._run_hermes_agent("make a safe obby", timeout=1)

    assert result["agent_ran"] is True
    assert len(calls) == 1
    command = calls[0]["cmd"]
    toolsets = command[command.index("-t") + 1].split(",")
    assert toolsets == ["file", "skills", "fact_store"]
    assert "terminal" not in toolsets
    assert "cronjob" not in toolsets
    assert "session_search" not in toolsets
    assert "memory" not in toolsets

    env = calls[0]["env"]
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["HERMES_ROBLOX_MODE"] == "1"
    assert env["PLAYRO_MEMORY_MODE"] == "holographic"
    hermes_home = Path(env["HERMES_HOME"])
    assert hermes_home.name == "hermes"
    assert hermes_home.parent.name == ".playro"
    assert hermes_home != inherited_home
    assert env["PLAYRO_RUNTIME_FLAG"] == "keep-me"
    assert env["PLAYRO_MEMORY_MODE"] == "holographic"
    assert env["PLAYRO_HERMES_HOME"] == "keep-hermes-home"
    assert env["PLAYRO_HERMES_BIN"] == "keep-hermes-bin"
    assert env["PLAYRO_ALLOW_PATH_HERMES"] == "1"
    assert env["PLAYRO_ALLOW_TEST_FLAG"] == "1"
    assert env["PLAYRO_RUNTIME_ENDPOINT"] == "keep-runtime-endpoint"
    assert env["PATH"] == "runtime-path"
    assert env["TEMP"] == str(tmp_path / "temp")
    assert env["TMP"] == str(tmp_path / "tmp")
    assert env["SYSTEMROOT"] == "C:\\Windows"
    assert env["COMSPEC"] == "C:\\Windows\\System32\\cmd.exe"
    assert env["PATHEXT"] == ".COM;.EXE;.BAT;.CMD"
    assert "UNRELATED_SECRET_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "PLAYRO_API_TOKEN" not in env
    assert "PLAYRO_OPENAI_API_KEY" not in env
    assert "PLAYRO_CLIENT_SECRET" not in env
    assert "PLAYRO_ALLOW_API_TOKEN" not in env
    assert "PLAYRO_RUNTIME_SECRET" not in env
    assert "PLAYRO_RUNTIME_AUTH_KEY" not in env

    cwd = Path(calls[0]["cwd"])
    assert cwd.name == "roblox_ai_studio"
    assert "product" in cwd.parts


def test_agent_prompt_uses_product_relative_generated_projects_path():
    prompt = ap._agent_prompt("make a safe obby")

    assert "Output the project to generated_projects/<slug>/" in prompt
    assert "Output the project to product/roblox_ai_studio/generated_projects/<slug>/" not in prompt


def test_hermes_agent_refine_uses_passed_project_path():
    import tempfile
    from unittest import mock

    captured_prompts: list[str] = []

    def fake_run(cmd, **kwargs):
        captured_prompts.append(cmd[cmd.index("-q") + 1])

        class Result:
            returncode = 0
            stdout = '{"changes": ["added coins"]}'

        return Result()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        custom_project = tmp_path / "playro-data" / "legacy-obby"
        custom_project.mkdir(parents=True)
        with (
            mock.patch.object(ap, "_resolve_hermes_bin", return_value=str(tmp_path / "hermes")),
            mock.patch.object(
                ap.HermesRobloxSession,
                "local",
                side_effect=lambda project_root: ap.HermesRobloxSession(project_root=project_root),
            ),
            mock.patch.object(ap.subprocess, "run", side_effect=fake_run),
        ):
            ap._run_hermes_agent(
                "add coin shop",
                timeout=1,
                refine=True,
                original_prompt="make a legacy obby",
                project_path=str(custom_project),
            )

        assert len(captured_prompts) == 1
        assert str(custom_project.resolve()) in captured_prompts[0]
        default_slug_dir = "generated_projects" + os.sep + "make-a-legacy-obby"
        assert default_slug_dir not in captured_prompts[0]


def test_hermes_toolset_override_requires_opt_in_and_denies_risky_tools(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
            stdout = "{}"

        return Result()

    monkeypatch.setattr(ap, "_resolve_hermes_bin", lambda: str(tmp_path / "hermes"))
    monkeypatch.setattr(ap.HermesRobloxSession, "local", lambda project_root: ap.HermesRobloxSession(project_root=project_root))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    monkeypatch.setenv("PLAYRO_ALLOW_UNSAFE_HERMES_TOOLSETS", "1")
    monkeypatch.setenv("PLAYRO_HERMES_TOOLSETS", "file, Terminal ,skills,cronjob,fact_store, SESSION_SEARCH , ToDo ")

    ap._run_hermes_agent("make a safe obby", timeout=1)

    toolsets = calls[0][calls[0].index("-t") + 1].split(",")
    assert toolsets == ["file", "skills", "fact_store"]


def test_hermes_toolset_env_is_ignored_without_opt_in(monkeypatch):
    monkeypatch.delenv("PLAYRO_ALLOW_UNSAFE_HERMES_TOOLSETS", raising=False)
    monkeypatch.setenv("PLAYRO_HERMES_TOOLSETS", "file,custom,skills")

    assert ap._select_hermes_toolsets() == "file,skills,fact_store"


def test_hermes_toolset_override_allows_custom_toolsets_when_opted_in(monkeypatch):
    monkeypatch.setenv("PLAYRO_ALLOW_UNSAFE_HERMES_TOOLSETS", "1")
    monkeypatch.setenv("PLAYRO_HERMES_TOOLSETS", "file, custom , Terminal , ToDo")

    assert ap._select_hermes_toolsets() == "file,skills,fact_store,custom"


def test_resolve_hermes_bin_requires_path_opt_in_for_path_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("PLAYRO_HERMES_BIN", raising=False)
    monkeypatch.delenv("PLAYRO_HERMES_HOME", raising=False)
    monkeypatch.delenv("PLAYRO_ALLOW_PATH_HERMES", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))

    try:
        ap._resolve_hermes_bin()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("PATH fallback should require PLAYRO_ALLOW_PATH_HERMES")

    monkeypatch.setenv("PLAYRO_ALLOW_PATH_HERMES", "yes")

    assert ap._resolve_hermes_bin() == "hermes"


def test_resolve_hermes_bin_requires_explicit_bin_to_exist(monkeypatch, tmp_path):
    hermes_bin = tmp_path / ("hermes.exe" if os.name == "nt" else "hermes")
    monkeypatch.setenv("PLAYRO_HERMES_BIN", str(hermes_bin))

    try:
        ap._resolve_hermes_bin()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("PLAYRO_HERMES_BIN should point to an existing trusted setup path")

    hermes_bin.write_text("", encoding="utf-8")

    assert ap._resolve_hermes_bin() == str(hermes_bin.resolve())


def test_resolve_hermes_bin_rejects_explicit_directory(monkeypatch, tmp_path):
    hermes_dir = tmp_path / "hermes-dir"
    hermes_dir.mkdir()
    monkeypatch.setenv("PLAYRO_HERMES_BIN", str(hermes_dir))

    try:
        ap._resolve_hermes_bin()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("PLAYRO_HERMES_BIN must point to a file, not a directory")


def test_resolve_hermes_bin_ignores_live_hermes_home_without_dev_opt_in(monkeypatch, tmp_path):
    live_home = tmp_path / "live-hermes"
    live_bin = live_home / "hermes-agent" / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    live_bin.mkdir(parents=True)
    (live_bin / ("hermes.exe" if os.name == "nt" else "hermes")).write_text("", encoding="utf-8")

    monkeypatch.delenv("PLAYRO_HERMES_BIN", raising=False)
    monkeypatch.delenv("PLAYRO_HERMES_HOME", raising=False)
    monkeypatch.delenv("PLAYRO_ALLOW_PATH_HERMES", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(live_home))

    try:
        resolved = ap._resolve_hermes_bin()
    except FileNotFoundError:
        return

    assert str(live_home) not in resolved


def _make_bundled_engine_bin(tmp_path: Path) -> Path:
    """Build the bundled-engine layout (<root>/.venv/Scripts/hermes) with marker."""

    agent_root = tmp_path / "hermes-agent"
    bin_dir = agent_root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True)
    hermes_bin = bin_dir / ("hermes.exe" if os.name == "nt" else "hermes")
    hermes_bin.write_text("", encoding="utf-8")
    (agent_root / ap.PLAYRO_ENGINE_MARKER).write_text("Playro engine bundle\n", encoding="utf-8")
    return hermes_bin


def test_detect_engine_kind_identifies_bundled_playro_engine(tmp_path):
    hermes_bin = _make_bundled_engine_bin(tmp_path)

    assert ap._detect_engine_kind(str(hermes_bin)) == "playro"


def test_detect_engine_kind_defaults_to_hermes_without_marker(tmp_path):
    hermes_bin = tmp_path / ("hermes.exe" if os.name == "nt" else "hermes")
    hermes_bin.write_text("", encoding="utf-8")

    assert ap._detect_engine_kind(str(hermes_bin)) == "hermes"


def test_detect_engine_kind_honors_explicit_override(monkeypatch, tmp_path):
    bundled = _make_bundled_engine_bin(tmp_path)

    monkeypatch.setenv("PLAYRO_ENGINE_KIND", "hermes")
    assert ap._detect_engine_kind(str(bundled)) == "hermes"

    plain = tmp_path / "plain-hermes"
    plain.write_text("", encoding="utf-8")
    monkeypatch.setenv("PLAYRO_ENGINE_KIND", "playro")
    assert ap._detect_engine_kind(str(plain)) == "playro"


def test_bundled_playro_engine_skips_chat_and_marks_deterministic_primary(monkeypatch, tmp_path):
    hermes_bin = _make_bundled_engine_bin(tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):  # pragma: no cover - must never be reached
        calls.append(cmd)
        raise AssertionError("bundled Playro engine must not spawn `hermes chat`")

    monkeypatch.setattr(ap, "_resolve_hermes_bin", lambda: str(hermes_bin))
    monkeypatch.setattr(ap.HermesRobloxSession, "local", lambda project_root: ap.HermesRobloxSession(project_root=project_root))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)

    result = ap._run_hermes_agent("make a safe obby", timeout=1)

    assert calls == []
    assert result["engine_kind"] == "playro"
    assert result["agent_ran"] is False
    assert result["agent_available"] is True
    assert result["deterministic_primary"] is True
    assert result["toolsets"] == "file,skills,fact_store"
    assert "chat not applicable" in result["fallback_reason"]


def test_real_hermes_engine_still_runs_chat(monkeypatch, tmp_path):
    hermes_bin = tmp_path / ("hermes.exe" if os.name == "nt" else "hermes")
    hermes_bin.write_text("", encoding="utf-8")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
            stdout = '{"title": "Test", "files": []}'

        return Result()

    monkeypatch.setattr(ap, "_resolve_hermes_bin", lambda: str(hermes_bin))
    monkeypatch.setattr(ap.HermesRobloxSession, "local", lambda project_root: ap.HermesRobloxSession(project_root=project_root))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)

    result = ap._run_hermes_agent("make a safe obby", timeout=1)

    assert result["engine_kind"] == "hermes"
    assert result["agent_ran"] is True
    assert len(calls) == 1
    assert calls[0][1] == "chat"


def test_engine_pipeline_label_distinguishes_primary_from_fallback():
    assert ap._engine_pipeline_label({"agent_ran": True}) == "Hermes agent"
    assert (
        ap._engine_pipeline_label({"agent_ran": False, "deterministic_primary": True})
        == "Playro engine (deterministic)"
    )
    assert ap._engine_pipeline_label({"agent_ran": False}) == "Deterministic fallback"


def test_hermes_agent_redacts_stdout_summary_and_structured_output(monkeypatch, tmp_path):
    aws_key = "AKIA" + "IOSFODNN7EXAMPLE"

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = (
                'Created project at C:\\Users\\Alice\\secret-game with api_key="sk-live-secret123"\n'
                '{"title":"Secret Path Game",'
                '"notes":"Wrote /Users/alice/private/game and used ghp_abcd1234SECRET",'
                f'"config":{{"token":"{aws_key}","password":"hunter2",'
                '"safe":"keep this detail"}}'
            )

        return Result()

    monkeypatch.setattr(ap, "_resolve_hermes_bin", lambda: str(tmp_path / "hermes"))
    monkeypatch.setattr(ap.HermesRobloxSession, "local", lambda project_root: ap.HermesRobloxSession(project_root=project_root))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)

    result = ap._run_hermes_agent("make a secret obby", timeout=1)

    summary = result["agent_summary"]
    structured = result["structured_output"]
    serialized_structured = json.dumps(structured)

    assert "Secret Path Game" in summary
    assert "keep this detail" in serialized_structured
    assert "[REDACTED_SECRET]" in summary
    assert "[REDACTED_PATH]" in summary
    assert structured["notes"] == "Wrote [REDACTED_PATH] and used [REDACTED_SECRET]"
    assert structured["config"]["token"] == "[REDACTED_SECRET]"
    assert structured["config"]["password"] == "[REDACTED_SECRET]"
    assert "sk-live-secret123" not in summary
    assert "ghp_abcd1234SECRET" not in serialized_structured
    assert aws_key not in serialized_structured
    assert "hunter2" not in serialized_structured
    assert "C:\\Users\\Alice" not in summary
    assert "/Users/alice" not in serialized_structured


def test_hermes_agent_redacts_exception_text(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise RuntimeError(
            "failed with token=ghp_exceptionSecret at /home/alice/private/build"
        )

    monkeypatch.setattr(ap, "_resolve_hermes_bin", lambda: str(tmp_path / "hermes"))
    monkeypatch.setattr(ap.HermesRobloxSession, "local", lambda project_root: ap.HermesRobloxSession(project_root=project_root))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)

    result = ap._run_hermes_agent("make a secret obby", timeout=1)

    assert result["error"] == "failed with token=[REDACTED_SECRET] at [REDACTED_PATH]"
    assert result["fallback_reason"] == (
        "agent error: failed with token=[REDACTED_SECRET] at [REDACTED_PATH]; using fallback"
    )
    assert "ghp_exceptionSecret" not in result["fallback_reason"]
    assert "/home/alice" not in result["fallback_reason"]


def test_agent_structured_redaction_covers_common_secret_field_names():
    payload = {
        "access_token": "access-token-value",
        "client_secret": "client-secret-value",
        "aws_secret_access_key": "aws-secret-value",
        "openai_api_key": "sk-openaiSecret123",
        "nested": {
            "refresh_token": "refresh-token-value",
            "safe_note": "keep generated_projects/foo visible",
        },
    }

    redacted = ap._redact_agent_output(payload)

    assert redacted["access_token"] == "[REDACTED_SECRET]"
    assert redacted["client_secret"] == "[REDACTED_SECRET]"
    assert redacted["aws_secret_access_key"] == "[REDACTED_SECRET]"
    assert redacted["openai_api_key"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["refresh_token"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["safe_note"] == "keep generated_projects/foo visible"


def test_agent_redacts_non_home_absolute_machine_paths():
    text = (
        "Wrote C:\\workspace\\Playro and D:\\builds\\playro; "
        "also /workspace/Playro, /tmp/playro-secret, /var/folders/abc/xyz; "
        "keep generated_projects/foo"
    )

    redacted = ap._redact_sensitive_text(text)

    assert redacted.count("[REDACTED_PATH]") == 5
    assert "C:\\workspace\\Playro" not in redacted
    assert "D:\\builds\\playro" not in redacted
    assert "/workspace/Playro" not in redacted
    assert "/tmp/playro-secret" not in redacted
    assert "/var/folders/abc/xyz" not in redacted
    assert "generated_projects/foo" in redacted


def test_agent_redacts_plain_text_common_secret_assignments():
    text = (
        "access_token=plainvalue "
        "client_secret: plainvalue "
        "aws_secret_access_key=plainvalue "
        "openai_api_key=plainvalue "
        "private_key: plainvalue "
        "keep generated_projects/foo"
    )

    redacted = ap._redact_sensitive_text(text)

    assert redacted.count("[REDACTED_SECRET]") == 5
    assert "plainvalue" not in redacted
    assert "access_token=[REDACTED_SECRET]" in redacted
    assert "client_secret: [REDACTED_SECRET]" in redacted
    assert "aws_secret_access_key=[REDACTED_SECRET]" in redacted
    assert "openai_api_key=[REDACTED_SECRET]" in redacted
    assert "private_key: [REDACTED_SECRET]" in redacted
    assert "generated_projects/foo" in redacted


def test_agent_redacts_broader_absolute_unix_paths():
    text = "Wrote /srv/playro/build and /etc/playro/secret but kept generated_projects/foo"

    redacted = ap._redact_sensitive_text(text)

    assert redacted.count("[REDACTED_PATH]") == 2
    assert "/srv/playro/build" not in redacted
    assert "/etc/playro/secret" not in redacted
    assert "generated_projects/foo" in redacted


def test_agent_redaction_preserves_urls_and_api_routes():
    text = "See https://example.com/docs/path then POST /v1/projects or call /api/builds"

    redacted = ap._redact_sensitive_text(text)

    assert redacted == text


def test_agent_redacts_authorization_bearer_header_value():
    text = "Authorization: Bearer eyJsecret next line stays useful"

    redacted = ap._redact_sensitive_text(text)

    assert redacted == "Authorization: [REDACTED_SECRET] next line stays useful"
    assert "Bearer eyJsecret" not in redacted
