import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product.roblox_ai_studio.hermes_backend.tool_surface import DEFAULT_TOOL_SURFACE
from product.roblox_ai_studio.app.gameplay_validation import validate_gameplay_mechanics
from product.roblox_ai_studio.roblox.generator import build_prompt_fidelity, plan_from_prompt, write_project


class GeneratorTests(unittest.TestCase):
    def test_tool_surface_excludes_environment_specific_tools(self):
        allowed, denied = DEFAULT_TOOL_SURFACE.validate_requested([
            "file",
            "luau_generator",
            "unraid",
            "server_management",
        ])
        self.assertEqual(allowed, ["file", "luau_generator"])
        self.assertEqual(denied, ["unraid", "server_management"])

    def test_plan_infers_obby_and_coin_systems(self):
        plan = plan_from_prompt("make a colorful obby with checkpoints coins and a shop")
        self.assertEqual(plan.genre, "Obstacle Course / Obby")
        self.assertIn("coin collection economy", plan.systems)
        self.assertIn("shop and upgrade loop", plan.systems)
        self.assertIn("checkpoints and respawn routing", plan.systems)

    def test_prompt_fidelity_scores_requested_prompt_features(self):
        prompt = "make a colorful obby with checkpoints, coins, a shop, and NPC quests"
        plan = plan_from_prompt(prompt)
        fidelity = build_prompt_fidelity(prompt, plan.systems)

        self.assertGreaterEqual(fidelity["score"], 60)
        self.assertIn("summary", fidelity)
        requested = [item for item in fidelity["items"] if item["requested"]]
        self.assertTrue(any(item["id"] == "mechanics" and item["matched"] for item in requested))
        self.assertTrue(any(item["id"] == "reward_loops" and item["matched"] for item in requested))

    def test_manifest_includes_prompt_fidelity(self):
        prompt = "make a racing game with laps, speed boosts, and a shop"
        with tempfile.TemporaryDirectory() as tmp:
            out = write_project(prompt, Path(tmp))
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("prompt_fidelity", manifest)
            self.assertGreaterEqual(manifest["prompt_fidelity"]["score"], 50)

    def test_keyword_generators_create_playable_server_authoritative_mechanics(self):
        prompts = {
            "obby": (
                "make a neon obby with checkpoint stages coins and a shop",
                [
                    "createCheckpoint",
                    "RespawnLocation",
                    "Checkpoint",
                    "createCoin",
                    "createUpgradePad",
                ],
            ),
            "tycoon": (
                "make a pirate tycoon with droppers collectors cash and upgrades",
                [
                    "createDropper",
                    "createCollector",
                    "Money",
                    "TycoonLevel",
                    "createUpgradePad",
                ],
            ),
            "simulator": (
                "make a pet simulator with training zones coins backpacks and upgrades",
                [
                    "createTrainingZone",
                    "Strength",
                    "Backpack",
                    "sellStrength",
                    "createUpgradePad",
                ],
            ),
 "tower defense": (
 "make a tower defense with waves enemies base health and towers",
 [
 "startWaveLoop",
 "createEnemy",
 "BaseHealth",
 "createTowerPad",
 "TowerDamage",
 ],
 ),
 "racing": (
 "make a racing game with laps speed boosts and vehicle upgrades",
 [
 "createLapCheckpoint",
 "createSpeedBoost",
 "createSpeedUpgradePad",
 "LapCount",
 "SpeedLevel",
 ],
 ),
 "rpg": (
 "make an rpg adventure with zones enemies and gear upgrades",
 [
 "createZoneUnlockPad",
 "createEnemySpawn",
 "createGearShopPad",
 "LevelUpXP",
 "unlockCost",
 ],
 ),
 }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for keyword, (prompt, expected_snippets) in prompts.items():
                out = write_project(prompt, tmp_path)
                server = (out / "src/ServerScriptService/Main.server.lua").read_text()
                config = (out / "src/ReplicatedStorage/GameConfig.lua").read_text()
                manifest = (out / "manifest.json").read_text()

                self.assertNotIn("OnServerEvent", server, f"{keyword} should not trust client events yet")
                self.assertIn("Players.PlayerAdded", server)
                self.assertIn("GeneratedGameplay", server)
                self.assertIn("GameConfig.Genre", config)
                self.assertIn("server-authoritative", manifest)
                for snippet in expected_snippets:
                    self.assertIn(snippet, server, f"{keyword} missing {snippet}")

    def test_custom_prompt_generates_requested_mechanics_without_template_genre(self):
        prompt = (
            "make a cyberpunk detective roleplay city with NPC quests, "
            "apartments, vehicles, and a reputation system"
        )
        plan = plan_from_prompt(prompt)

        self.assertEqual(plan.genre, "Custom Roblox Experience")
        self.assertIn("NPC quest objectives", plan.systems)
        self.assertIn("vehicle interaction loop", plan.systems)
        self.assertIn("reputation progression", plan.systems)
        self.assertIn("roleplay apartment hub", plan.systems)

        with tempfile.TemporaryDirectory() as tmp:
            out = write_project(prompt, Path(tmp))
            server = (out / "src/ServerScriptService/Main.server.lua").read_text(encoding="utf-8")
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["genre"], "Custom Roblox Experience")
            for snippet in [
                "createQuestNpc",
                "createVehiclePad",
                "createApartmentHub",
                "Reputation",
                "CustomObjective",
            ]:
                self.assertIn(snippet, server)

            result = validate_gameplay_mechanics(out)
            self.assertTrue(result.ok, result.errors)
            self.assertIn("custom_objectives", result.passed_slugs)

    def test_write_project_creates_reviewable_roblox_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = write_project("make a colorful obby with checkpoints and coins", Path(tmp))
            self.assertTrue((out / "game_plan.md").exists())
            self.assertTrue((out / "manifest.json").exists())
            self.assertTrue((out / "default.project.json").exists())
            self.assertTrue((out / "src/ServerScriptService/Main.server.lua").exists())
            self.assertTrue((out / "src/ReplicatedStorage/GameConfig.lua").exists())
            self.assertTrue((out / "src/StarterPlayer/StarterPlayerScripts/HUD.client.lua").exists())
            self.assertTrue((out / "wally.toml").exists())
            server = (out / "src/ServerScriptService/Main.server.lua").read_text()
            self.assertIn("Players.PlayerAdded", server)
            self.assertIn("GeneratedGameplay", server)
            project_json = json.loads((out / "default.project.json").read_text())
            self.assertEqual(project_json["tree"]["ReplicatedStorage"]["$path"], "src/ReplicatedStorage")
            self.assertEqual(project_json["tree"]["ServerScriptService"]["$path"], "src/ServerScriptService")
            self.assertEqual(
                project_json["tree"]["StarterPlayer"]["StarterPlayerScripts"]["$path"],
                "src/StarterPlayer/StarterPlayerScripts",
            )
            wally = (out / "wally.toml").read_text()
            self.assertIn("[package]", wally)
            self.assertIn("registry = \"https://github.com/UpliftGames/wally-index\"", wally)

    def test_same_slug_regeneration_removes_stale_project_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = "make a colorful obby with checkpoints and coins"
            project_dir = write_project(prompt, root)

            stale_files = [
                project_dir / "src" / "ServerScriptService" / "Old.server.lua",
                project_dir / "secret.txt",
                project_dir / "extra" / "old.txt",
                project_dir / "exports" / "old-bundle.zip",
            ]
            for stale_file in stale_files:
                stale_file.parent.mkdir(parents=True, exist_ok=True)
                stale_file.write_text("stale", encoding="utf-8")

            sibling = root / "sibling-project"
            sibling.mkdir()
            sibling_file = sibling / "keep.txt"
            sibling_file.write_text("keep", encoding="utf-8")

            regenerated = write_project(prompt, root)

            self.assertEqual(regenerated, project_dir)
            for stale_file in stale_files:
                self.assertFalse(stale_file.exists(), str(stale_file))
            self.assertTrue(sibling_file.exists())
            self.assertTrue((project_dir / "manifest.json").exists())
            self.assertTrue((project_dir / "default.project.json").exists())
            self.assertTrue((project_dir / "src/ServerScriptService/Main.server.lua").exists())
            self.assertTrue((project_dir / "src/ServerScriptService/Services/PlayerDataService.lua").exists())
            self.assertTrue((project_dir / "src/ReplicatedStorage/GameConfig.lua").exists())
            self.assertTrue((project_dir / "src/StarterPlayer/StarterPlayerScripts/HUD.client.lua").exists())

    def test_failed_regeneration_preserves_existing_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = "make a colorful obby with checkpoints and coins"
            project_dir = write_project(prompt, root)
            marker = project_dir / "do-not-delete.txt"
            marker.write_text("original project", encoding="utf-8")

            with patch(
                "product.roblox_ai_studio.roblox.generator.render_project_json",
                side_effect=RuntimeError("synthetic render failure"),
            ):
                with self.assertRaises(RuntimeError):
                    write_project(prompt, root)

            self.assertTrue(project_dir.exists())
            self.assertEqual(marker.read_text(encoding="utf-8"), "original project")
            self.assertTrue((project_dir / "manifest.json").exists())
            self.assertEqual(list(root.glob(f".{project_dir.name}.tmp-*")), [])
            self.assertEqual(list(root.glob(f".{project_dir.name}.backup-*")), [])

    def test_target_dir_must_remain_under_output_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "generated"
            outside = Path(tmp) / "outside-project"
            outside.mkdir()
            marker = outside / "keep.txt"
            marker.write_text("do not touch", encoding="utf-8")

            with self.assertRaises(ValueError):
                write_project(
                    "make a colorful obby with checkpoints and coins",
                    root,
                    target_dir=outside,
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "do not touch")

    def test_target_dir_cannot_replace_output_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "generated"
            root.mkdir()

            with self.assertRaises(ValueError):
                write_project(
                    "make a colorful obby with checkpoints and coins",
                    root,
                    target_dir=root,
                )

    def test_backup_cleanup_failure_does_not_poison_successful_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = "make a colorful obby with checkpoints and coins"
            project_dir = write_project(prompt, root)

            def flaky_remove(path: Path) -> None:
                if ".backup-" in path.name:
                    raise OSError("synthetic cleanup failure")
                if path.is_dir():
                    import shutil

                    shutil.rmtree(path)
                else:
                    path.unlink()

            with patch("product.roblox_ai_studio.roblox.generator._remove_path", side_effect=flaky_remove):
                regenerated = write_project(prompt, root)

            self.assertEqual(regenerated, project_dir)
            self.assertTrue((project_dir / "manifest.json").exists())
            self.assertTrue((project_dir / "default.project.json").exists())

    def test_write_project_creates_service_modules_for_standard_rojo_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = write_project("make a colorful obby with checkpoints and coins", Path(tmp))

            service_paths = [
                "src/ServerScriptService/Services/PlayerDataService.lua",
                "src/ServerScriptService/Services/RewardService.lua",
                "src/ServerScriptService/Services/WorldService.lua",
            ]
            for rel in service_paths:
                self.assertTrue((out / rel).exists(), rel)

            main = (out / "src/ServerScriptService/Main.server.lua").read_text(encoding="utf-8")
            self.assertIn("local Services = script.Parent:WaitForChild(\"Services\")", main)
            self.assertIn("require(Services:WaitForChild(\"PlayerDataService\"))", main)
            self.assertIn("require(Services:WaitForChild(\"RewardService\"))", main)
            self.assertIn("require(Services:WaitForChild(\"WorldService\"))", main)

            for rel in service_paths:
                module = (out / rel).read_text(encoding="utf-8")
                self.assertIn("local Service = {}", module)
                self.assertIn("function Service.Start", module)
                self.assertIn("return Service", module)

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            for rel in service_paths:
                self.assertIn(rel, manifest["scripts"])

    def test_generated_hud_uses_escaped_newline_inside_luau_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = write_project("make a colorful obby with checkpoints and coins", Path(tmp))
            hud = (out / "src/StarterPlayer/StarterPlayerScripts/HUD.client.lua").read_text(encoding="utf-8")

            self.assertIn('Base: %s\\nLap: %s', hud)
            self.assertNotIn('Base: %s\nLap: %s', hud)

    def test_refinement_adds_iteration_systems_and_luau(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = write_project(
                "make a pirate tycoon with coins",
                Path(tmp),
                refinement_prompt="add pets, a boss, and daily rewards",
            )
            plan = (out / "game_plan.md").read_text()
            self.assertIn("pet companion collection", plan)
            self.assertIn("boss encounter milestone", plan)
            self.assertIn("daily reward retention loop", plan)

            server_lua = (out / "src/ServerScriptService/Main.server.lua").read_text()
            self.assertIn("createPetSpawn", server_lua)
            self.assertIn("buildPetArea(folder)", server_lua)
            self.assertIn("createBossEncounter", server_lua)
            self.assertIn("buildBossArena(folder)", server_lua)

            config_lua = (out / "src/ReplicatedStorage/GameConfig.lua").read_text()
            self.assertIn("GameConfig.PetSpawnCost", config_lua)
            self.assertIn("GameConfig.BossHealth", config_lua)


    def test_generated_artifacts_use_roblox_ai_studio_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = write_project("make a colorful obby with coins", Path(tmp))
            server = (project_dir / "src/ServerScriptService/Main.server.lua").read_text(encoding="utf-8")
            hud = (project_dir / "src/StarterPlayer/StarterPlayerScripts/HUD.client.lua").read_text(encoding="utf-8")
            readme = (project_dir / "README.md").read_text(encoding="utf-8")
            manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))

            combined = "\n".join([server, hud, readme, manifest["generator"]])
            self.assertIn("Roblox AI Studio", combined)
            self.assertNotIn("Playro", combined)
            self.assertNotIn("HermesRobloxHUD", combined)


if __name__ == "__main__":
    unittest.main()
