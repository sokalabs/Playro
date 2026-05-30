"""Product-local API for the Roblox AI Studio desktop app.

This API is a desktop support layer. The visible product is the Electron GUI;
this backend gives that GUI a clean, Roblox-focused bridge into Hermes-Roblox
without importing live personal Hermes gateways, MCP servers, or environment-
specific plugins.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import os
import queue
import re
import secrets
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from concurrent.futures import ThreadPoolExecutor, Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import shutil

from product.roblox_ai_studio.app.security import (
    allowed_cors_origins,
    configured_api_token,
    is_safe_build_id,
    safe_project_dir,
    unexpected_lua_artifacts,
)

from product.roblox_ai_studio.build_loop import (
    create_build_mission,
    load_build_mission,
    run_build_loop_tick,
    set_build_loop_status,
)
from product.roblox_ai_studio.hermes_backend.capabilities import (
    capability_manifest,
    learning_records_for_build,
    write_learning_records,
)
from product.roblox_ai_studio.hermes_backend.runtime_catalog import runtime_catalog
from product.roblox_ai_studio.hermes_backend.skill_catalog import resolve_playro_skill
from product.roblox_ai_studio.hermes_backend.session import HermesRobloxSession
from product.roblox_ai_studio.hermes_backend.agent_pipeline import _run_hermes_agent
from product.roblox_ai_studio.app.build_events import BuildEvent, bus as event_bus
from product.roblox_ai_studio.app.artifacts import GENERATED_FILES, PLAYRO_CORE_ARTIFACT_FILES
from product.roblox_ai_studio.roblox.generator import write_project

DEFAULT_OUTPUT_ROOT = Path(os.environ.get("PLAYRO_DATA_DIR", Path(__file__).resolve().parents[1] / "generated_projects"))
ARTIFACT_PREVIEW_LIMIT = 4000
MAX_REQUEST_BODY_BYTES = int(os.environ.get("PLAYRO_MAX_REQUEST_BODY_BYTES", "65536"))
MAX_PROMPT_CHARS = int(os.environ.get("PLAYRO_MAX_PROMPT_CHARS", "4000"))
MAX_CONCURRENT_BUILDS = max(1, int(os.environ.get("PLAYRO_MAX_CONCURRENT_BUILDS", "2")))
PLAYRO_SSE_MAX_WAIT_SECS = int(os.environ.get("PLAYRO_SSE_MAX_WAIT_SECS", "300"))
_build_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BUILDS, thread_name_prefix="playro-build")
_active_builds: dict[str, Future] = {}
_active_builds_lock = threading.Lock()
_build_id_index: dict[tuple[str, str], Path] = {}
_build_id_index_lock = threading.Lock()
_listing_cache: dict[str, tuple[float, list[dict]]] = {}
_artifact_preview_cache: dict[str, tuple[float, list[dict]]] = {}
_listing_cache_lock = threading.Lock()

BUILD_STAGES = [
    ("prompt", "Prompt received", "Capture the Roblox game prompt and build settings."),
    ("plan", "Plan game structure", "Prepare Rojo services, shared config, server systems, client HUD, and metadata."),
    ("generate_files", "Generate project files", "Write Luau scripts, manifest, game plan, README, and default.project.json."),
    ("validate", "Validate artifacts", "Confirm expected files and product-safe backend surface."),
    ("package_open_instructions", "Package/open instructions", "Prepare Rojo/Roblox Studio next action."),
]


def _configured_api_token() -> str:
    return configured_api_token()


# Paths that are safe to expose without an API token (info only, no PII or
# project data). Every other path requires a valid `PLAYRO_API_TOKEN` match.
UNAUTHENTICATED_GET_PATHS: frozenset[str] = frozenset({"/health"})


def _allowed_cors_origins() -> set[str]:
    return allowed_cors_origins()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _new_build_id() -> str:
    return f"build_{secrets.token_urlsafe(18)}"


def _completed_stages() -> list[dict]:
    return [
        {
            "index": index,
            "key": key,
            "title": title,
            "detail": detail,
            "status": "completed",
        }
        for index, (key, title, detail) in enumerate(BUILD_STAGES, start=1)
    ]


def validate_project(project_dir: Path) -> dict:
    required_files = list(PLAYRO_CORE_ARTIFACT_FILES)
    missing = [file for file in required_files if not (project_dir / file).exists()]
    lua_files = [file for file in required_files if file.endswith(".lua") and (project_dir / file).exists()]
    allowed_lua = {path for path in PLAYRO_CORE_ARTIFACT_FILES if path.endswith(".lua")}
    unexpected_lua = unexpected_lua_artifacts(project_dir, allowed=allowed_lua)
    return {
        "ok": not missing and not unexpected_lua,
        "missing_files": missing,
        "unexpected_lua_files": unexpected_lua,
        "checked_files": required_files,
        "lua_files": lua_files,
        "rojo_project": str(project_dir / "default.project.json"),
    }


def _emit(build_id: str, stage: str, title: str, detail: str, *, data: dict | None = None) -> None:
    """Emit a build stage transition event to the SSE event bus."""
    event_bus.emit(BuildEvent(
        build_id=build_id,
        stage=stage,
        title=title,
        detail=detail,
        timestamp=time.time(),
        data=data,
    ))


def infer_genre_display(prompt: str) -> str:
    """Quick genre label from prompt text for event descriptions."""
    from product.roblox_ai_studio.roblox.generator import infer_genre
    return infer_genre(prompt)


@dataclass(frozen=True)
class ProjectBuildContextSnapshot:
    build_state: dict
    build_mission: dict
    build_job: dict

    @property
    def continuous(self) -> bool:
        mission = self.build_mission.get("mission", {}) if isinstance(self.build_mission, dict) else {}
        return bool(self.build_state.get("continuous")) or bool(mission.get("continuous"))

    @property
    def autonomous(self) -> bool:
        mission = self.build_mission.get("mission", {}) if isinstance(self.build_mission, dict) else {}
        return bool(mission.get("autonomous"))


def snapshot_project_build_context(project_dir: Path) -> ProjectBuildContextSnapshot:
    return ProjectBuildContextSnapshot(
        build_state=_read_json(project_dir / "build_state.json"),
        build_mission=_read_json(project_dir / "build_mission.json"),
        build_job=_read_json(project_dir / "build_job.json"),
    )


def resolve_refinement_build_flags(
    *,
    continuous: bool | None,
    autonomous: bool | None,
    snapshot: ProjectBuildContextSnapshot | None,
) -> tuple[bool, bool]:
    if snapshot is None:
        return bool(continuous), bool(autonomous)
    if continuous is None:
        continuous = snapshot.continuous
    else:
        continuous = bool(continuous)
    if autonomous is None:
        autonomous = snapshot.autonomous
    else:
        autonomous = bool(autonomous)
    return continuous, autonomous


def restore_preserved_build_mission(
    project_dir: Path,
    snapshot: ProjectBuildContextSnapshot,
) -> dict | None:
    if not snapshot.build_mission:
        return None
    try:
        _write_json(project_dir / "build_mission.json", snapshot.build_mission)
    except OSError as exc:
        print(f"build_mission restore failed: {exc}", file=sys.stderr)
        return None
    return snapshot.build_mission


def restore_preserved_build_job(
    project_dir: Path,
    snapshot: ProjectBuildContextSnapshot,
) -> dict | None:
    if not snapshot.build_job:
        return None
    try:
        _write_json(project_dir / "build_job.json", snapshot.build_job)
    except OSError as exc:
        print(f"build_job restore failed: {exc}", file=sys.stderr)
        return None
    return snapshot.build_job


def regenerate_existing_project(
    project_dir: Path,
    *,
    original_prompt: str,
    refinement: str,
    quality: str,
    selected_skill: dict | None = None,
) -> tuple[Path, dict]:
    snapshot = snapshot_project_build_context(project_dir)
    continuous, _autonomous = resolve_refinement_build_flags(
        continuous=None,
        autonomous=None,
        snapshot=snapshot,
    )
    output = write_project(
        original_prompt,
        project_dir.parent,
        refinement_prompt=refinement,
        target_dir=project_dir,
    )
    skill = selected_skill or resolve_playro_skill(None)
    build_state = _build_state(
        output,
        prompt=original_prompt,
        quality=quality,
        continuous=continuous,
        selected_skill=skill,
    )
    build_state["logs"].insert(0, f"Refinement applied: {refinement}")
    _write_json(output / "build_state.json", build_state)
    restore_preserved_build_mission(output, snapshot)
    restore_preserved_build_job(output, snapshot)
    return output, build_state


def create_build_job(
    prompt: str,
    *,
    output_root: Path | None = None,
    refinement_prompt: str | None = None,
    project_id: str | None = None,
    quality: str = "High quality",
    continuous: bool | None = None,
    autonomous: bool | None = None,
    build_id: str | None = None,
    skill_id: str | None = None,
) -> dict:
    if output_root is None:
        output_root = DEFAULT_OUTPUT_ROOT
    prompt = prompt.strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required", "action": "build_rejected"}

    selected_skill = resolve_playro_skill(skill_id)
    started_at = int(time.time())
    if build_id is None:
        build_id = _new_build_id()

    # When project_id is provided, this is a refinement iteration on an existing
    # project. Read the original prompt from the manifest so we reuse the project
    # directory instead of creating a new one.
    existing_project_dir = None
    refinement_snapshot: ProjectBuildContextSnapshot | None = None
    effective_prompt = prompt
    if project_id:
        # `_safe_project_dir` rejects slugs with separators or `..` and
        # confines the resolved path under `output_root`. If the slug is
        # malformed or the project does not exist we silently fall through
        # to the new-build path rather than touching any path outside the
        # output root.
        existing_project_dir = _safe_project_dir(project_id, output_root)
        if existing_project_dir is not None:
            refinement_snapshot = snapshot_project_build_context(existing_project_dir)
            continuous, autonomous = resolve_refinement_build_flags(
                continuous=continuous,
                autonomous=autonomous,
                snapshot=refinement_snapshot,
            )
            existing_manifest = _read_json(existing_project_dir / "manifest.json")
            effective_prompt = existing_manifest.get("original_prompt", prompt)
            # The current prompt is the refinement instruction
            refinement_prompt = refinement_prompt or prompt
        else:
            continuous, autonomous = resolve_refinement_build_flags(
                continuous=continuous,
                autonomous=autonomous,
                snapshot=None,
            )
        _emit(build_id, "idea", "Read refinement", f"Iterating on project {project_id} with refinement.")
    else:
        continuous, autonomous = resolve_refinement_build_flags(
            continuous=continuous,
            autonomous=autonomous,
            snapshot=None,
        )
        # Stage 1: idea — new build prompt received
        _emit(build_id, "idea", "Read prompt", f"Captured {infer_genre_display(prompt)} game prompt with Roblox-specific gameplay systems.")

    seed_metadata = {
        "build_job": {
            "id": build_id,
            "type": "roblox_project_build",
            "status": "running",
            "current_stage": "generate_files",
            "skill": selected_skill,
            "quality": quality,
            "started_at": started_at,
        },
        "history": [
            {
                "event": "build_started",
                "build_id": build_id,
                "status": "running",
                "stage": "prompt",
                "timestamp": started_at,
            }
        ],
    }

    # Stage 2: plan — prepare project structure
    if project_id:
        _emit(build_id, "plan", "Updating project", f"Applying refinement to existing project {project_id}.")
    else:
        _emit(build_id, "plan", "Plan Rojo project", "Preparing Rojo folders, shared config, server scripts, client HUD, and validation checks.")

    project_dir = write_project(
        effective_prompt,
        output_root,
        refinement_prompt=refinement_prompt,
        build_metadata=seed_metadata,
        target_dir=existing_project_dir,
    )

    # Stage 3: luau — generating files
    use_real_agent = os.environ.get("PLAYRO_USE_HERMES_AGENT", "1").strip().lower() not in {"0", "false", "no"}
    agent_result = {"agent_enabled": use_real_agent}
    if use_real_agent:
        _emit(build_id, "luau", "Ask Hermes build engine", "Running the product-local Hermes Agent pipeline for Roblox planning and repair notes.")
        agent_result = _run_hermes_agent(
            effective_prompt if not refinement_prompt else (refinement_prompt or prompt),
            timeout=int(os.environ.get("PLAYRO_HERMES_AGENT_TIMEOUT", "45")),
            refine=bool(refinement_prompt),
            original_prompt=effective_prompt if refinement_prompt else "",
            project_path=str(project_dir),
        )
    generated_files = [file for file in GENERATED_FILES if (project_dir / file).exists()]
    _emit(
        build_id, "luau", "Write Luau systems",
        f"Generated {len(generated_files)} server-authoritative mechanics and safe client UI files. Hermes Agent: {'ran' if agent_result.get('agent_ran') else agent_result.get('fallback_reason', 'disabled')}",
        data={"generated_files": generated_files, "agent": agent_result},
    )

    # Stage 4: validation + handoff
    completed_at = int(time.time())
    validation = validate_project(project_dir)
    generated_files = [file for file in GENERATED_FILES if (project_dir / file).exists()]
    manifest = _read_json(project_dir / "manifest.json")
    manifest["selected_skill"] = selected_skill
    manifest["quality_mode"] = quality
    learning_records = learning_records_for_build(
        project_id=project_dir.name,
        prompt=prompt,
        project_dir=project_dir,
        systems=manifest.get("systems", []),
        continuous=continuous,
    )
    learning_records_path = write_learning_records(project_dir, learning_records)
    capabilities_snapshot = capability_manifest()
    status = "completed" if validation["ok"] else "failed"
    job = {
        "id": build_id,
        "type": "roblox_project_build",
        "status": status,
        "prompt": prompt,
        "refinement_prompt": refinement_prompt,
        "quality": quality,
        "skill": selected_skill,
        "continuous": continuous,
        "project_path": str(project_dir),
        "rojo_project": str(project_dir / "default.project.json"),
        "current_stage": "package_open_instructions" if validation["ok"] else "validate",
        "stages": _completed_stages(),
        "generated_files": generated_files,
        "learning_records": learning_records,
        "learning_records_path": str(learning_records_path),
        "validation": validation,
        "agent": agent_result,
        "capabilities": capabilities_snapshot,
        "next_action": "Open the project folder and run `rojo serve default.project.json`, then connect from Roblox Studio.",
        "started_at": started_at,
        "completed_at": completed_at,
    }
    manifest["build_job"] = {
        "id": build_id,
        "type": "roblox_project_build",
        "status": status,
        "current_stage": job["current_stage"],
        "skill": selected_skill,
        "quality": quality,
        "stages": job["stages"],
        "generated_files": generated_files,
        "validation": validation,
        "next_action": job["next_action"],
        "started_at": started_at,
        "completed_at": completed_at,
    }
    history = manifest.setdefault("history", [])
    history.insert(
        0,
        {
            "event": "build_completed" if validation["ok"] else "build_failed",
            "build_id": build_id,
            "status": status,
            "stage": job["current_stage"],
            "timestamp": completed_at,
        },
    )
    _write_json(project_dir / "manifest.json", manifest)
    _write_json(project_dir / "build_job.json", job)
    _register_build_id_index(output_root, build_id, project_dir)
    build_state = _build_state(
        project_dir,
        prompt=prompt,
        quality=quality,
        continuous=continuous,
        selected_skill=selected_skill,
        learning_records=learning_records,
        learning_records_path=learning_records_path,
        capabilities=capabilities_snapshot,
    )
    build_state.update(
        {
            "id": build_id,
            "status": "Completed" if validation["ok"] else "Failed validation",
            "build_job": job,
            "current_stage": job["current_stage"],
            "selected_skill": selected_skill,
            "quality_mode": quality,
            "logs": [
                f"Started Roblox build job {build_id} with {selected_skill['name']} at {quality} quality.",
                f"Generated {len(generated_files)} files for {project_dir.name}.",
                "Validation passed." if validation["ok"] else "Validation failed.",
                job["next_action"],
            ],
        }
    )
    _write_json(project_dir / "build_state.json", build_state)
    build_mission = None
    if refinement_snapshot is not None:
        restored_mission = restore_preserved_build_mission(project_dir, refinement_snapshot)
        if restored_mission is not None:
            build_mission = load_build_mission(project_dir)
    if build_mission is None and (continuous or autonomous):
        build_mission = create_build_mission(
            project_dir,
            prompt=prompt,
            continuous=continuous,
            autonomous=autonomous,
        )

    # Stage 5: handoff complete
    _emit(
        build_id, "handoff", "Prepare Studio handoff",
        "Rojo project, Luau scripts, manifest, and handoff checks ready."
        if validation["ok"] else
        "Validation failed — some expected files are missing.",
        data={"project_id": project_dir.name, "ok": validation["ok"]},
    )
    # Final complete event so the SSE stream knows to close
    _emit(build_id, "complete", "Build complete", f"Build {build_id} finished.", data={"project_id": project_dir.name, "ok": validation["ok"], "files": generated_files})

    return {
        "ok": validation["ok"],
        "action": "build_started",
        "build_id": build_id,
        "build_job": job,
        "project": _project_record(project_dir),
        "project_path": str(project_dir),
        "rojo_project": str(project_dir / "default.project.json"),
        "files": generated_files,
        "timeline": job["stages"],
        "build_state": build_state,
        "build_mission": build_mission.to_dict() if build_mission else None,
    }


def project_id_from_path(project_path: str | None) -> str | None:
    if not project_path:
        return None
    return Path(str(project_path).replace("\\", "/")).name or None


def _build_index_key(output_root: Path, build_id: str) -> tuple[str, str]:
    return (str(output_root.resolve()), build_id)


def _register_build_id_index(output_root: Path, build_id: str, project_dir: Path) -> None:
    if not build_id:
        return
    with _build_id_index_lock:
        _build_id_index[_build_index_key(output_root, build_id)] = project_dir
    _invalidate_listing_cache(output_root)


def _listing_cache_stamp(output_root: Path) -> float:
    if not output_root.exists():
        return 0.0
    stamp = output_root.stat().st_mtime
    for project in _iter_project_dirs(output_root):
        stamp = max(stamp, project.stat().st_mtime)
        for name in ("manifest.json", "build_state.json", "build_job.json"):
            path = project / name
            if path.exists():
                stamp = max(stamp, path.stat().st_mtime)
    return stamp


def _iter_project_dirs(output_root: Path):
    if not output_root.exists():
        return
    for project in output_root.iterdir():
        if project.name.startswith(".") or not project.is_dir():
            continue
        yield project


def _invalidate_listing_cache(output_root: Path) -> None:
    root_key = str(output_root.resolve())
    with _listing_cache_lock:
        _listing_cache.pop(f"projects:{root_key}", None)
        _listing_cache.pop(f"jobs:{root_key}", None)
        stale_artifacts = [
            project_key
            for project_key in _artifact_preview_cache
            if Path(project_key).parent.resolve() == output_root.resolve()
        ]
        for project_key in stale_artifacts:
            _artifact_preview_cache.pop(project_key, None)


def _project_dir_for_build_id(build_id: str, output_root: Path) -> Path | None:
    key = _build_index_key(output_root, build_id)
    with _build_id_index_lock:
        cached = _build_id_index.get(key)
    if cached is not None and cached.is_dir():
        job = _read_json(cached / "build_job.json")
        if job.get("id") == build_id:
            return cached
    if not output_root.exists():
        return None
    for project in _iter_project_dirs(output_root):
        job = _read_json(project / "build_job.json")
        if job.get("id") == build_id:
            _register_build_id_index(output_root, build_id, project)
            return project
    return None


def get_build_job(build_id: str, output_root: Path | None = None) -> dict | None:
    if output_root is None:
        output_root = DEFAULT_OUTPUT_ROOT
    project_dir = _project_dir_for_build_id(build_id, output_root)
    if project_dir is None:
        return None
    return _read_json(project_dir / "build_job.json")


def list_build_jobs(output_root: Path | None = None) -> list[dict]:
    if output_root is None:
        output_root = DEFAULT_OUTPUT_ROOT
    cache_key = str(output_root.resolve())
    stamp = _listing_cache_stamp(output_root)
    with _listing_cache_lock:
        cached = _listing_cache.get(f"jobs:{cache_key}")
        if cached and cached[0] == stamp:
            return list(cached[1])
    if not output_root.exists():
        return []
    jobs = []
    for project in _iter_project_dirs(output_root):
        job = _read_json(project / "build_job.json")
        if job:
            jobs.append(job)
    jobs.sort(key=lambda item: item.get("completed_at", 0), reverse=True)
    with _listing_cache_lock:
        _listing_cache[f"jobs:{cache_key}"] = (stamp, jobs)
    return jobs


def _safe_project_dir(slug: str, output_root: Path | None = None) -> Path | None:
    if output_root is None:
        output_root = DEFAULT_OUTPUT_ROOT
    return safe_project_dir(slug, output_root)


def _project_record(project_dir: Path) -> dict:
    manifest = _read_json(project_dir / "manifest.json")
    build_state = _read_json(project_dir / "build_state.json")
    build_mission = _read_json(project_dir / "build_mission.json")
    title = manifest.get("title") or project_dir.name.replace("-", " ").title()
    prompt = manifest.get("original_prompt") or "Generated Roblox project"
    refinement = manifest.get("refinement_prompt")
    mode = build_state.get("mode") or ("refined" if refinement else "one-shot")
    learning_records = _read_json(project_dir / "learning_records.json")
    if isinstance(learning_records, dict):
        learning_count = len(learning_records.get("records", []))
    elif (project_dir / "learning_records.json").exists():
        try:
            learning_count = len(json.loads((project_dir / "learning_records.json").read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            learning_count = 0
    else:
        learning_count = 0
    return {
        "id": project_dir.name,
        "slug": project_dir.name,
        "name": title,
        "prompt": prompt,
        "status": build_state.get("status", "Generated"),
        "mode": mode,
        "time": build_state.get("updated_label", "Saved project"),
        "created_at": build_state.get("created_at"),
        "updated_at": build_state.get("updated_at") or int(project_dir.stat().st_mtime),
        "project_path": str(project_dir),
        "rojo_project": str(project_dir / "default.project.json"),
        "files": [file for file in GENERATED_FILES if (project_dir / file).exists()],
        "systems": manifest.get("systems", []),
        "prompt_fidelity": manifest.get("prompt_fidelity"),
        "genre": manifest.get("genre", "Roblox experience"),
        "skill": manifest.get("selected_skill") or build_state.get("selected_skill") or build_state.get("skill"),
        "quality_mode": manifest.get("quality_mode") or build_state.get("quality_mode") or build_state.get("quality", "High quality"),
        "quality": build_state.get("quality", "High quality"),
        "continuous": bool(build_state.get("continuous", False)) or bool(build_mission.get("mission", {}).get("continuous", False)),
        "autonomous": bool(build_mission.get("mission", {}).get("autonomous", False)),
        "build_loop_status": build_mission.get("loop", {}).get("status"),
        "learning_count": learning_count,
        "iteration_count": max(learning_count, len([k for k in manifest if k.endswith("_version")])) if learning_count else 0,
        "progress": build_state.get("progress", 100 if build_state else 0),
    }


def _project_artifact_stamp(project_dir: Path) -> float:
    stamp = project_dir.stat().st_mtime
    for rel_path in GENERATED_FILES:
        path = project_dir / rel_path
        if path.exists():
            stamp = max(stamp, path.stat().st_mtime)
    return stamp


def _project_artifact_previews(project_dir: Path) -> list[dict]:
    key = str(project_dir.resolve())
    stamp = _project_artifact_stamp(project_dir)
    with _listing_cache_lock:
        cached = _artifact_preview_cache.get(key)
        if cached and cached[0] == stamp:
            return list(cached[1])
    artifacts = [
        artifact
        for rel_path in GENERATED_FILES
        if (artifact := _artifact_record(project_dir, rel_path)) is not None
    ]
    with _listing_cache_lock:
        _artifact_preview_cache[key] = (stamp, artifacts)
    return artifacts


def _artifact_record(project_dir: Path, rel_path: str) -> dict | None:
    path = project_dir / rel_path
    if not path.exists() or not path.is_file():
        return None
    try:
        preview = path.read_text(encoding="utf-8")[:ARTIFACT_PREVIEW_LIMIT]
    except UnicodeDecodeError:
        preview = ""
    return {
        "path": rel_path,
        "bytes": path.stat().st_size,
        "preview": preview,
    }


def list_projects(output_root: Path | None = None) -> list[dict]:
    if output_root is None:
        output_root = DEFAULT_OUTPUT_ROOT
    cache_key = str(output_root.resolve())
    stamp = _listing_cache_stamp(output_root)
    with _listing_cache_lock:
        cached = _listing_cache.get(f"projects:{cache_key}")
        if cached and cached[0] == stamp:
            return list(cached[1])
    if not output_root.exists():
        return []
    projects = [p for p in _iter_project_dirs(output_root) if (p / "manifest.json").exists()]
    projects.sort(key=lambda p: (_read_json(p / "build_state.json").get("updated_at") or p.stat().st_mtime), reverse=True)
    records = [_project_record(project) for project in projects]
    with _listing_cache_lock:
        _listing_cache[f"projects:{cache_key}"] = (stamp, records)
    return records


def get_project(slug: str, output_root: Path | None = None) -> dict | None:
    if output_root is None:
        output_root = DEFAULT_OUTPUT_ROOT
    project_dir = _safe_project_dir(slug, output_root)
    if project_dir is None:
        return None
    record = _project_record(project_dir)
    manifest = _read_json(project_dir / "manifest.json")
    build_state = _read_json(project_dir / "build_state.json")
    build_mission = _read_json(project_dir / "build_mission.json")
    artifacts = _project_artifact_previews(project_dir)
    return {
        **record,
        "manifest": manifest,
        "build_state": build_state,
        "build_mission": build_mission,
        "history": build_state.get("logs", []),
        "next_actions": build_state.get("next_actions", []),
        "timeline": build_timeline(continuous=record["continuous"]),
        "artifacts": artifacts,
    }


def build_timeline(continuous: bool = False, active_stage: str | None = None) -> list[dict]:
    timeline = []
    for index, (key, title, detail) in enumerate(BUILD_STAGES, start=1):
        if active_stage == key:
            status = "active"
        elif active_stage:
            active_index = [stage[0] for stage in BUILD_STAGES].index(active_stage)
            status = "done" if index - 1 < active_index else "ready"
        else:
            status = "done"
        timeline.append({"index": index, "key": key, "title": title, "detail": detail, "status": status})
    if continuous:
        timeline.append(
            {
                "index": len(timeline) + 1,
                "key": "continuous",
                "title": "24/7 build loop queued",
                "detail": "Kanban/cron workers can keep improving this project while the user is away.",
                "status": "active" if active_stage == "continuous" else "done",
            }
        )
    return timeline


def _build_state(
    project_dir: Path,
    *,
    prompt: str,
    quality: str,
    continuous: bool,
    selected_skill: dict | None = None,
    learning_records: list | None = None,
    learning_records_path: Path | str | None = None,
    capabilities: dict | None = None,
) -> dict:
    manifest = _read_json(project_dir / "manifest.json")
    if selected_skill is None:
        selected_skill = manifest.get("selected_skill") or resolve_playro_skill(None)
    now = int(time.time())
    if learning_records is None:
        learning_records = learning_records_for_build(
            project_id=project_dir.name,
            prompt=prompt,
            project_dir=project_dir,
            systems=manifest.get("systems", []),
            continuous=continuous,
        )
        learning_records_path = write_learning_records(project_dir, learning_records)
    elif learning_records_path is None:
        learning_records_path = write_learning_records(project_dir, learning_records)
    state = {
        "id": project_dir.name,
        "status": "Generated",
        "progress": 100,
        "mode": "24/7 enabled" if continuous else "one-shot",
        "quality": quality,
        "skill": selected_skill,
        "continuous": continuous,
        "created_at": now,
        "updated_at": now,
        "updated_label": "Just now",
        "current_stage": "studio",
        "next_actions": [
            "Open the generated Rojo project in Roblox Studio.",
            "Refine the prompt from the desktop app if gameplay direction changes.",
            "Enable 24/7 mode to keep adding systems, tests, and polish.",
        ],
        "logs": [
            f"Desktop build created for: {prompt}",
            f"Generated {len([f for f in GENERATED_FILES if (project_dir / f).exists()])} Rojo-ready artifacts.",
            "Validated product boundary: Roblox-focused backend surface only.",
        ],
        "systems": manifest.get("systems", []),
    }
    if continuous:
        state["logs"].append("24/7 build mode requested; Kanban/cron can continue improvement passes.")
    state["capabilities"] = capabilities if capabilities is not None else capability_manifest()
    state["controls"] = {"pause_stop": {"enabled": True, "actions": ["pause", "resume", "stop"]}}
    state["learning_records"] = learning_records
    state["learning_records_path"] = str(learning_records_path)
    _write_json(project_dir / "build_state.json", state)
    return state


class RobloxAIStudioHandler(BaseHTTPRequestHandler):
    server_version = "RobloxAIStudioDesktop/0.3"

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib name
        return

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return not origin or origin in _allowed_cors_origins()

    def _set_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if not origin or origin not in _allowed_cors_origins():
            return
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Playro-API-Token")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_forbidden(self) -> None:
        self._send_json(403, {"ok": False, "error": "forbidden"})

    def _request_token(self) -> str:
        header_token = self.headers.get("X-Playro-API-Token", "").strip()
        if header_token:
            return header_token
        parsed_path = urlparse(self.path)
        # EventSource cannot attach custom headers, so allow query-string
        # tokens only for the SSE stream. Normal API routes must not accept
        # token-bearing URLs because they leak through logs, history, and
        # copied links more easily than headers.
        if not (parsed_path.path.startswith("/generate/") and parsed_path.path.endswith("/events")):
            return ""
        query = parse_qs(parsed_path.query)
        return (query.get("api_token") or [""])[0].strip()

    def _is_authorized(self) -> bool:
        # Fail-closed: a missing or empty `PLAYRO_API_TOKEN` denies every
        # protected request. The Electron shell always sets a fresh
        # 32-byte token, so this only affects standalone/dev launches
        # where the operator forgot to set one.
        token = _configured_api_token()
        if not token:
            return False
        request_token = self._request_token()
        try:
            return hmac.compare_digest(request_token.encode("utf-8"), token.encode("utf-8"))
        except (TypeError, UnicodeEncodeError):
            return False

    def _read_payload(self) -> dict:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length < 0 or length > MAX_REQUEST_BODY_BYTES:
            raise ValueError("request body too large")
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
        if not self._origin_allowed():
            self._send_forbidden()
            return
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlparse(self.path).path
        if not self._origin_allowed():
            self._send_forbidden()
            return
        public_paths = {"/health"}
        if path not in public_paths and not self._is_authorized():
            self._send_forbidden()
            return
        if path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "product": "Roblox AI Studio",
                    "backend": "Hermes-Roblox",
                    "mission": "Desktop app first. Product-grade UI. Hermes backend. Roblox creation from prompts.",
                },
            )
            return
        if path == "/desktop/capabilities":
            self._send_json(200, capability_manifest())
            return
        if path == "/desktop/skills":
            manifest = capability_manifest()
            self._send_json(200, {"ok": True, "skill_catalog": manifest["skill_catalog"], "skills": manifest["roblox_skills"]})
            return
        if path == "/backend/surface":
            self._send_json(200, HermesRobloxSession.local().describe_backend())
            return
        if path == "/backend/runtime":
            self._send_json(200, runtime_catalog())
            return
        if path == "/projects":
            self._send_json(200, {"ok": True, "projects": list_projects()})
            return
        if path == "/builds":
            self._send_json(200, {"ok": True, "builds": list_build_jobs()})
            return
        if path == "/desktop/keys":
            self._handle_desktop_keys()
            return
        if path == "/desktop/analytics":
            self._handle_desktop_analytics()
            return
        if path == "/desktop/logs":
            self._handle_desktop_logs()
            return
        if path == "/desktop/crews":
            self._handle_desktop_crews()
            return
        # SSE endpoint: /generate/<build_id>/events
        if path.startswith("/generate/") and path.endswith("/events"):
            self._handle_sse_events(path)
            return
        if path.startswith("/projects/"):
            project = get_project(path.removeprefix("/projects/"))
            if project is None:
                self._send_json(404, {"ok": False, "error": "project not found"})
                return
            self._send_json(200, {"ok": True, "project": project})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlparse(self.path).path
        if not self._origin_allowed() or not self._is_authorized():
            self._send_forbidden()
            return
        try:
            if path == "/generate":
                self._handle_generate()
                return
            if path == "/refine":
                self._handle_refine()
                return
            if path.startswith("/projects/") and path.endswith("/export"):
                self._handle_project_export()
                return
            if path == "/builds/continuous":
                self._handle_continuous_toggle()
                return
            if path == "/builds/tick":
                self._handle_build_tick()
                return
            if path == "/builds/status":
                self._handle_build_status()
                return
            self._send_json(404, {"ok": False, "error": "not found"})
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json"})
        except ValueError as exc:
            self._send_json(413 if "too large" in str(exc) else 400, {"ok": False, "error": str(exc)})

    def _handle_sse_events(self, path: str) -> None:
        """Stream build stage transitions as Server-Sent Events."""
        # Extract build_id from /generate/<build_id>/events
        prefix = "/generate/"
        suffix = "/events"
        if not (path.startswith(prefix) and path.endswith(suffix)):
            self._send_json(400, {"ok": False, "error": "invalid SSE path"})
            return
        build_id = path[len(prefix):-len(suffix)]
        if not is_safe_build_id(build_id):
            self._send_json(400, {"ok": False, "error": "invalid build_id"})
            return
        if not self._origin_allowed() or not self._is_authorized():
            self._send_forbidden()
            return

        # SSE response headers. Auth/origin validation must happen before any
        # 200/SSE headers or event-bus subscription so rejected clients never
        # get an opened stream or a queued subscription.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._set_cors_headers()
        self.end_headers()

        # Subscribe to the event bus for this build. EventSource can connect
        # after the short local generation job already finished, so replay the
        # persisted build_job as a terminal complete frame instead of leaving
        # the renderer waiting until it falls back to preview-only copy.
        event_queue = event_bus.subscribe(build_id)
        try:
            job = get_build_job(build_id)
            if job and job.get("status") in {"completed", "failed"}:
                project_id = project_id_from_path(job.get("project_path"))
                event = BuildEvent(
                    build_id=build_id,
                    stage="complete" if job.get("status") == "completed" else "error",
                    title="Build complete" if job.get("status") == "completed" else "Build failed",
                    detail=f"Build {build_id} finished.",
                    timestamp=time.time(),
                    data={
                        "project_id": project_id,
                        "ok": job.get("status") == "completed",
                        "files": job.get("generated_files") or job.get("files") or [],
                    },
                )
                self.wfile.write(event.to_sse().encode("utf-8"))
                self.wfile.flush()
                return
            stream_deadline = time.time() + max(1, PLAYRO_SSE_MAX_WAIT_SECS)
            while True:
                remaining = stream_deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    event = event_queue.get(timeout=min(15, max(0.1, remaining)))
                except queue.Empty:
                    job = get_build_job(build_id)
                    if job and job.get("status") in {"completed", "failed"}:
                        project_id = project_id_from_path(job.get("project_path"))
                        event = BuildEvent(
                            build_id=build_id,
                            stage="complete" if job.get("status") == "completed" else "error",
                            title="Build complete" if job.get("status") == "completed" else "Build failed",
                            detail=f"Build {build_id} finished.",
                            timestamp=time.time(),
                            data={
                                "project_id": project_id,
                                "ok": job.get("status") == "completed",
                                "files": job.get("generated_files") or job.get("files") or [],
                            },
                        )
                    else:
                        continue
                if event is None:  # sentinel = stream closed
                    break
                # Write the SSE frame
                self.wfile.write(event.to_sse().encode("utf-8"))
                self.wfile.flush()
                # Terminal stages end the stream
                if event.stage in ("complete", "error"):
                    break
        except Exception:
            # Client disconnected or other I/O error — just close
            pass
        finally:
            event_bus.unsubscribe(build_id, event_queue)


    def _handle_generate(self) -> None:
        payload = self._read_payload()
        prompt = str(payload.get("prompt", "")).strip()
        refine = payload.get("refine")
        project_id = str(payload.get("project_id", "")).strip() or None
        project_dir = _safe_project_dir(project_id) if project_id else None
        continuous: bool | None = None
        autonomous: bool | None = None
        quality = str(payload.get("quality") or "High quality")
        if not prompt:
            self._send_json(400, {"ok": False, "error": "prompt is required"})
            return
        if len(prompt) > MAX_PROMPT_CHARS:
            self._send_json(413, {"ok": False, "error": "prompt is too large"})
            return
        if refine is not None and not isinstance(refine, str):
            self._send_json(400, {"ok": False, "error": "refine must be a string"})
            return
        if project_id and project_dir is None:
            self._send_json(404, {"ok": False, "error": "project not found"})
            return
        if "continuous" in payload:
            continuous = bool(payload.get("continuous"))
        else:
            continuous = None
        if "autonomous" in payload:
            autonomous = bool(payload.get("autonomous"))
        else:
            autonomous = None
        with _active_builds_lock:
            _active_builds_copy = dict(_active_builds)
            for current_id, future in _active_builds_copy.items():
                if future.done():
                    _active_builds.pop(current_id, None)
            if len(_active_builds) >= MAX_CONCURRENT_BUILDS:
                self._send_json(429, {"ok": False, "error": "too many active builds"})
                return

        # Pre-allocate a build_id so the frontend can subscribe to SSE
        # before the build pipeline even starts.
        build_id = _new_build_id()

        # Run the actual build in a background thread so the HTTP
        # response returns immediately with the build_id.
        # The frontend then connects to /generate/{build_id}/events
        # to receive real-time stage transitions.
        def _run_build() -> None:
            try:
                create_build_job(
                    prompt,
                    refinement_prompt=refine,
                    project_id=project_id,
                    quality=quality,
                    continuous=continuous,
                    autonomous=autonomous,
                    build_id=build_id,
                    skill_id=str(payload.get("skill_id") or ""),
                )
            except Exception as exc:
                _emit(build_id, "error", "Build failed", str(exc), data={"error": str(exc)})

        future = _build_executor.submit(_run_build)
        with _active_builds_lock:
            _active_builds[build_id] = future
        future.add_done_callback(lambda _future, current_id=build_id: _active_builds.pop(current_id, None))

        self._send_json(200, {
            "ok": True,
            "action": "build_started",
            "build_id": build_id,
            "events_url": f"/generate/{build_id}/events",
            **({"project_id": project_id} if project_id else {}),
        })

    def _handle_refine(self) -> None:
        payload = self._read_payload()
        project_id = str(payload.get("project_id", "")).strip()
        refinement = str(payload.get("refinement", "")).strip()
        quality = str(payload.get("quality") or "High quality")
        if not project_id or not refinement:
            self._send_json(400, {"ok": False, "error": "project_id and refinement are required"})
            return
        if len(refinement) > MAX_PROMPT_CHARS:
            self._send_json(413, {"ok": False, "error": "refinement is too large"})
            return
        project_dir = _safe_project_dir(project_id)
        if project_dir is None:
            self._send_json(404, {"ok": False, "error": "project not found"})
            return
        manifest = _read_json(project_dir / "manifest.json")
        if not manifest:
            self._send_json(404, {"ok": False, "error": "project not found"})
            return
        original_prompt = manifest.get("original_prompt") or project_id.replace("-", " ")
        selected_skill = manifest.get("selected_skill") or resolve_playro_skill(None)
        output, build_state = regenerate_existing_project(
            project_dir,
            original_prompt=original_prompt,
            refinement=refinement,
            quality=quality,
            selected_skill=selected_skill,
        )
        project = _project_record(output)
        self._send_json(
            200,
            {
                "ok": True,
                "project": project,
                "files": project["files"],
                "timeline": build_timeline(continuous=project["continuous"]),
                "build_state": build_state,
            },
        )

    def _handle_continuous_toggle(self) -> None:
        payload = self._read_payload()
        project_id = str(payload.get("project_id", "")).strip()
        enabled = bool(payload.get("enabled"))
        if not project_id:
            self._send_json(400, {"ok": False, "error": "project_id is required"})
            return
        project_dir = _safe_project_dir(project_id)
        if project_dir is None:
            self._send_json(404, {"ok": False, "error": "project not found"})
            return
        state = _read_json(project_dir / "build_state.json") or _build_state(
            project_dir,
            prompt=_read_json(project_dir / "manifest.json").get("original_prompt", project_id),
            quality="High quality",
            continuous=enabled,
        )
        state["continuous"] = enabled
        state["mode"] = "24/7 enabled" if enabled else "one-shot"
        state["updated_at"] = int(time.time())
        state["updated_label"] = "Just now"
        state.setdefault("logs", []).insert(0, "24/7 build mode enabled from desktop app." if enabled else "24/7 build mode paused from desktop app.")
        _write_json(project_dir / "build_state.json", state)
        mission = create_build_mission(
            project_dir,
            prompt=_read_json(project_dir / "manifest.json").get("original_prompt", project_id),
            continuous=enabled,
            autonomous=bool(payload.get("autonomous", enabled)),
        )
        if not enabled:
            mission = set_build_loop_status(project_dir, "paused")
        self._send_json(
            200,
            {
                "ok": True,
                "project": _project_record(project_dir),
                "timeline": build_timeline(continuous=enabled, active_stage="continuous" if enabled else None),
                "build_state": state,
                "build_mission": mission.to_dict(),
                "pause_stop_supported": True,
            },
        )

    def _handle_build_tick(self) -> None:
        payload = self._read_payload()
        project_id = str(payload.get("project_id", "")).strip()
        if not project_id:
            self._send_json(400, {"ok": False, "error": "project_id is required"})
            return
        project_dir = _safe_project_dir(project_id)
        if project_dir is None:
            self._send_json(404, {"ok": False, "error": "project not found"})
            return
        result = run_build_loop_tick(project_dir)
        self._send_json(200, {"ok": True, "tick": asdict(result), "build_mission": load_build_mission(project_dir).to_dict()})

    def _handle_build_status(self) -> None:
        payload = self._read_payload()
        project_id = str(payload.get("project_id", "")).strip()
        status = str(payload.get("status", "")).strip()
        if not project_id or not status:
            self._send_json(400, {"ok": False, "error": "project_id and status are required"})
            return
        project_dir = _safe_project_dir(project_id)
        if project_dir is None:
            self._send_json(404, {"ok": False, "error": "project not found"})
            return
        mission = set_build_loop_status(project_dir, status)
        self._send_json(200, {"ok": True, "build_mission": mission.to_dict()})

    def _handle_project_export(self) -> None:
        """POST /projects/<slug>/export — package a generated project into a zip bundle."""
        from product.roblox_ai_studio.app.export_bundle import export_project

        path = urlparse(self.path).path
        # Extract slug from /projects/<slug>/export
        slug = path.removeprefix("/projects/").removesuffix("/export")
        project_dir = _safe_project_dir(slug)
        if project_dir is None:
            self._send_json(404, {"ok": False, "error": "project not found"})
            return
        try:
            result = export_project(project_dir)
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        except FileNotFoundError as exc:
            self._send_json(404, {"ok": False, "error": str(exc)})
            return
        if not result.get("ok"):
            self._send_json(422, result)
            return
        self._send_json(200, result)

    def _handle_desktop_analytics(self) -> None:
        """GET /desktop/analytics — product-local build analytics (Roblox-focused)."""
        builds = list_build_jobs()
        total = len(builds)
        completed = sum(1 for b in builds if str(b.get("status", "")).lower() in ("completed", "complete", "done"))
        failed = sum(1 for b in builds if re.search(r"fail|error", str(b.get("status", "")), re.I))
        self._send_json(200, {
            "ok": True,
            "total_builds": total,
            "completed_builds": completed,
            "failed_builds": failed,
            "success_rate": round((completed / total) * 100) if total else 0,
        })

    def _handle_desktop_logs(self) -> None:
        """GET /desktop/logs — recent Hermes-backed generation events (last 120 lines)."""
        builds = list_build_jobs()
        logs = []
        for b in builds[-120:]:
            ts = b.get("created_at", b.get("started_at", ""))
            status = str(b.get("status", "completed"))
            name = b.get("name", b.get("id", "Roblox build"))
            genre = b.get("genre", "")
            logs.append(
                {
                    "time": ts,
                    "stage": status,
                    "level": "error" if re.search(r"fail|error", status, re.I) else "info",
                    "message": f"{name} · {genre}".strip(" ·"),
                }
            )
        self._send_json(200, {"ok": True, "logs": logs})

    def _handle_desktop_keys(self) -> None:
        """GET /desktop/keys - product-local engine/adapter setup status (no live Hermes config)."""

        setup = {
            "hermes": "ok" if _resolve_product_command("hermes", "PLAYRO_HERMES_BIN") else "required",
            "rojo": "ok" if _resolve_product_command("rojo", "PLAYRO_ROJO_BIN") else "not found",
            "studio": "unknown",
        }
        # Best-effort: check for RobloxStudioBeta on common Windows paths
        studio_paths = [
            os.path.expandvars(r"%LocalAppData%\Roblox Studio\RobloxStudioBeta.exe"),
            os.path.expandvars(r"%ProgramFiles%\Roblox\Roblox Studio\RobloxStudioBeta.exe"),
        ]
        setup["studio"] = "ok" if any(os.path.isfile(p) for p in studio_paths) else "not found"
        self._send_json(200, {
            "ok": True,
            "hermes": setup["hermes"],
            "studio": setup["studio"],
            "rojo": setup["rojo"],
            "note": "Hermes is the required product-local engine; Playro only exposes the Roblox-first surface.",
        })

    def _handle_desktop_crews(self) -> None:
        """GET /desktop/crews — product-local build personas (no live Hermes profiles)."""
        builds = list_build_jobs()

        def count_for_mode(mode: str) -> int:
            return sum(1 for b in builds if str(b.get("quality", b.get("mode", ""))).lower() == mode)

        crews = [
            {
                "id": "adventurer",
                "label": "Adventurer",
                "description": "Balanced and fast. Great for prototyping and iterating on Roblox games quickly.",
                "quality_mode": "balanced",
                "default_model": "auto",
                "recent_builds": count_for_mode("balanced") + count_for_mode("standard"),
            },
            {
                "id": "architect",
                "label": "Architect",
                "description": "Premium detail. Complex systems, full Luau, rich economies, and polished game loops.",
                "quality_mode": "premium",
                "default_model": "auto",
                "recent_builds": count_for_mode("premium") + count_for_mode("polished"),
            },
            {
                "id": "speedrunner",
                "label": "Speedrunner",
                "description": "Fastest iteration. Lightweight models for quick sketches and concept validation.",
                "quality_mode": "fast",
                "default_model": "auto",
                "recent_builds": count_for_mode("fast") + count_for_mode("quick"),
            },
        ]
        self._send_json(200, {
            "ok": True,
            "crews": crews,
            "active_crew": "adventurer",
            "note": "Crews are product-scoped build personas. They control quality routing, not generic Hermes profiles.",
        })

def _resolve_product_command(command_name: str, env_var: str) -> str | None:
    explicit = os.environ.get(env_var, "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    suffix = ".exe" if os.name == "nt" else ""
    executable = f"{command_name}{suffix}"
    candidates: list[Path] = []
    if command_name == "hermes":
        home = Path(os.environ.get("PLAYRO_HERMES_HOME", "").strip() or Path.home() / ".playro" / "hermes")
        agent_dir = Path(os.environ.get("PLAYRO_HERMES_AGENT_DIR", "").strip() or home / "hermes-agent")
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        candidates.extend([agent_dir / ".venv" / bin_dir / executable, agent_dir / "venv" / bin_dir / executable, home / bin_dir / executable])
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            playro_home = Path(os.environ["LOCALAPPDATA"]) / "playro" / "hermes"
            candidates.append(playro_home / "hermes-agent" / ".venv" / "Scripts" / executable)
    elif command_name == "rojo":
        tools_root = Path(os.environ.get("PLAYRO_TOOLS_DIR", "").strip() or Path.home() / ".playro" / "tools")
        rojo_dir = Path(os.environ.get("PLAYRO_ROJO_DIR", "").strip() or tools_root / "rojo")
        candidates.extend([rojo_dir / executable, rojo_dir / "rojo" / executable])
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(command_name)


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_loopback_api_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _configured_api_host() -> str:
    host = os.environ.get("HERMES_ROBLOX_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if _is_loopback_api_host(host) or _env_truthy(os.environ.get("PLAYRO_ALLOW_REMOTE_API_BIND")):
        return host
    return "127.0.0.1"


class IPv6ThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def _server_class_for_host(host: str) -> type[ThreadingHTTPServer]:
    try:
        if ipaddress.ip_address(host).version == 6:
            return IPv6ThreadingHTTPServer
    except ValueError:
        pass
    return ThreadingHTTPServer


def _configured_api_port() -> int:
    raw_port = os.environ.get("HERMES_ROBLOX_API_PORT", "8765").strip()
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f"HERMES_ROBLOX_API_PORT must be an integer, got {raw_port!r}") from exc
    if port < 1 or port > 65535:
        raise ValueError(f"HERMES_ROBLOX_API_PORT must be between 1 and 65535, got {port}")
    return port


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server_class = _server_class_for_host(host)
    server = server_class((host, port), RobloxAIStudioHandler)
    print(f"Roblox AI Studio desktop API listening on http://{host}:{port}")
    print("POST /generate with JSON: {\"prompt\": \"make an obby\"}")
    if not _configured_api_token():
        # The Electron shell always exports a random `PLAYRO_API_TOKEN`; this
        # only fires for standalone Python launches. With no token, every
        # protected route now returns 403 (see `_is_authorized`).
        print(
            "[security] PLAYRO_API_TOKEN is not set; every non-/health route "
            "will return 403 until a token is exported.",
            file=sys.stderr,
        )
    server.serve_forever()


def main() -> int:
    run(host=_configured_api_host(), port=_configured_api_port())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
