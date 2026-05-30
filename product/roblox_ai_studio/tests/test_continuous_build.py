import contextlib
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from product.roblox_ai_studio.app.cli import main as cli_main
from product.roblox_ai_studio.build_loop import (
    BuildLoopStatus,
    create_build_mission,
    load_build_mission,
    run_build_loop_tick,
    set_build_loop_status,
)


class ContinuousBuildTests(unittest.TestCase):
    def test_create_continuous_build_mission_records_product_local_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "generated_projects" / "sky-obby"
            project_dir.mkdir(parents=True)

            mission = create_build_mission(
                project_dir,
                prompt="make a sky obby with coins",
                continuous=True,
                autonomous=True,
            )

            state_path = project_dir / "build_mission.json"
            self.assertTrue(state_path.exists())
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["mission"]["prompt"], "make a sky obby with coins")
            self.assertTrue(saved["mission"]["continuous"])
            self.assertTrue(saved["mission"]["autonomous"])
            self.assertEqual(saved["loop"]["status"], "running")
            self.assertFalse(saved["loop"]["pause_requested"])
            self.assertFalse(saved["loop"]["stop_requested"])
            self.assertEqual(saved["loop"]["runner"], "product-local prototype")
            self.assertIn("hermes_integration_hint", saved["loop"])
            self.assertEqual(saved["jobs"][0]["phase"], "plan")
            self.assertEqual(saved["jobs"][0]["status"], "queued")
            self.assertIs(mission.loop.status, BuildLoopStatus.RUNNING)

    def test_build_loop_tick_advances_plan_generate_validate_and_suggests_next_improvement(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "generated_projects" / "sky-obby"
            project_dir.mkdir(parents=True)
            create_build_mission(project_dir, prompt="make a sky obby with coins", continuous=True)

            first = run_build_loop_tick(project_dir)
            second = run_build_loop_tick(project_dir)
            third = run_build_loop_tick(project_dir)
            fourth = run_build_loop_tick(project_dir)

            mission = load_build_mission(project_dir)
            phases = [job.phase for job in mission.jobs]
            statuses = [job.status for job in mission.jobs]
            self.assertEqual([first.phase, second.phase, third.phase], ["plan", "generate", "validate"])
            self.assertEqual(first.status, "completed")
            self.assertEqual(second.status, "completed")
            self.assertEqual(third.status, "completed")
            self.assertEqual(fourth.phase, "suggest")
            self.assertIn("next improvement", fourth.summary.lower())
            self.assertEqual(phases[:4], ["plan", "generate", "validate", "suggest"])
            self.assertEqual(statuses[:4], ["completed", "completed", "completed", "completed"])
            self.assertEqual(mission.loop.iteration, 1)
            self.assertEqual(mission.loop.next_phase, "plan")

    def test_pause_and_stop_status_are_recorded_without_running_the_daemon(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "generated_projects" / "sky-obby"
            project_dir.mkdir(parents=True)
            create_build_mission(project_dir, prompt="make a sky obby with coins", continuous=True)

            paused = set_build_loop_status(project_dir, "paused")
            self.assertIs(paused.loop.status, BuildLoopStatus.PAUSED)
            self.assertTrue(paused.loop.pause_requested)
            self.assertFalse(paused.loop.stop_requested)
            self.assertEqual(run_build_loop_tick(project_dir).status, "skipped")

            stopped = set_build_loop_status(project_dir, "stopped")
            self.assertIs(stopped.loop.status, BuildLoopStatus.STOPPED)
            self.assertTrue(stopped.loop.stop_requested)
            self.assertEqual(run_build_loop_tick(project_dir).status, "skipped")

    def test_cli_can_start_24_7_build_mode_with_machine_readable_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main([
                    "make a pirate tycoon with pets",
                    "--output-root",
                    tmp,
                    "--continuous",
                    "--autonomous",
                    "--json",
                ])
            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            project_dir = Path(payload["project_path"])
            self.assertTrue(payload["build_mission"]["mission"]["continuous"])
            self.assertTrue(payload["build_mission"]["mission"]["autonomous"])
            self.assertEqual(payload["build_mission"]["loop"]["status"], "running")
            self.assertTrue((project_dir / "build_mission.json").exists())


if __name__ == "__main__":
    unittest.main()
