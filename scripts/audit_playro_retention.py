#!/usr/bin/env python3
"""Run the read-only Playro Hermes retention audit."""

from __future__ import annotations

import argparse
import json
import sys

from product.roblox_ai_studio.hermes_backend.retention_audit import (
    DEFAULT_ARCHIVE_REF,
    RetentionManifestError,
    audit_paths,
    discover_generated_paths,
    list_archive_paths,
    list_git_paths,
    load_retention_manifest,
    render_report,
    repo_root,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare current Playro/Hermes source against the retention manifest and old-Hermes archive branch."
    )
    parser.add_argument(
        "--manifest",
        help="Path to a retention manifest JSON file. Defaults to product/roblox_ai_studio/config/playro_retention_manifest.json.",
    )
    parser.add_argument(
        "--archive-ref",
        default=None,
        help=f"Archive ref to inspect. Defaults to the manifest archive_ref or {DEFAULT_ARCHIVE_REF}.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail when unclassified paths are present.")
    parser.add_argument("--json", action="store_true", help="Emit the audit report as JSON.")
    parser.add_argument(
        "--apply-cleanup",
        action="store_true",
        help="Reserved for future destructive cleanup. Currently rejected so normal verification remains read-only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply_cleanup:
        print("--apply-cleanup is not implemented. This audit is read-only by default and will not delete files.", file=sys.stderr)
        return 2

    try:
        manifest = load_retention_manifest(args.manifest)
    except RetentionManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    archive_ref = args.archive_ref or str(manifest.get("archive_ref") or DEFAULT_ARCHIVE_REF)
    manifest["archive_ref"] = archive_ref
    root = repo_root()
    current_paths = sorted(set(list_git_paths(root)) | set(discover_generated_paths(root, manifest)))
    archive_paths, archive_available, archive_error = list_archive_paths(archive_ref, root)
    report = audit_paths(
        current_paths=current_paths,
        archive_paths=archive_paths,
        manifest=manifest,
        strict=args.strict,
        archive_available=archive_available,
    )
    if archive_error:
        report["archive_error"] = archive_error

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_report(report), end="")
        if archive_error:
            print(f"\nArchive note: {archive_error}")
            print(f"Fetch hint: git fetch origin {archive_ref.replace('origin/', '')}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
