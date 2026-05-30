"""Canonical paths for Playro-generated Roblox project artifacts."""

from __future__ import annotations

# Rojo mapping, Luau scripts, and handoff docs required for smoke, export, and API validation.
PLAYRO_CORE_ARTIFACT_FILES: tuple[str, ...] = (
    "default.project.json",
    "manifest.json",
    "game_plan.md",
    "README.md",
    "wally.toml",
    "src/ReplicatedStorage/GameConfig.lua",
    "src/ServerScriptService/Main.server.lua",
    "src/ServerScriptService/Services/PlayerDataService.lua",
    "src/ServerScriptService/Services/RewardService.lua",
    "src/ServerScriptService/Services/WorldService.lua",
    "src/StarterPlayer/StarterPlayerScripts/HUD.client.lua",
)

# Sprint sample batch checks omit game_plan.md; gameplay validation covers plan content separately.
PLAYRO_SAMPLE_VALIDATION_FILES: tuple[str, ...] = tuple(
    path for path in PLAYRO_CORE_ARTIFACT_FILES if path != "game_plan.md"
)

PLAYRO_BUILD_METADATA_FILES: tuple[str, ...] = (
    "build_state.json",
    "build_job.json",
    "build_mission.json",
    "learning_records.json",
)

GENERATED_FILES: list[str] = [
    *PLAYRO_CORE_ARTIFACT_FILES,
    *PLAYRO_BUILD_METADATA_FILES,
]

SMOKE_REQUIRED_FILES: list[str] = list(PLAYRO_CORE_ARTIFACT_FILES)
REQUIRED_EXPORT_FILES: list[str] = list(PLAYRO_CORE_ARTIFACT_FILES)
