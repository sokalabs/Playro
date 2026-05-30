"""Roblox-focused Hermes capability and learning model.

The desktop app should show why Hermes is useful without becoming a generic
Hermes admin panel. This module keeps the surface product-local: skills,
self-learning, memory, orchestration, build jobs, 24/7 mode, pause/stop,
provider routing, and generated files are described only in terms of Roblox
creation workflows.
"""

from __future__ import annotations

import json
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .skill_catalog import native_playro_skill_templates, playro_skill_catalog, skill_catalog_summary
from .tool_surface import DEFAULT_TOOL_SURFACE


CAPABILITY_ORDER = (
    "skills",
    "self_learning",
    "memory",
    "sessions",
    "build_jobs",
    "continuous_24_7_mode",
    "pause_stop",
    "generated_files",
    "provider_routing",
    "orchestration",
)


QUALITY_MODES = [
    {"id": "fast_draft", "label": "Fast draft", "description": "Quick starter project with simple systems."},
    {"id": "balanced", "label": "Balanced", "description": "Good default for playable prototypes."},
    {"id": "high_quality", "label": "High quality", "description": "Deeper planning, more validation, and better polish."},
]

# Curated skill + speed combos for the desktop build-options flow (not genre templates).
PLAYRO_SKILL_PACKS: list[dict[str, Any]] = [
    {
        "id": "first-build",
        "label": "First build",
        "description": "Best default for any new game idea: plan the loop, then generate a playable prototype.",
        "skill_id": "playro-game-designer",
        "quality_mode": "balanced",
        "default": True,
    },
    {
        "id": "quick-start",
        "label": "Quick start",
        "description": "Fast draft when you want something playable sooner with lighter systems.",
        "skill_id": "playro-game-designer",
        "quality_mode": "fast_draft",
        "default": False,
    },
    {
        "id": "polished",
        "label": "Polished prototype",
        "description": "More planning, validation, and polish before files are written.",
        "skill_id": "playro-game-designer",
        "quality_mode": "high_quality",
        "default": False,
    },
    {
        "id": "big-systems",
        "label": "Systems focus",
        "description": "Economies, quests, combat, pets, rounds, inventory, and progression systems.",
        "skill_id": "playro-systems-builder",
        "quality_mode": "balanced",
        "default": False,
    },
    {
        "id": "worlds",
        "label": "World focus",
        "description": "Hubs, arenas, maps, NPC spaces, vehicles, pads, and themed layouts.",
        "skill_id": "playro-world-builder",
        "quality_mode": "balanced",
        "default": False,
    },
    {
        "id": "scripts",
        "label": "Luau focus",
        "description": "Server, client, and shared scripts for custom mechanics from your prompt.",
        "skill_id": "playro-luau-coder",
        "quality_mode": "balanced",
        "default": False,
    },
    {
        "id": "fix-build",
        "label": "Fix & validate",
        "description": "Check generated scripts for broken references, unsafe remotes, and mechanic gaps.",
        "skill_id": "playro-playtest-fixer",
        "quality_mode": "balanced",
        "default": False,
    },
]


def playro_skill_packs() -> list[dict[str, Any]]:
    return [dict(pack) for pack in PLAYRO_SKILL_PACKS]


def default_playro_skill_pack() -> dict[str, Any]:
    for pack in PLAYRO_SKILL_PACKS:
        if pack.get("default"):
            return dict(pack)
    return dict(PLAYRO_SKILL_PACKS[0])


