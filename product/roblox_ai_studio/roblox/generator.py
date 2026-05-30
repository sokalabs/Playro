"""Prompt-to-Roblox project generation for the local prototype."""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

from product.roblox_ai_studio.app.artifacts import PLAYRO_CORE_ARTIFACT_FILES

logger = logging.getLogger(__name__)


def _luau_template(text: str) -> str:
    """Normalize embedded Luau template blocks to column zero.

    Some generated Luau templates intentionally contain mixed indentation
    because they embed Luau control-flow. textwrap.dedent can leave a
    Python-body margin behind when the minimum common indentation is skewed
    by nested template content. Use the first non-empty line as the template
    margin so generated files do not carry Python source indentation.
    """
    lines = dedent(text).strip("\n").splitlines()
    first = next((line for line in lines if line.strip()), "")
    margin = len(first) - len(first.lstrip(" "))
    if margin:
        lines = [line[margin:] if len(line) >= margin and line[:margin].strip() == "" else line for line in lines]
    return "\n".join(lines) + "\n"


@dataclass
class GamePlan:
    title: str
    slug: str
    genre: str
    loop: str
    systems: list[str]
    scripts: list[str]
    iteration_hooks: list[str]


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:60].strip("-") or "roblox-game"


def infer_genre(prompt: str) -> str:
    p = prompt.lower()
    checks = [
        ("tower defense", "Tower Defense"),
        ("td", "Tower Defense"),
        ("obby", "Obstacle Course / Obby"),
        ("obstacle", "Obstacle Course / Obby"),
        ("tycoon", "Tycoon"),
        ("dropper", "Tycoon"),
        ("simulator", "Simulator"),
        ("training", "Simulator"),
        ("rpg", "RPG Adventure"),
        ("adventure", "RPG Adventure"),
        ("horror", "Horror"),
        ("pet", "Pet Collection"),
        ("race", "Racing"),
        ("racing", "Racing"),
 ]
    for needle, genre in checks:
        if needle in p:
            return genre
    return "Custom Roblox Experience"


def _add_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def plan_from_prompt(prompt: str) -> GamePlan:
    genre = infer_genre(prompt)
    base = slugify(prompt)
    title = " ".join(word.capitalize() for word in base.split("-")[:8])
    p = prompt.lower()

    systems = ["spawn flow", "player progression", "server-authoritative rewards"]
    if "coin" in p or "money" in p or "cash" in p:
        _add_unique(systems, "coin collection economy")
    if "shop" in p or "upgrade" in p:
        _add_unique(systems, "shop and upgrade loop")
    if "checkpoint" in p or "obby" in p or "obstacle" in p or genre == "Obstacle Course / Obby":
        _add_unique(systems, "checkpoints and respawn routing")
        _add_unique(systems, "server-built obby platforms")
    if "tycoon" in p or "dropper" in p or genre == "Tycoon":
        _add_unique(systems, "tycoon droppers and collectors")
        _add_unique(systems, "server-priced tycoon upgrades")
    if "simulator" in p or "training" in p or "backpack" in p or genre == "Simulator":
        _add_unique(systems, "clicker training and backpack loop")
        _add_unique(systems, "sell zone economy")
    if "enemy" in p or "combat" in p:
        _add_unique(systems, "simple combat encounter loop")
    if "pet" in p:
        _add_unique(systems, "pet companion collection")
    if "tower defense" in p or "wave" in p or genre == "Tower Defense":
        _add_unique(systems, "wave defense loop")
        _add_unique(systems, "server-spawned enemies and base health")
        _add_unique(systems, "tower purchase pads")
    if "quest" in p or "npc" in p:
        _add_unique(systems, "NPC quest objectives")
    if "boss" in p:
        _add_unique(systems, "boss encounter milestone")
    if "vehicle" in p or "car" in p or "drive" in p:
        _add_unique(systems, "vehicle interaction loop")
    if "reputation" in p or "rep " in p:
        _add_unique(systems, "reputation progression")
    if "apartment" in p or "house" in p or "roleplay" in p or "city" in p:
        _add_unique(systems, "roleplay apartment hub")
    if "survival" in p or "craft" in p or "resource" in p:
        _add_unique(systems, "resource survival loop")
    if "team" in p or "multiplayer" in p:
        _add_unique(systems, "cooperative multiplayer goals")
    if "round" in p or "arena" in p:
        _add_unique(systems, "round-based arena loop")
    if "race" in p or "car" in p or "drive" in p or genre == "Racing":
        _add_unique(systems, "lap checkpoint progression")
        _add_unique(systems, "speed boost collection")
        _add_unique(systems, "lap and racing economy")
    if "rpg" in p or "level up" in p or genre == "RPG Adventure":
        _add_unique(systems, "zone unlocking with coins")
        _add_unique(systems, "enemy spawning and XP rewards")
        _add_unique(systems, "level and XP tracking stats")
    if "rpg" in p or "adventure" in p or "explore" in p or genre == "RPG Adventure":
        _add_unique(systems, "zone-based exploration and unlock")
        _add_unique(systems, "enemy combat with XP rewards")
        _add_unique(systems, "level-up stat progression")
        _add_unique(systems, "gear shop and equipment upgrades")
    loops = {
        "Obstacle Course / Obby": (
            "Player spawns at stage 1, jumps across server-built platforms, touches "
            "checkpoints, collects coins, and spends coins on a safe speed upgrade."
        ),
        "Tycoon": (
            "Player earns money from server-owned droppers, collects it at a pad, "
            "buys upgrades, and unlocks stronger income loops."
        ),
        "Simulator": (
            "Player trains strength at zones, fills a backpack, sells strength for "
            "coins, then buys larger capacity and better rewards."
        ),
        "Tower Defense": (
            "Enemies move toward a base in timed waves while players earn coins, "
            "buy tower pads, and protect shared base health."
        ),
        "Racing": (
            "Player races around a track crossing lap checkpoints, picking up speed boosts, "
            "and competing to earn coins to buy permanent vehicle upgrades."
        ),
        "RPG Adventure": (
            "Player defeats enemies in open zones to earn XP, levels up, and uses coins "
            "to unlock new zones with harder enemies."
        ),
        "Custom Roblox Experience": (
            "Player joins a custom Roblox prototype, follows prompt-specific objectives, "
            "interacts with generated world systems, earns rewards, and progresses through "
            "mechanics inferred from the idea."
        ),
    }

    return GamePlan(
        title=title,
        slug=base,
        genre=genre,
        loop=loops.get(
            genre,
            "Player joins, learns the objective, completes short challenges, earns rewards, "
            "spends rewards on improvements, then repeats with clearer goals and harder content.",
        ),
        systems=systems,
        scripts=[path for path in PLAYRO_CORE_ARTIFACT_FILES if path.endswith(".lua")],
        iteration_hooks=[
            "Ask for one improvement at a time, then regenerate only affected systems.",
            "Record generated files and plan decisions in manifest.json.",
            "Future Studio adapter should playtest and feed errors back into repair prompts.",
        ],
    )


