"""Tests for export_bundle: zip creation, required files, exclusion, path traversal safety."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from product.roblox_ai_studio.app.export_bundle import (
    EXCLUDE_EXTENSIONS,
    FORBIDDEN_DIR_NAMES,
    REQUIRED_EXPORT_FILES,
    _is_path_traversal,
    _should_exclude,
    export_project,
)
from product.roblox_ai_studio.tests.fixtures import write_generated_project


def _make_full_project(root: Path, slug: str = "test-obby") -> Path:
    project_dir = write_generated_project(
        root,
        slug,
        prompt="make an obby with coins",
        include_metadata=True,
    )
    (project_dir / "build_state.json").write_text(json.dumps({"status": "Generated"}), encoding="utf-8")
    (project_dir / "build_job.json").write_text(json.dumps({"id": "b1", "status": "completed"}), encoding="utf-8")
    return project_dir


class ExportBundleCreationTests(unittest.TestCase):
    """Tests for successful export bundle creation."""

    def test_export_creates_zip_with_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            result = export_project(project_dir)

            self.assertTrue(result["ok"])
            self.assertEqual(result["project_id"], "test-obby")
            self.assertTrue(result["bundle_path"].endswith(".zip"))
            self.assertGreater(result["bundle_size_bytes"], 0)
            self.assertTrue(result["bundle_sha256"])

            # Verify zip exists and is valid
            zip_path = Path(result["bundle_path"])
            self.assertTrue(zip_path.exists())
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                # All required files should be inside the zip under <slug>/ prefix
                for req in REQUIRED_EXPORT_FILES:
                    expected = f"test-obby/{req}"
                    self.assertIn(expected, names, f"Required file {req} missing from zip")

    def test_export_manifest_written_to_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            result = export_project(project_dir)
            self.assertTrue(result["ok"])

            manifest_path = project_dir / "export_manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["project_id"], "test-obby")
            self.assertEqual(manifest["export_format_version"], "1.0")
            self.assertIn("bundle_sha256", manifest)
            self.assertIn("file_hashes", manifest)
            # All required files listed as present
            for req in REQUIRED_EXPORT_FILES:
                self.assertIn(req, manifest["required_files_present"])

    def test_export_updates_build_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            result = export_project(project_dir)
            self.assertTrue(result["ok"])

            build_state = json.loads((project_dir / "build_state.json").read_text(encoding="utf-8"))
            self.assertIn("exports", build_state)
            self.assertEqual(len(build_state["exports"]), 1)
            entry = build_state["exports"][0]
            self.assertEqual(entry["export_id"], result["export_manifest"]["export_id"])
            self.assertIn("bundle_sha256", entry)

    def test_export_writes_to_custom_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)
            custom_output = root / "custom_exports"
            custom_output.mkdir()

            result = export_project(project_dir, output_dir=custom_output)

            self.assertTrue(result["ok"])
            self.assertTrue(str(custom_output) in result["bundle_path"])


class ExportRequiredFilesTests(unittest.TestCase):
    """Tests for required file validation during export."""

    def test_export_fails_gracefully_on_missing_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)
            # Delete a required file
            (project_dir / "game_plan.md").unlink()

            result = export_project(project_dir)

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "missing required files")
            self.assertIn("game_plan.md", result["missing_files"])

    def test_export_fails_on_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "no-manifest"
            project_dir.mkdir()

            with self.assertRaises(FileNotFoundError):
                export_project(project_dir)

    def test_export_fails_on_nonexistent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "does-not-exist"

            with self.assertRaises(FileNotFoundError):
                export_project(project_dir)


class ExportExclusionTests(unittest.TestCase):
    """Tests for cache/transient file exclusion from export bundles."""

    def test_excludes_pycache_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)
            # Add __pycache__
            pycache = project_dir / "__pycache__"
            pycache.mkdir()
            (pycache / "module.cpython-313.pyc").write_bytes(b"\x00" * 10)

            result = export_project(project_dir)
            self.assertTrue(result["ok"])

            with zipfile.ZipFile(result["bundle_path"], "r") as zf:
                names = zf.namelist()
                for name in names:
                    self.assertNotIn("__pycache__", name)

            # pyc file should be in skipped
            self.assertTrue(any("__pycache__" in s for s in result["export_manifest"]["skipped_files"]))

    def test_excludes_log_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)
            (project_dir / "debug.log").write_text("log entry", encoding="utf-8")

            result = export_project(project_dir)
            self.assertTrue(result["ok"])

            with zipfile.ZipFile(result["bundle_path"], "r") as zf:
                names = zf.namelist()
                for name in names:
                    self.assertFalse(name.endswith(".log"))

    def test_excludes_exports_directory_from_bundle(self):
        """Exports directory from a previous export should not be bundled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            # First export
            result1 = export_project(project_dir)
            self.assertTrue(result1["ok"])

            # Second export should not include the first export's zip
            result2 = export_project(project_dir)
            self.assertTrue(result2["ok"])

            with zipfile.ZipFile(result2["bundle_path"], "r") as zf:
                names = zf.namelist()
                for name in names:
                    self.assertNotIn("exports/", name)


