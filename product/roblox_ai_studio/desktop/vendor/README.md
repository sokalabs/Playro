# Vendor Directory

This directory is reserved for release-time staging only.

Do not commit downloaded toolchains or generated runtime bundles here. Install Python, Rojo, and Node/Electron dependencies locally through their normal installers or package managers.

## Role in zero-touch provisioning

`vendor/playro-engine/` is the staging slot for the **product-local Playro AI Engine**. Populate it before cutting a self-contained Windows build with:

```bash
cd product/roblox_ai_studio/desktop
npm run prepare:engine-bundle
```

The generated bundle is packaged into `resources/playro-engine/`. On first launch Playro copies it into the product-local app-data engine home (`~/.playro/hermes`, or `%LOCALAPPDATA%\playro\hermes` on Windows) with no network access. See `vendor/playro-engine/README.md` for the expected runtime shape.

This bundle is the **preferred** provisioning source. When it is present, first-launch setup is fully offline and never reaches the remote fallback. When it is **absent**, headless provisioning falls back to running the official Hermes install script over HTTPS to pull Git/uv/Python 3.11+ into `~/.playro/hermes`. To guarantee a no-remote-execution posture, ship a build with this bundle populated so the fallback never triggers. See the desktop `README.md` Security note for details.
