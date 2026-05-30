#!/usr/bin/env python3
"""Mark Codex findings fixed after the security regression suite passes.

Usage:
  python scripts/security/close_verified_codex_findings.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_PATH = REPO_ROOT / "docs" / "security" / "codex-findings-tracker.json"
EVIDENCE = (
    "pytest tests/test_codex_security_fixes.py "
    "tests/test_codex_security_regressions.py "
    "tests/gateway/platforms/test_security.py "
    "tests/gateway/platforms/test_api_server_security.py "
    "product/roblox_ai_studio/app/test_security_controls.py -q"
)


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


def _run_regression() -> int:
    cmd = [sys.executable, "-m", "pytest"] + EVIDENCE.split()[1:] + ["-q", "--tb=line"]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Do not write tracker")
    parser.add_argument("--skip-tests", action="store_true", help="Mark fixed without pytest")
    args = parser.parse_args(argv)

    if not args.skip_tests and _run_regression() != 0:
        print("Security regression tests failed; tracker not updated.", file=sys.stderr)
        return 1

    data = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
    commit = _git_head()
    updated = 0
    for item in data.get("findings", []):
        if item.get("status") != "open":
            continue
        item["status"] = "fixed"
        item["commit"] = commit
        item["evidence"] = EVIDENCE
        updated += 1

    data["summary"] = {
        "total": len(data["findings"]),
        "open": sum(1 for f in data["findings"] if f.get("status") == "open"),
        "fixed": sum(1 for f in data["findings"] if f.get("status") == "fixed"),
        "wontfix": sum(1 for f in data["findings"] if f.get("status") == "wontfix"),
    }

    if args.dry_run:
        print(f"Would mark {updated} findings fixed (commit={commit})")
        return 0

    TRACKER_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Marked {updated} findings fixed ({data['summary']['open']} open remaining)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
