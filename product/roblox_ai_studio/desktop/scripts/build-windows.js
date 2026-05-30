const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { releaseChannel, isProductionRelease } = require('./release-utils');

function isUnsignedBuildRequested() {
  const scriptName = process.env.npm_lifecycle_event || '';
  return (
    process.env.PLAYRO_UNSIGNED_WINDOWS_BUILD === '1' ||
    scriptName === 'build:win' ||
    scriptName.endsWith(':test') ||
    scriptName.endsWith(':unsigned')
  );
}

function writeUnsignedWindowsConfig(baseConfigPath) {
  const config = JSON.parse(fs.readFileSync(baseConfigPath, 'utf8'));
  config.win = {
    ...(config.win || {}),
    signAndEditExecutable: false,
    verifyUpdateCodeSignature: false,
  };

  const generatedConfigPath = path.join(__dirname, '..', '.electron-builder.unsigned-win.json');
  fs.writeFileSync(generatedConfigPath, `${JSON.stringify(config, null, 2)}\n`);
  return generatedConfigPath;
}

const args = process.argv.slice(2);
const env = { ...process.env };
const baseConfigPath = path.resolve(__dirname, '..', 'electron-builder.json');
let configPath = baseConfigPath;
let generatedConfigPath = null;

if (!isProductionRelease()) {
  if (!isUnsignedBuildRequested()) {
    console.error('Unsigned Windows builds require an explicit test/unsigned script or PLAYRO_UNSIGNED_WINDOWS_BUILD=1.');
    console.error('Use npm run build:win for internal beta builds, or set PLAYRO_RELEASE_CHANNEL=production for signed release builds.');
    process.exit(1);
  }
  env.CSC_IDENTITY_AUTO_DISCOVERY = 'false';
  env.WIN_CSC_IDENTITY_AUTO_DISCOVERY = 'false';
  env.WIN_CSC_LINK = '';
  env.WIN_CSC_KEY_PASSWORD = '';
  env.CSC_LINK = '';
  env.CSC_KEY_PASSWORD = '';
  generatedConfigPath = writeUnsignedWindowsConfig(baseConfigPath);
  configPath = generatedConfigPath;
  console.log(`PLAYRO_BUILD_SIGNING=disabled channel=${releaseChannel()}`);
} else {
  console.log(`PLAYRO_BUILD_SIGNING=required channel=${releaseChannel()}`);
}

try {
  const result = spawnSync(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['electron-builder', '--config', configPath, ...args],
    { env, stdio: 'inherit', shell: process.platform === 'win32' }
  );

  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }

  process.exitCode = result.status ?? 1;
} finally {
  if (generatedConfigPath && fs.existsSync(generatedConfigPath)) {
    fs.unlinkSync(generatedConfigPath);
  }
}