PROMPT_FIDELITY_CATALOG: list[dict[str, object]] = [
    {
        "id": "mechanics",
        "label": "Mechanics",
        "prompt_keywords": [
            "combat",
            "fight",
            "enemy",
            "wave",
            "boss",
            "checkpoint",
            "obby",
            "obstacle",
            "parkour",
            "tycoon",
            "dropper",
            "simulator",
            "tower",
            "race",
            "lap",
            "quest",
            "survival",
            "craft",
            "arena",
            "round",
        ],
        "system_keywords": [
            "combat",
            "wave",
            "checkpoint",
            "obby",
            "tycoon",
            "simulator",
            "tower",
            "race",
            "quest",
            "boss",
            "survival",
            "arena",
            "spawn",
            "progression",
            "droppers",
            "enemies",
            "lap",
        ],
    },
    {
        "id": "world",
        "label": "World & map",
        "prompt_keywords": [
            "world",
            "map",
            "zone",
            "platform",
            "stage",
            "island",
            "city",
            "hub",
            "apartment",
            "house",
            "arena",
            "explore",
        ],
        "system_keywords": [
            "platform",
            "zone",
            "apartment",
            "hub",
            "exploration",
            "vehicle",
            "roleplay",
        ],
    },
    {
        "id": "rewards",
        "label": "Rewards",
        "prompt_keywords": ["coin", "cash", "money", "reward", "prize", "xp", "level", "progression", "rebirth"],
        "system_keywords": ["coin", "economy", "reward", "progression", "xp", "level", "sell"],
    },
    {
        "id": "ui",
        "label": "UI",
        "prompt_keywords": ["ui", "hud", "menu", "screen", "button", "interface"],
        "system_keywords": ["hud", "client"],
        "always_matched": True,
    },
    {
        "id": "npcs",
        "label": "NPCs & quests",
        "prompt_keywords": ["npc", "quest", "mission", "dialog", "character", "story"],
        "system_keywords": ["npc", "quest"],
    },
    {
        "id": "multiplayer",
        "label": "Multiplayer",
        "prompt_keywords": ["multiplayer", "team", "co-op", "coop", "friends", "party", "together"],
        "system_keywords": ["multiplayer", "cooperative", "team"],
    },
    {
        "id": "reward_loops",
        "label": "Reward loops",
        "prompt_keywords": ["shop", "upgrade", "store", "buy", "sell", "tycoon", "economy", "rebirth"],
        "system_keywords": ["shop", "upgrade", "economy", "tycoon", "collector", "droppers"],
    },
]


def _prompt_mentions(prompt_lower: str, keywords: list[str]) -> bool:
    return any(keyword in prompt_lower for keyword in keywords)


def _systems_cover(systems: list[str], keywords: list[str]) -> bool:
    blob = " ".join(systems).lower()
    return any(keyword in blob for keyword in keywords)


def build_prompt_fidelity(prompt: str, systems: list[str] | None = None) -> dict:
    """Score how much of the user prompt shows up in generated systems."""
    systems = list(systems or [])
    prompt_lower = prompt.lower()
    items: list[dict[str, object]] = []
    for category in PROMPT_FIDELITY_CATALOG:
        prompt_keywords = list(category["prompt_keywords"])
        system_keywords = list(category["system_keywords"])
        requested = _prompt_mentions(prompt_lower, prompt_keywords)
        matched = bool(category.get("always_matched")) or _systems_cover(systems, system_keywords)
        items.append(
            {
                "id": category["id"],
                "label": category["label"],
                "requested": requested,
                "matched": matched,
            }
        )

    requested_items = [item for item in items if item["requested"]]
    if not requested_items:
        score = 100
        label = "Starter match"
        summary = (
            "Playro turned your idea into a starter Roblox game. "
            "Add one clear feature in your next message to raise the match score."
        )
        missing: list[str] = []
    else:
        matched_count = sum(1 for item in requested_items if item["matched"])
        requested_count = len(requested_items)
        score = round((matched_count / requested_count) * 100)
        missing = [str(item["label"]) for item in requested_items if not item["matched"]]
        if score >= 85:
            label = "Strong match"
        elif score >= 60:
            label = "Good match"
        else:
            label = "Partial match"
        summary = f"Playro built {matched_count} of {requested_count} ideas from your prompt."

    return {
        "score": score,
        "label": label,
        "summary": summary,
        "items": items,
        "missing": missing,
        "matched_count": sum(1 for item in requested_items if item["matched"]) if requested_items else len(items),
        "requested_count": len(requested_items) if requested_items else len(items),
    }


def refine_plan(base_plan: GamePlan, refinement_prompt: str) -> GamePlan:
    """Apply a deterministic prototype refinement to an existing plan."""
    p = refinement_prompt.lower()
    systems = list(base_plan.systems)
    hooks = list(base_plan.iteration_hooks)

    additions = []
    if "boss" in p:
        additions.append("boss encounter milestone")
    if "pet" in p and "pet companion collection" not in systems:
        additions.append("pet companion collection")
    if "daily" in p or "reward" in p:
        additions.append("daily reward retention loop")
    if "shop" in p and "shop and upgrade loop" not in systems:
        additions.append("shop and upgrade loop")
    if "npc" in p or "quest" in p:
        additions.append("quest and NPC guidance")
    if "team" in p or "multiplayer" in p:
        additions.append("cooperative multiplayer goals")

    for item in additions:
        if item not in systems:
            systems.append(item)

    hooks.append(f"Refinement applied: {refinement_prompt}")
    return replace(base_plan, systems=systems, iteration_hooks=hooks)


def luau_string(value: str) -> str:
    return json.dumps(value)


def _needs_pet_system(plan: GamePlan) -> bool:
    return any("pet" in s.lower() for s in plan.systems)


def _needs_boss_system(plan: GamePlan) -> bool:
    return any("boss" in s.lower() for s in plan.systems)


