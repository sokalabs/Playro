# Playro Windows 11 Acceptance Test

Use this checklist when validating the packaged Windows build on a real Windows 11 machine or VM.

## Target release

Use the current beta handoff and release notes for exact tag, download URLs, and SHA-256 hashes:

- `product/roblox_ai_studio/desktop/release/BETA_TESTER_HANDOFF_v1.0.3.md`
- `product/roblox_ai_studio/desktop/release/RELEASE_NOTES_v1.0.3.md`

## Checksums

Verify the downloaded file before testing. Use the expected SHA-256 values from the beta handoff or release notes.

### PowerShell verify command

```powershell
Get-FileHash .\Playro.Setup.<version>.exe -Algorithm SHA256
Get-FileHash .\Playro.<version>.exe -Algorithm SHA256
```

## Preconditions

Install these before validating the full creator workflow:

1. Roblox Studio
   - https://create.roblox.com/
2. Rojo CLI
   - `winget install --id Rojo.Rojo --exact`
3. Rojo Studio plugin
   - from the Rojo docs: https://rojo.space/docs/v7/getting-started/installation/

## Acceptance checklist

### 1. Install / launch

- [ ] Download the current `Playro.Setup.<version>.exe` from the beta handoff
- [ ] Verify SHA-256 matches
- [ ] Run the installer
- [ ] Launch Playro from Start Menu or desktop shortcut
- [ ] Confirm the main window opens without crashing
- [ ] For production builds, confirm the installer publisher is SokaLabs and no `Unknown publisher` prompt appears
- [ ] For internal/test builds only, confirm any Windows Defender / SmartScreen prompt is documented as unsigned-build trust friction, not a runtime crash

### 2. Backend auto-start

- [ ] Wait for the app to finish loading
- [ ] Confirm the desktop UI does **not** stay stuck in offline mode
- [ ] In PowerShell, verify the local backend responds:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/health | Select-Object -ExpandProperty Content
```

Expected result: a healthy JSON response from the local backend.

### 3. Generate a starter project

Inside Playro:

- [ ] Enter a prompt such as: `make a colorful obby with checkpoints, coins, and a shop`
- [ ] Start generation
- [ ] Confirm a new project appears in history
- [ ] Confirm artifact/build panels populate

Expected generated files include:

- `default.project.json`
- `game_plan.md`
- `manifest.json`
- `src/ServerScriptService/Main.server.lua`
- `src/ReplicatedStorage/GameConfig.lua`
- `src/StarterPlayer/StarterPlayerScripts/HUD.client.lua`
- `README.md`

### 4. Verify project output location

The packaged Windows app should write projects to a user-writable shared folder, not the install directory.

- [ ] From Playro, open the generated project folder if the UI offers it
- [ ] Or inspect under `C:\Users\Public\Documents\Playro\playro-data`
- [ ] Confirm generated project files are not being written under `Program Files` or the app install directory

### 5. Verify Rojo flow

- [ ] Use the in-app Rojo setup/install button if shown
- [ ] If auto-install is unavailable, run:

```powershell
winget install --id Rojo.Rojo --exact
```

- [ ] Confirm Playro detects Rojo after install
- [ ] Use the Playro action that starts Rojo / opens Studio
- [ ] Confirm `rojo serve default.project.json` starts successfully

### 6. Verify Roblox Studio handoff

- [ ] Open Roblox Studio
- [ ] Connect with the Rojo plugin
- [ ] Confirm the generated place tree appears
- [ ] Press Play in Studio
- [ ] Confirm the starter experience loads without immediate script errors blocking first-run

## If something fails

Capture all of these:

1. Screenshot of the Playro window
2. Screenshot of the PowerShell error or Windows prompt
3. Exact step number from this checklist
4. If backend health fails, include:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/health
```

5. If Rojo fails, include:

```powershell
rojo --version
rojo serve default.project.json
```

## Pass criteria

The packaged Windows app is validated when all of these are true:

- Playro installs and launches on Windows 11
- backend auto-start works on `127.0.0.1:8765`
- a project can be generated from the desktop UI
- output lands in a user-writable Playro data directory
- Rojo setup works
- the generated project can be opened in Roblox Studio and used as a starting point
