import json
from pathlib import Path

import pytest

from product.roblox_ai_studio.hermes_backend.skill_catalog import playro_skill_catalog
from product.roblox_ai_studio.hermes_backend.retention_audit import (
    BUCKETS,
    RetentionManifestError,
    audit_paths,
    classify_path,
    discover_generated_paths,
    load_retention_manifest,
)


def test_retention_manifest_loads_with_valid_buckets():
    manifest = load_retention_manifest()

    assert set(BUCKETS) == {"active", "optional", "archive_only", "remove_generated"}
    assert manifest["archive_ref"] == "origin/archive/old-hermes-full-20260520-114549"
    for rule in manifest["rules"]:
        assert rule["bucket"] in BUCKETS
        assert rule["pattern"]
        assert rule["reason"]


def test_required_playro_paths_are_active():
    manifest = load_retention_manifest()

    assert classify_path("product/roblox_ai_studio/desktop/package.json", manifest).bucket == "active"
    assert classify_path("product/roblox_ai_studio/hermes_backend/tool_surface.py", manifest).bucket == "active"
    assert classify_path("product/playro_marketing_site/package.json", manifest).bucket == "active"
    assert classify_path("scripts/verify-playro-desktop-server.sh", manifest).bucket == "active"


def test_excluded_categories_are_archive_only_or_generated():
    manifest = load_retention_manifest()

    assert classify_path("optional-skills/blockchain/wallet/SKILL.md", manifest).bucket == "archive_only"
    assert classify_path("optional-skills/finance/modeling/SKILL.md", manifest).bucket == "archive_only"
    assert classify_path("skills/red-teaming/godmode/SKILL.md", manifest).bucket == "archive_only"
    assert classify_path("optional-skills/security/sherlock/SKILL.md", manifest).bucket == "archive_only"
    assert classify_path("hermes_agent.egg-info/PKG-INFO", manifest).bucket == "remove_generated"


def test_path_matching_uses_repo_glob_semantics():
    manifest = load_retention_manifest()

    assert classify_path("unraid/config.yml", manifest).bucket == "archive_only"
    assert classify_path("docs/unraid/config.yml", manifest).bucket == "archive_only"
    assert classify_path("scripts/nested/build-playro-helper.py", manifest).bucket is None


def test_ignored_generated_artifacts_can_be_discovered(tmp_path: Path):
    manifest = load_retention_manifest()
    generated_file = tmp_path / "hermes_agent.egg-info" / "PKG-INFO"
    generated_file.parent.mkdir()
    generated_file.write_text("generated", encoding="utf-8")

    assert discover_generated_paths(tmp_path, manifest) == ["hermes_agent.egg-info/PKG-INFO"]


def test_conditional_skills_are_not_user_visible_by_default():
    visible_paths = {skill["path"] for skill in playro_skill_catalog()}

    assert "skills/apple/imessage" not in visible_paths
    assert "skills/gaming/minecraft-modpack-server" not in visible_paths


def test_audit_reports_generated_separately_and_missing_critical_paths():
    manifest = load_retention_manifest()
    report = audit_paths(
        current_paths=[
            "product/roblox_ai_studio/app/api.py",
            "hermes_agent.egg-info/PKG-INFO",
            "unexpected/hermes-dashboard/app.py",
        ],
        archive_paths=["gateway/api_server.py"],
        manifest=manifest,
    )

    assert "hermes_agent.egg-info/PKG-INFO" in report["generated_present"]
    assert "unexpected/hermes-dashboard/app.py" in report["unclassified_present"]
    assert "product/roblox_ai_studio/desktop" in report["missing_critical_paths"]
    assert "gateway" in report["archive_restore_candidates"]


def test_strict_audit_fails_on_unclassified_high_level_surfaces():
    manifest = load_retention_manifest()

    report = audit_paths(
        current_paths=[
            "product/roblox_ai_studio/app/api.py",
            "mystery_runtime/file.py",
        ],
        archive_paths=[],
        manifest=manifest,
        strict=True,
    )

    assert report["ok"] is False
    assert "unclassified paths present" in report["errors"]


def test_manifest_conflicts_are_reported(tmp_path: Path):
    manifest_path = tmp_path / "bad_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "archive_ref": "origin/archive/old-hermes-full-20260520-114549",
                "rules": [
                    {"pattern": "skills/example/**", "bucket": "optional", "reason": "example"},
                    {"pattern": "skills/example/**", "bucket": "archive_only", "reason": "conflict"},
                ],
                "critical_paths": [],
                "restore_watchlist": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RetentionManifestError, match="conflicting retention buckets"):
        load_retention_manifest(manifest_path)
