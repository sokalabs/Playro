# Playro Rojo + Roblox Studio Acceptance Test

Use this on a real Windows desktop/VM with Roblox Studio installed. This verifies the part a Linux/headless build machine cannot prove: Rojo live sync and Studio playtest.

## Prerequisites

- Windows user is the same user who will run Playro and Roblox Studio.
- Roblox Studio is installed and logged in.
- Rojo CLI is installed:
  ```powershell
  winget install --id Rojo.Rojo --exact --accept-source-agreements --accept-package-agreements
  rojo --version
  ```
- Rojo Studio plugin is installed for the same user:
  ```powershell
  rojo plugin install
  dir "$env:LOCALAPPDATA\Roblox\Plugins\RojoManagedPlugin.rbxm"
  ```
- Restart Roblox Studio after plugin install.

## Test flow

1. Install or open the latest `Playro Setup 1.0.0.exe` / `Playro 1.0.0.exe`.
2. Generate a game with this prompt:
   ```text
   Make a neon obby with checkpoints, coins, moving platforms, pets, and a shop
   ```
3. Wait until Playro shows generated files and handoff buttons.
4. Click **Start Rojo & Open Studio**.
5. Expected Playro behavior:
   - Starts `rojo serve "<project>\default.project.json"` if Rojo is available.
   - Opens the generated project folder.
   - Attempts to launch Roblox Studio if `RobloxStudioBeta.exe` is detected.
   - Copies both commands to clipboard:
     ```powershell
     rojo serve "<project>\default.project.json"
     rojo build "<project>\default.project.json" --output "<project>\playro-studio-export.rbxlx"
     ```
6. In Studio, use the Rojo plugin to connect to the running localhost server.
7. Confirm Explorer contains generated services/scripts:
   - `ReplicatedStorage > GameConfig`
   - `ServerScriptService > Main`
   - `StarterPlayer > StarterPlayerScripts > HUD`
8. Press **Play**.
9. Open Developer Console with `F9`.
10. Pass criteria:
    - Avatar spawns.
    - Generated HUD/leaderstats are visible.
    - Output includes generated project loaded log.
    - No Luau syntax/runtime errors such as malformed HUD string.

## Deterministic fallback if live Rojo plugin does not connect

If the plugin cannot connect but Rojo CLI works, build a Studio file:

```powershell
cd "<generated-project-folder>"
rojo sourcemap default.project.json --output sourcemap.json
rojo build default.project.json --output playro-studio-export.rbxlx
start .\playro-studio-export.rbxlx
```

Then repeat the Studio Play + F9 Developer Console checks above.

## Capture on failure

Send back:

```powershell
rojo --version
where rojo
dir "$env:LOCALAPPDATA\Roblox\Plugins"
dir "<generated-project-folder>"
Get-Content "<generated-project-folder>\src\StarterPlayer\StarterPlayerScripts\HUD.client.lua" -Raw
Get-Content "<generated-project-folder>\src\ServerScriptService\Main.server.lua" -Raw | Select-Object -First 120
```

Also include screenshots of:
- Playro handoff result/toast
- Rojo plugin panel
- Studio Explorer
- F9 Developer Console
