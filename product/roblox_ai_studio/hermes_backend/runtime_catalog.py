"""Product-facing runtime catalog for restored Hermes runtime support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RUNTIME_GROUPS: dict[str, str] = {
    "agent": "Hermes agent runtime: prompt building, memory, skill injection, model routing, compression, and safety.",
    "tools": "Tool implementations available to Playro agents through product allowlists.",
    "gateway": "Messaging/API gateway runtime for phone and web access such as Discord, Telegram, webhooks, and API server.",
    "cron": "Scheduled/background build loops for 24/7 project improvement.",
    "providers": "Provider abstractions for model/account routing.",
    "hermes_cli": "CLI support layer for setup, skills, tools, profiles, gateway, and jobs.",
}


EXCLUDED_RUNTIME_PATHS: tuple[str, ...] = (
    "skills/red-teaming/godmode",
    "skills/mlops/inference/obliteratus",
    "optional-skills/blockchain",
    "optional-skills/finance",
    "optional-skills/security/sherlock",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _count_files(path: Path) -> int:
    if path.is_file():
        return 1
    if not path.is_dir():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts)


def runtime_catalog() -> dict[str, Any]:
    root = repo_root()
    groups = []
    for name, description in RUNTIME_GROUPS.items():
        path = root / name
        groups.append(
            {
                "id": name,
                "path": name,
                "description": description,
                "available": path.exists(),
                "file_count": _count_files(path),
            }
        )

    root_files = [
        "run_agent.py",
        "model_tools.py",
        "toolsets.py",
        "toolset_distributions.py",
        "hermes_constants.py",
        "hermes_state.py",
        "hermes_time.py",
        "hermes_logging.py",
        "hermes_bootstrap.py",
        "utils.py",
        "cli.py",
        "batch_runner.py",
    ]
    return {
        "ok": True,
        "policy": "Restored Hermes runtime support is available to Playro through product-facing allowlists; inherited plugin backends are not shipped in the public tree.",
        "groups": groups,
        "root_runtime_files": [
            {"path": file, "available": (root / file).exists()} for file in root_files
        ],
        "phone_access": {
            "enabled_by_runtime": (root / "gateway").exists(),
            "surfaces": ["api_server", "discord", "telegram", "webhook"],
            "note": "Gateway runtime is restored so mobile/phone build flows can be productized instead of requiring the desktop UI only.",
        },
        "background_builds": {
            "enabled_by_runtime": (root / "cron").exists(),
            "note": "Cron/runtime files are restored for opt-in 24/7 project improvement loops.",
        },
        "excluded_runtime_paths": list(EXCLUDED_RUNTIME_PATHS),
    }


def runtime_catalog_json() -> str:
    return json.dumps(runtime_catalog(), indent=2, sort_keys=True)