def render_config(plan: GamePlan, prompt: str) -> str:
    systems_lines = ",\n".join(f"  {luau_string(s)}" for s in plan.systems)

    # Conditionally add pet/boss config values
    extra_lines: list[str] = []
    if _needs_pet_system(plan):
        extra_lines.extend([
            "GameConfig.PetSpawnCost = 50",
            "GameConfig.PetBonusMin = 2",
            "GameConfig.PetBonusMax = 10",
        ])
    if _needs_boss_system(plan):
        extra_lines.extend([
            "GameConfig.BossHealth = 500",
            "GameConfig.BossHitDamage = 10",
            "GameConfig.BossReward = 200",
            "GameConfig.BossRespawnSeconds = 30",
        ])
    if plan.genre == "Racing":
        extra_lines.extend([
            "GameConfig.LapCount = 3",
            "GameConfig.SpeedBoostMultiplier = 1.5",
            "GameConfig.SpeedBoostDuration = 2",
            "GameConfig.SpeedUpgradeCost = 40",
            "GameConfig.LapReward = 25",
            "GameConfig.FinishReward = 100",
        ])
    if plan.genre == "RPG Adventure":
        extra_lines.extend([
            "GameConfig.XPReward = 10",
            "GameConfig.LevelUpXP = 50",
            "GameConfig.LevelUpStatBoost = 5",
            "GameConfig.GearCostMultiplier = 2",
            "GameConfig.ZoneUnlockCost = 100",
            "GameConfig.EnemyXPReward = 8",
            "GameConfig.EnemyCoinReward = 5",
        ])
    if plan.genre == "Custom Roblox Experience" or any(
        keyword in " ".join(plan.systems).lower()
        for keyword in ("npc", "quest", "vehicle", "reputation", "apartment", "survival")
    ):
        extra_lines.extend([
            "GameConfig.CustomObjectiveReward = 20",
            "GameConfig.ReputationReward = 5",
            "GameConfig.VehicleReward = 10",
            "GameConfig.ApartmentReward = 15",
            "GameConfig.ResourceReward = 4",
        ])

    extra_block = "\n".join(extra_lines) + "\n" if extra_lines else ""

    lines = [
        "-- Generated by Roblox AI Studio. Review before publishing.",
        "local GameConfig = {}",
        "",
        f"GameConfig.Title = {luau_string(plan.title)}",
        f"GameConfig.Genre = {luau_string(plan.genre)}",
        f"GameConfig.OriginalPrompt = {luau_string(prompt)}",
        "GameConfig.StartingCoins = 0",
        "GameConfig.CoinReward = 5",
        "GameConfig.CheckpointReward = 20",
        "GameConfig.UpgradeCost = 25",
        "GameConfig.TycoonDropReward = 10",
        "GameConfig.TrainingReward = 1",
        "GameConfig.BackpackCapacity = 10",
        "GameConfig.SellReward = 3",
        "GameConfig.BaseHealth = 100",
        "GameConfig.TowerCost = 30",
        "GameConfig.TowerDamage = 20",
        "GameConfig.EnemyReward = 15",
    ]
    if extra_block:
        lines.append("")
        lines.extend(extra_lines)

    lines.extend([
        "GameConfig.Systems = {",
        systems_lines,
        "}",
        "",
        "return GameConfig",
    ])

    return "\n".join(lines) + "\n"


def _server_prelude() -> str:
    return _luau_template(
        """
        -- Main server gameplay loop generated by Roblox AI Studio.
        -- Server owns rewards, parts, purchases, waves, and stats. Clients only receive replicated state.
        local Players = game:GetService("Players")
        local ReplicatedStorage = game:GetService("ReplicatedStorage")

        local GameConfig = require(ReplicatedStorage:WaitForChild("GameConfig"))
        local playerCooldowns = {}

        local function createStat(folder, className, name, value)
            local stat = Instance.new(className)
            stat.Name = name
            stat.Value = value
            stat.Parent = folder
            return stat
        end

        local function createLeaderstats(player)
            local leaderstats = Instance.new("Folder")
            leaderstats.Name = "leaderstats"
            leaderstats.Parent = player

            createStat(leaderstats, "IntValue", "Coins", GameConfig.StartingCoins)
            createStat(leaderstats, "IntValue", "Money", 0)
            createStat(leaderstats, "IntValue", "Checkpoint", 1)
            createStat(leaderstats, "IntValue", "Strength", 0)
            createStat(leaderstats, "IntValue", "Backpack", GameConfig.BackpackCapacity)
            createStat(leaderstats, "IntValue", "TycoonLevel", 1)
            createStat(leaderstats, "IntValue", "BaseHealth", GameConfig.BaseHealth)
            createStat(leaderstats, "IntValue", "Lap", 0)
            createStat(leaderstats, "IntValue", "SpeedLevel", 1)
            createStat(leaderstats, "IntValue", "XP", 0)
            createStat(leaderstats, "IntValue", "Level", 1)
            createStat(leaderstats, "IntValue", "Reputation", 0)
            createStat(leaderstats, "IntValue", "CustomObjective", 0)
        end

        local function getStat(player, name)
            local stats = player:FindFirstChild("leaderstats")
            return stats and stats:FindFirstChild(name)
        end

        local function addStat(player, name, amount)
            local stat = getStat(player, name)
            if stat then
                stat.Value += amount
            end
        end

        local function canUse(player, key, seconds)
            local now = os.clock()
            local playerKey = player.UserId .. ":" .. key
            if playerCooldowns[playerKey] and now - playerCooldowns[playerKey] < seconds then
                return false
            end
            playerCooldowns[playerKey] = now
            return true
        end

        local function makePart(folder, name, size, position, color)
            local part = Instance.new("Part")
            part.Name = name
            part.Size = size
            part.Position = position
            part.Anchored = true
            part.BrickColor = BrickColor.new(color)
            part.Parent = folder
            return part
        end

        local function rewardCoins(player, amount)
            addStat(player, "Coins", amount)
        end
        """
    )


def _common_upgrade_luau() -> str:
    return _luau_template(
        """
        local function createUpgradePad(folder, position)
            local pad = makePart(folder, "PrototypeUpgradePad", Vector3.new(10, 1, 10), position, "Lime green")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                if coins and coins.Value >= GameConfig.UpgradeCost and canUse(player, "upgrade", 1) then
                    coins.Value -= GameConfig.UpgradeCost
                    rewardCoins(player, GameConfig.CheckpointReward)
                end
            end)
        end
        """
    )


def _obby_luau() -> str:
    return _luau_template(
        """
        local function createCoin(folder, index, position)
            local coin = makePart(folder, "PrototypeCoin_" .. index, Vector3.new(3, 3, 3), position, "Bright yellow")
            coin.Shape = Enum.PartType.Ball
            coin.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and coin.CanTouch and canUse(player, coin.Name, 0.5) then
                    rewardCoins(player, GameConfig.CoinReward)
                    coin.Transparency = 1
                    coin.CanTouch = false
                    task.delay(4, function()
                        coin.Transparency = 0
                        coin.CanTouch = true
                    end)
                end
            end)
        end

        local function createCheckpoint(folder, index, position)
            local checkpoint = makePart(folder, "Checkpoint_" .. index, Vector3.new(12, 1, 12), position, "Bright blue")
            checkpoint.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local checkpointStat = player and getStat(player, "Checkpoint")
                if checkpointStat and index > checkpointStat.Value then
                    checkpointStat.Value = index
                    rewardCoins(player, GameConfig.CheckpointReward)
                end
            end)
            return checkpoint
        end

        local function buildPrototypeWorld()
            local folder = workspace:FindFirstChild("GeneratedGameplay") or Instance.new("Folder")
            folder.Name = "GeneratedGameplay"
            folder.Parent = workspace

            local spawnLocation = Instance.new("SpawnLocation")
            spawnLocation.Name = "RespawnLocation"
            spawnLocation.Size = Vector3.new(14, 1, 14)
            spawnLocation.Position = Vector3.new(0, 2, 0)
            spawnLocation.Anchored = true
            spawnLocation.BrickColor = BrickColor.new("Institutional white")
            spawnLocation.Parent = folder

            for index = 1, 6 do
                local platform = makePart(folder, "ChallengePlatform_" .. index, Vector3.new(14, 1, 14), Vector3.new(index * 18, index * 3, 0), "Bright orange")
                createCheckpoint(folder, index, platform.Position + Vector3.new(0, 1, 0))
                createCoin(folder, index, platform.Position + Vector3.new(0, 4, 0))
            end

            createUpgradePad(folder, Vector3.new(126, 22, 0))
        end
        """
    )