HERMES_PARITY_SURFACES = [
    {
        "id": "sessions",
        "label": "Build history",
        "hermes_source": "sessions",
        "playro_surface": "Every prompt, refinement, generated project, timeline, artifacts, and next action.",
        "status": "prototype",
        "rows": [
            ["History shape", "Prompt, selected skill, quality mode, generated files, timeline, and resume actions"],
            ["Storage", "Product-local project records, not generic chat transcripts"],
            ["Creator action", "Resume, refine, export, or open the generated Roblox project"],
        ],
    },
    {
        "id": "analytics",
        "label": "Build analytics",
        "hermes_source": "analytics",
        "playro_surface": "Success rate, validation failures, common Luau errors, build time, systems generated, and playtest readiness.",
        "status": "planned",
        "rows": [
            ["Validation focus", "Rojo files, Luau references, economy balance, Studio handoff"],
            ["Quality signal", "Gameplay mechanic coverage and generated artifact completeness"],
            ["Next metric", "Luau error frequency and repair success rate"],
        ],
    },
    {
        "id": "models",
        "label": "Quality routing",
        "hermes_source": "models/providers",
        "playro_surface": "Fast Draft, Balanced, and High Quality modes backed by product-local provider routing.",
        "status": "prototype",
        "rows": [
            ["Fast draft", "Cheap/fast starter scaffold"],
            ["Balanced", "Good default for playable Roblox prototypes"],
            ["High quality", "Deeper planning, validation, and polish"],
        ],
    },
    {
        "id": "logs",
        "label": "Build logs",
        "hermes_source": "logs",
        "playro_surface": "Human-readable Roblox build logs for planning, generation, validation, packaging, and handoff.",
        "status": "prototype",
        "rows": [
            ["Visible stages", "Plan -> Generate -> Validate -> Package"],
            ["Export target", "Shareable failure bundle for support or rebuild"],
            ["Boundary", "No machine administration logs exposed"],
        ],
    },
    {
        "id": "build24",
        "label": "24/7 builder",
        "hermes_source": "cron/background jobs",
        "playro_surface": "Bounded background improvement loops with pause, resume, stop, and review controls.",
        "status": "prototype",
        "rows": [
            ["Loop", "Read mission -> choose one improvement -> patch/generate -> validate -> record"],
            ["Controls", "Enable, pause, resume, stop, and review"],
            ["Safety", "Bounded ticks and product-local generated-file diffs"],
        ],
    },
    {
        "id": "skills",
        "label": "Roblox skills",
        "hermes_source": "skills",
        "playro_surface": "Game design, Luau coding, world building, systems generation, Rojo packaging, and playtest triage.",
        "status": "prototype",
        "rows": [
            ["Skill scope", "Reusable Roblox workflows, not the user's global skill library"],
            ["Promotion", "High-confidence learning records can later become native Hermes skills"],
            ["Selection", "Creator chooses a skill before generation"],
        ],
    },
    {
        "id": "plugins",
        "label": "Roblox adapters",
        "hermes_source": "plugins/MCP",
        "playro_surface": "Roblox-only adapters such as Rojo, Roblox Studio, Open Cloud, rbxmk, asset helpers, and marketplace import tools.",
        "status": "planned/prototype",
        "rows": [
            ["Rojo", "Sync generated project files into Studio"],
            ["Studio", "Open/test handoff guidance"],
            ["Open Cloud", "Opt-in publishing and universe operations later"],
        ],
    },
    {
        "id": "crews",
        "label": "Builder crews",
        "hermes_source": "profiles / multi agents",
        "playro_surface": "Specialist Roblox builders: planner, Luau scripter, UI builder, economy balancer, validator, and packager.",
        "status": "planned",
        "rows": [
            ["Planner", "Turns prompts into game structure"],
            ["Luau scripter", "Writes server/client/shared code"],
            ["Validator", "Checks artifacts, economy, and handoff"],
        ],
    },
    {
        "id": "config",
        "label": "Setup",
        "hermes_source": "config",
        "playro_surface": "Safe product settings for output folders, Studio/Rojo paths, runtime setup, and quality defaults.",
        "status": "prototype",
        "rows": [
            ["Runtime", "Bundled Playro service plus required product-local Hermes engine"],
            ["Creator tools", "Roblox Studio and Rojo checks"],
            ["Boundary", "No live Hermes config import"],
        ],
    },
    {
        "id": "keys",
        "label": "Keys and accounts",
        "hermes_source": "keys/auth",
        "playro_surface": "Product-local provider keys/OAuth and Roblox Open Cloud keys, all redacted and scoped to Playro.",
        "status": "planned",
        "rows": [
            ["Provider keys", "Used for higher-quality generation modes"],
            ["Roblox Open Cloud", "Opt-in future publish/import workflows"],
            ["Storage rule", "Product-local and redacted"],
        ],
    },
    {
        "id": "docs",
        "label": "Documentation",
        "hermes_source": "documentation",
        "playro_surface": "In-app Roblox docs for first project, Rojo setup, Studio testing, generated files, and troubleshooting.",
        "status": "prototype",
        "rows": [
            ["First build", "Prompt -> files -> Rojo -> Studio"],
            ["Generated files", "default.project.json, Luau scripts, manifest, README"],
            ["Troubleshooting", "Rojo missing, Studio plugin, Luau repair patterns"],
        ],
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def capability_manifest() -> dict[str, Any]:
    """Return the product capability shape consumed by the desktop app."""

    capabilities: dict[str, dict[str, Any]] = {
        "skills": {
            "surface_label": "Roblox build skills",
            "status": "prototype",
            "desktop_panel": "Skills",
            "description": "Reusable Roblox game design, Luau coding, world building, systems generation, Rojo packaging, and repair workflows surfaced as creator-friendly builder roles.",
            "roblox_examples": ["detective city planner", "survival systems builder", "vehicle loop coder", "Rojo package validator"],
            "future_target": "hermes_skill",
        },
        "self_learning": {
            "surface_label": "Self-learning build notes",
            "status": "prototype-local",
            "desktop_panel": "Skills",
            "description": "Each successful Roblox build records prompt patterns, generated systems, artifact checks, and improvement opportunities before promotion to native Hermes skills or memory.",
            "future_target": "hermes_skill",
        },
        "memory": {
            "surface_label": "Holographic project memory",
            "status": "prototype-local",
            "desktop_panel": "Projects",
            "description": "Uses a Playro-scoped holographic/fact graph by default for Roblox project preferences, iteration notes, generated systems, and creator decisions; falls back to classic Hermes memory when the fact graph is unavailable.",
            "default_mode": "holographic",
            "fallback_mode": "classic_hermes_memory",
            "future_target": "hermes_memory",
        },
        "sessions": {
            "surface_label": "Build sessions",
            "status": "prototype-local",
            "desktop_panel": "Projects",
            "description": "Adapts Hermes Desktop session history into Roblox build history: prompt, refinement, generated files, timeline, and next actions per project.",
            "future_target": "hermes_sessions",
        },
        "build_jobs": {
            "surface_label": "Build jobs",
            "status": "prototype",
            "desktop_panel": "Builds",
            "description": "Roblox prompt-to-project work appears as build jobs with visible stages, logs, artifacts, and next actions.",
            "states": ["queued", "planning", "generating", "validating", "ready", "paused", "stopped"],
        },
        "continuous_24_7_mode": {
            "surface_label": "24/7 Roblox builder",
            "status": "prototype",
            "desktop_panel": "Builds",
            "description": "Optional bounded autonomy can keep improving Roblox projects with future Kanban/cron passes while creators are away.",
            "requires_user_opt_in": True,
        },
        "pause_stop": {
            "surface_label": "Pause / stop autonomy",
            "status": "prototype",
            "desktop_panel": "Builds",
            "description": "Creator controls for pausing or stopping local background build loops before they mutate Roblox artifacts.",
            "controls": ["pause", "resume", "stop"],
        },
        "generated_files": {
            "surface_label": "Generated Roblox files",
            "status": "live",
            "desktop_panel": "Inspector",
            "description": "Shows Rojo-ready manifests, Luau scripts, game plans, README files, build state, and learning records produced for each Roblox project.",
            "artifact_types": ["Rojo project", "Luau server script", "Luau client script", "shared config", "game plan", "learning records"],
        },
        "provider_routing": {
            "surface_label": "Quality routing",
            "status": "planned/prototype",
            "desktop_panel": "Settings",
            "description": "Routes Roblox generation jobs across approved model/provider accounts by quality mode without exposing a generic proxy dashboard.",
            "modes": ["fast draft", "balanced", "high quality"],
        },
        "orchestration": {
            "surface_label": "Hermes orchestration",
            "status": "prototype",
            "desktop_panel": "Builds",
            "description": "Uses Hermes-style staged execution, future Kanban handoffs, and background workers for Roblox-focused generation and repair loops.",
        },
    }

    return {
        "ok": True,
        "product": "Roblox AI Studio",
        "scope": "roblox_creation",
        "foundation": "Hermes Agent runtime concepts, productized behind Roblox workflows",
        "capability_order": list(CAPABILITY_ORDER),
        "capabilities": capabilities,
        "roblox_skills": playro_skill_catalog(),
        "native_roblox_skill_templates": native_playro_skill_templates(),
        "skill_catalog": skill_catalog_summary(),
        "skill_packs": playro_skill_packs(),
        "default_skill_pack": default_playro_skill_pack()["id"],
        "quality_modes": QUALITY_MODES,
        "desktop_adaptations": {
            "from_hermes_desktop": ["skills", "memory", "sessions", "provider setup", "scheduled/background jobs"],
            "playro_mapping": "All adapted features are exposed as Roblox build workflows instead of a generic Hermes admin shell.",
        },
        "memory_policy": {
            "default": "holographic",
            "toolset": "fact_store",
            "fallback": "classic_hermes_memory",
            "scope": "product-local Playro/Roblox facts only",
            "does_not_import_live_hermes_memory": True,
        },
        "hermes_parity_surfaces": HERMES_PARITY_SURFACES,
        "sidebar_nav": [
            {"id": item["id"], "label": item["label"], "status": item["status"]}
            for item in HERMES_PARITY_SURFACES
        ],
        "tool_surface": DEFAULT_TOOL_SURFACE.desktop_manifest(),
        "boundaries": {
            "does_not_import_live_hermes_config": True,
            "does_not_expose_generic_admin_ui": True,
        },
        "created_at": _now_iso(),
    }


def learning_records_for_build(
    *,
    project_id: str,
    prompt: str,
    project_dir: Path,
    systems: Iterable[str] = (),
    continuous: bool = False,
) -> list[dict[str, Any]]:
    """Create product-local learning records for a Roblox build."""

    now = _now_iso()
    safe_systems = [str(system) for system in systems if str(system).strip()]
    files = [str(path.relative_to(project_dir)) for path in sorted(project_dir.rglob("*")) if path.is_file()]
    records: list[dict[str, Any]] = [
        {
            "id": f"{project_id}:prompt-pattern",
            "scope": "product-local",
            "category": "prompt_pattern",
            "title": "Roblox prompt interpretation pattern",
            "summary": f"Roblox build prompt captured for reuse: {prompt[:140]}",
            "source": "build",
            "project_id": project_id,
            "evidence": {"prompt": prompt},
            "future_target": "hermes_memory",
            "created_at": now,
        },
        {
            "id": f"{project_id}:system-patterns",
            "scope": "product-local",
            "category": "system_pattern",
            "title": "Roblox gameplay system pattern",
            "summary": "Roblox systems generated: " + (", ".join(safe_systems[:6]) if safe_systems else "starter gameplay loop"),
            "source": "build",
            "project_id": project_id,
            "evidence": {"systems": safe_systems},
            "future_target": "hermes_skill",
            "created_at": now,
        },
        {
            "id": f"{project_id}:artifact-pattern",
            "scope": "product-local",
            "category": "artifact_pattern",
            "title": "Rojo artifact checklist",
            "summary": f"Rojo-ready Roblox artifact set recorded with {len(files)} generated files.",
            "source": "build",
            "project_id": project_id,
            "evidence": {"files": files},
            "future_target": "hermes_skill",
            "created_at": now,
        },
    ]
    if continuous:
        records.append(
            {
                "id": f"{project_id}:autonomy-pattern",
                "scope": "product-local",
                "category": "autonomy_pattern",
                "title": "24/7 Roblox improvement path",
                "summary": "Roblox continuous build requested; future workers should plan bounded polish, validation, and generated-file diffs.",
                "source": "build",
                "project_id": project_id,
                "evidence": {"continuous": True},
                "future_target": "hermes_skill",
                "created_at": now,
            }
        )
    return records


def write_learning_records(project_dir: Path, records: list[dict[str, Any]]) -> Path:
    """Persist product-local learning records next to generated Roblox files."""

    path = project_dir / "learning_records.json"
    path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    return path
