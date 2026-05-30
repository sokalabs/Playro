# Playro Microsoft Store release path

Microsoft Store MSIX/AppX is the preferred public Windows distribution path for Playro because Store submission re-signs the package with Microsoft trust. This avoids the scary direct-download `Unknown publisher` / SmartScreen flow for normal customers.

## What this repo builds

From `product/roblox_ai_studio/desktop`:

```powershell
npm run build:store
```

This produces a Store package named like:

```text
dist/Playro.Store.<version>.x64.appx
```

The package uses Electron Builder's `appx` target with:

- `identityName`: `SokaLabs.Playro`
- `applicationId`: `Playro`
- `publisherDisplayName`: `SokaLabs`
- capabilities: `runFullTrust`, `internetClient`, `privateNetworkClientServer`
- Store tile assets from `build/appx/`

For Microsoft Store submission, Electron Builder docs state the Store will sign the submitted AppX package. Direct sideloading of AppX/MSIX still requires a trusted certificate.

## Microsoft Partner Center flow

1. Create/open Microsoft Partner Center developer account.
2. Reserve the app name `Playro` if available.
3. Create a Windows desktop app submission.
4. Upload `dist/Playro.Store.<version>.x64.appx` from the GitHub Actions artifact `Playro-Microsoft-Store-AppX`.
5. Fill Store listing:
   - Name: `Playro`
   - Category: Games / Developer tools, depending on Store availability.
   - Short description: `AI-powered Roblox game builder from prompt to playable project.`
   - Support contact: `sokabusiness@sokatech.xyz`
   - Website: `https://github.com/sokalabs/Playro` until a public Playro site exists.
6. Provide privacy policy URL before public submission.
7. Submit for Microsoft certification.

## Important distinction

- **Store install:** preferred for customers; Microsoft signs/re-signs during Store submission.
- **Direct EXE download:** still needs trusted code signing and reputation, or it remains internal/test only.
- **Direct AppX/MSIX sideload:** still needs a trusted cert on the user machine; do not market sideload packages as no-warning customer installs.

## Required Store assets

Electron Builder consumes these from `build/appx/`:

- `StoreLogo.png`
- `Square44x44Logo.png`
- `Square150x150Logo.png`
- `Wide310x150Logo.png`
- optional: `SmallTile.png`, `LargeTile.png`, `SplashScreen.png`

Current assets are generated from the Playro icon and are acceptable placeholders. Before a polished Store submission, replace them with designed Store artwork.

## Pre-submit checklist

- [ ] `npm run check` passes.
- [ ] `npm run smoke:static` passes.
- [ ] `npm run build:store` produces `dist/Playro.Store.<version>.x64.appx`.
- [ ] Store package is uploaded through Partner Center, not offered as a random website sideload.
- [ ] Store listing has screenshots, privacy policy, support email, and accurate Roblox/Rojo requirements.
- [ ] Direct `.exe` builds are either signed or clearly marked internal/test only.
