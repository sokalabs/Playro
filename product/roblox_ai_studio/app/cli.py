"""CLI surface for the Playro local prototype."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import tomllib

from product.roblox_ai_studio.app.api import create_build_job
from product.roblox_ai_studio.app.artifacts import SMOKE_REQUIRED_FILES
from product.roblox_ai_studio.app.export_bundle import export_project
from product.roblox_ai_studio.app.security import is_safe_project_id, safe_project_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start a Roblox build job from a prompt.")
    parser.add_argument("--version", action="store_true", help="Print the Playro engine version and exit")
    subparsers = parser.add_subparsers(dest="command", required=False)

    # generate subcommand (default behavior)
    gen_parser = subparsers.add_parser("generate", help="Generate a Roblox project from a prompt")
    gen_parser.add_argument("prompt", help="Plain-language Roblox game idea")
    gen_parser.add_argument(
        "--refine",
        default=None,
        help="Optional iteration prompt, e.g. 'add pets and daily rewards'",
    )
    gen_parser.add_argument(
        "--output-root",
        default=str(Path(__file__).resolve().parents[1] / "generated_projects"),
        help="Directory where generated Roblox projects are written",
    )
    gen_parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    gen_parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run clone-safe smoke validation checks in the CLI output payload.",
    )
    gen_parser.add_argument(
        "--continuous",
        "--24-7",
        action="store_true",
        help="Start this prompt as an optional 24/7 continuous build mission.",
    )
    gen_parser.add_argument(
        "--autonomous",
        action="store_true",
        help="Mark the mission as autonomous/long-running in product-local metadata.",
    )

    # export subcommand
    exp_parser = subparsers.add_parser("export", help="Export a generated project as a zip bundle")
    exp_parser.add_argument("project_id", help="Project slug (directory name under generated_projects)")
    exp_parser.add_argument(
        "--output-root",
        default=str(Path(__file__).resolve().parents[1] / "generated_projects"),
        help="Directory where generated Roblox projects are stored",
    )
    exp_parser.add_argument("--json", action="store_true", help="Print machine-readable result")

    return parser


def _playro_engine_version() -> str:
    try:
        return importlib.metadata.version("playro")
    except importlib.metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return "unknown"
        return str(data.get("project", {}).get("version") or "unknown")


def _smoke_report(project_path: str) -> dict:
    project_dir = Path(project_path)
    missing = [path for path in SMOKE_REQUIRED_FILES if not (project_dir / path).exists()]
    lua_files = [path for path in SMOKE_REQUIRED_FILES if path.endswith(".lua") and (project_dir / path).exists()]
    return {
        "ok": not missing,
        "project_path": str(project_dir),
        "required_files": SMOKE_REQUIRED_FILES,
        "missing_files": missing,
        "lua_files": lua_files,
        "rojo_project": str(project_dir / "default.project.json"),
    }


def main(argv: list[str] | None = None) -> int:
    import sys
    if argv is None:
        argv = sys.argv[1:]
    
    # Backward compatibility: if the first arg is not a subcommand and not a flag, prepend 'generate'
    if argv and argv[0] not in {"generate", "export"} and not argv[0].startswith("-"):
        argv = ["generate"] + argv

    args = build_parser().parse_args(argv)
    if args.version:
        print(f"Playro AI Engine {_playro_engine_version()}")
        return 0
    command = getattr(args, "command", "generate")

    # Export subcommand
    if command == "export":
        if not is_safe_project_id(args.project_id):
            if args.json:
                print(json.dumps({"ok": False, "error": "invalid project id"}, indent=2))
            else:
                print("Invalid project id: use a project slug without path separators.")
            return 1
        project_dir = safe_project_dir(args.project_id, Path(args.output_root))
        if project_dir is None:
            if args.json:
                print(json.dumps({"ok": False, "error": "project not found"}, indent=2))
            else:
                print(f"Project not found: {args.project_id}")
            return 1
        try:
            result = export_project(project_dir)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Export failed: {exc}")
            return 1
        if not result.get("ok"):
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Export failed: {result.get('error', 'unknown')}")
                if result.get("missing_files"):
                    print(f"Missing files: {', '.join(result['missing_files'])}")
            return 1
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Exported project: {result['project_id']}")
            print(f"Bundle: {result['bundle_path']}")
            print(f"Size: {result['bundle_size_bytes']} bytes")
            print(f"Files included: {result['included_file_count']}")
            print(f"SHA-256: {result['bundle_sha256']}")
        return 0

    # Generate (default) — backward compatible with bare prompt arg
    prompt = args.prompt
    if not prompt:
        print("Usage: cli.py <prompt> | cli.py generate <prompt> | cli.py export <project_id>")
        return 1
    if not args.json:
        print(f"Started Roblox build job for prompt: {prompt}")
    result = create_build_job(
        prompt,
        output_root=Path(args.output_root),
        refinement_prompt=args.refine,
        continuous=args.continuous,
        autonomous=args.autonomous,
    )
    job = result["build_job"]
    if args.smoke:
        result["smoke"] = _smoke_report(result["project_path"])
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Completed Roblox build job {job['id']} with status: {job['status']}")
        print(f"Generated files: {', '.join(job['generated_files'])}")
        print("Validation: passed" if job["validation"]["ok"] else "Validation: failed")
        print(f"Next action: {job['next_action']}")
        print(f"Project path: {result['project_path']}")
        if args.smoke:
            smoke_status = "passed" if result["smoke"]["ok"] else "failed"
            print(f"Clone-safe smoke check: {smoke_status}")
            if not result["smoke"]["ok"]:
                print(f"Missing files: {', '.join(result['smoke']['missing_files'])}")
        print("Builder metadata: manifest.json, build_job.json, build_state.json, and history updated.")
        if result.get("build_mission"):
            print("24/7 build mission: build_mission.json created with pause/stop metadata.")
        print("Tool surface: Roblox-focused allowlist; live Hermes environment tools are not imported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
