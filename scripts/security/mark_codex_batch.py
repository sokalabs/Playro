#!/usr/bin/env python3
"""Mark multiple Codex findings fixed by row number or path prefix."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_PATH = REPO_ROOT / "docs" / "security" / "codex-findings-tracker.json"
MARK_SCRIPT = REPO_ROOT / "scripts" / "security" / "mark_codex_finding.py"


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--rows", help="Comma-separated 1-based row numbers")
    group.add_argument("--path-prefix", help="Mark findings whose primary_path starts with this prefix")
    parser.add_argument("--status", default="fixed", choices=["open", "fixed", "wontfix"])
    parser.add_argument("--evidence", default="")
    args = parser.parse_args(argv)

    data = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
    findings = data["findings"]
    commit = _git_head()
    targets: list[int] = []

    if args.rows:
        targets = [int(part.strip()) for part in args.rows.split(",") if part.strip()]
    else:
        prefix = args.path_prefix
        targets = [
            item["row"]
            for item in findings
            if any(path.startswith(prefix) for path in item.get("paths", []))
        ]

    for row in targets:
        for item in findings:
            if item["row"] == row:
                item["status"] = args.status
                item["commit"] = commit
                if args.evidence:
                    item["evidence"] = args.evidence
                break

    data["summary"] = {
        "total": len(findings),
        "open": sum(1 for f in findings if f.get("status") == "open"),
        "fixed": sum(1 for f in findings if f.get("status") == "fixed"),
        "wontfix": sum(1 for f in findings if f.get("status") == "wontfix"),
    }
    TRACKER_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Marked {len(targets)} findings as {args.status} ({data['summary']['open']} open remaining)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
