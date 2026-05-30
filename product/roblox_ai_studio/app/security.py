"""Security helpers for the product-local Playro desktop API."""

from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
BUILD_ID_PATTERN = re.compile(r"^build_(?=.*[A-Z_-])[A-Za-z0-9_-]{16,64}$")


def configured_api_token() -> str:
    return os.environ.get("PLAYRO_API_TOKEN", "").strip()


def allowed_cors_origins() -> set[str]:
    """Return explicit origins allowed to talk to the local desktop API.

    We intentionally do not allow `null` by default. Electron renderer requests
    originate from file:// and authenticate with X-Playro-API-Token; allowing a
    browser null-origin document would make local project reads easier to abuse.
    """

    configured = os.environ.get("PLAYRO_ALLOWED_ORIGINS")
    if configured:
        return {origin.strip() for origin in configured.split(",") if origin.strip()}
    return {"file://", "app://playro", "http://localhost:8765", "http://127.0.0.1:8765"}


def is_safe_project_id(project_id: str | None) -> bool:
    return bool(project_id and PROJECT_ID_PATTERN.fullmatch(project_id.strip()))


def is_safe_build_id(build_id: str | None) -> bool:
    return bool(build_id and BUILD_ID_PATTERN.fullmatch(build_id.strip()))


def safe_project_dir(project_id: str | None, output_root: Path) -> Path | None:
    if not is_safe_project_id(project_id):
        return None
    try:
        output_root_resolved = output_root.resolve(strict=True)
    except OSError:
        return None
    if not output_root_resolved.is_absolute() or not output_root_resolved.is_dir():
        return None
    try:
        project_dir = (output_root_resolved / str(project_id).strip()).resolve(strict=True)
        project_dir.relative_to(output_root_resolved)
    except (OSError, ValueError):
        return None
    manifest_path = project_dir / "manifest.json"
    try:
        if not project_dir.is_dir() or not manifest_path.is_file():
            return None
    except OSError:
        return None
    return project_dir


PLAYRO_LUA_SCAN_DIRS: tuple[str, ...] = (
    "src/ReplicatedStorage",
    "src/ServerScriptService",
    "src/StarterPlayer/StarterPlayerScripts",
)


def unexpected_lua_artifacts(project_dir: Path, *, allowed: set[str]) -> list[str]:
    """Return relative paths of .lua files under Rojo-mapped dirs outside the allowlist."""

    unexpected: list[str] = []
    for scan_dir in PLAYRO_LUA_SCAN_DIRS:
        root = project_dir / scan_dir
        if not root.is_dir():
            continue
        for path in root.rglob("*.lua"):
            if not path.is_file():
                continue
            rel = path.relative_to(project_dir).as_posix()
            if rel not in allowed:
                unexpected.append(rel)
    return sorted(unexpected)