def _tycoon_luau() -> str:
    return _luau_template(
        """
        local function createDropper(folder, index, position)
            local dropper = makePart(folder, "Dropper_" .. index, Vector3.new(8, 6, 8), position, "Royal purple")
            task.spawn(function()
                while dropper.Parent do
                    task.wait(3)
                    for _, player in ipairs(Players:GetPlayers()) do
                        local level = getStat(player, "TycoonLevel")
                        addStat(player, "Money", GameConfig.TycoonDropReward * (level and level.Value or 1))
                    end
                end
            end)
        end

        local function createCollector(folder, position)
            local collector = makePart(folder, "CollectorPad", Vector3.new(12, 1, 12), position, "Bright yellow")
            collector.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local money = player and getStat(player, "Money")
                if money and money.Value > 0 and canUse(player, "collector", 1) then
                    rewardCoins(player, money.Value)
                    money.Value = 0
                end
            end)
        end

        local function createUpgradePad(folder, position)
            local pad = makePart(folder, "TycoonUpgradePad", Vector3.new(12, 1, 12), position, "Lime green")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                local level = player and getStat(player, "TycoonLevel")
                if coins and level and coins.Value >= GameConfig.UpgradeCost and canUse(player, "tycoonUpgrade", 1) then
                    coins.Value -= GameConfig.UpgradeCost
                    level.Value += 1
                end
            end)
        end

        local function buildPrototypeWorld()
            local folder = workspace:FindFirstChild("GeneratedGameplay") or Instance.new("Folder")
            folder.Name = "GeneratedGameplay"
            folder.Parent = workspace
            makePart(folder, "TycoonBase", Vector3.new(70, 1, 50), Vector3.new(30, 1, 0), "Dark stone grey")
            createDropper(folder, 1, Vector3.new(0, 5, -12))
            createDropper(folder, 2, Vector3.new(18, 5, -12))
            createCollector(folder, Vector3.new(40, 2, 0))
            createUpgradePad(folder, Vector3.new(58, 2, 0))
        end
        """
    )


def _simulator_luau() -> str:
    return _luau_template(
        """
        local function createTrainingZone(folder, index, position)
            local zone = makePart(folder, "TrainingZone_" .. index, Vector3.new(16, 1, 16), position, "Cyan")
            zone.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local strength = player and getStat(player, "Strength")
                local backpack = player and getStat(player, "Backpack")
                if strength and backpack and strength.Value < backpack.Value and canUse(player, zone.Name, 0.75) then
                    strength.Value += GameConfig.TrainingReward * index
                end
            end)
        end

        local function sellStrength(player)
            local strength = getStat(player, "Strength")
            if strength and strength.Value > 0 then
                rewardCoins(player, strength.Value * GameConfig.SellReward)
                strength.Value = 0
            end
        end

        local function createSellZone(folder, position)
            local zone = makePart(folder, "SellZone", Vector3.new(16, 1, 16), position, "Bright yellow")
            zone.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and canUse(player, "sell", 1) then
                    sellStrength(player)
                end
            end)
        end

        local function createUpgradePad(folder, position)
            local pad = makePart(folder, "BackpackUpgradePad", Vector3.new(12, 1, 12), position, "Lime green")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                local backpack = player and getStat(player, "Backpack")
                if coins and backpack and coins.Value >= GameConfig.UpgradeCost and canUse(player, "backpackUpgrade", 1) then
                    coins.Value -= GameConfig.UpgradeCost
                    backpack.Value += 10
                end
            end)
        end

        local function buildPrototypeWorld()
            local folder = workspace:FindFirstChild("GeneratedGameplay") or Instance.new("Folder")
            folder.Name = "GeneratedGameplay"
            folder.Parent = workspace
            createTrainingZone(folder, 1, Vector3.new(0, 2, 0))
            createTrainingZone(folder, 2, Vector3.new(22, 2, 0))
            createSellZone(folder, Vector3.new(44, 2, 0))
            createUpgradePad(folder, Vector3.new(66, 2, 0))
        end
        """
    )


def _tower_defense_luau() -> str:
    return _luau_template(
        """
        local towers = {}

        local function createEnemy(folder, wave, startPosition)
            local enemy = makePart(folder, "WaveEnemy_" .. wave .. "_" .. os.clock(), Vector3.new(4, 4, 4), startPosition, "Really red")
            local health = GameConfig.TowerDamage + (wave * 10)
            task.spawn(function()
                for step = 1, 10 do
                    task.wait(0.7)
                    for _, tower in ipairs(towers) do
                        if (tower.Position - enemy.Position).Magnitude < 35 then
                            health -= GameConfig.TowerDamage
                        end
                    end
                    if health <= 0 then
                        for _, player in ipairs(Players:GetPlayers()) do
                            rewardCoins(player, GameConfig.EnemyReward)
                        end
                        enemy:Destroy()
                        return
                    end
                    enemy.Position += Vector3.new(7, 0, 0)
                end
                for _, player in ipairs(Players:GetPlayers()) do
                    local baseHealth = getStat(player, "BaseHealth")
                    if baseHealth then
                        baseHealth.Value = math.max(0, baseHealth.Value - 10)
                    end
                end
                enemy:Destroy()
            end)
        end

        local function createTowerPad(folder, index, position)
            local pad = makePart(folder, "TowerPad_" .. index, Vector3.new(10, 1, 10), position, "Lime green")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                if coins and coins.Value >= GameConfig.TowerCost and not pad:FindFirstChild("TowerBuilt") and canUse(player, pad.Name, 1) then
                    coins.Value -= GameConfig.TowerCost
                    local marker = Instance.new("BoolValue")
                    marker.Name = "TowerBuilt"
                    marker.Parent = pad
                    local tower = makePart(folder, "PrototypeTower_" .. index, Vector3.new(5, 12, 5), position + Vector3.new(0, 7, 0), "Electric blue")
                    table.insert(towers, tower)
                end
            end)
        end

        local function startWaveLoop(folder)
            task.spawn(function()
                local wave = 1
                while folder.Parent do
                    for enemyIndex = 1, 3 + wave do
                        createEnemy(folder, wave, Vector3.new(-45, 4, enemyIndex * 6))
                        task.wait(1.5)
                    end
                    wave += 1
                    task.wait(8)
                end
            end)
        end

        local function buildPrototypeWorld()
            local folder = workspace:FindFirstChild("GeneratedGameplay") or Instance.new("Folder")
            folder.Name = "GeneratedGameplay"
            folder.Parent = workspace
            makePart(folder, "EnemyPath", Vector3.new(100, 1, 12), Vector3.new(0, 1, 12), "Dark stone grey")
            makePart(folder, "BaseCore", Vector3.new(14, 14, 14), Vector3.new(55, 8, 12), "Really blue")
            createTowerPad(folder, 1, Vector3.new(-10, 2, -8))
            createTowerPad(folder, 2, Vector3.new(18, 2, -8))
            startWaveLoop(folder)
        end
        """
    )