class ExportPathTraversalSafetyTests(unittest.TestCase):
    """Tests for path traversal detection and rejection."""

    def test_is_path_traversal_detects_dotdot(self):
        self.assertTrue(_is_path_traversal("../etc/passwd", Path("/safe")))
        self.assertTrue(_is_path_traversal("sub/../../etc/passwd", Path("/safe")))

    def test_is_path_traversal_allows_normal_paths(self):
        self.assertFalse(_is_path_traversal("src/ServerScriptService/Main.server.lua", Path("/safe")))
        self.assertFalse(_is_path_traversal("manifest.json", Path("/safe")))

    def test_is_path_traversal_detects_backslash(self):
        self.assertTrue(_is_path_traversal("sub\\..\\etc", Path("/safe")))

    def test_should_exclude_pycache(self):
        self.assertTrue(_should_exclude("__pycache__/module.pyc", "module.pyc"))

    def test_should_exclude_node_modules(self):
        self.assertTrue(_should_exclude("node_modules/react/index.js", "index.js"))

    def test_should_exclude_log_extension(self):
        self.assertTrue(_should_exclude("debug.log", "debug.log"))

    def test_should_not_exclude_lua_files(self):
        self.assertFalse(_should_exclude("src/ServerScriptService/Main.server.lua", "Main.server.lua"))

    def test_should_not_exclude_json_manifest(self):
        self.assertFalse(_should_exclude("manifest.json", "manifest.json"))

    def test_export_with_symlink_pointing_outside_does_not_escape(self):
        """A symlink inside the project pointing outside should be skipped, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            # Create a file outside the project
            outside = root / "outside_secret.txt"
            outside.write_text("secret", encoding="utf-8")

            # Create symlink inside project pointing outside
            symlink = project_dir / "secret_link.txt"
            try:
                symlink.symlink_to(outside)
            except OSError:
                self.skipTest("Symlink creation not supported on this platform")

            # Symlinks should be skipped gracefully — the export must succeed
            result = export_project(project_dir)
            self.assertTrue(result.get("ok"), "Export should succeed even with external symlinks")

            # The symlink target must not appear in the bundle
            with zipfile.ZipFile(result["bundle_path"], "r") as zf:
                names = zf.namelist()
                for name in names:
                    self.assertNotIn("secret_link", name)

            # The symlink should be recorded as skipped
            self.assertTrue(
                any("secret_link" in s for s in result["export_manifest"]["skipped_files"]),
                "Symlink should appear in skipped_files",
            )


class ExportDeterminismTests(unittest.TestCase):
    """Tests for deterministic behavior of exports."""

    def test_included_files_are_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            result = export_project(project_dir)
            self.assertTrue(result["ok"])
            files = result["included_files"]
            self.assertEqual(files, sorted(files))

    def test_zip_entries_are_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            result = export_project(project_dir)
            self.assertTrue(result["ok"])

            with zipfile.ZipFile(result["bundle_path"], "r") as zf:
                names = zf.namelist()
                self.assertEqual(names, sorted(names))

    def test_file_hashes_are_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            result = export_project(project_dir)
            self.assertTrue(result["ok"])

            manifest = json.loads((project_dir / "export_manifest.json").read_text(encoding="utf-8"))
            # Verify at least one hash is correct by computing independently
            for rel_path, expected_hash in manifest["file_hashes"].items():
                if rel_path == "build_state.json":
                    continue  # This file is mutated after hashing
                if (project_dir / rel_path).exists():
                    import hashlib
                    h = hashlib.sha256()
                    with open(project_dir / rel_path, "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            h.update(chunk)
                    self.assertEqual(h.hexdigest(), expected_hash, f"Hash mismatch for {rel_path}")


class ExportIdempotencyTests(unittest.TestCase):
    """Tests for multiple exports of the same project."""

    def test_multiple_exports_record_in_build_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = _make_full_project(root)

            r1 = export_project(project_dir)
            r2 = export_project(project_dir)

            self.assertTrue(r1["ok"])
            self.assertTrue(r2["ok"])

            build_state = json.loads((project_dir / "build_state.json").read_text(encoding="utf-8"))
            self.assertEqual(len(build_state["exports"]), 2)


if __name__ == "__main__":
    unittest.main()
