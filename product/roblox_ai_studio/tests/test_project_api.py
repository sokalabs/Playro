import json
import tempfile
import unittest
from pathlib import Path

from product.roblox_ai_studio.app import api
from product.roblox_ai_studio.app.api import GENERATED_FILES
from product.roblox_ai_studio.tests.fixtures import write_generated_project
from product.roblox_ai_studio.tests.http_harness import playro_api_server


class ProjectApiTests(unittest.TestCase):
    def test_list_projects_uses_stamp_cache_until_output_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "generated_projects"
            write_generated_project(generated_root, "coin-obby", prompt="make a coin obby", include_metadata=True)
            first = api.list_projects(generated_root)
            second = api.list_projects(generated_root)
            self.assertEqual(first, second)
            (generated_root / "coin-obby" / "build_state.json").write_text(
                json.dumps({"status": "Generated", "updated_at": 999}),
                encoding="utf-8",
            )
            third = api.list_projects(generated_root)
            self.assertNotEqual(second[0]["updated_at"], third[0]["updated_at"])

    def test_list_projects_reads_only_product_local_generated_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            generated_root = tmp_path / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(
                generated_root,
                "coin-obby",
                prompt="make a coin obby",
                build_state={"status": "Generated", "updated_at": 200, "updated_label": "Latest", "quality": "Polished", "progress": 100},
            )
            write_generated_project(
                tmp_path / "elsewhere" / "generated_projects",
                "external-project",
                prompt="do not read this",
            )

            projects = api.list_projects(generated_root)

            self.assertEqual([project["id"] for project in projects], ["coin-obby"])
            self.assertEqual(projects[0]["name"], "Test Obby")
            self.assertEqual(projects[0]["prompt"], "make a coin obby")
            self.assertEqual(Path(projects[0]["project_path"]).parts[-4:], ("product", "roblox_ai_studio", "generated_projects", "coin-obby"))
            project_dir = generated_root / "coin-obby"
            self.assertEqual(
                projects[0]["files"],
                [rel for rel in GENERATED_FILES if (project_dir / rel).exists()],
            )

    def test_dot_prefixed_staging_dirs_are_excluded_from_project_and_job_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "generated_projects"
            real_project = write_generated_project(
                generated_root,
                "coin-obby",
                prompt="make a coin obby",
                build_state={"status": "Generated", "updated_at": 200},
            )
            (real_project / "build_job.json").write_text(
                json.dumps({"id": "build_real", "completed_at": 200}),
                encoding="utf-8",
            )
            staging = write_generated_project(
                generated_root,
                ".coin-obby.tmp-deadbeef",
                prompt="staging copy",
                build_state={"status": "Generated", "updated_at": 999},
            )
            (staging / "build_job.json").write_text(
                json.dumps({"id": "build_staging", "completed_at": 999}),
                encoding="utf-8",
            )

            self.assertEqual([project["id"] for project in api.list_projects(generated_root)], ["coin-obby"])
            self.assertEqual([job["id"] for job in api.list_build_jobs(generated_root)], ["build_real"])

    def test_get_project_returns_detail_history_and_artifact_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(
                generated_root,
                "coin-obby",
                prompt="make a coin obby",
                build_state={
                    "status": "Generated",
                    "mode": "24/7 enabled",
                    "logs": ["Generated project", "Validated files"],
                    "next_actions": ["Open in Studio"],
                    "created_at": 100,
                    "updated_at": 200,
                },
            )
            (generated_root / "coin-obby" / "README.md").write_text("# Coin Obby\nReady.", encoding="utf-8")

            detail = api.get_project("coin-obby", generated_root)

            self.assertIsNotNone(detail)
            self.assertEqual(detail["id"], "coin-obby")
            self.assertEqual(detail["history"], ["Generated project", "Validated files"])
            self.assertEqual(detail["next_actions"], ["Open in Studio"])
            self.assertGreaterEqual(
                {artifact["path"] for artifact in detail["artifacts"]},
                {"manifest.json", "README.md", "src/ServerScriptService/Main.server.lua"},
            )
            manifest = next(artifact for artifact in detail["artifacts"] if artifact["path"] == "manifest.json")
            self.assertIn('"original_prompt": "make a coin obby"', manifest["preview"])

    def test_get_project_artifact_preview_cache_refreshes_when_files_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(generated_root, "coin-obby", prompt="make a coin obby")
            readme_path = generated_root / "coin-obby" / "README.md"
            readme_path.write_text("# Coin Obby\nReady.", encoding="utf-8")

            before = api.get_project("coin-obby", generated_root)
            api.get_project("coin-obby", generated_root)
            readme_path.write_text("# Coin Obby\nUpdated preview.", encoding="utf-8")
            after = api.get_project("coin-obby", generated_root)

            readme_before = next(item for item in before["artifacts"] if item["path"] == "README.md")
            readme_after = next(item for item in after["artifacts"] if item["path"] == "README.md")
            self.assertIn("Ready.", readme_before["preview"])
            self.assertIn("Updated preview.", readme_after["preview"])

    def test_get_project_rejects_path_traversal_and_missing_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(generated_root, "coin-obby", prompt="make a coin obby")

            self.assertIsNone(api.get_project("../coin-obby", generated_root))
            self.assertIsNone(api.get_project("missing", generated_root))

    def test_post_export_project_route(self):
        from urllib.request import urlopen, Request

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            generated_root = tmp_path / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(
                generated_root,
                "coin-obby",
                prompt="make a coin obby",
                include_metadata=True,
                build_state={"status": "Generated", "updated_at": 200, "updated_label": "Latest", "quality": "Polished", "progress": 100},
            )

            with playro_api_server(output_root=generated_root) as server:
                req = Request(
                    f"{server.base_url}/projects/coin-obby/export",
                    method="POST",
                    headers={"X-Playro-API-Token": "test-token"},
                )
                with urlopen(req) as response:
                    self.assertEqual(response.status, 200)
                    data = json.loads(response.read().decode())
                    self.assertTrue(data["ok"])
                    self.assertEqual(data["action"], "project_exported")
                    self.assertEqual(data["project_id"], "coin-obby")
                    self.assertTrue("bundle_path" in data)

if __name__ == "__main__":
    unittest.main()
