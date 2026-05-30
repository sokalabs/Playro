# Roblox Game Generation Skill Seed

Purpose: product-local seed skill for turning a game prompt into a Roblox project.

## Steps

1. Classify Roblox genre from the prompt.
2. Extract requested systems: economy, checkpoints, shop, pets, enemies, quests, waves, teams.
3. Produce a short game plan with core loop and systems.
4. Generate reviewable Luau files:
   - shared config ModuleScript
   - server-authoritative gameplay Script
   - client HUD LocalScript
5. Generate Rojo `default.project.json`.
6. Record original prompt, refinements, generated files, and product boundary in manifest.
7. Suggest one next refinement.

## Safety

- Never trust client input for economy or rewards.
- Keep generated scripts readable and beginner-editable.
- Do not include unrelated Hermes live tools or machine-specific integrations.
