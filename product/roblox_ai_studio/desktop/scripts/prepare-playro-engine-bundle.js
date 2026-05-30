const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const desktopRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(desktopRoot, '..', '..', '..');
const vendorRoot = path.join(desktopRoot, 'vendor', 'playro-engine');
const bundleRoot = path.join(vendorRoot, 'hermes-agent');
const legacyBundledPythonRoot = path.join(desktopRoot, 'vendor', 'python-win-x64');
const legacyBundledPythonExe = path.join(legacyBundledPythonRoot, 'python.exe');
const markerFile = path.join(bundleRoot, 'PLAYRO_ENGINE_BUNDLE.txt');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', shell: process.platform === 'win32', ...options });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with exit ${result.status}`);
  }
}

function rm(target) {
  if (fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true });
}

const blockedBundlePrefixes = [
  'product/roblox_ai_studio/desktop/dist',
  'product/roblox_ai_studio/artifacts',
  'artifacts',
  'product/roblox_ai_studio/desktop/vendor/playro-engine'
];

const blockedSecretNames = new Set([
  '.env', '.env.local', '.env.development', '.env.development.local', '.env.production', '.env.production.local',
  '.env.test', '.env.test.local', '.npmrc', '.pypirc', '.netrc', '.dockercfg', 'id_rsa', 'id_dsa', 'id_ecdsa',
  'id_ed25519', 'credentials', 'credentials.json'
]);

const blockedSecretExtensions = new Set(['.pem', '.key', '.p12', '.pfx']);

function normalizeRel(file) {
  return file.replace(/\\/g, '/');
}

function isBlockedBundlePath(rel) {
  return blockedBundlePrefixes.some(prefix => rel === prefix || rel.startsWith(`${prefix}/`));
}

function isSecretPath(rel) {
  const normalized = normalizeRel(rel);
  const name = path.posix.basename(normalized);
  const lowerName = name.toLowerCase();
  if (blockedSecretNames.has(lowerName)) return true;
  if (/^\.env\..+/i.test(name) && !/\.example$/i.test(name)) return true;
  if (blockedSecretExtensions.has(path.posix.extname(lowerName))) return true;
  const segments = normalized.split('/');
  return segments.some(part => part === '.ssh' || part === '.aws' || part === '.azure')
    || normalized === '.config/gcloud'
    || normalized.startsWith('.config/gcloud/')
    || normalized.includes('/.config/gcloud/');
}

function trackedRepoFiles() {
  const result = spawnSync('git', ['ls-files', '-z', '--cached'], { cwd: repoRoot, encoding: 'buffer' });
  if (result.error || result.status === null || result.status !== 0) {
    const stderr = result.stderr ? result.stderr.toString('utf8').trim() : '';
    const stdout = result.stdout ? result.stdout.toString('utf8').trim() : '';
    const detail = [
      result.error ? result.error.message : '',
      stderr,
      stdout ? `stdout: ${stdout}` : ''
    ].filter(Boolean).join(': ');
    const exit = result.status === null ? 'unavailable' : result.status;
    throw new Error(`git ls-files failed with exit ${exit}${detail ? `: ${detail}` : ''}`);
  }
  return result.stdout
    .toString('utf8')
    .split('\0')
    .filter(Boolean)
    .map(normalizeRel)
    .filter(rel => !isBlockedBundlePath(rel) && !isSecretPath(rel));
}

function copyRepoFile(rel) {
  const from = path.join(repoRoot, rel);
  const to = path.join(bundleRoot, rel);
  const stat = fs.lstatSync(from);
  fs.mkdirSync(path.dirname(to), { recursive: true });
  if (stat.isSymbolicLink()) {
    const linkTarget = fs.readlinkSync(from);
    try { fs.symlinkSync(linkTarget, to); } catch (_error) {}
  } else if (stat.isFile()) {
    fs.copyFileSync(from, to);
    fs.chmodSync(to, stat.mode);
  }
}

function copyTrackedRepo() {
  for (const rel of trackedRepoFiles()) {
    copyRepoFile(rel);
  }
}

function pythonSupportsVenv(candidate) {
  const probe = spawnSync(candidate, ['-m', 'venv', '--help'], { shell: process.platform === 'win32', encoding: 'utf8' });
  return probe.status === 0;
}

function resolvePythonExe() {
  const override = process.env.PLAYRO_WINDOWS_PYTHON;
  if (override && fs.existsSync(override)) {
    if (!pythonSupportsVenv(override)) throw new Error(`${override} does not support -m venv`);
    return override;
  }
  if (fs.existsSync(legacyBundledPythonExe) && pythonSupportsVenv(legacyBundledPythonExe)) {
    return legacyBundledPythonExe;
  }
  if (process.platform === 'win32') {
    for (const candidate of ['py', 'python']) {
      const probe = spawnSync(candidate, ['--version'], { shell: true, encoding: 'utf8' });
      if (probe.status === 0 && pythonSupportsVenv(candidate)) return candidate;
    }
  }
  throw new Error('Missing Windows Python with venv support. Install Python locally or set PLAYRO_WINDOWS_PYTHON to python.exe.');
}

function ensureWindowsVenv() {
  const pythonExe = resolvePythonExe();
  const pth = path.join(legacyBundledPythonRoot, 'python311._pth');
  if (pythonExe === legacyBundledPythonExe && fs.existsSync(pth)) {
    const current = fs.readFileSync(pth, 'utf8');
    if (!current.includes('import site')) {
      fs.writeFileSync(pth, `${current.trim()}\nimport site\n`, 'utf8');
    }
  }

  const venvDir = path.join(bundleRoot, '.venv');
  rm(venvDir);
  run(pythonExe, ['-m', 'venv', venvDir]);
  const venvPython = path.join(venvDir, 'Scripts', 'python.exe');
  run(venvPython, ['-m', 'ensurepip', '--upgrade']);
  run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel']);
  const engineExtras = process.env.PLAYRO_ENGINE_EXTRAS || 'cli,acp,bedrock';
  const editableTarget = engineExtras.trim() ? `${bundleRoot}[${engineExtras}]` : bundleRoot;
  run(venvPython, ['-m', 'pip', 'install', '-e', editableTarget]);
  const hermesExe = path.join(venvDir, 'Scripts', 'hermes.exe');
  if (!fs.existsSync(hermesExe)) throw new Error(`Bundle missing ${hermesExe}`);
  run(hermesExe, ['--version']);
}

function main() {
  rm(bundleRoot);
  fs.mkdirSync(vendorRoot, { recursive: true });
  copyTrackedRepo();
  fs.writeFileSync(markerFile, [
    'Playro AI engine bundle',
    'Source: tracked repository files',
    `Prepared: ${new Date().toISOString()}`,
    'This is the product-local Playro AI engine runtime staged for packaging.'
  ].join('\n'), 'utf8');
  if (process.env.PLAYRO_PREPARE_WINDOWS_ENGINE === '1') {
    ensureWindowsVenv();
  } else {
    console.log('Prepared Playro AI engine source bundle. Set PLAYRO_PREPARE_WINDOWS_ENGINE=1 on Windows to create the bundled .venv/Scripts/hermes.exe runtime.');
  }
}

main();
