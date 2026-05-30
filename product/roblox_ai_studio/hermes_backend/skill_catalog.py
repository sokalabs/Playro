"""Product-local skill catalog for Playro.

This bridges the restored Hermes `skills/` and `optional-skills/` directories into
Playro's Roblox-focused backend surface. The files are shipped with the repo,
but this module controls what the desktop app and API expose.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - PyYAML is normally present in Hermes envs
    yaml = None  # type: ignore[assignment]


PLAYRO_NATIVE_SKILLS: list[dict[str, Any]] = [
    {
        "id": "playro-game-designer",
        "name": "Game Designer",
        "stage": "Plan",
        "description": "Turn any Roblox idea into a core loop, mechanics, progression, world plan, and build steps.",
        "bucket": "core",
        "source": "playro_native",
        "path": "product/roblox_ai_studio/hermes_backend/skill_catalog.py",
        "usable": True,
    },
    {
        "id": "playro-luau-coder",
        "name": "Luau Coder",
        "stage": "Generate",
        "description": "Generate and repair server, client, and shared Luau scripts for custom Roblox mechanics.",
        "bucket": "core",
        "source": "playro_native",
        "path": "product/roblox_ai_studio/hermes_backend/skill_catalog.py",
        "usable": True,
    },
    {
        "id": "playro-world-builder",
        "name": "World Builder",
        "stage": "Generate",
        "description": "Create prototype worlds, hubs, arenas, NPC spaces, vehicles, pads, and themed layouts.",
        "bucket": "core",
        "source": "playro_native",
        "path": "product/roblox_ai_studio/hermes_backend/skill_catalog.py",
        "usable": True,
    },
    {
        "id": "playro-systems-builder",
        "name": "Systems Builder",
        "stage": "Generate",
        "description": "Build economies, quests, combat, reputation, pets, rounds, teams, inventory, and progression systems.",
        "bucket": "core",
        "source": "playro_native",
        "path": "product/roblox_ai_studio/hermes_backend/skill_catalog.py",
        "usable": True,
    },
    {
        "id": "playro-playtest-fixer",
        "name": "Playtest Fixer",
        "stage": "Validate",
        "description": "Check generated scripts for broken config references, unsafe remotes, missing services, and mechanic gaps.",
        "bucket": "toolbox",
        "source": "playro_native",
        "path": "product/roblox_ai_studio/hermes_backend/skill_catalog.py",
        "usable": True,
    },
    {
        "id": "playro-rojo-packager",
        "name": "Rojo Packager",
        "stage": "Package",
        "description": "Create default.project.json, service folders, handoff docs, and Roblox Studio sync instructions.",
        "bucket": "toolbox",
        "source": "playro_native",
        "path": "product/roblox_ai_studio/hermes_backend/skill_catalog.py",
        "usable": True,
    },
]


@lru_cache(maxsize=1)
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def manifest_path() -> Path:
    return repo_root() / "product" / "roblox_ai_studio" / "config" / "playro_skill_manifest.json"


@lru_cache(maxsize=1)
def load_skill_manifest() -> dict[str, Any]:
    try:
        return json.loads(manifest_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "default_enabled_buckets": ["core", "toolbox"],
            "available_buckets": {},
            "counts": {},
            "restored_skills": [],
            "excluded_skills": [],
        }


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    match = re.search(r"\n---\s*\n", text[3:])
    if not match:
        return {}
    frontmatter = text[3 : match.start() + 3]
    if yaml is not None:
        try:
            parsed = yaml.safe_load(frontmatter)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    result: dict[str, Any] = {}
    for line in frontmatter.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip('"\'')
    return result


def _short_description(description: str, limit: int = 180) -> str:
    clean = " ".join(str(description or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def _stage_for_skill(path: str, name: str, description: str) -> str:
    text = f"{path} {name} {description}".lower()
    if "roblox" in text or "luau" in text or "gaming" in text:
        return "Roblox"
    if "creative" in text or "media" in text or "image" in text or "video" in text or "music" in text:
        return "Assets"
    if "github" in text or "debug" in text or "test" in text or "code" in text or "dev" in text:
        return "Build"
    if "memory" in text or "honcho" in text or "obsidian" in text or "note" in text:
        return "Memory"
    if "mcp" in text or "plugin" in text or "adapter" in text or "api" in text:
        return "Adapter"
    if "research" in text or "search" in text or "scrap" in text or "arxiv" in text:
        return "Research"
    return "Toolbox"


def _load_restored_skill(entry: dict[str, Any]) -> dict[str, Any] | None:
    rel = str(entry.get("path") or "").strip()
    if not rel:
        return None
    skill_file = repo_root() / rel / "SKILL.md"
    if not skill_file.exists():
        return None
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return None
    frontmatter = _parse_frontmatter(text)
    name = str(frontmatter.get("name") or skill_file.parent.name)
    description = str(frontmatter.get("description") or "Reusable Hermes skill available to Playro builders.")
    bucket = str(entry.get("bucket") or "toolbox")
    return {
        "id": name,
        "name": name.replace("-", " ").title(),
        "stage": _stage_for_skill(rel, name, description),
        "description": _short_description(description),
        "bucket": bucket,
        "source": "hermes_skill",
        "path": rel,
        "usable": bucket in set(load_skill_manifest().get("default_enabled_buckets", ["core", "toolbox"])),
    }


@lru_cache(maxsize=1)
def restored_hermes_skills() -> tuple[dict[str, Any], ...]:
    manifest = load_skill_manifest()
    skills: list[dict[str, Any]] = []
    for entry in manifest.get("restored_skills", []):
        if isinstance(entry, dict):
            skill = _load_restored_skill(entry)
            if skill:
                skills.append(skill)
    return tuple(skills)


def native_playro_skill_templates() -> list[dict[str, Any]]:
    """Return the native Playro skills in the legacy capability shape."""

    return [
        {
            "id": skill["id"],
            "name": skill["name"],
            "stage": "Handoff" if skill["id"] == "playro-rojo-packager" else skill["stage"],
            "description": (
                "Check default.project.json, generated folders, README, and Studio sync instructions."
                if skill["id"] == "playro-rojo-packager"
                else skill["description"]
            ),
            "future_target": "hermes_skill",
        }
        for skill in PLAYRO_NATIVE_SKILLS
    ]


@lru_cache(maxsize=2)
def playro_skill_catalog(*, include_conditional: bool = False) -> tuple[dict[str, Any], ...]:
    """Return user-facing Playro skills, including restored Hermes toolbox skills."""

    manifest = load_skill_manifest()
    enabled_buckets = set(manifest.get("default_enabled_buckets", ["core", "toolbox"]))
    if include_conditional:
        enabled_buckets.add("conditional")
    native = tuple(dict(skill) for skill in PLAYRO_NATIVE_SKILLS)
    restored = [dict(skill) for skill in restored_hermes_skills() if skill["bucket"] in enabled_buckets]
    # Keep native Playro skills in deliberate product order, then sort restored skills.
    bucket_order = {"core": 0, "toolbox": 1, "conditional": 2}
    restored = sorted(restored, key=lambda item: (bucket_order.get(str(item.get("bucket")), 9), str(item.get("name"))))
    return native + tuple(restored)


def resolve_playro_skill(skill_id: str | None) -> dict[str, Any]:
    requested = (skill_id or "").strip()
    catalog = playro_skill_catalog(include_conditional=True)
    for skill in catalog:
        if skill["id"] == requested or skill["path"] == requested:
            return dict(skill)
    return dict(catalog[0])


def skill_catalog_summary() -> dict[str, Any]:
    manifest = load_skill_manifest()
    all_restored = restored_hermes_skills()
    visible = playro_skill_catalog(include_conditional=False)
    conditional = [skill for skill in all_restored if skill.get("bucket") == "conditional"]
    return {
        "manifest_policy": manifest.get("policy"),
        "default_enabled_buckets": manifest.get("default_enabled_buckets", ["core", "toolbox"]),
        "available_buckets": manifest.get("available_buckets", {}),
        "counts": {
            "native": len(PLAYRO_NATIVE_SKILLS),
            "restored": len(all_restored),
            "visible": len(visible),
            "conditional_hidden": len(conditional),
            "excluded": len(manifest.get("excluded_skills", [])),
        },
        "conditional_skills": conditional,
        "excluded_skills": manifest.get("excluded_skills", []),
    }
