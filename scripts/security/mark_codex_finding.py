#!/usr/bin/env python3
"""Update Codex security finding status in the tracker JSON."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_PATH = REPO_ROOT / "docs" / "security" / "codex-findings-tracker.json"
STATUSES = frozenset({"open", "fixed", "wontfix"})


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


def _load_tracker() -> dict:
    if not TRACKER_PATH.exists():
        raise SystemExit(
            f"Tracker not found at {TRACKER_PATH}. "
            "Run scripts/security/generate_codex_tracker.py first."
        )
    return json.loads(TRACKER_PATH.read_text(encoding="utf-8"))


def _save_tracker(data: dict) -> None:
    TRACKER_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _finding_id_from_url(url: str) -> str:
    match = re.search(r"/findings/([0-9a-f]+)", url or "")
    return match.group(1) if match else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("finding_id", help="1-based row number or finding hash from finding_url")
    parser.add_argument(
        "--status",
        choices=sorted(STATUSES),
        default="fixed",
        help="New status (default: fixed)",
    )
    parser.add_argument("--commit", default="", help="Commit hash (default: current HEAD)")
    parser.add_argument("--evidence", default="", help="Test command or note")
    parser.add_argument("--note", default="", help="Optional wontfix rationale")
    args = parser.parse_args(argv)

    data = _load_tracker()
    findings = data.get("findings", [])
    target = None
    key = str(args.finding_id).strip()

    if key.isdigit():
        idx = int(key) - 1
        if 0 <= idx < len(findings):
            target = findings[idx]
    else:
        for item in findings:
            if item.get("id") == key or _finding_id_from_url(item.get("finding_url", "")) == key:
                target = item
                break

    if target is None:
        print(f"Finding not found: {args.finding_id}", file=sys.stderr)
        return 1

    target["status"] = args.status
    target["commit"] = args.commit or _git_head()
    if args.evidence:
        target["evidence"] = args.evidence
    if args.note:
        target["note"] = args.note

    open_count = sum(1 for f in findings if f.get("status") == "open")
    data["summary"] = {
        "total": len(findings),
        "open": open_count,
        "fixed": sum(1 for f in findings if f.get("status") == "fixed"),
        "wontfix": sum(1 for f in findings if f.get("status") == "wontfix"),
    }
    _save_tracker(data)
    print(
        f"Updated #{target.get('row', '?')} {target.get('title', '')[:60]} -> {args.status} "
        f"({open_count} open remaining)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
