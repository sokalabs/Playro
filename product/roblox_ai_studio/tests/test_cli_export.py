"""CLI export regression tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from product.roblox_ai_studio.app.cli import main
from product.roblox_ai_studio.tests.fixtures import write_generated_project


def _make_exportable_project(root: Path, slug: str) -> Path:
    project_dir = write_generated_project(
        root,
        slug,
        prompt="make a colorful obby",
        include_metadata=True,
    )
    (project_dir / "build_state.json").write_text(json.dumps({"status": "Generated"}), encoding="utf-8")
    (project_dir / "build_job.json").write_text(json.dumps({"id": "b1", "status": "completed"}), encoding="utf-8")
    return project_dir


class CliExportTests(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(argv)
        return exit_code, output.getvalue()

    def test_export_rejects_project_id_traversal_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            output_root = tmp_root / "generated"
            output_root.mkdir()
            outside_project = _make_exportable_project(tmp_root, "outside-project")

            for project_id in ("../outside-project", "subdir/project", str(outside_project.resolve())):
                with self.subTest(project_id=project_id):
                    exit_code, output = self._run_cli(
                        ["export", project_id, "--output-root", str(output_root)]
                    )

                    self.assertEqual(exit_code, 1)
                    self.assertIn("Invalid project id", output)
                    self.assertNotIn(str(outside_project.resolve()), output)
            self.assertFalse((outside_project / "exports").exists())

    def test_export_rejects_invalid_project_id_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)

            exit_code, output = self._run_cli(
                ["export", "../outside-project", "--output-root", str(output_root), "--json"]
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(json.loads(output), {"ok": False, "error": "invalid project id"})

    def test_export_accepts_valid_project_id_under_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            _make_exportable_project(output_root, "valid-obby")

            exit_code, output = self._run_cli(
                ["export", "valid-obby", "--output-root", str(output_root)]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Exported project: valid-obby", output)
            self.assertIn("Bundle:", output)
            self.assertTrue((output_root / "valid-obby" / "exports").is_dir())


if __name__ == "__main__":
    unittest.main()
