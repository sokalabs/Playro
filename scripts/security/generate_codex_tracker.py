#!/usr/bin/env python3
"""Generate machine-readable tracker + markdown summary from Codex findings CSV."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "docs" / "security" / "codex-findings-2026-05-22.csv"
JSON_PATH = REPO_ROOT / "docs" / "security" / "codex-findings-tracker.json"
MD_PATH = REPO_ROOT / "docs" / "security" / "codex-findings-tracker.md"


def _finding_id_from_url(url: str) -> str:
    match = re.search(r"/findings/([0-9a-f]+)", url or "")
    return match.group(1) if match else ""


def _load_existing_by_id() -> dict[str, dict]:
    if not JSON_PATH.exists():
        return {}
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(item.get("id") or ""): item
        for item in data.get("findings", [])
        if item.get("id")
    }


def main() -> int:
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing CSV: {CSV_PATH}")

    existing = _load_existing_by_id()
    findings: list[dict] = []
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        for row_num, row in enumerate(csv.DictReader(handle), start=1):
            paths = [p.strip() for p in (row.get("relevant_paths") or "").split("|") if p.strip()]
            finding_id = _finding_id_from_url(row.get("finding_url", ""))
            prior = existing.get(finding_id, {})
            findings.append(
                {
                    "row": row_num,
                    "id": finding_id,
                    "finding_url": row.get("finding_url", ""),
                    "title": row.get("title", ""),
                    "severity": row.get("severity", ""),
                    "status": prior.get("status", "open"),
                    "paths": paths,
                    "primary_path": paths[0] if paths else "",
                    "commit": prior.get("commit", ""),
                    "evidence": prior.get("evidence", ""),
                    "note": prior.get("note", ""),
                }
            )

    payload = {
        "source_csv": str(CSV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "summary": {
            "total": len(findings),
            "open": sum(1 for f in findings if f.get("status") == "open"),
            "fixed": sum(1 for f in findings if f.get("status") == "fixed"),
            "wontfix": sum(1 for f in findings if f.get("status") == "wontfix"),
        },
        "findings": findings,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Codex Security Findings Tracker",
        "",
        f"Source: `{payload['source_csv']}`",
        "",
        "| Metric | Count |",
        "|--------|------:|",
        f"| Total | {len(findings)} |",
        f"| Open | {payload['summary']['open']} |",
        f"| Fixed | {payload['summary']['fixed']} |",
        f"| Wontfix | {payload['summary']['wontfix']} |",
        "",
        "Update status with:",
        "",
        "```bash",
        "python scripts/security/mark_codex_finding.py <row-or-id> --status fixed --evidence 'pytest ...'",
        "```",
        "",
        "Regenerate this table from JSON:",
        "",
        "```bash",
        "python scripts/security/generate_codex_tracker.py",
        "```",
        "",
        "<!-- AUTO-GENERATED: do not edit rows by hand; run generate_codex_tracker.py -->",
        "",
        "| # | Status | Title | Primary path |",
        "|--:|--------|-------|--------------|",
    ]
    for item in findings:
        title = item["title"].replace("|", "\\|")
        path = item["primary_path"].replace("|", "\\|")
        status = item.get("status", "open")
        lines.append(f"| {item['row']} | {status} | {title} | `{path}` |")

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {JSON_PATH} and {MD_PATH} ({len(findings)} findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
