# Playro AI engine bundle staging

This directory is packaged into `resources/playro-engine/`.

Before cutting a self-contained Windows build, populate it with tracked repository files only:

```bash
cd product/roblox_ai_studio/desktop
npm run prepare:engine-bundle
```

On Windows, to also build the product-local `.venv` using bundled Python:

```powershell
cd product\roblox_ai_studio\desktop
npm run prepare:engine-bundle:win
```

Expected packaged runtime shape:

```
resources/playro-engine/hermes-agent/.venv/Scripts/hermes.exe
```

The preparation script intentionally ignores untracked workspace files and common secret-bearing filenames so local credentials are not packaged.

On first launch, Playro copies this bundled runtime into the product-local app-data directory and presents it as the **Playro AI engine**. If this bundle is not populated, Playro falls back to downloading the engine into app data.
