import unittest
from pathlib import Path

from product.roblox_ai_studio.app import api
from product.roblox_ai_studio.tests.fixtures import write_generated_project


class WebUISmokeTests(unittest.TestCase):
    def test_list_projects_reads_only_product_local_generated_projects(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
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
            self.assertGreaterEqual(
                set(projects[0]["files"]),
                {"default.project.json", "manifest.json", "game_plan.md", "README.md", "src/ServerScriptService/Main.server.lua"},
            )

    def test_get_project_returns_detail_history_and_artifact_previews(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
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

    def test_get_project_includes_iteration_count(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(
                generated_root,
                "coin-obby",
                prompt="make a coin obby",
                build_state={
                    "status": "Generated",
                    "created_at": 100,
                    "updated_at": 200,
                },
            )

            record = api._project_record(generated_root / "coin-obby")
            self.assertIn("iteration_count", record)
            self.assertIsInstance(record["iteration_count"], int)

    def test_get_project_rejects_path_traversal_and_missing_projects(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "product" / "roblox_ai_studio" / "generated_projects"
            write_generated_project(generated_root, "coin-obby", prompt="make a coin obby")

            self.assertIsNone(api.get_project("../coin-obby", generated_root))
            self.assertIsNone(api.get_project("missing", generated_root))

    def test_renderer_has_prompt_refinement_and_project_detail_api_calls(self):
        root = Path(__file__).resolve().parents[1]
        renderer = (root / "desktop/src/renderer.js").read_text(encoding="utf-8")

        self.assertIn("optional refinement", renderer.lower())
        self.assertIn("#refinement", renderer)
        self.assertIn("/generate", renderer)
        self.assertIn("Build Roblox Project", renderer)
        self.assertIn("Build history", renderer)
        self.assertIn("Studio handoff files", renderer)
        self.assertIn("renderBuildReceipt", renderer)
        self.assertIn("inferBuildIntent", renderer)
        self.assertIn("Skill:", renderer)
        self.assertIn("skill", renderer.lower())
        self.assertIn("Quality routing", renderer)
        self.assertIn("Install Playro AI engine", renderer)
        self.assertIn("Playro AI engine", renderer)
        self.assertIn("renderHermesInstallerOverlay", renderer)
        self.assertIn("Installing Playro AI engine", renderer)
        self.assertIn("Step 1/7: Starting installation", renderer)
        self.assertNotIn("Hermes powers", renderer)

        # New panel smoke strings
        self.assertIn("Build analytics", renderer)
        self.assertIn("Build logs", renderer)
        self.assertIn("Keys and accounts", renderer)
        self.assertIn("renderBuildAnalyticsPanel", renderer)
        self.assertIn("renderBuildLogsPanel", renderer)
        self.assertIn("renderKeysPanel", renderer)
        self.assertIn("fetchBuildAnalytics", renderer)
        self.assertIn("fetchBuildLogs", renderer)
        self.assertIn("fetchKeysPanel", renderer)
        self.assertIn("build-analytics-scrim", renderer)
        self.assertIn("build-logs-scrim", renderer)
        self.assertIn("keys-panel-scrim", renderer)
        
        # Hermes runtime gate strings
        self.assertIn("Playro AI engine", renderer)


    def test_renderer_build_detail_panel_shows_original_prompt_and_iteration_count(self):
        root = Path(__file__).resolve().parents[1]
        renderer = (root / "desktop/src/renderer.js").read_text(encoding="utf-8")

        self.assertIn("Original prompt", renderer)
        self.assertIn("iteration_count", renderer)
        self.assertIn("learning_count", renderer)
        self.assertIn("build-detail-prompt", renderer)


if __name__ == "__main__":
    unittest.main()
