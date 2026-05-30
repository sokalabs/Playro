"""Export bundle packaging for generated Roblox projects.

Creates a deterministic zip archive with manifest metadata, excludes
transient/cache files, and records export status in build_state and a
dedicated export_manifest.json inside the project directory.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import time
import zipfile
from pathlib import Path

from product.roblox_ai_studio.app.artifacts import REQUIRED_EXPORT_FILES

# Patterns/directories to exclude from the export bundle.
# Covers transient Chromium, cache, node_modules, and build artifacts.
EXCLUDE_PATTERNS: list[str] = [
    "__pycache__",
    ".cache",
    "cache",
    "node_modules",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.pyc",
    "*.pyo",
    ".git",
    ".gitignore",
    ".svn",
    ".hg",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    ".env",
    ".env.local",
    ".env.*.local",
]

# File extensions to skip (transient / environment-specific)
EXCLUDE_EXTENSIONS: set[str] = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".bak",
    ".swp",
    ".swo",
}

# Directories that should never appear inside a valid project export
FORBIDDEN_DIR_NAMES: set[str] = {
    "__pycache__",
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    ".cache",
    "cache",
}


def _should_exclude(rel_path: str, name: str) -> bool:
    """Check if a file/dir should be excluded from the export bundle."""
    # Check forbidden directory names
    parts = Path(rel_path).parts
    for part in parts:
        if part in FORBIDDEN_DIR_NAMES:
            return True

    # Check excluded extensions
    if Path(name).suffix.lower() in EXCLUDE_EXTENSIONS:
        return True

    # Check excluded patterns with glob semantics against the file name and
    # normalized relative path. This covers patterns such as `.env.*.local`.
    normalized_rel = Path(rel_path).as_posix()
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(normalized_rel, pattern):
            return True

    return False


def _is_path_traversal(rel_path: str, project_dir: Path) -> bool:
    """Detect path traversal attempts in archive member paths."""
    parts = Path(rel_path).parts
    if Path(rel_path).is_absolute() or any(part in {"", ".", ".."} or "\\" in part for part in parts):
        return True
    resolved = (project_dir / rel_path).resolve()
    try:
        resolved.relative_to(project_dir.resolve())
    except ValueError:
        return True
    return False


def _file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def export_project(
    project_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Package a generated Roblox project into a deterministic zip bundle.

    Args:
        project_dir: Path to the generated project directory (must contain manifest.json).
        output_dir: Directory to write the zip to. Defaults to project_dir / "exports".

    Returns:
        Dict with export result, manifest, and paths.

    Raises:
        FileNotFoundError: If project_dir does not exist or lacks manifest.json.
        ValueError: If path traversal is detected in project files.
    """
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    if not (project_dir / "manifest.json").exists():
        raise FileNotFoundError(f"No manifest.json in project: {project_dir}")

    # Validate required files before export
    missing = [f for f in REQUIRED_EXPORT_FILES if not (project_dir / f).exists()]
    if missing:
        return {
            "ok": False,
            "error": "missing required files",
            "missing_files": missing,
            "project_id": project_dir.name,
        }

    # Output directory
    if output_dir is None:
        output_dir = project_dir / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Deterministic zip name: <slug>-export-<timestamp>-<uuid>.zip
    import uuid
    slug = project_dir.name
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:6]
    zip_name = f"{slug}-export-{timestamp}-{unique_id}.zip"
    zip_path = output_dir / zip_name

    # Collect files, applying exclusion rules
    included_files: list[str] = []
    skipped_files: list[str] = []
    file_hashes: dict[str, str] = {}

    for path in sorted(project_dir.rglob("*"), key=lambda item: item.relative_to(project_dir).as_posix()):
        if not path.is_file():
            continue

        # Skip symlinks — they may resolve outside the project directory
        # and cause false path-traversal errors or leak external files.
        if path.is_symlink():
            try:
                rel = path.relative_to(project_dir).as_posix()
            except ValueError:
                rel = path.name
            skipped_files.append(rel)
            continue

        try:
            rel = path.relative_to(project_dir).as_posix()
        except ValueError:
            continue

        # Skip files inside the exports directory itself (no recursive bundles)
        if rel.startswith("exports/"):
            skipped_files.append(rel)
            continue

        # Skip export_manifest.json from previous exports
        if rel == "export_manifest.json":
            skipped_files.append(rel)
            continue

        # Check for path traversal
        if _is_path_traversal(rel, project_dir):
            raise ValueError(f"Path traversal detected: {rel}")

        # Check exclusion rules
        if _should_exclude(rel, path.name):
            skipped_files.append(rel)
            continue

        included_files.append(rel)
        file_hashes[rel] = _file_sha256(path)

    # Create deterministic zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in included_files:
            full_path = project_dir / rel
            # Verify no path traversal in the archive entry itself
            archive_name = f"{slug}/{rel}"
            archive_path = Path(archive_name)
            if archive_path.is_absolute() or any(part in {"", ".", ".."} or "\\" in part for part in archive_path.parts):
                raise ValueError(f"Unsafe archive path: {archive_name}")
            zf.write(full_path, archive_name)

    # Compute zip hash
    zip_sha256 = _file_sha256(zip_path)
    zip_size = zip_path.stat().st_size

    # Read project manifest for metadata
    manifest: dict = {}
    try:
        manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    # Build export manifest
    export_manifest = {
        "export_id": f"export_{timestamp}",
        "project_id": slug,
        "project_title": manifest.get("title", slug),
        "original_prompt": manifest.get("original_prompt", ""),
        "genre": manifest.get("genre", ""),
        "systems": manifest.get("systems", []),
        "bundle_file": zip_name,
        "bundle_path": str(zip_path),
        "bundle_size_bytes": zip_size,
        "bundle_sha256": zip_sha256,
        "included_files": included_files,
        "included_file_count": len(included_files),
        "skipped_files": skipped_files,
        "skipped_file_count": len(skipped_files),
        "file_hashes": file_hashes,
        "required_files_present": [f for f in REQUIRED_EXPORT_FILES if f in included_files],
        "exported_at": timestamp,
        "export_format_version": "1.0",
    }

    # Write export manifest to project dir
    export_manifest_path = project_dir / "export_manifest.json"
    export_manifest_path.write_text(
        json.dumps(export_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # Update build_state.json with export status
    build_state_path = project_dir / "build_state.json"
    if build_state_path.exists():
        try:
            build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            build_state = {}
    else:
        build_state = {}

    build_state.setdefault("exports", []).append(
        {
            "export_id": export_manifest["export_id"],
            "bundle_file": zip_name,
            "bundle_path": str(zip_path),
            "bundle_size_bytes": zip_size,
            "bundle_sha256": zip_sha256,
            "included_file_count": len(included_files),
            "exported_at": timestamp,
        }
    )
    build_state_path.write_text(
        json.dumps(build_state, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "action": "project_exported",
        "project_id": slug,
        "bundle_file": zip_name,
        "bundle_path": str(zip_path),
        "bundle_size_bytes": zip_size,
        "bundle_sha256": zip_sha256,
        "included_files": included_files,
        "included_file_count": len(included_files),
        "skipped_file_count": len(skipped_files),
        "export_manifest": export_manifest,
    }
