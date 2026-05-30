"""Private on-disk store for ``terminal.docker_env``.

Docker-only secrets must not be serialized into the Hermes process
environment (``TERMINAL_DOCKER_ENV``) where local terminal subprocesses or
logs can read them.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home
from utils import atomic_replace

_STORE_NAME = "docker_env.json"


def docker_env_store_path() -> Path:
    return get_hermes_home() / "runtime" / _STORE_NAME


def read_docker_env() -> dict[str, str]:
    """Return configured docker_env entries, or ``{}`` when unset."""
    path = docker_env_store_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized[key] = value
    return normalized


def write_docker_env(env: Any) -> None:
    """Persist docker_env and remove any legacy host env mirror."""
    if env is None:
        payload: dict[str, str] = {}
    elif not isinstance(env, dict):
        raise ValueError("terminal.docker_env must be a mapping of string keys to string values")
    else:
        payload = {}
        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("terminal.docker_env keys and values must be strings")
            payload[key] = value

    path = docker_env_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        atomic_replace(tmp_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    os.environ.pop("TERMINAL_DOCKER_ENV", None)


def clear_legacy_docker_env_envvar() -> None:
    """Drop ``TERMINAL_DOCKER_ENV`` from the process environment if present."""
    os.environ.pop("TERMINAL_DOCKER_ENV", None)
