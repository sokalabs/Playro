import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product.roblox_ai_studio.app.api import create_build_job, get_build_job, list_build_jobs
from product.roblox_ai_studio.app.artifacts import PLAYRO_CORE_ARTIFACT_FILES
from product.roblox_ai_studio.app.cli import main


class BuildJobTests(unittest.TestCase):
    def test_create_build_job_persists_status_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = create_build_job(
                "build a cyberpunk obby with coins and pets",
                output_root=tmp_path,
                quality="Studio quality",
                skill_id="playro-systems-builder",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["action"], "build_started")
            job = result["build_job"]
            self.assertEqual(job["type"], "roblox_project_build")
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["skill"]["id"], "playro-systems-builder")
            self.assertEqual(job["quality"], "Studio quality")
            self.assertEqual(
                [stage["key"] for stage in job["stages"]],
                [
                    "prompt",
                    "plan",
                    "generate_files",
                    "validate",
                    "package_open_instructions",
                ],
            )
            self.assertTrue(all(stage["status"] == "completed" for stage in job["stages"]))
            self.assertEqual(job["generated_files"], list(PLAYRO_CORE_ARTIFACT_FILES))
            self.assertTrue(job["validation"]["ok"])
            self.assertIn("rojo serve default.project.json", job["next_action"])

            project_dir = Path(job["project_path"])
            self.assertTrue((project_dir / "default.project.json").exists())
            self.assertTrue((project_dir / "src/ServerScriptService/Main.server.lua").exists())

            manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["build_job"]["id"], job["id"])
            self.assertEqual(manifest["build_job"]["status"], "completed")
            self.assertEqual(manifest["build_job"]["current_stage"], "package_open_instructions")
            self.assertEqual(manifest["selected_skill"]["id"], "playro-systems-builder")
            self.assertEqual(manifest["quality_mode"], "Studio quality")
            self.assertEqual(manifest["history"][0]["event"], "build_completed")

            build_job_file = json.loads((project_dir / "build_job.json").read_text(encoding="utf-8"))
            self.assertEqual(build_job_file["id"], job["id"])
            self.assertEqual(build_job_file["validation"]["missing_files"], [])

            history = list_build_jobs(tmp_path)
            self.assertEqual(history[0]["id"], job["id"])
            self.assertEqual(get_build_job(job["id"], tmp_path)["status"], "completed")
            # Indexed lookup should match the same job without scanning unrelated dirs.
            self.assertEqual(get_build_job("build_nonexistent", tmp_path), None)

    def test_cli_prints_machine_readable_json_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    "make a forest tycoon with coins",
                    "--output-root",
                    str(tmp_path),
                    "--json",
                ])

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["build_job"]["status"], "completed")
            self.assertTrue(payload["build_job"]["validation"]["ok"])

    def test_cli_human_mode_prints_builder_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    "make a forest tycoon with coins",
                    "--output-root",
                    str(tmp_path),
                ])

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("Started Roblox build job", output)
            self.assertIn("Completed Roblox build job", output)
            self.assertIn("Project path:", output)

    def test_cli_json_smoke_mode_reports_clone_safe_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    "make a sky obby with checkpoints and coins",
                    "--output-root",
                    str(tmp_path),
                    "--smoke",
                    "--json",
                ])

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertIn("smoke", payload)
            self.assertTrue(payload["smoke"]["ok"])
            self.assertIn("default.project.json", payload["smoke"]["required_files"])
            self.assertIn("src/ServerScriptService/Main.server.lua", payload["smoke"]["lua_files"])
            self.assertIn("src/StarterPlayer/StarterPlayerScripts/HUD.client.lua", payload["smoke"]["lua_files"])

    def test_cli_version_uses_package_metadata(self):
        stdout = io.StringIO()
        with patch("importlib.metadata.version", return_value="9.8.7"):
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--version"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), "Playro AI Engine 9.8.7")


if __name__ == "__main__":
    unittest.main()
