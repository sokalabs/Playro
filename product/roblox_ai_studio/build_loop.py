"""Product-local continuous build mission state for Roblox AI Studio.

This module intentionally stores all state next to generated Roblox projects. It
models the prototype shape for optional 24/7/autonomous build loops without
binding the product to the operator's live Hermes cron, Kanban board, MCP
registry, or machine-specific configuration.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

STATE_FILE = "build_mission.json"
PHASE_SEQUENCE = ("plan", "generate", "validate", "suggest")


class BuildLoopStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class BuildJob:
    id: str
    phase: str
    status: str
    summary: str
    created_at: int
    completed_at: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildLoop:
    status: BuildLoopStatus
    iteration: int
    next_phase: str
    pause_requested: bool = False
    stop_requested: bool = False
    runner: str = "product-local prototype"
    hermes_integration_hint: str = (
        "Future Hermes cron or Kanban workers can call the product-local CLI/API "
        "against this build_mission.json file; this prototype does not import "
        "live Hermes runtime config, tool registry, or board state."
    )
    updated_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class BuildMission:
    id: str
    project_id: str
    project_path: str
    prompt: str
    continuous: bool
    autonomous: bool
    created_at: int
    mission_type: str = "roblox-game-build"
    jobs: list[BuildJob] = field(default_factory=list)
    loop: BuildLoop = field(
        default_factory=lambda: BuildLoop(
            status=BuildLoopStatus.RUNNING,
            iteration=0,
            next_phase="plan",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "roblox-ai-studio.build_mission.v1",
            "mission": {
                "id": self.id,
                "project_id": self.project_id,
                "project_path": self.project_path,
                "prompt": self.prompt,
                "continuous": self.continuous,
                "autonomous": self.autonomous,
                "created_at": self.created_at,
                "mission_type": self.mission_type,
            },
            "loop": asdict(self.loop) | {"status": self.loop.status.value},
            "jobs": [asdict(job) for job in self.jobs],
        }


def mission_path(project_dir: Path) -> Path:
    return project_dir / STATE_FILE


def _now() -> int:
    return int(time.time())


def _job(phase: str, status: str = "queued", summary: str | None = None) -> BuildJob:
    return BuildJob(
        id=f"job_{uuid.uuid4().hex[:10]}",
        phase=phase,
        status=status,
        summary=summary or f"Queued {phase} phase for the build mission.",
        created_at=_now(),
    )


def _mission_from_dict(payload: dict[str, Any]) -> BuildMission:
    mission_payload = payload.get("mission", payload)
    loop_payload = payload.get("loop", mission_payload.get("loop", {}))
    jobs_payload = payload.get("jobs", mission_payload.get("jobs", []))
    loop = BuildLoop(
        status=BuildLoopStatus(loop_payload.get("status", "running")),
        iteration=int(loop_payload.get("iteration", 0)),
        next_phase=str(loop_payload.get("next_phase", "plan")),
        pause_requested=bool(loop_payload.get("pause_requested", False)),
        stop_requested=bool(loop_payload.get("stop_requested", False)),
        runner=str(loop_payload.get("runner", "product-local prototype")),
        hermes_integration_hint=str(loop_payload.get("hermes_integration_hint", BuildLoop.hermes_integration_hint)),
        updated_at=int(loop_payload.get("updated_at", _now())),
    )
    jobs = [
        BuildJob(
            id=str(item.get("id")),
            phase=str(item.get("phase")),
            status=str(item.get("status")),
            summary=str(item.get("summary", "")),
            created_at=int(item.get("created_at", _now())),
            completed_at=item.get("completed_at"),
            metadata=dict(item.get("metadata", {})),
        )
        for item in jobs_payload
    ]
    return BuildMission(
        id=str(mission_payload.get("id")),
        project_id=str(mission_payload.get("project_id")),
        project_path=str(mission_payload.get("project_path")),
        prompt=str(mission_payload.get("prompt", "")),
        continuous=bool(mission_payload.get("continuous", False)),
        autonomous=bool(mission_payload.get("autonomous", False)),
        created_at=int(mission_payload.get("created_at", _now())),
        mission_type=str(mission_payload.get("mission_type", "roblox-game-build")),
        jobs=jobs,
        loop=loop,
    )


def _write(project_dir: Path, mission: BuildMission) -> BuildMission:
    project_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "roblox-ai-studio.build_mission.v1",
        "mission": {
            "id": mission.id,
            "project_id": mission.project_id,
            "project_path": mission.project_path,
            "prompt": mission.prompt,
            "continuous": mission.continuous,
            "autonomous": mission.autonomous,
            "created_at": mission.created_at,
            "mission_type": mission.mission_type,
        },
        "loop": asdict(mission.loop) | {"status": mission.loop.status.value},
        "jobs": [asdict(job) for job in mission.jobs],
    }
    mission_path(project_dir).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return mission


def create_build_mission(
    project_dir: Path,
    *,
    prompt: str,
    continuous: bool = False,
    autonomous: bool = False,
) -> BuildMission:
    """Create or replace the product-local build mission file for a project."""
    status = BuildLoopStatus.RUNNING if continuous or autonomous else BuildLoopStatus.COMPLETED
    mission = BuildMission(
        id=f"mission_{uuid.uuid4().hex[:12]}",
        project_id=project_dir.name,
        project_path=str(project_dir),
        prompt=prompt,
        continuous=continuous,
        autonomous=autonomous,
        created_at=_now(),
        jobs=[_job("plan")],
        loop=BuildLoop(status=status, iteration=0, next_phase="plan"),
    )
    return _write(project_dir, mission)


def load_build_mission(project_dir: Path) -> BuildMission:
    payload = json.loads(mission_path(project_dir).read_text(encoding="utf-8"))
    return _mission_from_dict(payload)


def set_build_loop_status(project_dir: Path, status: str) -> BuildMission:
    mission = load_build_mission(project_dir)
    next_status = BuildLoopStatus(status)
    mission.loop.status = next_status
    mission.loop.pause_requested = next_status is BuildLoopStatus.PAUSED
    mission.loop.stop_requested = next_status is BuildLoopStatus.STOPPED
    mission.loop.updated_at = _now()
    mission.jobs.insert(
        0,
        _job(
            "control",
            status="recorded",
            summary=f"Build loop marked {next_status.value}; daemon execution is not implemented in this prototype.",
        ),
    )
    return _write(project_dir, mission)


def _complete_job(job: BuildJob, summary: str, metadata: dict[str, Any]) -> BuildJob:
    job.status = "completed"
    job.summary = summary
    job.completed_at = _now()
    job.metadata.update(metadata)
    return job


def run_build_loop_tick(project_dir: Path) -> BuildJob:
    """Advance one safe prototype loop phase and persist metadata.

    A tick records plan -> generate -> validate -> next-improvement suggestion
    metadata only. It does not spawn agents, import live Hermes config, or run a
    daemon. Future schedulers can call this function or the CLI/API wrapper.
    """
    mission = load_build_mission(project_dir)
    if mission.loop.status in {BuildLoopStatus.PAUSED, BuildLoopStatus.STOPPED}:
        return _job("control", status="skipped", summary=f"Build loop is {mission.loop.status.value}.")

    phase = mission.loop.next_phase if mission.loop.next_phase in PHASE_SEQUENCE else "plan"
    queued = next((job for job in mission.jobs if job.phase == phase and job.status == "queued"), None)
    job = queued or _job(phase)
    if queued is None:
        mission.jobs.append(job)

    summaries = {
        "plan": "Planned the next Roblox improvement pass from the current mission prompt.",
        "generate": "Recorded generation metadata for the next improvement pass; file mutation remains explicit and reviewable.",
        "validate": "Validated expected prototype artifacts and product-local mission state metadata.",
        "suggest": "Suggested the next improvement for the continuous build loop.",
    }
    metadata = {
        "safe_prototype": True,
        "project_local_state": str(mission_path(project_dir)),
        "no_live_hermes_import": True,
        "phase_order": list(PHASE_SEQUENCE),
    }
    _complete_job(job, summaries[phase], metadata)

    next_index = (PHASE_SEQUENCE.index(phase) + 1) % len(PHASE_SEQUENCE)
    if phase == "suggest":
        mission.loop.iteration += 1
    mission.loop.next_phase = PHASE_SEQUENCE[next_index]
    mission.loop.updated_at = _now()
    mission.jobs.append(_job(mission.loop.next_phase))
    _write(project_dir, mission)
    return job
