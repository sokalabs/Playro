param(
  [string]$CertificatePath = $env:CSC_LINK,
  [string]$CertificatePassword = $env:CSC_KEY_PASSWORD,
  [string]$ReleaseChannel = "production"
)

$ErrorActionPreference = "Stop"

function Fail($Message) {
  Write-Error "RELEASE_FAIL: $Message"
  exit 1
}

$DesktopRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $DesktopRoot

if (-not $CertificatePath) {
  Fail "Missing certificate path. Set CSC_LINK or pass -CertificatePath C:\secure\SokaLabs-CodeSigning.pfx"
}

if (-not (Test-Path $CertificatePath)) {
  Fail "Certificate file does not exist: $CertificatePath"
}

if (-not $CertificatePassword) {
  Fail "Missing certificate password. Set CSC_KEY_PASSWORD or pass -CertificatePassword."
}

$env:PLAYRO_RELEASE_CHANNEL = $ReleaseChannel
$env:CSC_LINK = (Resolve-Path $CertificatePath).Path
$env:CSC_KEY_PASSWORD = $CertificatePassword

Write-Host "== Playro Windows production release =="
Write-Host "Desktop root: $DesktopRoot"
Write-Host "Release channel: $env:PLAYRO_RELEASE_CHANNEL"
Write-Host "Certificate: $env:CSC_LINK"
Write-Host ""

npm ci
npm run check
npm run smoke:static
npm run build:win
npm run verify:packaged
npm run release:assert-signed
npm run release:manifest
npm run release:notes
npm run release:sell-check

Write-Host ""
Write-Host "RELEASE_READY: signed Playro Windows artifacts passed production gates."
Write-Host "Next: upload dist/*.exe, dist/release-manifest-*.json, dist/release-manifest-*.md, and release/RELEASE_NOTES_*.md to the GitHub release."
