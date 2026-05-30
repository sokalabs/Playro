"""File passthrough registry for remote terminal backends.

Remote backends (Docker, Modal, SSH) create sandboxes with no host files.
This module ensures that credential files, skill directories, and host-side
explicitly registered cache files (documents, images, audio, screenshots) are
synced into those sandboxes so the agent can access only files associated with
the current request.

**Credentials and skills** — session-scoped registry fed by skill declarations
(``required_credential_files``) and user config (``terminal.credential_files``).

**Cache files** — gateway-cached uploads, browser screenshots, TTS audio,
and processed images.  These must be registered per request before a remote
backend can mount or sync them; global cache directories are never exposed.

Remote backends call :func:`get_credential_file_mounts`,
:func:`get_skills_directory_mount` / :func:`iter_skills_files`, and
:func:`iter_cache_files` at sandbox creation time and before each command
(for resync on Modal).
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Dict, Iterator, List
from hermes_cli.config import cfg_get

logger = logging.getLogger(__name__)

# Session-scoped list of credential files to mount.
# Backed by ContextVar to prevent cross-session data bleed in the gateway pipeline.
_registered_files_var: ContextVar[Dict[str, str]] = ContextVar("_registered_files")
_registered_cache_files_var: ContextVar[Dict[str, str]] = ContextVar("_registered_cache_files")


def _get_registered() -> Dict[str, str]:
    """Get or create the registered credential files dict for the current context/session."""
    try:
        return _registered_files_var.get()
    except LookupError:
        val: Dict[str, str] = {}
        _registered_files_var.set(val)
        return val


def _get_registered_cache_files() -> Dict[str, str]:
    """Get/create request-scoped cache files mapped to sandbox paths."""
    try:
        return _registered_cache_files_var.get()
    except LookupError:
        val: Dict[str, str] = {}
        _registered_cache_files_var.set(val)
        return val


# Cache for config-based file list (loaded once per process).
_config_files: List[Dict[str, str]] | None = None


def _resolve_hermes_home() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home()


def register_credential_file(
    relative_path: str,
    container_base: str = "/root/.hermes",
) -> bool:
    """Register a credential file for mounting into remote sandboxes.

    *relative_path* is relative to ``HERMES_HOME`` (e.g. ``google_token.json``).
    Returns True if the file exists on the host and was registered.

    Security: rejects absolute paths and path traversal sequences (``..``).
    The resolved host path must remain inside HERMES_HOME so that a malicious
    skill cannot declare ``required_credential_files: ['../../.ssh/id_rsa']``
    and exfiltrate sensitive host files into a container sandbox.
    """
    hermes_home = _resolve_hermes_home()

    # Reject absolute paths — they bypass the HERMES_HOME sandbox entirely.
    if os.path.isabs(relative_path):
        logger.warning(
            "credential_files: rejected absolute path %r (must be relative to HERMES_HOME)",
            relative_path,
        )
        return False

    host_path = hermes_home / relative_path

    # Resolve symlinks and normalise ``..`` before the containment check so
    # that traversal like ``../. ssh/id_rsa`` cannot escape HERMES_HOME.
    from tools.path_security import validate_within_dir

    containment_error = validate_within_dir(host_path, hermes_home)
    if containment_error:
        logger.warning(
            "credential_files: rejected path traversal %r (%s)",
            relative_path,
            containment_error,
        )
        return False

    resolved = host_path.resolve()
    if not resolved.is_file():
        logger.debug("credential_files: skipping %s (not found)", resolved)
        return False

    container_path = f"{container_base.rstrip('/')}/{relative_path}"
    _get_registered()[container_path] = str(resolved)
    logger.debug("credential_files: registered %s -> %s", resolved, container_path)
    return True


def register_credential_files(
    entries: list,
    container_base: str = "/root/.hermes",
) -> List[str]:
    """Register multiple credential files from skill frontmatter entries.

    Each entry is either a string (relative path) or a dict with a ``path``
    key.  Returns the list of relative paths that were NOT found on the host
    (i.e. missing files).
    """
    missing = []
    for entry in entries:
        if isinstance(entry, str):
            rel_path = entry.strip()
        elif isinstance(entry, dict):
            rel_path = (entry.get("path") or entry.get("name") or "").strip()
        else:
            continue
        if not rel_path:
            continue
        if not register_credential_file(rel_path, container_base):
            missing.append(rel_path)
    return missing


def _load_config_files() -> List[Dict[str, str]]:
    """Load ``terminal.credential_files`` from config.yaml (cached)."""
    global _config_files
    if _config_files is not None:
        return _config_files

    result: List[Dict[str, str]] = []
    try:
        from hermes_cli.config import read_raw_config
        hermes_home = _resolve_hermes_home()
        cfg = read_raw_config()
        cred_files = cfg_get(cfg, "terminal", "credential_files")
        if isinstance(cred_files, list):
            from tools.path_security import validate_within_dir

            for item in cred_files:
                if isinstance(item, str) and item.strip():
                    rel = item.strip()
                    if os.path.isabs(rel):
                        logger.warning(
                            "credential_files: rejected absolute config path %r", rel,
                        )
                        continue
                    host_path = hermes_home / rel
                    containment_error = validate_within_dir(host_path, hermes_home)
                    if containment_error:
                        logger.warning(
                            "credential_files: rejected config path traversal %r (%s)",
                            rel, containment_error,
                        )
                        continue
                    resolved_path = host_path.resolve()
                    if resolved_path.is_file():
                        container_path = f"/root/.hermes/{rel}"
                        result.append({
                            "host_path": str(resolved_path),
                            "container_path": container_path,
                        })
    except Exception as e:
        logger.warning("Could not read terminal.credential_files from config: %s", e)

    _config_files = result
    return _config_files


def get_credential_file_mounts() -> List[Dict[str, str]]:
    """Return all credential files that should be mounted into remote sandboxes.

    Each item has ``host_path`` and ``container_path`` keys.
    Combines skill-registered files and user config.
    """
    mounts: Dict[str, str] = {}

    # Skill-registered files
    for container_path, host_path in _get_registered().items():
        # Re-check existence (file may have been deleted since registration)
        if Path(host_path).is_file():
            mounts[container_path] = host_path

    # Config-based files
    for entry in _load_config_files():
        cp = entry["container_path"]
        if cp not in mounts and Path(entry["host_path"]).is_file():
            mounts[cp] = entry["host_path"]

    return [
        {"host_path": hp, "container_path": cp}
        for cp, hp in mounts.items()
    ]


def get_skills_directory_mount(
    container_base: str = "/root/.hermes",
) -> list[Dict[str, str]]:
    """Return mount info for all skill directories (local + external).

    Skills may include ``scripts/``, ``templates/``, and ``references/``
    subdirectories that the agent needs to execute inside remote sandboxes.

    **Security:** Bind mounts follow symlinks, so a malicious symlink inside
    the skills tree could expose arbitrary host files to the container.  When
    symlinks are detected, this function creates a sanitized copy (regular
    files only) in a temp directory and returns that path instead.  When no
    symlinks are present (the common case), the original directory is returned
    directly with zero overhead.

    Returns a list of dicts with ``host_path`` and ``container_path`` keys.
    The local skills dir mounts at ``<container_base>/skills``, external dirs
    at ``<container_base>/external_skills/<index>``.
    """
    mounts = []
    hermes_home = _resolve_hermes_home()
    skills_dir = hermes_home / "skills"
    if skills_dir.is_dir():
        host_path = _safe_skills_path(skills_dir)
        mounts.append({
            "host_path": host_path,
            "container_path": f"{container_base.rstrip('/')}/skills",
        })

    # Mount external skill dirs
    try:
        from agent.skill_utils import get_external_skills_dirs
        for idx, ext_dir in enumerate(get_external_skills_dirs()):
            if ext_dir.is_dir():
                host_path = _safe_skills_path(ext_dir)
                mounts.append({
                    "host_path": host_path,
                    "container_path": f"{container_base.rstrip('/')}/external_skills/{idx}",
                })
    except ImportError:
        pass

    return mounts


_safe_skills_tempdir: Path | None = None


def _safe_skills_path(skills_dir: Path) -> str:
    """Return *skills_dir* if symlink-free, else a sanitized temp copy."""
    global _safe_skills_tempdir

    symlinks = [p for p in skills_dir.rglob("*") if p.is_symlink()]
    if not symlinks:
        return str(skills_dir)

    for link in symlinks:
        logger.warning("credential_files: skipping symlink in skills dir: %s -> %s",
                       link, os.readlink(link))

    import atexit
    import shutil
    import tempfile

    # Reuse the same temp dir across calls to avoid accumulation.
    if _safe_skills_tempdir and _safe_skills_tempdir.is_dir():
        shutil.rmtree(_safe_skills_tempdir, ignore_errors=True)

    safe_dir = Path(tempfile.mkdtemp(prefix="hermes-skills-safe-"))
    _safe_skills_tempdir = safe_dir

    for item in skills_dir.rglob("*"):
        if item.is_symlink():
            continue
        rel = item.relative_to(skills_dir)
        target = safe_dir / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(item), str(target))

    def _cleanup():
        if safe_dir.is_dir():
            shutil.rmtree(safe_dir, ignore_errors=True)

    atexit.register(_cleanup)
    logger.info("credential_files: created symlink-safe skills copy at %s", safe_dir)
    return str(safe_dir)


def iter_skills_files(
    container_base: str = "/root/.hermes",
) -> List[Dict[str, str]]:
    """Yield individual (host_path, container_path) entries for skills files.

    Includes both the local skills dir and any external dirs configured via
    skills.external_dirs.  Skips symlinks entirely.  Preferred for backends
    that upload files individually (Daytona, Modal) rather than mounting a
    directory.
    """
    result: List[Dict[str, str]] = []

    hermes_home = _resolve_hermes_home()
    skills_dir = hermes_home / "skills"
    if skills_dir.is_dir():
        container_root = f"{container_base.rstrip('/')}/skills"
        for item in skills_dir.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            rel = item.relative_to(skills_dir)
            result.append({
                "host_path": str(item),
                "container_path": f"{container_root}/{rel}",
            })

    # Include external skill dirs
    try:
        from agent.skill_utils import get_external_skills_dirs
        for idx, ext_dir in enumerate(get_external_skills_dirs()):
            if not ext_dir.is_dir():
                continue
            container_root = f"{container_base.rstrip('/')}/external_skills/{idx}"
            for item in ext_dir.rglob("*"):
                if item.is_symlink() or not item.is_file():
                    continue
                rel = item.relative_to(ext_dir)
                result.append({
                    "host_path": str(item),
                    "container_path": f"{container_root}/{rel}",
                })
    except ImportError:
        pass

    return result


# ---------------------------------------------------------------------------
# Request-scoped cache file passthrough (documents, images, audio, screenshots)
# ---------------------------------------------------------------------------

# The four cache subdirectories that may contain request-scoped files.
# Each tuple is (new_subpath, old_name) matching hermes_constants.get_hermes_dir().
_CACHE_DIRS: list[tuple[str, str]] = [
    ("cache/documents", "document_cache"),
    ("cache/images", "image_cache"),
    ("cache/audio", "audio_cache"),
    ("cache/screenshots", "browser_screenshots"),
]


def _cache_roots(container_base: str = "/root/.hermes") -> list[tuple[Path, str]]:
    """Return existing host cache roots and their sandbox root paths."""
    from hermes_constants import get_hermes_dir

    roots: list[tuple[Path, str]] = []
    for new_subpath, old_name in _CACHE_DIRS:
        host_dir = get_hermes_dir(new_subpath, old_name)
        if host_dir.is_dir():
            container_root = f"{container_base.rstrip('/')}/{new_subpath}"
            roots.append((host_dir.resolve(), container_root))
    return roots


def _cache_container_path_for(
    host_path: str,
    container_base: str = "/root/.hermes",
) -> tuple[str, str] | None:
    """Return ``(resolved_host_path, container_path)`` for a safe cache file."""
    path = Path(host_path).expanduser()
    try:
        resolved_path = path.resolve(strict=True)
    except OSError:
        return None
    if path.is_symlink() or not resolved_path.is_file():
        return None

    for host_dir, container_root in _cache_roots(container_base=container_base):
        try:
            rel = resolved_path.relative_to(host_dir)
        except ValueError:
            continue
        return str(resolved_path), str(Path(container_root) / rel)
    return None


def register_cache_file(
    host_path: str,
    container_base: str = "/root/.hermes",
) -> bool:
    """Register a single current-request cache file for remote sandbox access.

    Remote backends must never receive whole global cache directories because
    gateway caches are shared across users/sessions.  Callers should register
    only cache files referenced by the active message or request.
    """
    mapped = _cache_container_path_for(host_path, container_base=container_base)
    if mapped is None:
        logger.warning(
            "credential_files: rejected cache file outside known cache dirs: %s",
            host_path,
        )
        return False

    resolved_host_path, container_path = mapped
    _get_registered_cache_files()[resolved_host_path] = container_path
    return True


def get_cache_directory_mounts(
    container_base: str = "/root/.hermes",
) -> List[Dict[str, str]]:
    """Return no directory mounts; global cache directory passthrough is disabled.

    This compatibility shim intentionally avoids exposing shared gateway cache
    directories to remote sandboxes.  Use :func:`register_cache_file` and
    :func:`iter_cache_files` for request-scoped cache file passthrough.
    """
    return []


def to_agent_visible_cache_path(
    host_path: str,
    container_base: str = "/root/.hermes",
) -> str:
    """Translate a registered host cache file to its sandbox-visible path.

    Returns the input unchanged if it is not a registered cache file, or if the
    active terminal backend does not require path translation (only Docker for
    now).
    """
    if os.environ.get("TERMINAL_ENV", "local") != "docker":
        return host_path

    mapped = _cache_container_path_for(host_path, container_base=container_base)
    if mapped is None:
        return host_path

    resolved_host_path, container_path = mapped
    return _get_registered_cache_files().get(resolved_host_path, host_path)


def iter_cache_files(
    container_base: str = "/root/.hermes",
) -> List[Dict[str, str]]:
    """Return request-scoped cache files registered for remote backends.

    Used by upload/sync backends such as Modal.  Unlike the previous global
    cache scan, this only returns files explicitly registered in the current
    context/request.
    """
    result: List[Dict[str, str]] = []
    for host_path in sorted(_get_registered_cache_files()):
        mapped = _cache_container_path_for(host_path, container_base=container_base)
        if mapped is None:
            continue
        resolved_host_path, container_path = mapped
        result.append({
            "host_path": resolved_host_path,
            "container_path": container_path,
        })
    return result


def clear_credential_files() -> None:
    """Reset the skill-scoped registry (e.g. on session reset)."""
    _registered_files_var.set({})
    _get_registered_cache_files().clear()


def clear_cache_files() -> None:
    """Reset request-scoped cache file registrations."""
    _get_registered_cache_files().clear()


@contextmanager
def isolated_credential_files() -> Iterator[None]:
    """Run a gateway turn with fresh credential and cache registries.

    Executor worker threads may be reused across gateway sessions.  Replacing
    the ContextVar value at both entry and exit prevents credential mounts or
    request-scoped cache files registered by a previous job in that worker
    context from leaking into this turn or being restored for a later turn.
    """
    _registered_files_var.set({})
    _registered_cache_files_var.set({})
    try:
        yield
    finally:
        _registered_files_var.set({})
        _registered_cache_files_var.set({})