def _pet_luau() -> str:
    return _luau_template(
        """
        local PET_TYPES = {
            {name = "Cat", cost = 50, bonus = 2},
            {name = "Dog", cost = 100, bonus = 5},
            {name = "Dragon", cost = 250, bonus = 10},
        }

        local function createPetSpawn(folder, position)
            local pad = makePart(folder, "PetSpawnPad", Vector3.new(12, 1, 12), position, "Pink")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                if coins and coins.Value >= 50 and canUse(player, "petSpawn", 2) then
                    coins.Value -= 50
                    local ownedPets = player:FindFirstChild("OwnedPets")
                    if not ownedPets then
                        ownedPets = Instance.new("Folder")
                        ownedPets.Name = "OwnedPets"
                        ownedPets.Parent = player
                    end
                    local petType = PET_TYPES[math.random(1, #PET_TYPES)]
                    if petType.cost <= 50 then
                        local pet = Instance.new("IntValue")
                        pet.Name = "Pet_" .. petType.name
                        pet.Value = petType.bonus
                        pet.Parent = ownedPets
                        rewardCoins(player, petType.bonus)
                    end
                end
            end)
        end

        local function buildPetArea(folder)
            createPetSpawn(folder, Vector3.new(-20, 2, 0))
        end
        """
    )


def _boss_luau() -> str:
    return _luau_template(
        """
        local function createBossEncounter(folder, position)
            local boss = makePart(folder, "Boss", Vector3.new(10, 10, 10), position, "Really red")
            local bossHealth = Instance.new("IntValue")
            bossHealth.Name = "BossHealth"
            bossHealth.Value = 500
            bossHealth.Parent = boss
            boss.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and canUse(player, "bossHit", 0.5) then
                    bossHealth.Value -= 10
                    if bossHealth.Value <= 0 then
                        for _, p in ipairs(Players:GetPlayers()) do
                            rewardCoins(p, 200)
                        end
                        boss:Destroy()
                        task.delay(30, function()
                            createBossEncounter(folder, position)
                        end)
                    end
                end
            end)
        end

        local function buildBossArena(folder)
            createBossEncounter(folder, Vector3.new(0, 25, -30))
        end
        """
    )


def _generic_luau() -> str:
    return _luau_template(
        """
        local function createQuestNpc(folder, index, position)
            local npc = makePart(folder, "QuestNPC_" .. index, Vector3.new(5, 7, 5), position, "Bright blue")
            npc.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and canUse(player, npc.Name, 1) then
                    addStat(player, "CustomObjective", 1)
                    addStat(player, "Reputation", GameConfig.ReputationReward)
                    rewardCoins(player, GameConfig.CustomObjectiveReward)
                end
            end)
        end

        local function createVehiclePad(folder, index, position)
            local pad = makePart(folder, "VehiclePad_" .. index, Vector3.new(14, 1, 20), position, "Really black")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and canUse(player, pad.Name, 1) then
                    addStat(player, "Reputation", GameConfig.VehicleReward)
                    rewardCoins(player, GameConfig.VehicleReward)
                end
            end)
        end

        local function createApartmentHub(folder, position)
            local hub = makePart(folder, "ApartmentHub", Vector3.new(28, 18, 18), position, "Institutional white")
            hub.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and canUse(player, "apartmentHub", 1) then
                    addStat(player, "Reputation", GameConfig.ApartmentReward)
                    rewardCoins(player, GameConfig.ApartmentReward)
                end
            end)
        end

        local function createResourceNode(folder, index, position)
            local node = makePart(folder, "ResourceNode_" .. index, Vector3.new(6, 6, 6), position, "Earth green")
            node.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and canUse(player, node.Name, 1) then
                    addStat(player, "CustomObjective", 1)
                    rewardCoins(player, GameConfig.ResourceReward)
                end
            end)
        end

        local function buildPrototypeWorld()
            local folder = workspace:FindFirstChild("GeneratedGameplay") or Instance.new("Folder")
            folder.Name = "GeneratedGameplay"
            folder.Parent = workspace

            makePart(folder, "CustomExperienceHub", Vector3.new(70, 1, 70), Vector3.new(0, 1, 0), "Dark stone grey")
            createQuestNpc(folder, 1, Vector3.new(-20, 5, 0))
            createQuestNpc(folder, 2, Vector3.new(20, 5, 0))
            createVehiclePad(folder, 1, Vector3.new(0, 2, 26))
            createApartmentHub(folder, Vector3.new(0, 10, -28))
            createResourceNode(folder, 1, Vector3.new(-28, 4, 28))
            createUpgradePad(folder, Vector3.new(28, 2, 28))
        end
        """
    )


