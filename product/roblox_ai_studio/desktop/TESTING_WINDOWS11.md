# Playro Windows 11 Acceptance Test

Use this checklist when validating the packaged Windows build on a real Windows 11 machine or VM.

## Target release

Use the current beta handoff and release notes for exact tag, download URLs, and SHA-256 hashes. These files are generated at release time under `product/roblox_ai_studio/desktop/release/` by `npm run release:manifest` and `npm run release:notes`, named for the current `package.json` version (currently `1.0.4`), e.g.:

- `product/roblox_ai_studio/desktop/release/RELEASE_NOTES_v1.0.4.md`

If the `release/` directory is not present in your checkout, generate it from a packaged build with `npm run release:manifest` then `npm run release:notes`.

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

### 2. First-launch headless provisioning

First-launch provisioning is **fully automatic and headless** — there is no consent wizard, no required clicks, and no setup gate to approve. The setup screen is progress-only and auto-advances.

- [ ] On first launch, confirm the setup screen shows **progress only** (streamed steps), with no button you must click to proceed
- [ ] Confirm provisioning **auto-advances** to the main app once dependencies are ready
- [ ] Confirm **no terminal / console window** flashes or stays open during provisioning (child processes spawn with hidden windows)
- [ ] After provisioning, confirm the engine home exists and is populated:
  - bundled-engine path: `%LOCALAPPDATA%\playro\hermes`
- [ ] Confirm env was written programmatically (no manual editing was required):

```powershell
Test-Path "$env:LOCALAPPDATA\playro\hermes\.env"
```

> Provisioning prefers the bundled product-local Playro AI Engine. If a build ships **without** the bundle, provisioning falls back to the packaged local Roblox generator and runs **no** remote installer. The official Hermes remote installer is opt-in only — it runs (over HTTPS) to pull Git/uv/Python 3.11+ into the engine home **only** when an operator sets `PLAYRO_ENABLE_REMOTE_HERMES_INSTALL=1`. See the **Security note** below.

### 3. Backend auto-start

- [ ] Wait for the app to finish loading
- [ ] Confirm the desktop UI does **not** stay stuck in offline mode
- [ ] In PowerShell, verify the local backend responds:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/health | Select-Object -ExpandProperty Content
```

Expected result: a healthy JSON response from the local backend.

### 4. Generate a starter project

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

### 5. Verify project output location

The packaged Windows app should write projects to a user-writable shared folder, not the install directory.

- [ ] From Playro, open the generated project folder if the UI offers it
- [ ] Or inspect under `C:\Users\Public\Documents\Playro\playro-data`
- [ ] Confirm generated project files are not being written under `Program Files` or the app install directory

### 6. Verify Rojo flow

- [ ] Use the in-app Rojo setup/install button if shown
- [ ] If auto-install is unavailable, run:

```powershell
winget install --id Rojo.Rojo --exact
```

- [ ] Confirm Playro detects Rojo after install
- [ ] Use the Playro action that starts Rojo / opens Studio
- [ ] Confirm `rojo serve default.project.json` starts successfully

### 7. Verify Roblox Studio handoff

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
- first-launch provisioning is headless: progress-only, auto-advancing, no required clicks, and no visible terminal windows
- backend auto-start works on `127.0.0.1:8765`
- a project can be generated from the desktop UI
- output lands in a user-writable Playro data directory
- Rojo setup works
- the generated project can be opened in Roblox Studio and used as a starting point

## Headless / CI runs

For unattended acceptance runs, set the environment flags before launch:

- `PLAYRO_HEADLESS=1` — suppress all spawned windows (use for CI; prevents any provisioning UI from blocking an automated run).
- `PLAYRO_ALLOW_LOCAL_GENERATOR=1` — skip engine provisioning and use the packaged local Roblox generator fallback (dev/test only; not a substitute for validating the real engine path).
- `PLAYRO_ENABLE_REMOTE_HERMES_INSTALL=1` — opt in to the official Hermes remote installer fallback. Off by default; leave unset to keep a no-remote-execution posture.

The automated acceptance smoke is:

```powershell
npm run smoke:windows-acceptance
```

## Security note

Remote installer execution is **disabled by default** and **opt-in only**. When a build ships **without** the bundled product-local Playro AI Engine, first-launch provisioning uses the packaged local Roblox generator and runs **no** remote script. Only when an operator explicitly sets `PLAYRO_ENABLE_REMOTE_HERMES_INSTALL=1` does Playro run the official Hermes install script (over HTTPS) to pull Git/uv/Python 3.11+ into `~/.playro/hermes`.

What is and is not trusted (when the opt-in flag is set):

- The installer source is pinned to the **official Hermes installer** and fetched over **HTTPS**. Playro does not run an arbitrary or user-supplied install URL.
- The bundled engine is always preferred; the remote fallback only runs when no bundle is present **and** the opt-in flag is set.
- Loopback hardening is unchanged: the backend binds to `127.0.0.1:8765`, every API call carries the per-session loopback API token, and the origin allowlist remains in force.

The default build has a no-remote-execution posture out of the box (the flag is unset). To additionally validate full offline provisioning, test a build whose `vendor/playro-engine/` bundle was populated (`npm run prepare:engine-bundle`) and confirm provisioning completes with networking disabled.
