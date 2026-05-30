"""Shared Playro test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from product.roblox_ai_studio.app.artifacts import PLAYRO_CORE_ARTIFACT_FILES


def write_generated_project(
    root: Path,
    slug: str,
    *,
    prompt: str,
    title: str = "Test Obby",
    build_state: dict | None = None,
    include_metadata: bool = True,
) -> Path:
    """Create a minimal generated project tree with canonical artifact paths."""

    project_dir = root / slug
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "src/ServerScriptService/Services").mkdir(parents=True, exist_ok=True)
    (project_dir / "src/ReplicatedStorage").mkdir(parents=True, exist_ok=True)
    (project_dir / "src/StarterPlayer/StarterPlayerScripts").mkdir(parents=True, exist_ok=True)

    (project_dir / "manifest.json").write_text(
        json.dumps(
            {
                "title": title,
                "slug": slug,
                "genre": "Obstacle Course / Obby",
                "systems": ["coin collection economy"],
                "original_prompt": prompt,
                "rojo_project_file": "default.project.json",
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "default.project.json").write_text("{}", encoding="utf-8")

    if include_metadata:
        (project_dir / "README.md").write_text("# Test Obby\nReady.", encoding="utf-8")
        (project_dir / "game_plan.md").write_text("# Plan\nCollect coins.", encoding="utf-8")
        (project_dir / "wally.toml").write_text(
            '[package]\nname = "playro/test"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )

    (project_dir / "src/ReplicatedStorage/GameConfig.lua").write_text("return {}\n", encoding="utf-8")
    (project_dir / "src/ServerScriptService/Main.server.lua").write_text("print('hello')", encoding="utf-8")
    for service_name in ["PlayerDataService", "RewardService", "WorldService"]:
        (project_dir / "src/ServerScriptService/Services" / f"{service_name}.lua").write_text(
            "local Service = {}\nfunction Service.Start() end\nreturn Service\n",
            encoding="utf-8",
        )
    (project_dir / "src/StarterPlayer/StarterPlayerScripts/HUD.client.lua").write_text(
        "-- client hud\n",
        encoding="utf-8",
    )

    for rel_path in PLAYRO_CORE_ARTIFACT_FILES:
        (project_dir / rel_path).parent.mkdir(parents=True, exist_ok=True)

    if build_state is not None:
        (project_dir / "build_state.json").write_text(json.dumps(build_state), encoding="utf-8")

    return project_dir
