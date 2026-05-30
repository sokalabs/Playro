"""Shared file safety rules used by both tools and ACP shims."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union


def _hermes_home_path() -> Path:
    """Resolve the active HERMES_HOME (profile-aware) without circular imports."""
    try:
        from hermes_constants import get_hermes_home  # local import to avoid cycles
        return get_hermes_home()
    except Exception:
        return Path(os.path.expanduser("~/.hermes"))


def build_write_denied_paths(home: str, hermes_home: Optional[Union[str, Path]] = None) -> set[str]:
    """Return exact sensitive paths that must never be written.

    ``home`` must be the home directory for the filesystem where the write
    will occur.  For local writes that is the Hermes process user's home; for
    SSH/container-backed writes it is the backend user's home.
    """
    resolved_hermes_home = Path(hermes_home) if hermes_home is not None else _hermes_home_path()
    return {
        os.path.realpath(p)
        for p in [
            os.path.join(home, ".ssh", "authorized_keys"),
            os.path.join(home, ".ssh", "id_rsa"),
            os.path.join(home, ".ssh", "id_ed25519"),
            os.path.join(home, ".ssh", "config"),
            os.path.join(home, ".hermes", ".env"),
            str(resolved_hermes_home / ".env"),
            os.path.join(home, ".bashrc"),
            os.path.join(home, ".zshrc"),
            os.path.join(home, ".profile"),
            os.path.join(home, ".bash_profile"),
            os.path.join(home, ".zprofile"),
            os.path.join(home, ".netrc"),
            os.path.join(home, ".pgpass"),
            os.path.join(home, ".npmrc"),
            os.path.join(home, ".pypirc"),
            "/etc/sudoers",
            "/etc/passwd",
            "/etc/shadow",
        ]
    }


def build_write_denied_prefixes(home: str) -> list[str]:
    """Return sensitive directory prefixes that must never be written."""
    return [
        os.path.realpath(p) + os.sep
        for p in [
            os.path.join(home, ".ssh"),
            os.path.join(home, ".aws"),
            os.path.join(home, ".gnupg"),
            os.path.join(home, ".kube"),
            "/etc/sudoers.d",
            "/etc/systemd",
            os.path.join(home, ".docker"),
            os.path.join(home, ".azure"),
            os.path.join(home, ".config", "gh"),
        ]
    ]


def get_safe_write_root() -> Optional[str]:
    """Return the resolved HERMES_WRITE_SAFE_ROOT path, or None if unset."""
    root = os.getenv("HERMES_WRITE_SAFE_ROOT", "")
    if not root:
        return None
    try:
        return os.path.realpath(os.path.expanduser(root))
    except Exception:
        return None


def resolve_write_path(path: str, cwd: Optional[str] = None) -> str:
    """Resolve a write target using the same cwd that will execute it.

    Relative file-operation paths are interpreted by the terminal backend
    against its effective cwd. Authorization must resolve those paths against
    that same cwd instead of the Python process cwd, otherwise a terminal
    ``cd`` can create a check/use mismatch.
    """
    expanded = os.path.expanduser(str(path))
    if cwd and not os.path.isabs(expanded):
        expanded = os.path.join(os.path.expanduser(str(cwd)), expanded)
    return os.path.realpath(expanded)


def _expand_path_for_home(path: str, home: str) -> str:
    """Expand leading ``~`` against an explicit backend home directory."""
    value = str(path)
    if value == "~":
        return home
    if value.startswith("~/"):
        return home + value[1:]
    return os.path.expanduser(value)


def is_write_denied(path: str, cwd: Optional[str] = None, home: Optional[str] = None) -> bool:
    """Return True if path is blocked by the write denylist or safe root.

    Args:
        path: Candidate path to check.
        home: Optional home directory for the filesystem where the write will
            occur. Supplying this is required for remote backends whose home
            directory may differ from the local Hermes process user's home.
    """
    effective_home = os.path.realpath(os.path.expanduser(home or "~"))
    if home is not None:
        expanded = _expand_path_for_home(str(path), effective_home)
        if cwd and not os.path.isabs(expanded):
            expanded_cwd = _expand_path_for_home(str(cwd), effective_home)
            expanded = os.path.join(expanded_cwd, expanded)
        resolved = os.path.realpath(expanded)
    else:
        resolved = resolve_write_path(path, cwd=cwd)

    if resolved in build_write_denied_paths(effective_home):
        return True
    for prefix in build_write_denied_prefixes(effective_home):
        if resolved.startswith(prefix):
            return True

    safe_root = get_safe_write_root()
    if safe_root and not (resolved == safe_root or resolved.startswith(safe_root + os.sep)):
        return True

    return False


def get_read_block_error(path: str) -> Optional[str]:
    """Return an error message when a read targets internal Hermes cache files."""
    resolved = Path(path).expanduser().resolve()
    hermes_home = _hermes_home_path().resolve()
    blocked_dirs = [
        hermes_home / "skills" / ".hub" / "index-cache",
        hermes_home / "skills" / ".hub",
    ]
    for blocked in blocked_dirs:
        try:
            resolved.relative_to(blocked)
        except ValueError:
            continue
        return (
            f"Access denied: {path} is an internal Hermes cache file "
            "and cannot be read directly to prevent prompt injection. "
            "Use the skills_list or skill_view tools instead."
        )
    return None
