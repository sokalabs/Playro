const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  verifyPackagedLayout,
  hashFile
} = require('../verify-packaged-layout');

function writeFile(root, rel, contents = '') {
  const target = path.join(root, rel);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, contents);
}

function createPackagedLayout({ appMainSource, currentMainSource = appMainSource, includeAppSource = true } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'playro-packaged-layout-'));
  writeFile(root, 'src/main.js', currentMainSource);
  writeFile(root, 'dist/win-unpacked/resources/backend/product/roblox_ai_studio/app/api.py');
  writeFile(root, 'dist/win-unpacked/resources/backend/product/roblox_ai_studio/roblox/generator.py');
  writeFile(root, 'dist/win-unpacked/resources/backend/product/roblox_ai_studio/hermes_backend/session.py');
  writeFile(root, 'dist/win-unpacked/resources/python/python.exe');
  writeFile(root, 'dist/win-unpacked/resources/rojo/rojo.exe');
  if (includeAppSource) writeFile(root, 'dist/win-unpacked/resources/app/src/main.js', appMainSource);
  return root;
}

const validMainSource = `
function resolveDataRoot() {
  if (process.env.PLAYRO_DATA_DIR) return process.env.PLAYRO_DATA_DIR;
  const base = app.getPath('userData');
  return path.join(base, 'playro-data');
}
app.whenReady().then(async () => {});
function createSetupWindow() {}
function runFullPlayroSetup() {}
const dataRoot = resolveDataRoot();
spawn('python', [], { env: { PLAYRO_DATA_DIR: dataRoot } });
`;

test('verifyPackagedLayout accepts current userData data root behavior', () => {
  const root = createPackagedLayout({ appMainSource: validMainSource });

  assert.doesNotThrow(() => verifyPackagedLayout({ root }));
});

test('verifyPackagedLayout rejects stale unpacked app source', () => {
  const root = createPackagedLayout({
    currentMainSource: validMainSource,
    appMainSource: validMainSource.replace('playro-data', 'stale-playro-data')
  });

  assert.throws(
    () => verifyPackagedLayout({ root }),
    /Packaged app source is stale relative to src\/main\.js/
  );
});

test('verifyPackagedLayout still requires backend data dir env passing', () => {
  const root = createPackagedLayout({
    appMainSource: validMainSource.replace('PLAYRO_DATA_DIR: dataRoot', 'PLAYRO_OTHER_DIR: dataRoot'),
    currentMainSource: validMainSource.replace('PLAYRO_DATA_DIR: dataRoot', 'PLAYRO_OTHER_DIR: dataRoot')
  });

  assert.throws(
    () => verifyPackagedLayout({ root }),
    /Packaged backend launch does not pass PLAYRO_DATA_DIR/
  );
});

test('verifyPackagedLayout rejects missing packaged Electron app source', () => {
  const root = createPackagedLayout({
    appMainSource: validMainSource,
    includeAppSource: false
  });

  assert.throws(
    () => verifyPackagedLayout({ root }),
    /Missing packaged Electron app source/
  );
});

test('hashFile returns a stable content hash', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'playro-hash-'));
  const target = path.join(root, 'main.js');
  fs.writeFileSync(target, validMainSource);

  assert.equal(hashFile(target), hashFile(target));
  assert.match(hashFile(target), /^[a-f0-9]{64}$/);
});