def _racing_luau() -> str:
    return _luau_template(
        """
        local currentLap = {}

        local function createSpeedBoost(folder, index, position)
            local boost = makePart(folder, "SpeedBoost_" .. index, Vector3.new(8, 1, 8), position, "Bright green")
            boost.Touched:Connect(function(hit)
                local character = hit.Parent
                local humanoid = character and character:FindFirstChild("Humanoid")
                if humanoid and canUse(hit, "boost_" .. index, 3) then
                    humanoid.WalkSpeed = humanoid.WalkSpeed * GameConfig.SpeedBoostMultiplier
                    task.delay(GameConfig.SpeedBoostDuration, function()
                        if humanoid and humanoid.Parent then
                            humanoid.WalkSpeed = 16
                        end
                    end)
                end
            end)
        end

        local function createLapCheckpoint(folder, index, position)
            local checkpoint = makePart(folder, "LapCheckpoint_" .. index, Vector3.new(14, 1, 14), position, "Bright yellow")
            checkpoint.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if not player or not canUse(player, "lapCheckpoint_" .. index, 0.75) then return end
                local lapStat = getStat(player, "Lap")
                if not lapStat then return end
                local lastCheckpoint = currentLap[player.UserId] or 0
                if index == lastCheckpoint + 1 then
                    currentLap[player.UserId] = index
                end
                if index == 4 and lastCheckpoint == 3 then
                    lapStat.Value += 1
                    currentLap[player.UserId] = 0
                    rewardCoins(player, GameConfig.LapReward)
                    if lapStat.Value >= GameConfig.LapCount then
                        rewardCoins(player, GameConfig.FinishReward)
                        lapStat.Value = 0
                    end
                end
            end)
        end

        local function createSpeedUpgradePad(folder, position)
            local pad = makePart(folder, "SpeedUpgradePad", Vector3.new(12, 1, 12), position, "Lime green")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                local speedStat = player and getStat(player, "SpeedLevel")
                if coins and speedStat and coins.Value >= GameConfig.SpeedUpgradeCost and canUse(player, "speedUpgrade", 1) then
                    coins.Value -= GameConfig.SpeedUpgradeCost
                    speedStat.Value += 1
                end
            end)
        end

        local function buildPrototypeWorld()
            local folder = workspace:FindFirstChild("GeneratedGameplay") or Instance.new("Folder")
            folder.Name = "GeneratedGameplay"
            folder.Parent = workspace

            local spawnLocation = Instance.new("SpawnLocation")
            spawnLocation.Name = "RaceStart"
            spawnLocation.Size = Vector3.new(20, 1, 14)
            spawnLocation.Position = Vector3.new(0, 2, 0)
            spawnLocation.Anchored = true
            spawnLocation.BrickColor = BrickColor.new("Institutional white")
            spawnLocation.Parent = folder

            createLapCheckpoint(folder, 1, Vector3.new(0, 2, 30))
            createSpeedBoost(folder, 1, Vector3.new(20, 2, 40))
            createLapCheckpoint(folder, 2, Vector3.new(50, 2, 40))
            createSpeedBoost(folder, 2, Vector3.new(70, 2, 30))
            createLapCheckpoint(folder, 3, Vector3.new(70, 2, -10))
            createSpeedBoost(folder, 3, Vector3.new(50, 2, -20))
            createLapCheckpoint(folder, 4, Vector3.new(20, 2, -10))
            createSpeedUpgradePad(folder, Vector3.new(-20, 2, 0))
        end
        """
    )


def _rpg_adventure_luau() -> str:
    return _luau_template(
        """
        local ZONES = {
            {name = "Forest", unlockCost = 0, enemyHealth = 30, enemyReward = 5},
            {name = "Cave", unlockCost = 100, enemyHealth = 60, enemyReward = 10},
            {name = "Volcano", unlockCost = 300, enemyHealth = 120, enemyReward = 25},
        }

        local function createEnemySpawn(folder, zoneIndex, position)
            local zone = ZONES[zoneIndex]
            local enemy = makePart(folder, "ZoneEnemy_" .. zoneIndex, Vector3.new(5, 5, 5), position, "Really red")
            enemy.Shape = Enum.PartType.Ball
            local enemyHP = Instance.new("IntValue")
            enemyHP.Name = "EnemyHP"
            enemyHP.Value = zone.enemyHealth
            enemyHP.Parent = enemy
            enemy.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                if player and canUse(player, "attack_" .. zoneIndex, 0.5) then
                    enemyHP.Value -= 10 + (getStat(player, "Level") and getStat(player, "Level").Value * 2 or 0)
                    if enemyHP.Value <= 0 and not enemy:GetAttribute("Defeated") then
                        enemy:SetAttribute("Defeated", true)
                        enemy.CanTouch = false
                        rewardCoins(player, zone.enemyReward)
                        addStat(player, "XP", GameConfig.EnemyXPReward)
                        local xpStat = getStat(player, "XP")
                        local levelStat = getStat(player, "Level")
                        if xpStat and levelStat and xpStat.Value >= GameConfig.LevelUpXP * levelStat.Value then
                            levelStat.Value += 1
                            xpStat.Value = 0
                            addStat(player, "Strength", GameConfig.LevelUpStatBoost)
                        end
                        enemy.Transparency = 1
                        enemy.CanCollide = false
                        task.delay(5, function()
                            if enemy and enemy.Parent then
                                enemy.Transparency = 0
                                enemy.CanCollide = true
                                enemy.CanTouch = true
                                enemy:SetAttribute("Defeated", false)
                                enemyHP.Value = zone.enemyHealth
                            end
                        end)
                    end
                end
            end)
        end

        local function createZoneUnlockPad(folder, zoneIndex, position)
            local zone = ZONES[zoneIndex]
            local pad = makePart(folder, "ZoneUnlock_" .. zone.name, Vector3.new(12, 1, 12), position, "Bright orange")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                if coins and zone.unlockCost > 0 and coins.Value >= zone.unlockCost and canUse(player, "zone_" .. zoneIndex, 1) then
                    coins.Value -= zone.unlockCost
                    rewardCoins(player, 10)
                end
            end)
        end

        local function createGearShopPad(folder, position)
            local pad = makePart(folder, "GearShopPad", Vector3.new(12, 1, 12), position, "Lime green")
            pad.Touched:Connect(function(hit)
                local player = Players:GetPlayerFromCharacter(hit.Parent)
                local coins = player and getStat(player, "Coins")
                local level = player and getStat(player, "Level")
                if coins and level and coins.Value >= GameConfig.UpgradeCost * GameConfig.GearCostMultiplier and canUse(player, "gearShop", 1) then
                    coins.Value -= GameConfig.UpgradeCost * GameConfig.GearCostMultiplier
                    addStat(player, "Strength", GameConfig.LevelUpStatBoost * 2)
                end
            end)
        end

        local function buildPrototypeWorld()
            local folder = workspace:FindFirstChild("GeneratedGameplay") or Instance.new("Folder")
            folder.Name = "GeneratedGameplay"
            folder.Parent = workspace

            createEnemySpawn(folder, 1, Vector3.new(0, 4, 20))
            createZoneUnlockPad(folder, 2, Vector3.new(40, 2, 20))
            createEnemySpawn(folder, 2, Vector3.new(40, 4, 40))
            createZoneUnlockPad(folder, 3, Vector3.new(80, 2, 20))
            createEnemySpawn(folder, 3, Vector3.new(80, 4, 40))
            createGearShopPad(folder, Vector3.new(-20, 2, 0))
        end
        """
    )


def _service_module_luau(service_name: str, description: str) -> str:
    return _luau_template(
        f"""
        -- {service_name} generated by Roblox AI Studio.
        -- {description}
        local Service = {{}}
        Service.Name = {luau_string(service_name)}

        function Service.Start(context)
            Service.Context = context
            print("[Roblox AI Studio] Started service:", Service.Name)
        end

        return Service
        """
    )


