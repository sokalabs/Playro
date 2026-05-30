# Playro Sprint Sample Projects

These sample Roblox projects were generated with the product CLI (`python3 -m product.roblox_ai_studio.app.cli`) for clone-testable sprint validation.

## Generation prompts

1. `make a lava obby with moving platforms checkpoints and coin pickups`
2. `make a co-op tower defense with enemy waves base health and tower purchase pads`

## Sample project folders

- `make-a-lava-obby-with-moving-platforms-checkpoints-and-coin`
- `make-a-co-op-tower-defense-with-enemy-waves-base-health-and`

Each sample includes:
- `default.project.json` (Rojo mapping)
- `manifest.json` (prompt + systems + loop)
- `src/ReplicatedStorage/GameConfig.lua`
- `src/ServerScriptService/Main.server.lua`
- `src/StarterPlayer/StarterPlayerScripts/HUD.client.lua`
- `README.md` and `game_plan.md`

## Expected playable mechanics

### Lava Obby sample
- Server-spawned obby platforms and checkpoints
- Coin pickups and checkpoint rewards
- Upgrade pad loop for repeated progression

### Co-op Tower Defense sample
- Server-spawned enemy waves toward a base
- Shared base health reduction on leaks
- Tower purchase pads and tower damage loop

## Smoke validation

Run:

```bash
python3 -m product.roblox_ai_studio.app.sample_validation --samples-root product/roblox_ai_studio/generated_projects/sprint_samples --min-projects 2
```

The command validates sample count, required files, Rojo paths in `default.project.json`, and basic Luau structure markers.
