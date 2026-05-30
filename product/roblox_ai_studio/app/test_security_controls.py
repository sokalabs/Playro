from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from product.roblox_ai_studio.app.export_bundle import _should_exclude
from product.roblox_ai_studio.app.api import _configured_api_host, _server_class_for_host, validate_project
from product.roblox_ai_studio.app.artifacts import PLAYRO_CORE_ARTIFACT_FILES
from product.roblox_ai_studio.app.security import (
    allowed_cors_origins,
    is_safe_build_id,
    safe_project_dir,
    unexpected_lua_artifacts,
)
from product.roblox_ai_studio.hermes_backend.provider_bridge.config import (
    safe_endpoint_for_display,
    validate_provider_endpoint,
)


class PlayroSecurityControlsTest(unittest.TestCase):
    def test_default_cors_excludes_null_origin(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PLAYRO_ALLOWED_ORIGINS", None)
            origins = allowed_cors_origins()
        self.assertNotIn("null", origins)
        self.assertIn("file://", origins)

    def test_safe_project_dir_blocks_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "good-project_1"
            project.mkdir()
            (project / "manifest.json").write_text("{}", encoding="utf-8")
            self.assertEqual(safe_project_dir("good-project_1", root), project.resolve())
            self.assertIsNone(safe_project_dir("../good-project_1", root))
            self.assertIsNone(safe_project_dir("good-project_1/../../etc", root))
            self.assertIsNone(safe_project_dir("", root))

    def test_build_id_shape_is_strict(self) -> None:
        self.assertTrue(is_safe_build_id("build_abcdEFGH0123_-abcdEFGH0123_"))
        self.assertFalse(is_safe_build_id("../build_abcdEFGH0123_-abcdEFGH0123_"))
        self.assertFalse(is_safe_build_id("build_short"))

    def test_export_excludes_env_and_cache_paths(self) -> None:
        self.assertTrue(_should_exclude(".env.production.local", ".env.production.local"))
        self.assertTrue(_should_exclude("cache/token.json", "token.json"))
        self.assertTrue(_should_exclude(".svn/entries", "entries"))
        self.assertFalse(_should_exclude("src/ServerScriptService/Main.server.lua", "Main.server.lua"))

    def test_unexpected_lua_artifacts_detects_extra_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed = {path for path in PLAYRO_CORE_ARTIFACT_FILES if path.endswith(".lua")}
            extra = root / "src/ServerScriptService/Telemetry.server.lua"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("print('x')", encoding="utf-8")
            found = unexpected_lua_artifacts(root, allowed=allowed)
            self.assertIn("src/ServerScriptService/Telemetry.server.lua", found)

    def test_validate_project_fails_on_unexpected_lua(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in PLAYRO_CORE_ARTIFACT_FILES:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if rel.endswith(".lua"):
                    path.write_text("-- ok\n", encoding="utf-8")
                elif rel.endswith(".json"):
                    path.write_text("{}", encoding="utf-8")
                else:
                    path.write_text("ok", encoding="utf-8")
            sneaky = root / "src/StarterPlayer/StarterPlayerScripts/Loader.client.lua"
            sneaky.write_text("print('hidden')", encoding="utf-8")
            result = validate_project(root)
            self.assertFalse(result["ok"])
            self.assertIn("src/StarterPlayer/StarterPlayerScripts/Loader.client.lua", result["unexpected_lua_files"])

    def test_provider_endpoint_redaction_and_validation(self) -> None:
        endpoint = "https://" + "user:secret@" + "example.com/v1?api_key=abc"
        self.assertEqual(safe_endpoint_for_display(endpoint), "https://example.com/v1")
        with self.assertRaises(ValueError):
            validate_provider_endpoint(endpoint)
        with self.assertRaises(ValueError):
            validate_provider_endpoint("http://example.com/v1")
        with self.assertRaises(ValueError):
            validate_provider_endpoint("https://127.0.0.1:8080/v1")
        self.assertEqual(validate_provider_endpoint("https://api.example.com/v1/"), "https://api.example.com/v1")


class PlayroApiHostConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._original_host = os.environ.get("HERMES_ROBLOX_API_HOST")
        self._original_allow_remote = os.environ.get("PLAYRO_ALLOW_REMOTE_API_BIND")

    def tearDown(self) -> None:
        if self._original_host is None:
            os.environ.pop("HERMES_ROBLOX_API_HOST", None)
        else:
            os.environ["HERMES_ROBLOX_API_HOST"] = self._original_host
        if self._original_allow_remote is None:
            os.environ.pop("PLAYRO_ALLOW_REMOTE_API_BIND", None)
        else:
            os.environ["PLAYRO_ALLOW_REMOTE_API_BIND"] = self._original_allow_remote

    def test_api_host_ignores_wildcard_bind_without_dev_flag(self) -> None:
        os.environ["HERMES_ROBLOX_API_HOST"] = "0.0.0.0"
        os.environ.pop("PLAYRO_ALLOW_REMOTE_API_BIND", None)

        self.assertEqual(_configured_api_host(), "127.0.0.1")

    def test_api_host_ignores_lan_bind_without_dev_flag(self) -> None:
        os.environ["HERMES_ROBLOX_API_HOST"] = "192.168.1.50"
        os.environ.pop("PLAYRO_ALLOW_REMOTE_API_BIND", None)

        self.assertEqual(_configured_api_host(), "127.0.0.1")

    def test_api_host_allows_loopback_without_dev_flag(self) -> None:
        os.environ.pop("PLAYRO_ALLOW_REMOTE_API_BIND", None)
        for host in ("127.0.0.1", "localhost", "::1"):
            with self.subTest(host=host):
                os.environ["HERMES_ROBLOX_API_HOST"] = host
                self.assertEqual(_configured_api_host(), host)

    def test_api_host_allows_remote_bind_with_dev_flag(self) -> None:
        os.environ["HERMES_ROBLOX_API_HOST"] = "0.0.0.0"
        os.environ["PLAYRO_ALLOW_REMOTE_API_BIND"] = "1"

        self.assertEqual(_configured_api_host(), "0.0.0.0")

    def test_api_server_uses_ipv6_family_for_ipv6_loopback(self) -> None:
        self.assertEqual(_server_class_for_host("::1").address_family, socket.AF_INET6)

    def test_api_server_uses_default_ipv4_family_for_ipv4_loopback(self) -> None:
        self.assertEqual(_server_class_for_host("127.0.0.1").address_family, socket.AF_INET)


class PlayroApiTokenAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        from product.roblox_ai_studio.app import api

        self.api = api
        self._original_api_token = api.os.environ.get("PLAYRO_API_TOKEN")
        self._original_allowed_origins = api.os.environ.get("PLAYRO_ALLOWED_ORIGINS")

    def tearDown(self) -> None:
        if self._original_api_token is None:
            self.api.os.environ.pop("PLAYRO_API_TOKEN", None)
        else:
            self.api.os.environ["PLAYRO_API_TOKEN"] = self._original_api_token
        if self._original_allowed_origins is None:
            self.api.os.environ.pop("PLAYRO_ALLOWED_ORIGINS", None)
        else:
            self.api.os.environ["PLAYRO_ALLOWED_ORIGINS"] = self._original_allowed_origins

    def _handler(self, path: str = "/projects", headers: dict[str, str] | None = None):
        request = type("Request", (), {})()
        request.path = path
        request.headers = headers or {}
        return self.api.RobloxAIStudioHandler.__new__(self.api.RobloxAIStudioHandler), request

    def test_api_token_auth_fails_closed_when_secret_missing(self) -> None:
        self.api.os.environ.pop("PLAYRO_API_TOKEN", None)
        handler, request = self._handler(headers={"X-Playro-API-Token": "anything"})
        handler.path = request.path
        handler.headers = request.headers
        self.assertFalse(handler._is_authorized())

    def test_api_token_auth_rejects_missing_or_wrong_token(self) -> None:
        self.api.os.environ["PLAYRO_API_TOKEN"] = "correct-token"
        for headers in ({}, {"X-Playro-API-Token": "wrong-token"}):
            handler, request = self._handler(headers=headers)
            handler.path = request.path
            handler.headers = request.headers
            self.assertFalse(handler._is_authorized())

    def test_api_token_auth_accepts_header_token(self) -> None:
        self.api.os.environ["PLAYRO_API_TOKEN"] = "correct-token"
        handler, request = self._handler(headers={"X-Playro-API-Token": "correct-token"})
        handler.path = request.path
        handler.headers = request.headers
        self.assertTrue(handler._is_authorized())

    def test_api_token_auth_accepts_query_token_for_eventsource_only(self) -> None:
        self.api.os.environ["PLAYRO_API_TOKEN"] = "correct-token"
        handler, request = self._handler(
            path="/generate/build_abcdEFGH0123_-abcdEFGH0123_/events?api_token=correct-token",
            headers={"Origin": "app://playro"},
        )
        handler.path = request.path
        handler.headers = request.headers
        self.assertTrue(handler._is_authorized())
        self.assertTrue(self.api.urlparse(handler.path).path.endswith("/events"))

    def test_api_token_auth_rejects_query_token_on_normal_api_routes(self) -> None:
        self.api.os.environ["PLAYRO_API_TOKEN"] = "correct-token"
        for path in ("/projects?api_token=correct-token", "/builds?api_token=correct-token"):
            handler, request = self._handler(path=path, headers={"Origin": "app://playro"})
            handler.path = request.path
            handler.headers = request.headers
            self.assertFalse(handler._is_authorized())

    def test_api_token_auth_rejects_null_and_untrusted_browser_origins(self) -> None:
        self.api.os.environ["PLAYRO_API_TOKEN"] = "correct-token"
        for origin in ("null", "https://evil.example"):
            handler, request = self._handler(headers={"Origin": origin, "X-Playro-API-Token": "correct-token"})
            handler.path = request.path
            handler.headers = request.headers
            self.assertFalse(handler._origin_allowed())



if __name__ == "__main__":
    unittest.main()
