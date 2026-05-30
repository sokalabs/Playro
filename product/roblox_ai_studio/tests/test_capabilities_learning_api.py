import tempfile
import unittest
from pathlib import Path

from product.roblox_ai_studio.app import api
from product.roblox_ai_studio.hermes_backend.capabilities import (
    capability_manifest,
    default_playro_skill_pack,
    learning_records_for_build,
    playro_skill_packs,
)


class CapabilitiesLearningApiTests(unittest.TestCase):
    def test_capability_manifest_is_roblox_focused_and_exposes_hermes_strengths(self):
        manifest = capability_manifest()

        self.assertEqual(manifest["product"], "Roblox AI Studio")
        self.assertEqual(manifest["scope"], "roblox_creation")
        self.assertIn("skills", manifest["capabilities"])
        self.assertIn("sessions", manifest["capabilities"])
        self.assertEqual(manifest["roblox_skills"][0]["id"], "playro-game-designer")
        native_skill_names = {skill["name"] for skill in manifest["native_roblox_skill_templates"]}
        self.assertGreaterEqual(native_skill_names, {"Game Designer", "Luau Coder", "World Builder", "Systems Builder", "Playtest Fixer", "Rojo Packager"})
        self.assertNotIn("Obby planner", native_skill_names)
        self.assertNotIn("Tycoon economy", native_skill_names)
        self.assertGreaterEqual(manifest["skill_catalog"]["counts"]["visible"], 100)
        self.assertIn("toolbox", manifest["skill_catalog"]["default_enabled_buckets"])
        self.assertTrue(any(skill["source"] == "hermes_skill" for skill in manifest["roblox_skills"]))
        self.assertGreaterEqual({mode["id"] for mode in manifest["quality_modes"]}, {"fast_draft", "balanced", "high_quality"})
        self.assertEqual(manifest["default_skill_pack"], "first-build")
        packs = manifest["skill_packs"]
        self.assertGreaterEqual(len(packs), 5)
        skill_ids = {skill["id"] for skill in manifest["roblox_skills"]}
        mode_ids = {mode["id"] for mode in manifest["quality_modes"]}
        for pack in packs:
            self.assertIn(pack["skill_id"], skill_ids)
            self.assertIn(pack["quality_mode"], mode_ids)
        self.assertTrue(any(pack.get("default") for pack in packs))
        pack_labels = {pack["label"] for pack in packs}
        self.assertNotIn("Obby", " ".join(pack_labels))
        self.assertEqual(default_playro_skill_pack()["id"], manifest["default_skill_pack"])
        self.assertEqual(len(playro_skill_packs()), len(packs))
        self.assertTrue(manifest["desktop_adaptations"]["playro_mapping"].startswith("All adapted features"))
        self.assertTrue(manifest["boundaries"]["does_not_import_live_hermes_config"])
        self.assertIn("memory", manifest["capabilities"])
        self.assertEqual(manifest["capabilities"]["memory"]["default_mode"], "holographic")
        self.assertEqual(manifest["memory_policy"]["default"], "holographic")
        self.assertEqual(manifest["memory_policy"]["toolset"], "fact_store")
        self.assertTrue(manifest["memory_policy"]["does_not_import_live_hermes_memory"])
        self.assertIn("build_jobs", manifest["capabilities"])
        self.assertIn("continuous_24_7_mode", manifest["capabilities"])
        self.assertIn("pause_stop", manifest["capabilities"])
        self.assertIn("generated_files", manifest["capabilities"])
        self.assertEqual(manifest["capabilities"]["skills"]["surface_label"], "Roblox build skills")
        self.assertEqual(manifest["capabilities"]["provider_routing"]["surface_label"], "Quality routing")
        parity_ids = {item["id"] for item in manifest["hermes_parity_surfaces"]}
        self.assertGreaterEqual(
            parity_ids,
            {"sessions", "analytics", "models", "logs", "build24", "skills", "plugins", "crews", "config", "keys", "docs"},
        )
        self.assertTrue(all("playro_surface" in item and "rows" in item for item in manifest["hermes_parity_surfaces"]))
        self.assertIn({"id": "analytics", "label": "Build analytics", "status": "planned"}, manifest["sidebar_nav"])
        serialized = repr(manifest).lower()
        self.assertIn("roblox", serialized)
        for banned in ["unraid", "homelab", "server_management", "live_hermes_environment"]:
            self.assertNotIn(banned, repr(manifest["capabilities"]).lower())

    def test_learning_records_are_product_local_and_ready_for_future_skill_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "pirate-tycoon"
            project_dir.mkdir()
            for rel in ["manifest.json", "game_plan.md", "src/ServerScriptService/Main.server.lua"]:
                path = project_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}" if rel.endswith(".json") else "content", encoding="utf-8")

            records = learning_records_for_build(
                project_id="pirate-tycoon",
                prompt="make a Roblox pirate tycoon with pets and boss fights",
                project_dir=project_dir,
                systems=["pet companion collection", "boss encounter milestone"],
                continuous=True,
            )

            self.assertGreaterEqual(len(records), 3)
            categories = {record["category"] for record in records}
            self.assertGreaterEqual(categories, {"prompt_pattern", "system_pattern", "artifact_pattern", "autonomy_pattern"})
            self.assertTrue(all(record["scope"] == "product-local" for record in records))
            self.assertTrue(all(record["future_target"] in {"hermes_skill", "hermes_memory"} for record in records))
            self.assertTrue(all("Roblox" in record["summary"] or "Rojo" in record["summary"] for record in records))

    def test_build_state_contains_learning_records_and_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_output_root = api.DEFAULT_OUTPUT_ROOT
            api.DEFAULT_OUTPUT_ROOT = Path(tmp)
            try:
                project_dir = Path(tmp) / "coin-obby"
                project_dir.mkdir()
                (project_dir / "src/ServerScriptService").mkdir(parents=True)
                (project_dir / "manifest.json").write_text(
                    '{"title":"Coin Obby","original_prompt":"make a Roblox coin obby","systems":["coin collection economy"]}',
                    encoding="utf-8",
                )
                for rel in api.GENERATED_FILES:
                    path = project_dir / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if not path.exists():
                        path.write_text("{}" if rel.endswith(".json") else "content", encoding="utf-8")

                state = api._build_state(project_dir, prompt="make a Roblox coin obby", quality="High quality", continuous=True)

                self.assertEqual(state["capabilities"]["capabilities"]["continuous_24_7_mode"]["status"], "prototype")
                self.assertTrue(state["controls"]["pause_stop"]["enabled"])
                self.assertTrue(state["learning_records"])
                self.assertTrue(state["learning_records_path"].endswith("learning_records.json"))
                self.assertTrue((project_dir / "learning_records.json").exists())
                project = api._project_record(project_dir)
                self.assertEqual(project["learning_count"], len(state["learning_records"]))
                self.assertIn("learning_records.json", project["files"])
            finally:
                api.DEFAULT_OUTPUT_ROOT = original_output_root


if __name__ == "__main__":
    unittest.main()