SERVICE_MODULES = {
    "PlayerDataService": "Owns leaderstats/player lifecycle setup hooks for generated prototypes.",
    "RewardService": "Keeps economy/reward logic isolated from world-building code.",
    "WorldService": "Owns generated prototype world assembly hooks.",
}


def render_service_module(service_name: str) -> str:
    return _service_module_luau(service_name, SERVICE_MODULES[service_name])


def render_server(plan: GamePlan) -> str:
    if plan.genre == "Tycoon":
        body = _tycoon_luau()
    elif plan.genre == "Simulator":
        body = _simulator_luau()
    elif plan.genre == "Tower Defense":
        body = _tower_defense_luau()
    elif plan.genre == "Obstacle Course / Obby":
        body = _obby_luau()
    elif plan.genre == "Racing":
        body = _racing_luau()
    elif plan.genre == "RPG Adventure":
        body = _rpg_adventure_luau()
    else:
        body = _generic_luau()

    # Append pet and/or boss Luau blocks when the plan requests them
    extras: list[str] = []
    if _needs_pet_system(plan):
        extras.append(_pet_luau())
    if _needs_boss_system(plan):
        extras.append(_boss_luau())

    # Patch buildPrototypeWorld to also call pet/boss builders when present
    pet_call = "\n buildPetArea(folder)" if _needs_pet_system(plan) else ""
    boss_call = "\n buildBossArena(folder)" if _needs_boss_system(plan) else ""

    # If we have extras, declare their helper functions before buildPrototypeWorld
    # so injected calls resolve to local functions at runtime in Luau.
    if extras:
        extra_code = "\n".join(extras)
        world_anchor = "folder.Parent = workspace"
        if world_anchor in body:
            body = body.replace(
                world_anchor,
                world_anchor + pet_call + boss_call,
                1,
            )
    else:
        extra_code = ""

    service_bootstrap = _luau_template(
        """
        local Services = script.Parent:WaitForChild("Services")
        local PlayerDataService = require(Services:WaitForChild("PlayerDataService"))
        local RewardService = require(Services:WaitForChild("RewardService"))
        local WorldService = require(Services:WaitForChild("WorldService"))

        local ServiceContext = {
            GameConfig = GameConfig,
        }

        PlayerDataService.Start(ServiceContext)
        RewardService.Start(ServiceContext)
        WorldService.Start(ServiceContext)
        """
    )

    return (
        _server_prelude()
        + "\n"
        + service_bootstrap
        + "\n"
        + ("" if "local function createUpgradePad" in body else _common_upgrade_luau())
        + "\n"
        + (extra_code + "\n" if extra_code else "")
        + body
 + "\n"
 + "Players.PlayerAdded:Connect(function(player)\n"
 + "  createLeaderstats(player)\n"
 + "end)\n"
 + "\n"
 + "buildPrototypeWorld()\n"
 + 'print("Roblox AI Studio generated project loaded:", GameConfig.Title)\n'
 ).rstrip() + "\n"


def render_hud() -> str:
    return _luau_template(
        """
        -- Starter HUD script generated by Roblox AI Studio.
        local Players = game:GetService("Players")
        local player = Players.LocalPlayer

        local screenGui = Instance.new("ScreenGui")
        screenGui.Name = "RobloxAIStudioHUD"
        screenGui.ResetOnSpawn = false
        screenGui.Parent = player:WaitForChild("PlayerGui")

        local label = Instance.new("TextLabel")
        label.Size = UDim2.fromOffset(620, 72)
        label.Position = UDim2.fromOffset(20, 20)
        label.BackgroundTransparency = 0.2
        label.BackgroundColor3 = Color3.fromRGB(25, 25, 35)
        label.TextColor3 = Color3.fromRGB(255, 255, 255)
        label.TextScaled = true
        label.Text = "Roblox AI Studio Prototype"
        label.Parent = screenGui

        local function valueOf(stats, name, fallback)
            local stat = stats and stats:FindFirstChild(name)
            return stat and stat.Value or fallback
        end

        local function update()
            local stats = player:FindFirstChild("leaderstats")
            label.Text = string.format(
                "Coins: %s | Money: %s | Checkpoint: %s | Strength: %s | Backpack: %s | Base: %s\\nLap: %s | Speed: %s | XP: %s | Level: %s",
                valueOf(stats, "Coins", 0),
                valueOf(stats, "Money", 0),
                valueOf(stats, "Checkpoint", 1),
                valueOf(stats, "Strength", 0),
                valueOf(stats, "Backpack", 0),
                valueOf(stats, "BaseHealth", 0),
                valueOf(stats, "Lap", 0),
                valueOf(stats, "SpeedLevel", 1),
                valueOf(stats, "XP", 0),
                valueOf(stats, "Level", 1)
            )
        end

        player.ChildAdded:Connect(update)
        task.spawn(function()
            while task.wait(0.5) do
                update()
            end
        end)
        """
    ).strip() + "\n"


def render_project_json(plan: GamePlan) -> str:
    return json.dumps(
        {
            "name": plan.slug,
            "servePort": 34872,
            "globIgnorePaths": ["**/*.spec.luau", "Packages/**"],
            "tree": {
                "$className": "DataModel",
                "ReplicatedStorage": {
                    "$className": "ReplicatedStorage",
                    "$path": "src/ReplicatedStorage",
                },
                "ServerScriptService": {
                    "$className": "ServerScriptService",
                    "$path": "src/ServerScriptService",
                },
                "StarterPlayer": {
                    "$className": "StarterPlayer",
                    "StarterPlayerScripts": {
                        "$className": "StarterPlayerScripts",
                        "$path": "src/StarterPlayer/StarterPlayerScripts",
                    },
                },
            },
        },
        indent=2,
    ) + "\n"


def render_wally_toml(plan: GamePlan) -> str:
    package_name = f"playro/{plan.slug}"[:80].rstrip("-")
    lines = [
        "[package]",
        f"name = {json.dumps(package_name)}",
        'version = "0.1.0"',
        'registry = "https://github.com/UpliftGames/wally-index"',
        'realm = "shared"',
        "",
        "[dependencies]",
        "# Add Roblox packages here as this prototype grows.",
        "# Fusion = \"elttob/fusion@0.3.0\"",
        "# FastCastRedux = \"encodedvenom/fastcastredux@0.1.3\"",
        "",
        "# Knit is intentionally not included by default because upstream Knit is archived.",
        "# Prefer Playro-generated service modules or pin a maintained framework before publishing.",
    ]
    return "\n".join(lines) + "\n"


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


# Fixed-size striped locks serialize writes without retaining one lock per historical project path.
_PROJECT_WRITE_LOCK_STRIPES = tuple(threading.Lock() for _ in range(256))


