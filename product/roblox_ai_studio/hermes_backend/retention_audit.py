"""Manifest-driven retention audit helpers for Playro's Hermes foundation.

The audit is intentionally read-only. It reports suspicious paths and generated
artifacts so cleanup decisions stay reviewable instead of being ad hoc deletes.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

BUCKETS = ("active", "optional", "archive_only", "remove_generated")
DEFAULT_ARCHIVE_REF = "origin/archive/old-hermes-full-20260520-114549"


class RetentionManifestError(ValueError):
    """Raised when the retention manifest cannot be used safely."""


@dataclass(frozen=True)
class Classification:
    path: str
    bucket: str | None
    rule: dict[str, Any] | None = None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_manifest_path() -> Path:
    return repo_root() / "product" / "roblox_ai_studio" / "config" / "playro_retention_manifest.json"


def normalize_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/").strip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise RetentionManifestError(f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno} column {exc.colno}") from exc
    except OSError as exc:
        raise RetentionManifestError(f"Unable to read retention manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RetentionManifestError(f"Retention manifest {path} must contain a JSON object")
    return data


def load_retention_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path is not None else default_manifest_path()
    manifest = _load_json(manifest_path)
    rules = manifest.get("rules")
    if not isinstance(rules, list):
        raise RetentionManifestError(f"Retention manifest {manifest_path} must define a rules list")

    seen: dict[str, str] = {}
    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            raise RetentionManifestError(f"Rule {index} in {manifest_path} must be an object")
        pattern = normalize_path(str(rule.get("pattern") or ""))
        bucket = str(rule.get("bucket") or "")
        reason = str(rule.get("reason") or "")
        if not pattern:
            raise RetentionManifestError(f"Rule {index} in {manifest_path} is missing pattern")
        if bucket not in BUCKETS:
            raise RetentionManifestError(f"Rule {index} in {manifest_path} has invalid bucket {bucket!r}")
        if not reason:
            raise RetentionManifestError(f"Rule {index} in {manifest_path} is missing reason")
        if pattern in seen and seen[pattern] != bucket:
            raise RetentionManifestError(f"Rule {index} in {manifest_path} has conflicting retention buckets for {pattern}")
        seen[pattern] = bucket
        rule["pattern"] = pattern

    manifest.setdefault("archive_ref", DEFAULT_ARCHIVE_REF)
    manifest.setdefault("critical_paths", [])
    manifest.setdefault("restore_watchlist", [])
    return manifest


def _segment_matches(path_part: str, pattern_part: str) -> bool:
    regex = "^" + "".join(
        "[^/]*" if char == "*" else "[^/]" if char == "?" else re_escape(char)
        for char in pattern_part
    ) + "$"
    return bool(__import__("re").match(regex, path_part))


def re_escape(value: str) -> str:
    return __import__("re").escape(value)


def _parts_match(path_parts: tuple[str, ...], pattern_parts: tuple[str, ...]) -> bool:
    if not pattern_parts:
        return not path_parts
    head, *tail = pattern_parts
    tail_tuple = tuple(tail)
    if head == "**":
        return _parts_match(path_parts, tail_tuple) or bool(path_parts and _parts_match(path_parts[1:], pattern_parts))
    return bool(path_parts and _segment_matches(path_parts[0], head) and _parts_match(path_parts[1:], tail_tuple))


def _path_matches(path: str, pattern: str) -> bool:
    path_parts = tuple(part for part in normalize_path(path).split("/") if part)
    pattern_parts = tuple(part for part in normalize_path(pattern).split("/") if part)
    return _parts_match(path_parts, pattern_parts)


def classify_path(path: str | Path, manifest: dict[str, Any] | None = None) -> Classification:
    manifest = manifest or load_retention_manifest()
    normalized = normalize_path(path)
    matches = [rule for rule in manifest.get("rules", []) if _path_matches(normalized, str(rule.get("pattern") or ""))]
    if not matches:
        return Classification(path=normalized, bucket=None, rule=None)

    priority = {"remove_generated": 0, "archive_only": 1, "active": 2, "optional": 3}
    best = min(matches, key=lambda rule: priority[str(rule["bucket"])])
    return Classification(path=normalized, bucket=str(best["bucket"]), rule=best)


def _has_path(paths: set[str], expected: str) -> bool:
    expected = normalize_path(expected)
    return expected in paths or any(path.startswith(expected + "/") for path in paths)


def _bucket_summary(classified: list[Classification]) -> dict[str, list[str]]:
    summary = {bucket: [] for bucket in BUCKETS}
    for item in classified:
        if item.bucket in summary:
            summary[item.bucket].append(item.path)
    return {bucket: sorted(paths) for bucket, paths in summary.items() if paths}


def audit_paths(
    *,
    current_paths: Iterable[str | Path],
    archive_paths: Iterable[str | Path],
    manifest: dict[str, Any] | None = None,
    strict: bool = False,
    archive_available: bool = True,
) -> dict[str, Any]:
    manifest = manifest or load_retention_manifest()
    current = {normalize_path(path) for path in current_paths if normalize_path(path)}
    archive = {normalize_path(path) for path in archive_paths if normalize_path(path)}
    classified = [classify_path(path, manifest) for path in sorted(current)]

    generated_present = sorted(item.path for item in classified if item.bucket == "remove_generated")
    archive_only_present = sorted(item.path for item in classified if item.bucket == "archive_only")
    unclassified_present = sorted(item.path for item in classified if item.bucket is None)
    missing_critical = sorted(
        normalize_path(path)
        for path in manifest.get("critical_paths", [])
        if not _has_path(current, str(path))
    )
    restore_candidates = sorted(
        normalize_path(path)
        for path in manifest.get("restore_watchlist", [])
        if not _has_path(current, str(path)) and _has_path(archive, str(path))
    )

    errors: list[str] = []
    warnings: list[str] = []
    if missing_critical:
        errors.append("missing Playro-critical paths")
    if strict and unclassified_present:
        errors.append("unclassified paths present")
    if archive_only_present:
        warnings.append("archive-only paths present on current branch")
    if generated_present:
        warnings.append("generated artifacts present")
    if not archive_available:
        warnings.append(
            f"archive ref missing; fetch with: git fetch origin {manifest.get('archive_ref', DEFAULT_ARCHIVE_REF).replace('origin/', '')}"
        )

    return {
        "ok": not errors,
        "strict": strict,
        "archive_ref": manifest.get("archive_ref", DEFAULT_ARCHIVE_REF),
        "archive_available": archive_available,
        "classified_present": _bucket_summary(classified),
        "unclassified_present": unclassified_present,
        "archive_restore_candidates": restore_candidates,
        "archive_only_present": archive_only_present,
        "generated_present": generated_present,
        "missing_critical_paths": missing_critical,
        "warnings": warnings,
        "errors": errors,
    }


def list_git_paths(root: Path | None = None) -> list[str]:
    root = root or repo_root()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [normalize_path(line) for line in result.stdout.splitlines() if line.strip()]


def _literal_prefix(pattern: str) -> str:
    prefix = []
    for part in normalize_path(pattern).split("/"):
        if any(char in part for char in "*?"):
            break
        prefix.append(part)
    return "/".join(prefix)


def discover_generated_paths(root: Path | None = None, manifest: dict[str, Any] | None = None) -> list[str]:
    root = root or repo_root()
    manifest = manifest or load_retention_manifest()
    generated_rules = [rule for rule in manifest.get("rules", []) if rule.get("bucket") == "remove_generated"]
    discovered: set[str] = set()
    for rule in generated_rules:
        pattern = str(rule["pattern"])
        prefix = _literal_prefix(pattern)
        search_root = root / prefix if prefix else root
        if not search_root.exists():
            continue
        candidates = [search_root] if search_root.is_file() else (item for item in search_root.rglob("*") if item.is_file())
        for candidate in candidates:
            rel = normalize_path(candidate.relative_to(root))
            if _path_matches(rel, pattern):
                discovered.add(rel)
    return sorted(discovered)


def list_archive_paths(archive_ref: str, root: Path | None = None) -> tuple[list[str], bool, str | None]:
    root = root or repo_root()
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", archive_ref],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or f"Archive ref {archive_ref} is unavailable"
        return [], False, message
    return [normalize_path(line) for line in result.stdout.splitlines() if line.strip()], True, None


def render_report(report: dict[str, Any], *, limit: int = 25) -> str:
    lines = ["Playro Hermes Retention Audit", ""]
    lines.append(f"Status: {'PASS' if report['ok'] else 'FAIL'}")
    lines.append(f"Archive ref: {report['archive_ref']} ({'available' if report['archive_available'] else 'missing'})")
    lines.append(f"Strict mode: {'on' if report['strict'] else 'off'}")

    def section(title: str, values: Iterable[str]) -> None:
        items = list(values)
        lines.extend(["", title])
        if not items:
            lines.append("  none")
            return
        for item in items[:limit]:
            lines.append(f"  - {item}")
        if len(items) > limit:
            lines.append(f"  ... {len(items) - limit} more")

    section("Errors", report["errors"])
    section("Warnings", report["warnings"])
    section("Missing Playro-critical paths", report["missing_critical_paths"])
    section("Generated artifacts present", report["generated_present"])
    section("Archive-only paths present", report["archive_only_present"])
    section("Unclassified paths present", report["unclassified_present"])
    section("Archive restore candidates", report["archive_restore_candidates"])

    lines.extend(["", "Classified paths by bucket"])
    for bucket in BUCKETS:
        paths = report["classified_present"].get(bucket, [])
        lines.append(f"  {bucket}: {len(paths)}")
    return "\n".join(lines) + "\n"
