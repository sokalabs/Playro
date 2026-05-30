"""Product session facade for the Hermes-Roblox prototype.

This is a thin product-level boundary around Hermes concepts. It gives the
prototype a clean Roblox-focused backend surface without importing live personal
Hermes runtime config, plugins, MCP servers, or tool registries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .tool_surface import DEFAULT_TOOL_SURFACE, ProductToolSurface


@dataclass
class HermesRobloxSession:
    """Minimal Hermes-backed product session state for a generation run."""

    project_root: Path
    tool_surface: ProductToolSurface = DEFAULT_TOOL_SURFACE
    memory: dict[str, Any] = field(default_factory=dict)
    learned_skills: list[dict[str, str]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def local(cls, project_root: Path | None = None) -> "HermesRobloxSession":
        if project_root is None:
            project_root = Path(__file__).resolve().parents[3]
        return cls(project_root=project_root)

    def describe_backend(self) -> dict[str, Any]:
        return {
            "foundation": "Hermes Agent codebase/runtime concepts",
            "product": "Playro",
            "desktop_app_role": "Backend builder/orchestrator for a Codex-like Roblox creation app",
            "tool_surface": self.tool_surface.desktop_manifest(),
            "self_learning": {
                "status": "prototype-local",
                "description": "Successful build/repair patterns can become Roblox-focused product skills before binding to Hermes native skill management.",
                "skill_store": "product/roblox_ai_studio/skills/",
            },
            "memory": {
                "status": "prototype-local facade",
                "description": "Stores build preferences and iteration notes without importing live Hermes memory/config.",
            },
            "continuous_builds": {
                "status": "planned/prototype",
                "description": "24/7 build mode should run bounded Kanban/cron build loops with pause/stop controls.",
            },
            "created_at": self.created_at,
        }

    def export_config(self) -> dict[str, str]:
        """Return product-local runtime config for batch/smoke tooling.

        This intentionally exposes only Playro-scoped defaults and environment
        overrides instead of importing live personal Hermes configuration.
        """

        import os

        return {
            "model.provider": os.environ.get("PLAYRO_MODEL_PROVIDER", "auto"),
            "model.default": os.environ.get("PLAYRO_MODEL", "auto"),
            "tool_surface": "roblox-focused",
        }

    def remember_iteration(self, key: str, value: Any) -> None:
        """Prototype-local memory hook.

        Future versions can bind this to Hermes memory providers. The local
        prototype keeps it in-process to avoid importing the live environment.
        """
        self.memory[key] = value

    def record_learning(self, name: str, summary: str, source: str = "build") -> dict[str, str]:
        """Record a product-local learning event for the desktop skills panel."""

        learning = {
            "name": name,
            "summary": summary,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.learned_skills.append(learning)
        return learning
