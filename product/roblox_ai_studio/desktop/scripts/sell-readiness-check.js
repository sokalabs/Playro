const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { releaseChannel, isProductionRelease } = require('./release-utils');

const desktopRoot = path.resolve(__dirname, '..');
const distRoot = path.join(desktopRoot, 'dist');
const releaseRoot = path.join(desktopRoot, 'release');
const pkg = JSON.parse(fs.readFileSync(path.join(desktopRoot, 'package.json'), 'utf8'));

function fail(msg) {
  console.error(`SELL_READY_FAIL: ${msg}`);
  process.exit(1);
}

function sha256(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function mustExist(filePath) {
  if (!fs.existsSync(filePath)) fail(`Missing required file: ${filePath}`);
}

function mustContain(filePath, needle, label) {
  const content = fs.readFileSync(filePath, 'utf8');
  if (!content.includes(needle)) fail(`${path.basename(filePath)} missing section/content: ${label}`);
}

function main() {
  const version = pkg.version;

  const installer = path.join(distRoot, `Playro Setup ${version}.exe`);
  const portable = path.join(distRoot, `Playro ${version}.exe`);
  const manifestPath = path.join(distRoot, `release-manifest-v${version}.json`);
  const notesPath = path.join(releaseRoot, `RELEASE_NOTES_v${version}.md`);

  [installer, portable, manifestPath, notesPath].forEach(mustExist);

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

  if (manifest?.product !== 'Playro') fail('Manifest product must be Playro');
  if (manifest?.version !== version) fail(`Manifest version mismatch: expected ${version}`);
  if (!manifest?.assets?.installer?.sha256 || !manifest?.assets?.portable?.sha256) {
    fail('Manifest missing installer/portable sha256 values');
  }
  if (isProductionRelease()) {
    if (manifest.release_channel !== releaseChannel()) fail('Production manifest release_channel mismatch');
    if (manifest.signed_windows_artifacts_required !== true) fail('Production manifest must require signed Windows artifacts');
    if (manifest.unsigned_build_label) fail('Production manifest must not carry an unsigned/internal test label');
  } else if (!manifest.unsigned_build_label?.includes('INTERNAL TEST BUILD')) {
    fail('Test/internal manifest must clearly label unsigned builds as internal test builds');
  }

  const installerSha = sha256(installer);
  const portableSha = sha256(portable);

  if (installerSha !== manifest.assets.installer.sha256) {
    fail('Installer sha256 mismatch between dist file and manifest');
  }
  if (portableSha !== manifest.assets.portable.sha256) {
    fail('Portable sha256 mismatch between dist file and manifest');
  }

  mustContain(notesPath, '## Support', 'support section');
  mustContain(notesPath, '## Known limitations', 'known limitations section');
  mustContain(notesPath, 'sokabusiness@sokatech.xyz', 'support contact email');
  mustContain(notesPath, '## Checksums (SHA-256)', 'checksums section');
  mustContain(notesPath, isProductionRelease() ? 'release:assert-signed' : 'INTERNAL TEST BUILD', 'release signing/internal-build status');

  console.log(`SELL_READY_OK version=${version}`);
  console.log(`installer_sha256=${installerSha}`);
  console.log(`portable_sha256=${portableSha}`);
  console.log(`notes=${path.relative(desktopRoot, notesPath)}`);
}

main();
