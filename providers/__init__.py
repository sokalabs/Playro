"""Provider module registry.

Provider profiles can live in two places:

1. Bundled plugins: ``plugins/model-providers/<name>/`` (shipped with hermes-agent)
2. Enabled user plugins: ``$HERMES_HOME/plugins/model-providers/<name>/``

Each plugin directory contains:
  - ``__init__.py`` — calls ``register_provider(profile)`` at import
  - ``plugin.yaml`` — manifest (name, kind: model-provider, version, description)

Discovery is lazy: the first call to ``get_provider_profile()`` or
``list_providers()`` scans both locations. Bundled plugins are imported
automatically; user plugins are imported only when their ``plugin.yaml``
declares ``kind: model-provider`` and the plugin is allowed by
``plugins.enabled``/``plugins.disabled``. Enabled user plugins override
bundled plugins on name collision (last-writer-wins), so third parties can
monkey-patch or replace any built-in profile without editing the repo.

For backward compatibility, ``providers/*.py`` files (other than ``base.py``
and ``__init__.py``) are still discovered via ``pkgutil.iter_modules``.
This lets out-of-tree users drop a single-file profile into an editable
install without the plugin dir structure. New profiles should prefer the
plugin layout.

Usage::

    from providers import get_provider_profile
    profile = get_provider_profile("nvidia")   # ProviderProfile or None
    profile = get_provider_profile("kimi")     # checks name + aliases
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path

from providers.base import OMIT_TEMPERATURE, ProviderProfile  # noqa: F401

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, ProviderProfile] = {}
_ALIASES: dict[str, str] = {}
_discovered = False

# Repo-root ``plugins/model-providers/`` — populated at discovery time.
_BUNDLED_PLUGINS_DIR = (
    Path(__file__).resolve().parent.parent / "plugins" / "model-providers"
)


def register_provider(profile: ProviderProfile) -> None:
    """Register a provider profile by name and aliases.

    Later registrations with the same name replace earlier ones — so user
    plugins under ``$HERMES_HOME/plugins/model-providers/`` can override
    bundled profiles without editing repo code.
    """
    _REGISTRY[profile.name] = profile
    for alias in profile.aliases:
        _ALIASES[alias] = profile.name


def get_provider_profile(name: str) -> ProviderProfile | None:
    """Look up a provider profile by name or alias.

    Returns None if the provider has no profile (falls back to generic).
    """
    if not _discovered:
        _discover_providers()
    canonical = _ALIASES.get(name, name)
    return _REGISTRY.get(canonical)


def list_providers() -> list[ProviderProfile]:
    """Return all registered provider profiles (one per canonical name)."""
    if not _discovered:
        _discover_providers()
    # Deduplicate: _REGISTRY has canonical names; _ALIASES points to same objects
    seen: set[int] = set()
    result: list[ProviderProfile] = []
    for profile in _REGISTRY.values():
        pid = id(profile)
        if pid not in seen:
            seen.add(pid)
            result.append(profile)
    return result


def _load_yaml_mapping(path: Path) -> dict:
    """Load a small YAML mapping, falling back to a line parser if needed."""
    text = path.read_text(encoding="utf-8")
    if importlib.util.find_spec("yaml") is not None:
        yaml = importlib.import_module("yaml")
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}

    result: dict[str, object] = {}
    current_section: str | None = None
    current_list: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1].strip()
            result.setdefault(current_section, {})
            current_list = None
            continue

        target = result
        if current_section and indent > 0:
            section = result.setdefault(current_section, {})
            if isinstance(section, dict):
                target = section

        if stripped.startswith("-") and current_list and isinstance(target, dict):
            value = stripped[1:].strip().strip('"\'')
            values = target.setdefault(current_list, [])
            if isinstance(values, list):
                values.append(value)
            continue

        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if isinstance(target, dict):
            if not value:
                target[key] = []
                current_list = key
            elif value.startswith("[") and value.endswith("]"):
                target[key] = [
                    item.strip().strip('"\'')
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
                current_list = None
            else:
                target[key] = value.strip('"\'')
                current_list = None

    return result


def _get_plugin_config_list(name: str) -> set[str] | None:
    """Read ``plugins.<name>`` from ``$HERMES_HOME/config.yaml``."""
    try:
        from hermes_constants import get_hermes_home

        config_file = get_hermes_home() / "config.yaml"
        if not config_file.exists():
            return None
        config = _load_yaml_mapping(config_file)
    except Exception:
        return None

    plugins_cfg = config.get("plugins")
    if not isinstance(plugins_cfg, dict) or name not in plugins_cfg:
        return None
    values = plugins_cfg.get(name)
    if not isinstance(values, list):
        return None
    return {value for value in values if isinstance(value, str)}


def _get_disabled_plugins() -> set[str]:
    """Read the disabled plugins deny-list without importing plugin code."""
    return _get_plugin_config_list("disabled") or set()


def _get_enabled_plugins() -> set[str] | None:
    """Read the enabled plugins allow-list without importing plugin code."""
    return _get_plugin_config_list("enabled")


def _user_plugins_dir() -> Path | None:
    """Return ``$HERMES_HOME/plugins/model-providers/`` if it exists."""
    try:
        from hermes_constants import get_hermes_home

        d = get_hermes_home() / "plugins" / "model-providers"
        return d if d.is_dir() else None
    except Exception:
        return None


def _user_plugin_manifest(plugin_dir: Path) -> tuple[str, str] | None:
    """Return ``(name, kind)`` from a user provider plugin manifest.

    User-installed model providers are untrusted code, so discovery must make
    its allow/deny decision before importing ``__init__.py``. Requiring a
    manifest also keeps the provider-specific loader aligned with the general
    plugin manager's contract.
    """
    manifest_file = plugin_dir / "plugin.yaml"
    if not manifest_file.exists():
        manifest_file = plugin_dir / "plugin.yml"
    if not manifest_file.exists():
        return None

    try:
        data = _load_yaml_mapping(manifest_file)
    except Exception as exc:
        logger.warning(
            "Failed to parse user provider plugin %s: %s", plugin_dir.name, exc
        )
        return None

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        name = plugin_dir.name

    kind = data.get("kind")
    if not isinstance(kind, str):
        kind = "standalone"

    return name.strip(), kind.strip().lower()


def _user_plugin_allowed(plugin_dir: Path) -> bool:
    """Return True if a user model-provider plugin may be imported."""
    manifest = _user_plugin_manifest(plugin_dir)
    if manifest is None:
        logger.debug(
            "Skipping user provider plugin %s (missing or invalid manifest)",
            plugin_dir.name,
        )
        return False

    _, kind = manifest
    key = f"model-providers/{plugin_dir.name}"
    # Only path-derived identifiers are trusted for authorization. The
    # manifest name comes from the untrusted plugin being evaluated, so it
    # must not allow a plugin directory to impersonate another enabled plugin.
    identifiers = {key, plugin_dir.name}

    if kind != "model-provider":
        logger.debug("Skipping user provider plugin %s (kind=%s)", key, kind)
        return False

    disabled = _get_disabled_plugins()
    if identifiers & disabled:
        logger.debug("Skipping disabled user provider plugin %s", key)
        return False

    enabled = _get_enabled_plugins()
    if enabled is None or not (identifiers & enabled):
        logger.debug("Skipping user provider plugin %s (not in plugins.enabled)", key)
        return False

    return True


def _import_plugin_dir(plugin_dir: Path, source: str) -> None:
    """Import a single plugin directory so it self-registers.

    ``source`` is "bundled" or "user", used only for log messages.
    """
    if source == "user" and not _user_plugin_allowed(plugin_dir):
        return

    init_file = plugin_dir / "__init__.py"
    if not init_file.exists():
        return

    # Give bundled plugins a stable import path (``plugins.model_providers.<name>``)
    # so relative imports within the plugin work. User plugins load via
    # ``importlib.util.spec_from_file_location`` with a unique module name so
    # multiple HERMES_HOME profiles don't alias each other.
    safe_name = plugin_dir.name.replace("-", "_")
    if source == "bundled":
        module_name = f"plugins.model_providers.{safe_name}"
    else:
        module_name = f"_hermes_user_provider_{safe_name}"

    if module_name in sys.modules:
        return  # already imported

    try:
        spec = importlib.util.spec_from_file_location(
            module_name, init_file, submodule_search_locations=[str(plugin_dir)]
        )
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        logger.warning(
            "Failed to load %s provider plugin %s: %s", source, plugin_dir.name, exc
        )
        sys.modules.pop(module_name, None)


def _discover_providers() -> None:
    """Populate the registry by importing every provider plugin.

    Order:
      1. Bundled plugins at ``<repo>/plugins/model-providers/<name>/``
      2. User plugins at ``$HERMES_HOME/plugins/model-providers/<name>/``
      3. Legacy per-file modules at ``providers/<name>.py`` (back-compat)

    Each step imports its plugins, which call ``register_provider()`` at
    module-level. Later steps win on name collision.
    """
    global _discovered
    if _discovered:
        return
    _discovered = True

    # 1. Bundled plugins — shipped with hermes-agent.
    if _BUNDLED_PLUGINS_DIR.is_dir():
        for child in sorted(_BUNDLED_PLUGINS_DIR.iterdir()):
            if not child.is_dir() or child.name.startswith(("_", ".")):
                continue
            _import_plugin_dir(child, "bundled")

    # 2. User plugins — under $HERMES_HOME/plugins/model-providers/<name>/.
    #    These can override any bundled profile of the same name (last-writer-wins
    #    in register_provider()).
    user_dir = _user_plugins_dir()
    if user_dir is not None:
        for child in sorted(user_dir.iterdir()):
            if not child.is_dir() or child.name.startswith(("_", ".")):
                continue
            _import_plugin_dir(child, "user")

    # 3. Legacy single-file profiles at providers/<name>.py. Kept for
    #    back-compat — if someone drops a ``providers/foo.py`` into an
    #    editable install, it still works without the plugin layout.
    try:
        import pkgutil

        import providers as _pkg

        for _importer, modname, _ispkg in pkgutil.iter_modules(_pkg.__path__):
            if modname.startswith("_") or modname == "base":
                continue
            try:
                importlib.import_module(f"providers.{modname}")
            except ImportError as exc:
                logger.warning(
                    "Failed to import legacy provider module %s: %s", modname, exc
                )
    except Exception:
        pass
