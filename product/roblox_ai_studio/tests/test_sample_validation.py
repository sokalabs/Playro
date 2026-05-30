import json
import tempfile
import unittest
from pathlib import Path

from product.roblox_ai_studio.roblox.generator import write_project
from product.roblox_ai_studio.app.sample_validation import validate_sample_projects, validate_single_project
from product.roblox_ai_studio.app.gameplay_validation import validate_gameplay_mechanics


class SampleValidationTests(unittest.TestCase):
    def test_validate_sample_projects_requires_two_projects_and_core_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project("make a pirate tycoon with droppers and upgrades", root)

            one_project = validate_sample_projects(root, min_projects=2)
            self.assertFalse(one_project["ok"])
            self.assertIn("Expected at least 2 sample projects", one_project["errors"][0])

            write_project("make a sky obby with checkpoints and coins", root)
            two_projects = validate_sample_projects(root, min_projects=2)
            self.assertTrue(two_projects["ok"])
            self.assertEqual(two_projects["project_count"], 2)

    def test_validate_single_project_detects_bad_rojo_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = write_project("make a tower defense with waves and towers", root)
            project_json_path = project_dir / "default.project.json"

            payload = json.loads(project_json_path.read_text(encoding="utf-8"))
            payload["tree"]["ServerScriptService"]["$path"] = "src/ServerScriptServiceBroken"
            project_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_single_project(project_dir)
            self.assertFalse(result["ok"])
            self.assertIn("ServerScriptService.$path", result["errors"])

    def test_gameplay_mechanics_validation_passes_valid_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = write_project("make a pirate tycoon with coins and shop", root)
            p2 = write_project("make a simulator with pets and boss", root)
            p3 = write_project("make a racing game", root)
            p4 = write_project("make an rpg adventure", root)

            res1 = validate_gameplay_mechanics(p1)
            self.assertTrue(res1.ok, f"Tycoon validation failed: {res1.errors}")
            self.assertIn("tycoon_mechanics", res1.passed_slugs)
            self.assertIn("server_coins", res1.passed_slugs)

            res2 = validate_gameplay_mechanics(p2)
            self.assertTrue(res2.ok, f"Simulator validation failed: {res2.errors}")
            self.assertIn("simulator_mechanics", res2.passed_slugs)
            self.assertIn("pet_mechanics", res2.passed_slugs)
            self.assertIn("boss_mechanics", res2.passed_slugs)

            res3 = validate_gameplay_mechanics(p3)
            self.assertTrue(res3.ok, f"Racing validation failed: {res3.errors}")
            self.assertIn("racing_mechanics", res3.passed_slugs)

            res4 = validate_gameplay_mechanics(p4)
            self.assertTrue(res4.ok, f"RPG validation failed: {res4.errors}")
            self.assertIn("rpg_mechanics", res4.passed_slugs)

    def test_gameplay_mechanics_validation_detects_missing_server_coins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = write_project("make an obby", root)
            
            # Tamper with the server script to remove server coin reward function
            server_lua = p1 / "src/ServerScriptService/Main.server.lua"
            text = server_lua.read_text(encoding="utf-8")
            text = text.replace("rewardCoins", "noRewardsHere")
            text = text.replace("addStat", "noStatsHere")
            server_lua.write_text(text, encoding="utf-8")

            res = validate_gameplay_mechanics(p1)
            self.assertFalse(res.ok)
            self.assertIn("server_coins", res.failed_slugs)
            self.assertTrue(any("server script lacks rewardCoins" in e for e in res.errors))


if __name__ == "__main__":
    unittest.main()
