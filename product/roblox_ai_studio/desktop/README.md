# Playro Desktop

Electron desktop shell for the Playro Roblox game builder.

## Zero-touch Windows provisioning

First launch on Windows is now **fully automatic and headless**. There is no consent wizard, no required clicks, and no setup gate the user has to approve. The setup window is progress-only: it streams provisioning status over the `playro-setup-progress` IPC channel and auto-advances to the main app once dependencies are ready.

What happens on first launch:

- **Bundled engine first.** Provisioning prefers the product-local Playro AI Engine staged under `vendor/playro-engine/` and packaged into `resources/playro-engine/`. When present, it is copied into the product-local app-data engine home (`~/.playro/hermes`, or `%LOCALAPPDATA%\playro\hermes` on Windows) with no network access.
- **Local generator fallback by default.** When no bundled engine is present, provisioning falls back to the packaged local Roblox generator — it does **not** download or run any remote installer. An operator can opt in to the official Hermes remote installer (see the Security note) to instead pull Git, uv, and Python 3.11+ into the Hermes home (`~/.playro/hermes`).
- **Hidden console windows.** Every child process Playro spawns during provisioning (the installer, Rojo install, the backend) is launched with `windowsHide` so no terminal flashes or lingers on screen.
- **Programmatic env.** Required environment is written programmatically to `~/.playro/hermes/.env`; the user never has to edit a file by hand.

The IPC contract is unchanged: `check-setup`, `install-hermes-runtime`, `prompt-install-hermes-runtime`, `start-full-setup`, `skip-playro-setup`, and the `hermes-install-progress` / `playro-setup-progress` progress channels are the same as before — only their behavior is now headless and auto-advancing.

### Environment flags

- `PLAYRO_HEADLESS=1` — suppress all spawned windows (used for CI and unattended runs).
- `PLAYRO_ALLOW_LOCAL_GENERATOR=1` — skip engine provisioning and use the packaged local Roblox generator fallback (intended for dev/test).
- `PLAYRO_ENABLE_REMOTE_HERMES_INSTALL=1` — opt in to the official Hermes remote installer fallback. **Off by default**; when unset, Playro never downloads or executes a remote install script (see the Security note).

### Security note

Remote installer execution is **disabled by default** and **opt-in only**. When no trusted product-local engine bundle is present, Playro uses the local generator fallback and never downloads or runs a remote script. Only when an operator explicitly sets `PLAYRO_ENABLE_REMOTE_HERMES_INSTALL=1` does Playro run the official Hermes install script to provision Git/uv/Python.

Honest tradeoffs (apply only when the opt-in flag is set):

- The installer source is pinned to the **official Hermes installer** and fetched over **HTTPS**. Playro does not execute an arbitrary or user-supplied install URL.
- The bundled product-local engine is always preferred; the remote installer only runs when no bundle is present **and** the opt-in flag is set.
- Main never runs the installer unprompted — the remote path is reachable only through the explicit opt-in.
- The existing loopback hardening is unchanged: the backend binds to `127.0.0.1:8765`, every API call carries the per-session loopback API token (`PLAYRO_API_TOKEN`), and the origin allowlist (`PLAYRO_ALLOWED_ORIGINS`) remains in force.

The default build therefore has a no-remote-execution posture out of the box. Ship a build with the product-local engine bundle populated (`npm run prepare:engine-bundle`) to provide the full engine offline as well.

## Local checks

```bash
cd product/roblox_ai_studio/desktop
npm run check
npm run smoke
npm run build:win
npm run verify:packaged
npm run release:manifest
npm run release:notes
npm run release:sell-check
# For production direct-download EXEs, use npm run release:win:production instead of build:win:test.
```

`refinement-flow-smoke.js` exercises the important submit loop without a live backend:

1. render the landing prompt box,
2. submit a first prompt,
3. submit a follow-up refinement from the refinement box,
4. assert the refinement is appended as a user message and shown as a preview-only refinement if the backend is unavailable.

Smoke artifacts are written under `product/roblox_ai_studio/artifacts/desktop-smoke/`.

`npm run smoke` requires Chrome, Edge, or Chromium for rendered desktop proof. Set `PLAYRO_BROWSER_BIN` if the browser is installed outside the default paths.

## Windows acceptance notes

The 1280x800 Windows/RDP test viewport has limited vertical room. The landing page uses compact responsive top padding so the prompt box and Build Roblox Project CTA remain visible/clickable in that viewport.

For live proof runs, use `TESTING_WINDOWS11.md` on a real Windows 11 desktop or disposable test VM. Keep VM controller tooling outside the Playro product docs unless it is checked into this repo and documented as a product-local test harness.
