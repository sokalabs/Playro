"""Roblox-focused Hermes backend surface policy.

This module is intentionally small and explicit. Hermes supports many tools,
plugins, MCP servers, and environment-specific integrations, but this product
fork must not inherit the live install's registry by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class ProductToolSurface:
    """Allowlist for the Roblox-focused product surface."""

    allowed_toolsets: tuple[str, ...] = (
        "file",
        "terminal",
        "skills",
        "memory",
        "web",
        "roblox_project",
        "luau_generator",
        "game_planner",
    )
    allowed_dynamic_sources: tuple[str, ...] = (
        "product_local_skills",
        "roblox_open_cloud_opt_in",
        "rojo_project_tools",
        "luau_validation_tools",
    )
    allowed_hermes_capabilities: tuple[str, ...] = (
        "agent_runtime",
        "skills",
        "self_learning",
        "persistent_memory",
        "kanban_orchestration",
        "cron_background_builds",
        "provider_routing",
        "gateway_api_surface",
    )
    desktop_capabilities: tuple[str, ...] = (
        "prompt_to_build",
        "build_status_timeline",
        "generated_files_view",
        "skill_learning_view",
        "continuous_24_7_mode",
        "pause_stop_autonomy",
        "open_in_roblox_studio_guidance",
    )
    forbidden_keywords: tuple[str, ...] = (
        "unraid",
        "docker_host_admin",
        "homelab",
        "server_management",
        "homeassistant",
        "cloudflare_ops",
        "machine_specific_mcp",
        "live_hermes_environment",
    )
    notes: tuple[str, ...] = (
        "Do not mirror the current Hermes install tool registry.",
        "Expose Hermes skills, memory, self-learning, orchestration, cron, and provider routing through a Roblox-focused boundary.",
        "Add product tools only when directly useful for Roblox game creation.",
        "Treat external Studio/Open Cloud integrations as opt-in adapters.",
    )

    def is_allowed(self, toolset: str) -> bool:
        normalized = toolset.strip().lower().replace("-", "_")
        return normalized in {t.lower().replace("-", "_") for t in self.allowed_toolsets}

    def validate_requested(self, requested: Iterable[str]) -> tuple[list[str], list[str]]:
        allowed: list[str] = []
        denied: list[str] = []
        for item in requested:
            if self.is_allowed(item):
                allowed.append(item)
            else:
                denied.append(item)
        return allowed, denied

    def desktop_manifest(self) -> dict[str, object]:
        """Return the capability shape the desktop app can display."""

        return {
            "allowed_toolsets": list(self.allowed_toolsets),
            "allowed_dynamic_sources": list(self.allowed_dynamic_sources),
            "hermes_capabilities": list(self.allowed_hermes_capabilities),
            "desktop_capabilities": list(self.desktop_capabilities),
            "notes": list(self.notes),
        }


DEFAULT_TOOL_SURFACE = ProductToolSurface()
