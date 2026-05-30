const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { releaseChannel, isProductionRelease } = require('./release-utils');

const desktopRoot = path.resolve(__dirname, '..');
const distRoot = path.join(desktopRoot, 'dist');
const pkg = JSON.parse(fs.readFileSync(path.join(desktopRoot, 'package.json'), 'utf8'));

function sha256(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function hashTree(rootPath) {
  const hash = crypto.createHash('sha256');
  const files = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(fullPath);
      else if (entry.isFile()) files.push(fullPath);
    }
  }
  walk(rootPath);
  for (const filePath of files.sort()) {
    const rel = path.relative(rootPath, filePath).replace(/\\/g, '/');
    hash.update(rel);
    hash.update('\0');
    hash.update(fs.readFileSync(filePath));
    hash.update('\0');
  }
  return { sha256: hash.digest('hex'), file_count: files.length };
}

function sizeBytes(filePath) {
  return fs.statSync(filePath).size;
}

function assertFile(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing build artifact: ${filePath}. Run npm run build:win:test for unsigned beta builds or npm run release:win:production for signed production builds first.`);
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
  const releaseTag = releaseTagFor(version);
  const setupName = `Playro Setup ${version}.exe`;
  const portableName = `Playro ${version}.exe`;

  const setupPath = path.join(distRoot, setupName);
  const portablePath = path.join(distRoot, portableName);
  const unpackedExePath = path.join(distRoot, 'win-unpacked', 'Playro.exe');
  const unpackedResourcesPath = path.join(distRoot, 'win-unpacked', 'resources');
  const unpackedAsarPath = path.join(unpackedResourcesPath, 'app.asar');
  const unpackedAppDir = path.join(unpackedResourcesPath, 'app');
  const packagedAppPath = fs.existsSync(unpackedAsarPath) ? unpackedAsarPath : unpackedAppDir;

  [setupPath, portablePath, unpackedExePath, packagedAppPath].forEach(assertFile);
  const packagedAppReference = fs.statSync(packagedAppPath).isDirectory()
    ? hashTree(packagedAppPath)
    : { sha256: sha256(packagedAppPath), file_count: 1 };

  const manifest = {
    product: 'Playro',
    version,
    generated_at: new Date().toISOString(),
    release_tag: releaseTag,
    release_channel: releaseChannel(),
    signed_windows_artifacts_required: isProductionRelease(),
    unsigned_build_label: isProductionRelease() ? null : 'INTERNAL TEST BUILD - unsigned artifacts may trigger SmartScreen',
    release_page: `https://github.com/sokalabs/Playro/releases/tag/${releaseTag}`,
    assets: {
      installer: {
        file: setupName,
        url: `https://github.com/sokalabs/Playro/releases/download/${releaseTag}/Playro.Setup.${version}.exe`,
        sha256: sha256(setupPath),
        size_bytes: sizeBytes(setupPath),
      },
      portable: {
        file: portableName,
        url: `https://github.com/sokalabs/Playro/releases/download/${releaseTag}/Playro.${version}.exe`,
        sha256: sha256(portablePath),
        size_bytes: sizeBytes(portablePath),
      },
    },
    installed_binaries_reference: {
      playro_exe_sha256: sha256(unpackedExePath),
      packaged_app_mode: fs.existsSync(unpackedAsarPath) ? 'asar' : 'unpacked',
      packaged_app_reference: path.relative(distRoot, packagedAppPath).replace(/\\/g, '/'),
      packaged_app_sha256: packagedAppReference.sha256,
      packaged_app_file_count: packagedAppReference.file_count,
    },
  };

  const jsonPath = path.join(distRoot, `release-manifest-v${version}.json`);
  fs.writeFileSync(jsonPath, JSON.stringify(manifest, null, 2), 'utf8');

  const md = [
    `# Playro v${version} release manifest`,
    '',
    `Generated at: ${manifest.generated_at}`,
    '',
    `Release page: ${manifest.release_page}`,
    '',
    `Release channel: ${manifest.release_channel}`,
    '',
    manifest.unsigned_build_label ? `> ${manifest.unsigned_build_label}` : '> Windows artifacts are required to be Authenticode-signed for this production release.',
    '',
    '## Download assets',
    '',
    `- Installer: ${manifest.assets.installer.url}`,
    `  - SHA-256: \`${manifest.assets.installer.sha256}\``,
    `  - Size: ${manifest.assets.installer.size_bytes} bytes`,
    `- Portable: ${manifest.assets.portable.url}`,
    `  - SHA-256: \`${manifest.assets.portable.sha256}\``,
    `  - Size: ${manifest.assets.portable.size_bytes} bytes`,
    '',
    '## Packaged reference hashes',
    '',
    `- win-unpacked/Playro.exe: \`${manifest.installed_binaries_reference.playro_exe_sha256}\``,
    `- ${manifest.installed_binaries_reference.packaged_app_reference} (${manifest.installed_binaries_reference.packaged_app_mode}): \`${manifest.installed_binaries_reference.packaged_app_sha256}\``,
    '',
    '> Note: release URLs assume GitHub asset filenames are normalized to `Playro.Setup.<version>.exe` and `Playro.<version>.exe` when publishing.',
    '',
  ].join('\n');
  const mdPath = path.join(distRoot, `release-manifest-v${version}.md`);
  fs.writeFileSync(mdPath, md, 'utf8');

  console.log(`Wrote ${path.relative(desktopRoot, jsonPath)}`);
  console.log(`Wrote ${path.relative(desktopRoot, mdPath)}`);
  console.log(`installer_sha256=${manifest.assets.installer.sha256}`);
  console.log(`portable_sha256=${manifest.assets.portable.sha256}`);
}

main();