def _project_write_lock(target: Path) -> threading.Lock:
    key = str(target.resolve(strict=False))
    return _PROJECT_WRITE_LOCK_STRIPES[hash(key) % len(_PROJECT_WRITE_LOCK_STRIPES)]


def _resolve_project_target(output_root: Path, slug: str, target_dir: Path | None) -> Path:
    output_root_resolved = output_root.resolve(strict=False)
    target = (target_dir if target_dir is not None else output_root / slug).resolve(strict=False)
    if target == output_root_resolved:
        raise ValueError("target_dir must point to a project directory, not output_root")
    try:
        target.relative_to(output_root_resolved)
    except ValueError as exc:
        raise ValueError("target_dir must be inside output_root") from exc
    return target


def _replace_ready_project(staging: Path, target: Path) -> None:
    backup: Path | None = None
    if target.exists():
        backup = target.with_name(f".{target.name}.backup-{uuid4().hex}")
        target.rename(backup)
    try:
        staging.rename(target)
    except Exception:
        if backup and backup.exists() and not target.exists():
            backup.rename(target)
        raise
    if backup and backup.exists():
        try:
            _remove_path(backup)
        except OSError as exc:
            logger.warning("Failed to remove Playro project backup %s: %s", backup, exc)


def write_project(
    prompt: str,
    output_root: Path,
    refinement_prompt: str | None = None,
    build_metadata: dict | None = None,
    target_dir: Path | None = None,
) -> Path:
    plan = plan_from_prompt(prompt)
    if refinement_prompt:
        plan = refine_plan(plan, refinement_prompt)
    target = _resolve_project_target(output_root, plan.slug, target_dir)
    with _project_write_lock(target):
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}.tmp-"))
        try:
            (staging / "src" / "ServerScriptService" / "Services").mkdir(parents=True, exist_ok=True)
            (staging / "src" / "ReplicatedStorage").mkdir(parents=True, exist_ok=True)
            (staging / "src" / "StarterPlayer" / "StarterPlayerScripts").mkdir(parents=True, exist_ok=True)

            manifest = asdict(plan) | {
                "original_prompt": prompt,
                "refinement_prompt": refinement_prompt,
                "generator": "Roblox AI Studio local prototype",
                "rojo_project_file": "default.project.json",
                "playable_status": "Open with Rojo/Roblox Studio or copy scripts into matching services.",
                "authority_model": "server-authoritative prototype mechanics; clients display HUD only",
                "prompt_fidelity": build_prompt_fidelity(prompt, plan.systems),
            }
            if build_metadata:
                manifest.update(build_metadata)
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            (staging / "default.project.json").write_text(render_project_json(plan), encoding="utf-8")
            (staging / "wally.toml").write_text(render_wally_toml(plan), encoding="utf-8")
            (staging / "src" / "ReplicatedStorage" / "GameConfig.lua").write_text(
                render_config(plan, prompt),
                encoding="utf-8",
            )
            (staging / "src" / "ServerScriptService" / "Main.server.lua").write_text(
                render_server(plan),
                encoding="utf-8",
            )
            for service_name in SERVICE_MODULES:
                (staging / "src" / "ServerScriptService" / "Services" / f"{service_name}.lua").write_text(
                    render_service_module(service_name),
                    encoding="utf-8",
                )
            (staging / "src" / "StarterPlayer" / "StarterPlayerScripts" / "HUD.client.lua").write_text(
                render_hud(),
                encoding="utf-8",
            )
            (staging / "game_plan.md").write_text(render_plan_markdown(plan, prompt, refinement_prompt), encoding="utf-8")
            (staging / "README.md").write_text(render_project_readme(plan), encoding="utf-8")
            _replace_ready_project(staging, target)
        except Exception:
            if staging.exists():
                _remove_path(staging)
            raise
    return target


def render_plan_markdown(plan: GamePlan, prompt: str, refinement_prompt: str | None = None) -> str:
 systems = "\n".join(f"- {s}" for s in plan.systems)
 hooks = "\n".join(f"- {h}" for h in plan.iteration_hooks)
 scripts = "\n".join(f"- `{s}`" for s in plan.scripts)
 refinement = f"\nRefinement prompt:\n\n> {refinement_prompt}\n" if refinement_prompt else ""

 lines = [
 f"# {plan.title}",
 "",
 "Original prompt:",
 "",
 f"> {prompt}",
 refinement,
 f"Genre: {plan.genre}",
 "",
 "## Core loop",
 "",
 plan.loop,
 "",
 "## Generated systems",
 "",
 systems,
 "",
 "## Generated files",
 "",
 scripts,
 "- `default.project.json`",
 "",
 "## Playability notes",
 "",
 "- Server scripts create prototype parts and own rewards/purchases/waves.",
 "- Client HUD is read-only and shows replicated leaderstats.",
 "- Generated Luau is intentionally beginner-readable and avoids trusting RemoteEvents.",
 "",
 "## Iteration hooks",
 "",
 hooks,
 ]
 return "\n".join(line for line in lines if line or True).strip() + "\n"


def render_project_readme(plan: GamePlan) -> str:
 lines = [
 f"# {plan.title}",
 "",
 "Generated by Roblox AI Studio local prototype.",
 "",
 "## How to inspect in Roblox Studio",
 "",
 "Option A: Rojo",
 "1. Install Rojo if needed.",
 "2. From this generated project folder, run `rojo serve default.project.json`.",
 "3. In Roblox Studio, connect with the Rojo plugin.",
 "4. Optional: if you add uncommented package dependencies in `wally.toml`, run `wally install` before serving.",
 "5. Press Play and try the generated loop: prompt-specific objectives, rewards, NPCs, vehicles, shops, or specialized mechanics depending on the idea.",
 "",
 "Option B: manual copy",
 "- Copy `src/ReplicatedStorage/GameConfig.lua` into ReplicatedStorage as ModuleScript `GameConfig`.",
 "- Copy `src/ServerScriptService/Main.server.lua` into ServerScriptService as Script `Main`.",
 "- Copy every file in `src/ServerScriptService/Services/` into ServerScriptService > Services as ModuleScripts.",
 "- Copy `src/StarterPlayer/StarterPlayerScripts/HUD.client.lua` into StarterPlayer > StarterPlayerScripts as LocalScript `HUD`.",
 "",
 "## Files",
 "",
 "- `default.project.json`: Rojo project mapping",
 "- `src/ReplicatedStorage/GameConfig.lua`: generated config module",
 "- `src/ServerScriptService/Main.server.lua`: server-authoritative prototype systems",
 "- `src/ServerScriptService/Services/*.lua`: beginner-readable service modules for lifecycle, rewards, and world-building hooks",
 "- `src/StarterPlayer/StarterPlayerScripts/HUD.client.lua`: starter client HUD",
 "- `game_plan.md`: design plan from the prompt",
 "- `manifest.json`: generation metadata",
 ]
 return "\n".join(lines).strip() + "\n"
