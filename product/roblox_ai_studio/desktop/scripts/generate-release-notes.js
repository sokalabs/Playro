const fs = require('fs');
const path = require('path');
const { releaseChannel, isProductionRelease } = require('./release-utils');

const desktopRoot = path.resolve(__dirname, '..');
const releaseRoot = path.join(desktopRoot, 'release');
const distRoot = path.join(desktopRoot, 'dist');
const pkg = JSON.parse(fs.readFileSync(path.join(desktopRoot, 'package.json'), 'utf8'));

function required(p) {
  if (!fs.existsSync(p)) {
    throw new Error(`Missing required file: ${p}`);
  }
}

function releaseTagFor(version) {
  const explicit = process.env.PLAYRO_RELEASE_TAG;
  if (explicit && explicit.trim()) return explicit.trim();

  if (isProductionRelease()) {
    return `desktop-v${version}`;
  }
  return `desktop-v${version}-test`;
}

function main() {
  const version = pkg.version;
  const tag = releaseTagFor(version);
  const manifestPath = path.join(distRoot, `release-manifest-v${version}.json`);
  required(manifestPath);

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

  fs.mkdirSync(releaseRoot, { recursive: true });

  const notesPath = path.join(releaseRoot, `RELEASE_NOTES_v${version}.md`);

  const maturityText = isProductionRelease()
    ? '> Maturity: Commercial release. Windows artifacts must be Authenticode-signed before publishing.'
    : '> Maturity: INTERNAL TEST BUILD. Unsigned artifacts are allowed only for private testing and may trigger SmartScreen.';

  const content = [
    `# Playro v${version} release notes`,
    '',
    `Tag: \`${tag}\``,
    '',
    `Release channel: \`${releaseChannel()}\``,
    '',
    maturityText,
    '',
    '## Downloads',
    '',
    `- Installer: ${manifest.assets.installer.url}`,
    `- Portable: ${manifest.assets.portable.url}`,
    '',
    '## Checksums (SHA-256)',
    '',
    `- ${manifest.assets.installer.file}: \`${manifest.assets.installer.sha256}\``,
    `- ${manifest.assets.portable.file}: \`${manifest.assets.portable.sha256}\``,
    '',
    '## What is included',
    '',
    '- Desktop-first Playro app flow (prompt -> build -> handoff).',
    '- Deterministic completion signal when real project files are generated.',
    '- Refine/submit loop and timeline visibility improvements.',
    '- Release manifest artifacts for reproducible handoff.',
    '',
    '## Requirements',
    '',
    '- Windows 10/11 (64-bit).',
    '- Roblox Studio installed for playtesting.',
    '- Rojo CLI and Rojo Studio plugin for sync workflow.',
    '',
    '## Upgrade existing installs',
    '',
    `- If Playro is already installed, download and run \`Playro.Setup.${version}.exe\`.`,
    '- Choose the existing Playro install location when prompted; the installer uses the same Playro app identity and upgrades over the prior install.',
    '- User app data is preserved by the installer/uninstaller configuration for this beta.',
    '- This is not an in-app auto-updater yet; beta testers update by running the new setup `.exe` manually.',
    '',
    '## Known limitations',
    '',
    '- Prototype quality: operational hardening is ongoing.',
    isProductionRelease()
      ? '- Windows binaries must be signed and pass `npm run release:assert-signed` before publishing.'
      : '- INTERNAL TEST BUILD: unsigned binaries may trigger SmartScreen friction and must not be sent as production builds.',
    '- Reliability depends on local Roblox/Studio environment configuration.',
    '',
    '## Support',
    '',
    '- Issues: https://github.com/sokalabs/Playro/issues',
    '- Contact: sokabusiness@sokatech.xyz',
    '',
    '## Rollback',
    '',
    '- Keep previous known-good release and checksum manifest for downgrade.',
    '- If customers hit blocker regressions, revert to prior tag and installer immediately.',
    '',
    '## Verification references',
    '',
    `- Manifest JSON: \`dist/release-manifest-v${version}.json\``,
    `- Manifest Markdown: \`dist/release-manifest-v${version}.md\``,
    '- Desktop checks: `npm run check`, `npm run smoke`, `npm run verify:packaged`.',
    '',
  ].join('\n');

  fs.writeFileSync(notesPath, content, 'utf8');
  console.log(`Wrote ${path.relative(desktopRoot, notesPath)}`);
}

main();
