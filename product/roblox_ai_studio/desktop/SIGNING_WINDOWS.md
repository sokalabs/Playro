# Playro Windows code signing

Playro can build working unsigned Windows `.exe` files for internal testing right now. Authenticode signing is only required when the direct-download `.exe` needs to look production-trustworthy for public customers. Unsigned builds show `Publisher: Unknown publisher` and can trigger Windows Defender SmartScreen warnings, but they can still run after the user chooses **More info → Run anyway**.

## Certificate requirement

Use a real Windows code-signing certificate issued to the shipping publisher identity, preferably:

1. **EV code-signing certificate** — best for fast SmartScreen trust.
2. **OV/standard code-signing certificate** — removes `Unknown publisher`, but SmartScreen reputation may still need time/downloads.

Practical buying path:

1. Pick the publisher/legal name you want Windows to show, e.g. `SokaLabs` or the exact legal business name behind SokaLabs.
2. Buy an EV or OV Windows code-signing certificate from a trusted CA/reseller such as DigiCert, Sectigo, GlobalSign, SSL.com, or Certum.
3. Complete organization identity validation with the CA.
4. Export/get the signing certificate in a format Electron Builder can use:
   - `.pfx` + password for normal PFX signing, or
   - a cloud/HSM provider flow if the CA requires hardware-backed signing.
5. Keep the certificate and password outside the repo.

Self-signed certificates are only useful for local development and do not fix customer SmartScreen warnings.

## GitHub Actions secrets

For Electron Builder signing with a PFX certificate, add these repository secrets:

- `WINDOWS_CERTIFICATE` — base64-encoded `.pfx` file.
- `WINDOWS_CERTIFICATE_PASSWORD` — password for the `.pfx`.

How to create the base64 value on Windows:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\secure\SokaLabs-CodeSigning.pfx")) | Set-Clipboard
```

Then in GitHub:

1. Open `sokalabs/Playro`.
2. Go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Create `WINDOWS_CERTIFICATE` with the copied base64 text.
4. Create `WINDOWS_CERTIFICATE_PASSWORD` with the PFX password.
5. Run **Actions → Build Roblox AI Studio Desktop → Run workflow** with a version value.

Optional if using a different provider/HSM flow:

- `CSC_LINK` — certificate URL/file/base64 accepted by Electron Builder.
- `CSC_KEY_PASSWORD` — certificate password.

Never commit certificates, passwords, or tokens to the repo.

## Local signing environment

From `product/roblox_ai_studio/desktop`, set:

```powershell
$env:CSC_LINK="C:\secure\SokaLabs-CodeSigning.pfx"
$env:CSC_KEY_PASSWORD="<certificate password>"
$env:PLAYRO_RELEASE_CHANNEL="production"
npm run release:win:local
```

Or pass the values directly:

```powershell
.\scripts\release-windows-production.ps1 `
  -CertificatePath "C:\secure\SokaLabs-CodeSigning.pfx" `
  -CertificatePassword "<certificate password>"
```

On macOS/Linux shells for local test builds without signing:

```bash
npm run build:win:test
```

Test/internal builds are allowed to be unsigned, but must stay on a `*-test` release tag and must not be marketed as production.

## Unsigned EXE build for now

Use this when you just need a working Playro `.exe` without buying a cert yet:

```powershell
cd product\roblox_ai_studio\desktop
npm ci
npm run check
npm run smoke:static
npm run build:win:test
npm run verify:packaged
```

Outputs:

- `dist/Playro Setup <version>.exe`
- `dist/Playro <version>.exe`

This path intentionally disables certificate auto-discovery in CI and does not require `WINDOWS_CERTIFICATE` secrets. It is good for development, demos, and internal testing. It is not ideal for public customers because Windows may show SmartScreen.

## Production release gate

When you later want a trusted direct-download `.exe`, use the production Windows release flow:

```powershell
$env:PLAYRO_RELEASE_CHANNEL="production"
npm ci
npm run check
npm run smoke:static
npm run release:win:production
npm run release:manifest
npm run release:notes
npm run release:sell-check
```

`npm run release:assert-signed` fails when any of these are unsigned or invalid:

- `dist/Playro Setup <version>.exe`
- `dist/Playro <version>.exe`
- `dist/win-unpacked/Playro.exe`

Run this check on Windows because it uses PowerShell `Get-AuthenticodeSignature`.

## SmartScreen expectations

Signing changes the installer from `Unknown publisher` to the verified certificate subject. SmartScreen reputation is strongest with EV certificates. With OV certificates, Microsoft reputation can still take time. If needed, submit signed builds to Microsoft Security Intelligence for analysis/reputation review.
