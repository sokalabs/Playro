# Playro AI engine bundle staging

This directory is packaged into `resources/playro-engine/`.

Before cutting a self-contained Windows build, populate it with tracked repository files only:

```bash
cd product/roblox_ai_studio/desktop
npm run prepare:engine-bundle
```

On Windows, to also build the product-local `.venv`, install Python locally or set `PLAYRO_WINDOWS_PYTHON` to a trusted `python.exe`:

```powershell
cd product\roblox_ai_studio\desktop
npm run prepare:engine-bundle:win
```

Expected packaged runtime shape:

```
resources/playro-engine/hermes-agent/.venv/Scripts/hermes.exe
```

The preparation script intentionally ignores untracked workspace files and common secret-bearing filenames so local credentials are not packaged.

On first launch, Playro copies this generated runtime bundle into the product-local app-data directory and presents it as the **Playro AI engine**. The generated bundle is release-time staging output and should not be committed.
