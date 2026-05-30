# Testing Playro Desktop

This guide covers local desktop checks for contributors. Packaged installers and portable executables are build artifacts and should be distributed through GitHub Releases or another binary release channel, not committed to the source tree.

## What starts automatically

When the desktop app opens, it starts the product-local Playro backend automatically on `127.0.0.1:8765` by default.

Generated projects from the packaged app are written to a user-writable Playro data directory. During development you can override that location with `PLAYRO_DATA_DIR`.

## External Roblox tools

Roblox Studio and Rojo are external creator tools:

1. Install Roblox Studio: https://create.roblox.com/
2. Install Rojo CLI: https://rojo.space/docs/v7/getting-started/installation/
3. Install the Rojo Studio plugin from Rojo's docs.

The desktop app checks for Rojo/Studio and shows setup buttons. If Rojo is installed, **Start Rojo & Open Studio** starts `rojo serve <default.project.json>` automatically. If Rojo is missing, the app opens the project folder and copies the command so the user knows exactly what to run after installing Rojo.

## Dev test from clone

```powershell
git clone https://github.com/sokalabs/Playro.git
cd Playro
cd product\roblox_ai_studio\desktop
npm install
npm start
```

## Local static and smoke checks

```bash
cd product/roblox_ai_studio/desktop
npm run check
npm run smoke:static
```

`npm run smoke` includes runtime/browser checks and may require Chromium or a local browser on `PATH`.

## Backend smoke from repo root

```bash
python -m product.roblox_ai_studio.app.cli \
  "make a colorful obby with checkpoints, coins, and a shop" \
  --output-root ./tmp/playro-smoke \
  --smoke \
  --json
```

## Build desktop artifacts locally

```powershell
cd product\roblox_ai_studio\desktop
npm install
npm run check
npm run smoke:static
npm run prepare:engine-bundle:win
npm run build:win
npm run verify:packaged
npm run release:manifest
```

Output appears in `product/roblox_ai_studio/desktop/dist/`, which is ignored by Git.

## Release gate

Before sharing a release build, confirm the packaged layout verification passes and that published release hashes match the generated release manifest. Production/public Windows builds should be signed before broad distribution.
