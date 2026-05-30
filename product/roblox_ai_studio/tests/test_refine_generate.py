"""Tests for the /generate endpoint when called with project_id for refinement."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from product.roblox_ai_studio.app import api
from product.roblox_ai_studio.build_loop import create_build_mission
from product.roblox_ai_studio.tests.fixtures import write_generated_project
from product.roblox_ai_studio.tests.http_harness import playro_api_server

_TEST_HEADERS = {"Content-Type": "application/json", "X-Playro-API-Token": "test-token"}


def _wait_for_build(build_id: str) -> None:
    future = None
    for _ in range(50):
        with api._active_builds_lock:
            future = api._active_builds.get(build_id)
        if future is None or future.done():
            break
        time.sleep(0.1)
    if future is not None:
        future.result(timeout=1)


def _post_json(server, path: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    req = Request(
        f"{server.base_url}{path}",
        data=body,
        headers=_TEST_HEADERS,
        method="POST",
    )
    try:
        with urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _make_continuous_project(
    generated_root: Path,
    slug: str = "coin-obby",
    *,
    prompt: str = "make a coin obby",
) -> Path:
    project_dir = write_generated_project(
        generated_root,
        slug,
        prompt=prompt,
        build_state={"continuous": True},
    )
    create_build_mission(project_dir, prompt=prompt, continuous=True, autonomous=True)
    return project_dir


class RefinementGenerateTests(unittest.TestCase):
    def setUp(self):
        self._original_api_token = api.os.environ.get("PLAYRO_API_TOKEN")
        api.os.environ["PLAYRO_API_TOKEN"] = "test-token"

    def tearDown(self):
        if self._original_api_token is None:
            api.os.environ.pop("PLAYRO_API_TOKEN", None)
        else:
            api.os.environ["PLAYRO_API_TOKEN"] = self._original_api_token

    def test_generate_with_project_id_returns_project_id_in_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(generated_root, "coin-obby", prompt="make a coin obby")
            with playro_api_server(output_root=generated_root) as server:
                status, data = _post_json(
                    server,
                    "/generate",
                    {
                        "prompt": "add a leaderboard",
                        "project_id": "coin-obby",
                        "refine": "add a leaderboard",
                        "quality": "Balanced",
                    },
                )
                self.assertEqual(status, 200)
                self.assertTrue(data["ok"])
                self.assertEqual(data["action"], "build_started")
                self.assertEqual(data["project_id"], "coin-obby")
                self.assertIn("build_id", data)
                self.assertIn(data["build_id"], data["events_url"])
                _wait_for_build(data["build_id"])

    def test_generate_without_project_id_omits_project_id_from_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            with playro_api_server(output_root=generated_root) as server:
                status, data = _post_json(
                    server,
                    "/generate",
                    {"prompt": "make a coin obby", "quality": "Balanced"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(data["ok"])
                self.assertNotIn("project_id", data)
                _wait_for_build(data["build_id"])

    def test_create_build_job_receives_refinement_kwargs(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(generated_root, "coin-obby", prompt="make a coin obby")
            with patch("product.roblox_ai_studio.app.api.create_build_job", autospec=True) as mock_create:
                mock_create.return_value = {
                    "ok": True,
                    "action": "build_started",
                    "build_job": {"id": "test", "status": "completed"},
                }
                with playro_api_server(output_root=generated_root) as server:
                    status, _data = _post_json(
                        server,
                        "/generate",
                        {
                            "prompt": "add a coin shop",
                            "project_id": "coin-obby",
                            "refine": "add a coin shop",
                            "quality": "Balanced",
                        },
                    )
                    self.assertEqual(status, 200)
                    for _ in range(20):
                        if mock_create.called:
                            break
                        time.sleep(0.1)
                    mock_create.assert_called_once()
                    call_kwargs = mock_create.call_args
                    self.assertEqual(
                        call_kwargs.kwargs.get("project_id") or call_kwargs[1].get("project_id"),
                        "coin-obby",
                    )
                    self.assertTrue(
                        call_kwargs.kwargs.get("refinement_prompt") or call_kwargs[1].get("refinement_prompt")
                    )

    def test_refine_preserves_build_mission_after_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            project_dir = _make_continuous_project(generated_root)

            def destructive_write_project(prompt, output_root, refinement_prompt=None, **kwargs):
                shutil.rmtree(project_dir)
                target = kwargs.get("target_dir") or output_root / "coin-obby"
                return write_generated_project(target.parent, target.name, prompt=prompt)

            with patch("product.roblox_ai_studio.app.api.write_project", side_effect=destructive_write_project):
                with playro_api_server(output_root=generated_root) as server:
                    status, data = _post_json(
                        server,
                        "/refine",
                        {"project_id": "coin-obby", "refinement": "add checkpoints"},
                    )
                    self.assertEqual(status, 200)

            saved_mission = json.loads((project_dir / "build_mission.json").read_text(encoding="utf-8"))
            self.assertTrue(saved_mission["mission"]["continuous"])
            self.assertTrue(saved_mission["mission"]["autonomous"])
            self.assertTrue(data["project"]["continuous"])
            self.assertTrue(data["project"]["autonomous"])

    def test_refine_preserves_build_job_after_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            project_dir = _make_continuous_project(generated_root)
            build_job = {"id": "build_existing", "status": "completed", "completed_at": 123}
            (project_dir / "build_job.json").write_text(json.dumps(build_job), encoding="utf-8")

            def destructive_write_project(prompt, output_root, refinement_prompt=None, **kwargs):
                shutil.rmtree(project_dir)
                target = kwargs.get("target_dir") or output_root / "coin-obby"
                return write_generated_project(target.parent, target.name, prompt=prompt)

            with patch("product.roblox_ai_studio.app.api.write_project", side_effect=destructive_write_project):
                with playro_api_server(output_root=generated_root) as server:
                    status, _data = _post_json(
                        server,
                        "/refine",
                        {"project_id": "coin-obby", "refinement": "add checkpoints"},
                    )
                    self.assertEqual(status, 200)

            self.assertEqual(
                json.loads((project_dir / "build_job.json").read_text(encoding="utf-8")),
                build_job,
            )
            self.assertEqual([job["id"] for job in api.list_build_jobs(generated_root)], ["build_existing"])

    def test_generate_refinement_preserves_existing_autonomous_build_mission(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            project_dir = _make_continuous_project(generated_root)
            existing_mission = json.loads((project_dir / "build_mission.json").read_text(encoding="utf-8"))

            def destructive_write_project(prompt, output_root, refinement_prompt=None, build_metadata=None, **kwargs):
                shutil.rmtree(project_dir)
                target = kwargs.get("target_dir") or output_root / "coin-obby"
                return write_generated_project(target.parent, target.name, prompt=prompt)

            with patch("product.roblox_ai_studio.app.api.write_project", side_effect=destructive_write_project):
                with playro_api_server(output_root=generated_root) as server:
                    status, data = _post_json(
                        server,
                        "/generate",
                        {
                            "prompt": "add checkpoints",
                            "project_id": "coin-obby",
                            "refine": "add checkpoints",
                            "quality": "Balanced",
                        },
                    )
                    self.assertEqual(status, 200)
                    _wait_for_build(data["build_id"])

            build_state = json.loads((project_dir / "build_state.json").read_text(encoding="utf-8"))
            saved_mission = json.loads((project_dir / "build_mission.json").read_text(encoding="utf-8"))
            self.assertTrue(build_state["continuous"])
            self.assertEqual(saved_mission, existing_mission)

    def test_create_build_job_preserves_mission_before_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp)
            project_dir = _make_continuous_project(generated_root)
            existing_mission = json.loads((project_dir / "build_mission.json").read_text(encoding="utf-8"))

            def destructive_write_project(prompt, output_root, refinement_prompt=None, build_metadata=None, target_dir=None):
                shutil.rmtree(project_dir)
                target = target_dir or output_root / "coin-obby"
                return write_generated_project(target.parent, target.name, prompt=prompt)

            with patch("product.roblox_ai_studio.app.api.write_project", side_effect=destructive_write_project):
                result = api.create_build_job(
                    "add checkpoints",
                    output_root=generated_root,
                    project_id="coin-obby",
                    refinement_prompt="add checkpoints",
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result.get("build_mission"), existing_mission)
            saved_mission = json.loads((project_dir / "build_mission.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_mission, existing_mission)

    def test_create_build_job_refinement_stays_in_requested_project_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp)
            project_dir = write_generated_project(generated_root, "coin-obby", prompt="make a coin obby")

            result = api.create_build_job(
                "add leaderboard",
                output_root=generated_root,
                project_id="coin-obby",
                refinement_prompt="add leaderboard",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(Path(result["project_path"]), project_dir)
            self.assertFalse((generated_root / "make-a-coin-obby").exists())

    def test_generate_requires_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with playro_api_server(output_root=Path(tmp)) as server:
                status, _data = _post_json(
                    server,
                    "/generate",
                    {"project_id": "coin-obby", "refine": True},
                )
                self.assertEqual(status, 400)

    def test_generate_returns_404_before_starting_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("product.roblox_ai_studio.app.api.create_build_job", autospec=True) as mock_create:
                with patch(
                    "product.roblox_ai_studio.app.api.snapshot_project_build_context",
                    autospec=True,
                ) as mock_snapshot:
                    with playro_api_server(output_root=Path(tmp)) as server:
                        status, data = _post_json(
                            server,
                            "/generate",
                            {
                                "prompt": "add checkpoints",
                                "project_id": "missing-project",
                            },
                        )
                        self.assertEqual(status, 404)
                        self.assertFalse(data.get("ok", True))
                        mock_create.assert_not_called()
                        mock_snapshot.assert_not_called()

    def test_refine_writes_into_existing_project_dir_when_slug_differs(self):
        from urllib.request import Request, urlopen

        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            project_dir = write_generated_project(
                generated_root,
                "legacy-obby",
                prompt="make a totally different title for slug generation",
            )
            captured_target_dirs: list[Path] = []
            original_write_project = api.write_project

            def capture_target_dir(prompt, output_root, refinement_prompt=None, build_metadata=None, target_dir=None):
                captured_target_dirs.append(target_dir)
                return original_write_project(
                    prompt,
                    output_root,
                    refinement_prompt=refinement_prompt,
                    build_metadata=build_metadata,
                    target_dir=target_dir,
                )

            with patch("product.roblox_ai_studio.app.api.write_project", side_effect=capture_target_dir):
                with playro_api_server(output_root=generated_root) as server:
                    body = json.dumps({"project_id": "legacy-obby", "refinement": "add checkpoints"}).encode()
                    req = Request(
                        f"{server.base_url}/refine",
                        data=body,
                        headers={"Content-Type": "application/json", "X-Playro-API-Token": "test-token"},
                        method="POST",
                    )
                    with urlopen(req) as response:
                        self.assertEqual(response.status, 200)
                        data = json.loads(response.read().decode())

            self.assertEqual(captured_target_dirs, [project_dir.resolve()])
            self.assertEqual(data["project"]["id"], "legacy-obby")
            self.assertTrue((project_dir / "build_state.json").exists())

    def test_refine_returns_404_before_reading_missing_manifest_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "product.roblox_ai_studio.app.api.snapshot_project_build_context",
                autospec=True,
            ) as mock_snapshot:
                with playro_api_server(output_root=Path(tmp)) as server:
                    status, _data = _post_json(
                        server,
                        "/refine",
                        {"project_id": "missing-project", "refinement": "add checkpoints"},
                    )
                    self.assertEqual(status, 404)
                    mock_snapshot.assert_not_called()

    def test_unknown_build_sse_stream_closes_after_deadline(self):
        original_deadline = getattr(api, "PLAYRO_SSE_MAX_WAIT_SECS", None)
        api.PLAYRO_SSE_MAX_WAIT_SECS = 1
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with playro_api_server(output_root=Path(tmp)) as server:
                    req = Request(
                        f"{server.base_url}/generate/build_UNKNOWN_SSE_0001/events",
                        headers={"X-Playro-API-Token": "test-token"},
                        method="GET",
                    )
                    started = time.monotonic()
                    with urlopen(req, timeout=3) as response:
                        self.assertEqual(response.status, 200)
                        response.read()
                    self.assertLess(time.monotonic() - started, 2.5)
        finally:
            if original_deadline is None:
                delattr(api, "PLAYRO_SSE_MAX_WAIT_SECS")
            else:
                api.PLAYRO_SSE_MAX_WAIT_SECS = original_deadline


if __name__ == "__main__":
    unittest.main()
