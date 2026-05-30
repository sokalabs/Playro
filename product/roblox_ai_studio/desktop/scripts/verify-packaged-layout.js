const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const DEFAULT_ROOT = path.resolve(__dirname, '..');
const REQUIRED_BACKEND_FILES = [
  'product/roblox_ai_studio/app/api.py',
  'product/roblox_ai_studio/roblox/generator.py',
  'product/roblox_ai_studio/hermes_backend/session.py'
];
const REQUIRED_APP_MARKERS = [
  {
    marker: 'app.whenReady().then(async ()',
    message: 'Packaged app does not block first launch on the required Playro AI engine before creating the Playro window'
  },
  {
    marker: 'createSetupWindow',
    message: 'Packaged app is missing the full Playro Setup window flow'
  },
  {
    marker: 'runFullPlayroSetup',
    message: 'Packaged app is missing the full Playro Setup window flow'
  },
  {
    marker: 'PLAYRO_DATA_DIR: dataRoot',
    message: 'Packaged backend launch does not pass PLAYRO_DATA_DIR'
  },
  {
    marker: "app.getPath('userData')",
    message: "Packaged app does not use Electron userData as the default Playro data root"
  },
  {
    marker: "path.join(base, 'playro-data')",
    message: "Packaged app does not store default Playro data under userData/playro-data"
  }
];
const FORBIDDEN_APP_MARKERS = [
  {
    marker: "buttons: ['Open setup', 'Quit Playro']",
    message: 'Packaged app still contains the old native setup warning modal'
  },
  {
    marker: 'Complete required Playro setup',
    message: 'Packaged app still contains the old native setup warning modal'
  }
];

function hashBuffer(buffer) {
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

function hashFile(filePath) {
  return hashBuffer(fs.readFileSync(filePath));
}

function assertExists(filePath, message) {
  if (!fs.existsSync(filePath)) throw new Error(message);
}

function readPackagedAppSource({ root = DEFAULT_ROOT } = {}) {
  const asarPath = path.join(root, 'dist', 'win-unpacked', 'resources', 'app.asar');
  const appMain = path.join(root, 'dist', 'win-unpacked', 'resources', 'app', 'src', 'main.js');
  if (fs.existsSync(asarPath)) {
    return {
      source: fs.readFileSync(asarPath),
      sourcePath: asarPath,
      kind: 'asar'
    };
  }
  if (fs.existsSync(appMain)) {
    return {
      source: fs.readFileSync(appMain),
      sourcePath: appMain,
      kind: 'unpacked'
    };
  }
  throw new Error('Missing packaged Electron app source: expected resources/app/src/main.js or resources/app.asar');
}

function assertCurrentMainMatchesPackaged({ root = DEFAULT_ROOT, packagedSource }) {
  if (packagedSource.kind === 'asar') {
    throw new Error('Packaged app uses app.asar; verify-packaged-layout.js cannot compare src/main.js freshness while asar is enabled. Current desktop packaging is expected to keep asar disabled.');
  }

  const currentMain = path.join(root, 'src', 'main.js');
  assertExists(currentMain, 'Missing current desktop source: src/main.js');
  const currentHash = hashFile(currentMain);
  const packagedHash = hashFile(packagedSource.sourcePath);
  if (currentHash !== packagedHash) {
    throw new Error(`Packaged app source is stale relative to src/main.js (current ${currentHash}, packaged ${packagedHash}). Rebuild with npm run build:win.`);
  }
}

function assertAppSourceMarkers(appSource) {
  for (const { marker, message } of REQUIRED_APP_MARKERS) {
    if (!appSource.includes(Buffer.from(marker))) throw new Error(message);
  }
  for (const { marker, message } of FORBIDDEN_APP_MARKERS) {
    if (appSource.includes(Buffer.from(marker))) throw new Error(message);
  }
}

function verifyPackagedLayout({
  root = DEFAULT_ROOT,
  allowMissingPackagedLayout = process.env.PLAYRO_ALLOW_MISSING_PACKAGED_LAYOUT === '1',
  logger = console.log
} = {}) {
  const packagedRoot = path.join(root, 'dist', 'win-unpacked');
  const backend = path.join(packagedRoot, 'resources', 'backend');
  if (!fs.existsSync(packagedRoot) || !fs.existsSync(backend)) {
    if (allowMissingPackagedLayout) {
      logger('Skipping packaged backend layout verification: dist/win-unpacked is not present');
      return { skipped: true };
    }
    throw new Error('Packaged layout verification requires dist/win-unpacked/resources/backend. Run npm run build:win for unsigned beta builds or npm run release:win:production for signed production builds first.');
  }

  for (const rel of REQUIRED_BACKEND_FILES) {
    assertExists(path.join(backend, rel), `Missing packaged backend file: ${rel}`);
  }
  const packagedSource = readPackagedAppSource({ root });
  assertCurrentMainMatchesPackaged({ root, packagedSource });
  assertAppSourceMarkers(packagedSource.source);

  logger('Packaged backend layout verified');
  return { skipped: false };
}

if (require.main === module) {
  verifyPackagedLayout();
}

module.exports = {
  REQUIRED_APP_MARKERS,
  REQUIRED_BACKEND_FILES,
  assertAppSourceMarkers,
  hashFile,
  readPackagedAppSource,
  verifyPackagedLayout
};
