"""Deterministic gameplay-mechanics validation for generated Roblox projects.

Inspects Luau source and manifest for actual server-authoritative mechanics
(coins, checkpoints, shop/upgrades, and genre-specific systems like pets,
bosses, tower defense, tycoon droppers, etc.) -- not just file presence.

Every check is a plain string/pattern test against the generated source,
so this runs without Roblox Studio and is fully deterministic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MechanicCheck:
    """One atomic gameplay-mechanics assertion."""

    slug: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class GameplayValidationResult:
    """Aggregate result from validating one generated project."""

    project: str
    genre: str
    ok: bool
    checks: list[MechanicCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed_slugs(self) -> list[str]:
        return [c.slug for c in self.checks if c.passed]

    @property
    def failed_slugs(self) -> list[str]:
        return [c.slug for c in self.checks if not c.passed]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict | None:
    text = _read(path)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _has(text: str, needle: str) -> bool:
    return needle in text


def _has_any(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def _has_all(text: str, *needles: str) -> bool:
    return all(n in text for n in needles)


def _count_occurrences(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


# ---------------------------------------------------------------------------
# Core mechanic checks (apply to every genre)
# ---------------------------------------------------------------------------

def _check_server_authoritative_coins(server_lua: str, config_lua: str) -> MechanicCheck:
    """Server must own coin rewards -- coin changes only in server script, not from client events."""
    server_owns_rewards = _has_any(server_lua, "rewardCoins", "addStat")
    no_client_coin_control = "OnServerEvent" not in server_lua or "Coin" not in server_lua.split("OnServerEvent")[-1][:200]
    config_defines_coin = _has_any(config_lua, "CoinReward", "StartingCoins")

    passed = server_owns_rewards and no_client_coin_control and config_defines_coin
    detail = ""
    if not server_owns_rewards:
        detail = "server script lacks rewardCoins/addStat for coins"
    elif not no_client_coin_control:
        detail = "client can directly modify coins via OnServerEvent (economy not server-authoritative)"
    elif not config_defines_coin:
        detail = "GameConfig missing CoinReward/StartingCoins"

    return MechanicCheck(
        slug="server_coins",
        description="Server-authoritative coin economy",
        passed=passed,
        detail=detail or "server owns coin rewards; config defines coin values",
    )


def _check_checkpoints(server_lua: str, manifest: dict | None) -> MechanicCheck:
    """Checkpoints must be server-created and track progress server-side."""
    has_checkpoint_func = _has(server_lua, "createCheckpoint") or _has(server_lua, "Checkpoint")
    has_checkpoint_stat = _has(server_lua, "Checkpoint") and _has(server_lua, "leaderstats")
    manifest_mentions_checkpoints = manifest is not None and "checkpoint" in json.dumps(manifest.get("systems", [])).lower()

    # Genre-specific: obby/obstacle MUST have checkpoints; others optional
    genre = (manifest or {}).get("genre", "")
    is_obby = "obby" in genre.lower() or "obstacle" in genre.lower()

    if is_obby:
        passed = has_checkpoint_func and has_checkpoint_stat
        if not passed:
            detail = "obby genre requires server checkpoints in server script"
        else:
            detail = "obby has server checkpoints with leaderstats tracking"
    else:
        passed = True  # non-obby genres pass by default
        detail = "checkpoints not required for this genre"
        if has_checkpoint_func:
            detail = "server checkpoints present (optional for this genre)"

    return MechanicCheck(
        slug="checkpoints",
        description="Server-side checkpoint routing",
        passed=passed,
        detail=detail,
    )


def _check_shop_upgrades(server_lua: str, config_lua: str, manifest: dict | None) -> MechanicCheck:
    """Shop/upgrade pads must validate cost on server before deducting currency."""
    has_upgrade_pad = _has_any(server_lua, "createUpgradePad", "UpgradePad", "BackpackUpgradePad", "TycoonUpgradePad")
    validates_cost = _has_any(server_lua, "coins.Value >=", "coins.Value <", "coins.Value -= ")
    config_defines_cost = _has_any(config_lua, "UpgradeCost", "TowerCost")

    genre = (manifest or {}).get("genre", "")
    needs_shop = any(
        kw in genre.lower()
        for kw in ("obby", "tycoon", "simulator", "tower defense", "rpg", "adventure")
    )

    # Also check manifest systems for shop/upgrade keywords
    systems = (manifest or {}).get("systems", [])
    systems_text = " ".join(systems).lower()
    manifest_wants_shop = "shop" in systems_text or "upgrade" in systems_text

    if needs_shop or manifest_wants_shop:
        passed = has_upgrade_pad and validates_cost and config_defines_cost
        detail = ""
        if not has_upgrade_pad:
            detail = "server script missing upgrade pad creation"
        elif not validates_cost:
            detail = "upgrade pad does not validate currency before deducting"
        elif not config_defines_cost:
            detail = "GameConfig missing UpgradeCost/TowerCost"
        else:
            detail = "server validates cost before purchase; config defines prices"
    else:
        passed = True
        detail = "shop/upgrades not required for this genre"

    return MechanicCheck(
        slug="shop_upgrades",
        description="Server-validated shop/upgrade system",
        passed=passed,
        detail=detail,
    )


def _check_leaderstats_server_owned(server_lua: str) -> MechanicCheck:
    """Leaderstats must be created server-side in PlayerAdded, not by client."""
    creates_in_player_added = _has(server_lua, "Players.PlayerAdded") and _has(server_lua, "createLeaderstats")
    no_remote_set = not _has(server_lua, "OnServerEvent") or "Value =" not in server_lua.split("OnServerEvent")[-1][:300]

    passed = creates_in_player_added and no_remote_set
    detail = ""
    if not creates_in_player_added:
        detail = "leaderstats not created in PlayerAdded handler"
    elif not no_remote_set:
        detail = "client may set stat values via RemoteEvent (not server-authoritative)"
    else:
        detail = "leaderstats created server-side in PlayerAdded; no client stat writes"

    return MechanicCheck(
        slug="leaderstats_server",
        description="Leaderstats owned by server",
        passed=passed,
        detail=detail,
    )


def _check_cooldown_rate_limit(server_lua: str) -> MechanicCheck:
    """Server must have cooldown/rate-limit to prevent exploit spam."""
    has_cooldown = _has_any(server_lua, "canUse", "playerCooldowns", "os.clock()")

    passed = has_cooldown
    detail = "server has cooldown/rate-limiting" if passed else "no cooldown/rate-limit found (exploit-vulnerable)"

    return MechanicCheck(
        slug="cooldown_rate_limit",
        description="Server-side cooldown/rate-limiting",
        passed=passed,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Genre-specific mechanic checks
# ---------------------------------------------------------------------------

def _check_tycoon_mechanics(server_lua: str, config_lua: str, manifest: dict | None) -> MechanicCheck:
    """Tycoon: droppers, collectors, tycoon-level upgrades -- all server-owned."""
    has_dropper = _has(server_lua, "createDropper") or _has(server_lua, "Dropper")
    has_collector = _has(server_lua, "createCollector") or _has(server_lua, "CollectorPad")
    has_tycoon_level = _has(server_lua, "TycoonLevel")
    config_has_drop_reward = _has(config_lua, "TycoonDropReward")

    passed = has_dropper and has_collector and has_tycoon_level and config_has_drop_reward
    missing = []
    if not has_dropper:
        missing.append("dropper")
    if not has_collector:
        missing.append("collector")
    if not has_tycoon_level:
        missing.append("TycoonLevel stat")
    if not config_has_drop_reward:
        missing.append("TycoonDropReward config")

    return MechanicCheck(
        slug="tycoon_mechanics",
        description="Tycoon: droppers, collector, level upgrades",
        passed=passed,
        detail="all tycoon mechanics present" if passed else f"missing: {', '.join(missing)}",
    )


def _check_simulator_mechanics(server_lua: str, config_lua: str, manifest: dict | None) -> MechanicCheck:
    """Simulator: training zones, backpack capacity, sell zone -- all server-owned."""
    has_training = _has(server_lua, "createTrainingZone") or _has(server_lua, "TrainingZone")
    has_backpack = _has(server_lua, "Backpack") and _has(server_lua, "BackpackCapacity")
    has_sell = _has(server_lua, "sellStrength") or _has(server_lua, "SellZone")
    config_has_training = _has_any(config_lua, "TrainingReward", "BackpackCapacity", "SellReward")

    passed = has_training and has_backpack and has_sell and config_has_training
    missing = []
    if not has_training:
        missing.append("training zone")
    if not has_backpack:
        missing.append("backpack stat")
    if not has_sell:
        missing.append("sell zone")
    if not config_has_training:
        missing.append("simulator config values")

    return MechanicCheck(
        slug="simulator_mechanics",
        description="Simulator: training, backpack, sell zone",
        passed=passed,
        detail="all simulator mechanics present" if passed else f"missing: {', '.join(missing)}",
    )


def _check_tower_defense_mechanics(server_lua: str, config_lua: str, manifest: dict | None) -> MechanicCheck:
    """Tower Defense: wave loop, enemy spawning, base health, tower purchase."""
    has_wave = _has(server_lua, "startWaveLoop") or _has(server_lua, "wave")
    has_enemy = _has(server_lua, "createEnemy") or _has(server_lua, "WaveEnemy")
    has_base_health = _has(server_lua, "BaseHealth")
    has_tower_pad = _has(server_lua, "createTowerPad") or _has(server_lua, "TowerPad")
    config_has_td = _has_any(config_lua, "TowerCost", "TowerDamage", "BaseHealth", "EnemyReward")

    passed = has_wave and has_enemy and has_base_health and has_tower_pad and config_has_td
    missing = []
    if not has_wave:
        missing.append("wave loop")
    if not has_enemy:
        missing.append("enemy spawn")
    if not has_base_health:
        missing.append("base health")
    if not has_tower_pad:
        missing.append("tower pad")
    if not config_has_td:
        missing.append("TD config values")

    return MechanicCheck(
        slug="tower_defense_mechanics",
        description="Tower Defense: waves, enemies, base, towers",
        passed=passed,
        detail="all TD mechanics present" if passed else f"missing: {', '.join(missing)}",
    )


def _check_pet_mechanics(server_lua: str, manifest: dict | None) -> MechanicCheck:
    """Pet collection: at minimum, manifest mentions pet system and server handles pet data."""
    systems = (manifest or {}).get("systems", [])
    systems_text = " ".join(systems).lower()
    manifest_wants_pets = "pet" in systems_text

    # Check for pet-related Luau patterns
    has_pet_stat = _has_any(server_lua, "Pets", "OwnedPets", "petCompanion")
    has_pet_collection = _has_any(server_lua, "createPet", "adoptPet", "PetSpawn")

    if manifest_wants_pets:
        # Must have at least pet stat tracking in server or a pet creation function
        passed = has_pet_stat or has_pet_collection
        detail = "pet system present in server script" if passed else "manifest requests pets but server script lacks pet mechanics"
    else:
        passed = True
        detail = "pets not requested"

    return MechanicCheck(
        slug="pet_mechanics",
        description="Pet companion system (when requested)",
        passed=passed,
        detail=detail,
    )


def _check_boss_mechanics(server_lua: str, manifest: dict | None) -> MechanicCheck:
    """Boss encounters: when requested, server must have boss-related logic."""
    systems = (manifest or {}).get("systems", [])
    systems_text = " ".join(systems).lower()
    manifest_wants_boss = "boss" in systems_text

    has_boss = _has_any(server_lua, "Boss", "bossEncounter", "BossHealth")

    if manifest_wants_boss:
        passed = has_boss
        detail = "boss encounter present in server script" if passed else "manifest requests boss but server script lacks boss logic"
    else:
        passed = True
        detail = "boss not requested"

    return MechanicCheck(
        slug="boss_mechanics",
        description="Boss encounter (when requested)",
        passed=passed,
        detail=detail,
    )


def _check_racing_mechanics(server_lua: str, config_lua: str, manifest: dict | None) -> MechanicCheck:
    """Racing: lap progression, speed boosts, vehicle upgrades."""
    has_lap = _has(server_lua, "createLapCheckpoint") or _has(server_lua, "LapCheckpoint")
    has_boost = _has(server_lua, "createSpeedBoost") or _has(server_lua, "WalkSpeed")
    has_lap_stat = _has(server_lua, "Lap")
    config_has_racing = _has_any(config_lua, "LapCount", "SpeedBoostMultiplier", "SpeedUpgradeCost")

    passed = has_lap and has_boost and has_lap_stat and config_has_racing
    missing = []
    if not has_lap:
        missing.append("lap checkpoint")
    if not has_boost:
        missing.append("speed boost pad")
    if not has_lap_stat:
        missing.append("Lap stat")
    if not config_has_racing:
        missing.append("Racing config values")

    return MechanicCheck(
        slug="racing_mechanics",
        description="Racing: lap progression, speed boosts",
        passed=passed,
        detail="all racing mechanics present" if passed else f"missing: {', '.join(missing)}",
    )


def _check_rpg_mechanics(server_lua: str, config_lua: str, manifest: dict | None) -> MechanicCheck:
    """RPG: zones, enemies, XP, level up."""
    has_zone = _has(server_lua, "createZoneUnlockPad") or _has(server_lua, "ZoneUnlock")
    has_enemy = _has(server_lua, "createEnemySpawn") or _has(server_lua, "EnemyHP")
    has_level_stats = _has(server_lua, "XP") and _has(server_lua, "Level")
    config_has_rpg = _has_any(config_lua, "XPReward", "LevelUpXP", "ZoneUnlockCost")

    passed = has_zone and has_enemy and has_level_stats and config_has_rpg
    missing = []
    if not has_zone:
        missing.append("zone unlock")
    if not has_enemy:
        missing.append("enemy spawn")
    if not has_level_stats:
        missing.append("XP/Level stats")
    if not config_has_rpg:
        missing.append("RPG config values")

    return MechanicCheck(
        slug="rpg_mechanics",
        description="RPG: zones, enemies, leveling",
        passed=passed,
        detail="all RPG mechanics present" if passed else f"missing: {', '.join(missing)}",
    )

def _check_custom_objectives(server_lua: str, config_lua: str, manifest: dict | None) -> MechanicCheck:
    """Custom prompts: validate prompt-inferred objectives rather than a fixed genre template."""
    systems_text = " ".join((manifest or {}).get("systems", [])).lower()
    wants_custom = any(
        keyword in systems_text
        for keyword in ("npc", "quest", "vehicle", "reputation", "apartment", "survival", "custom")
    ) or (manifest or {}).get("genre") == "Custom Roblox Experience"
    has_objective_stat = _has(server_lua, "CustomObjective")
    has_reputation = _has(server_lua, "Reputation") and _has_any(config_lua, "ReputationReward", "CustomObjectiveReward")
    has_prompt_interaction = _has_any(server_lua, "createQuestNpc", "createVehiclePad", "createApartmentHub", "createResourceNode")

    passed = not wants_custom or (has_objective_stat and has_reputation and has_prompt_interaction)
    missing = []
    if wants_custom and not has_objective_stat:
        missing.append("CustomObjective stat")
    if wants_custom and not has_reputation:
        missing.append("reputation rewards/config")
    if wants_custom and not has_prompt_interaction:
        missing.append("custom world interactions")

    return MechanicCheck(
        slug="custom_objectives",
        description="Custom prompt objectives and interaction loop",
        passed=passed,
        detail="custom prompt objectives present" if passed else f"missing: {', '.join(missing)}",
    )


# ---------------------------------------------------------------------------
# Genre routing
# ---------------------------------------------------------------------------

GENRE_CHECK_MAP: dict[str, list[str]] = {
 "Obstacle Course / Obby": ["checkpoints", "shop_upgrades"],
 "Tycoon": ["tycoon_mechanics", "shop_upgrades"],
 "Simulator": ["simulator_mechanics", "shop_upgrades"],
 "Tower Defense": ["tower_defense_mechanics", "shop_upgrades"],
 "Pet Collection": ["pet_mechanics", "shop_upgrades"],
 "Racing": ["racing_mechanics", "shop_upgrades"],
 "RPG Adventure": ["rpg_mechanics", "shop_upgrades"],
}

# Checks that always run regardless of genre
CORE_CHECKS = [
    "server_coins",
    "leaderstats_server",
    "cooldown_rate_limit",
]

# Conditional checks triggered by manifest content
CONDITIONAL_CHECKS = {
    "pet_mechanics": lambda manifest: "pet" in " ".join((manifest or {}).get("systems", [])).lower(),
    "boss_mechanics": lambda manifest: "boss" in " ".join((manifest or {}).get("systems", [])).lower(),
    "custom_objectives": lambda manifest: any(
        keyword in " ".join((manifest or {}).get("systems", [])).lower()
        for keyword in ("npc", "quest", "vehicle", "reputation", "apartment", "survival", "custom")
    ),
}


# ---------------------------------------------------------------------------
# Main validation entry point
# ---------------------------------------------------------------------------

def validate_gameplay_mechanics(project_dir: Path) -> GameplayValidationResult:
    """Run deterministic gameplay-mechanics checks on a generated project.

    Returns a GameplayValidationResult with per-check pass/fail and detail.
    """
    manifest = _load_json(project_dir / "manifest.json")
    server_lua = _read(project_dir / "src" / "ServerScriptService" / "Main.server.lua")
    config_lua = _read(project_dir / "src" / "ReplicatedStorage" / "GameConfig.lua")
    hud_lua = _read(project_dir / "src" / "StarterPlayer" / "StarterPlayerScripts" / "HUD.client.lua")
    genre = (manifest or {}).get("genre", "Unknown")

    # Determine which checks to run
    check_slugs = list(CORE_CHECKS)
    genre_checks = GENRE_CHECK_MAP.get(genre, ["shop_upgrades"])
    check_slugs.extend(genre_checks)

    # Add conditional checks based on manifest systems
    for slug, condition in CONDITIONAL_CHECKS.items():
        if slug not in check_slugs and condition(manifest):
            check_slugs.append(slug)

    # De-duplicate while preserving order
    seen = set()
    unique_slugs = []
    for s in check_slugs:
        if s not in seen:
            seen.add(s)
            unique_slugs.append(s)
    check_slugs = unique_slugs

 # Dispatch table
    check_fns = {
        "server_coins": lambda: _check_server_authoritative_coins(server_lua, config_lua),
        "checkpoints": lambda: _check_checkpoints(server_lua, manifest),
        "shop_upgrades": lambda: _check_shop_upgrades(server_lua, config_lua, manifest),
        "leaderstats_server": lambda: _check_leaderstats_server_owned(server_lua),
        "cooldown_rate_limit": lambda: _check_cooldown_rate_limit(server_lua),
        "tycoon_mechanics": lambda: _check_tycoon_mechanics(server_lua, config_lua, manifest),
        "simulator_mechanics": lambda: _check_simulator_mechanics(server_lua, config_lua, manifest),
        "tower_defense_mechanics": lambda: _check_tower_defense_mechanics(server_lua, config_lua, manifest),
        "pet_mechanics": lambda: _check_pet_mechanics(server_lua, manifest),
        "boss_mechanics": lambda: _check_boss_mechanics(server_lua, manifest),
        "racing_mechanics": lambda: _check_racing_mechanics(server_lua, config_lua, manifest),
        "rpg_mechanics": lambda: _check_rpg_mechanics(server_lua, config_lua, manifest),
        "custom_objectives": lambda: _check_custom_objectives(server_lua, config_lua, manifest),
    }

    checks: list[MechanicCheck] = []
    errors: list[str] = []

    for slug in check_slugs:
        fn = check_fns.get(slug)
        if fn is None:
            errors.append(f"unknown check slug: {slug}")
            continue
        try:
            check = fn()
            checks.append(check)
            if not check.passed:
                errors.append(f"{check.slug}: {check.detail}")
        except Exception as exc:
            errors.append(f"{slug}: exception during check: {exc}")
            checks.append(MechanicCheck(
                slug=slug,
                description=f"check for {slug}",
                passed=False,
                detail=f"exception: {exc}",
            ))

    ok = all(c.passed for c in checks) and not errors

    return GameplayValidationResult(
        project=project_dir.name,
        genre=genre,
        ok=ok,
        checks=checks,
        errors=errors,
    )


def validate_gameplay_batch(samples_root: Path, min_projects: int = 2) -> dict:
    """Validate all projects under samples_root with gameplay checks."""
    if not samples_root.exists():
        return {
            "ok": False,
            "samples_root": str(samples_root),
            "project_count": 0,
            "errors": [f"samples root does not exist: {samples_root}"],
            "projects": [],
        }

    projects = [
        path
        for path in sorted(samples_root.iterdir())
        if path.is_dir() and (path / "manifest.json").exists()
    ]

    results = [validate_gameplay_mechanics(p) for p in projects]
    aggregate_errors = []
    for r in results:
        aggregate_errors.extend(r.errors)

    if len(projects) < min_projects:
        aggregate_errors.insert(0, f"Expected at least {min_projects} projects, found {len(projects)}")

    return {
        "ok": len(aggregate_errors) == 0,
        "samples_root": str(samples_root),
        "project_count": len(projects),
        "errors": aggregate_errors,
        "projects": [
            {
                "project": r.project,
                "genre": r.genre,
                "ok": r.ok,
                "passed": r.passed_slugs,
                "failed": r.failed_slugs,
                "errors": r.errors,
            }
            for r in results
        ],
    }
