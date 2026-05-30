"""Smoke validation for generated Roblox sample projects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from product.roblox_ai_studio.app.artifacts import PLAYRO_SAMPLE_VALIDATION_FILES
from product.roblox_ai_studio.app.gameplay_validation import validate_gameplay_mechanics

DEFAULT_SAMPLES_ROOT = Path(__file__).resolve().parents[1] / "generated_projects" / "sprint_samples"

REQUIRED_FILES = list(PLAYRO_SAMPLE_VALIDATION_FILES)

REQUIRED_ROJO_PATHS = {
    "ReplicatedStorage.$path": "src/ReplicatedStorage",
    "ServerScriptService.$path": "src/ServerScriptService",
    "StarterPlayer.StarterPlayerScripts.$path": "src/StarterPlayer/StarterPlayerScripts",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _get_nested(payload: dict, dotted_path: str):
    node = payload
    for part in dotted_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def validate_single_project(project_dir: Path) -> dict:
    errors: list[str] = []
    checked_files: list[str] = []

    for rel in REQUIRED_FILES:
        checked_files.append(rel)
        if not (project_dir / rel).exists():
            errors.append(f"missing:{rel}")

    project_json_path = project_dir / "default.project.json"
    if project_json_path.exists():
        try:
            project_json = json.loads(_read_text(project_json_path))
        except json.JSONDecodeError:
            project_json = None
            errors.append("default.project.json is invalid JSON")

        if isinstance(project_json, dict):
            for dotted_path, expected in REQUIRED_ROJO_PATHS.items():
                value = _get_nested(project_json, f"tree.{dotted_path}")
                if value != expected:
                    errors.append(dotted_path)

    # Base Luau/file checks
    manifest_path = project_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(_read_text(manifest_path))
            if not manifest.get("original_prompt"):
                errors.append("manifest.original_prompt")
            if not isinstance(manifest.get("systems"), list) or not manifest.get("systems"):
                errors.append("manifest.systems")
            if not manifest.get("loop"):
                errors.append("manifest.loop")
        except json.JSONDecodeError:
            errors.append("manifest.json is invalid JSON")

    server_lua = project_dir / "src/ServerScriptService/Main.server.lua"
    if server_lua.exists():
        text = _read_text(server_lua)
        if "Players.PlayerAdded" not in text:
            errors.append("Main.server.lua missing Players.PlayerAdded")
        if "GeneratedGameplay" not in text:
            errors.append("Main.server.lua missing GeneratedGameplay")

    config_lua = project_dir / "src/ReplicatedStorage/GameConfig.lua"
    if config_lua.exists() and "GameConfig" not in _read_text(config_lua):
        errors.append("GameConfig.lua missing GameConfig table")

    hud_lua = project_dir / "src/StarterPlayer/StarterPlayerScripts/HUD.client.lua"
    if hud_lua.exists() and "ScreenGui" not in _read_text(hud_lua):
        errors.append("HUD.client.lua missing ScreenGui")

    # Run gameplay mechanics validation
    if not errors:  # Only if base file checks passed
        mechanics_res = validate_gameplay_mechanics(project_dir)
        if not mechanics_res.ok:
            errors.extend(mechanics_res.errors)

    return {
        "project": project_dir.name,
        "path": str(project_dir),
        "ok": not errors,
        "errors": errors,
        "checked_files": checked_files,
    }


def validate_sample_projects(samples_root: Path, min_projects: int = 2) -> dict:
    if not samples_root.exists():
        return {
            "ok": False,
            "samples_root": str(samples_root),
            "project_count": 0,
            "errors": [f"samples root does not exist: {samples_root}"],
            "projects": [],
        }

    projects = [
        path
        for path in sorted(samples_root.iterdir())
        if path.is_dir() and (path / "manifest.json").exists() and (path / "default.project.json").exists()
    ]

    results = [validate_single_project(project_dir) for project_dir in projects]
    aggregate_errors = [error for result in results for error in result["errors"]]
    if len(projects) < min_projects:
        aggregate_errors.insert(0, f"Expected at least {min_projects} sample projects, found {len(projects)}")

    return {
        "ok": len(aggregate_errors) == 0,
        "samples_root": str(samples_root),
        "project_count": len(projects),
        "errors": aggregate_errors,
        "projects": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate generated Roblox sample projects")
    parser.add_argument("--samples-root", default=str(DEFAULT_SAMPLES_ROOT), help="Directory containing sample projects")
    parser.add_argument("--min-projects", type=int, default=2, help="Minimum expected project count")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_sample_projects(Path(args.samples_root), min_projects=args.min_projects)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Sample validation root: {result['samples_root']}")
        print(f"Projects found: {result['project_count']}")
        if result["ok"]:
            print("Validation: PASS")
        else:
            print("Validation: FAIL")
            for error in result["errors"]:
                print(f"- {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
