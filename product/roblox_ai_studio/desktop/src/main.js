const { app, BrowserWindow, ipcMain, clipboard, shell, screen } = require('electron');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const crypto = require('crypto');

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
const isPackaged = app.isPackaged;
const ROOT = isPackaged ? path.join(__dirname, '..') : path.resolve(__dirname, '..', '..');
const API_PORT = process.env.HERMES_ROBLOX_API_PORT || '8765';
const API_TOKEN = process.env.PLAYRO_API_TOKEN || crypto.randomBytes(32).toString('hex');

function resolveBackendDir() {
  return isPackaged ? path.join(process.resourcesPath, 'backend') : path.join(ROOT, '..', '..');
}

function resolveDataRoot() {
  if (process.env.PLAYRO_DATA_DIR) {
    const override = path.resolve(process.env.PLAYRO_DATA_DIR);
    fs.mkdirSync(override, { recursive: true });
    return override;
  }

  const base = app.getPath('userData');
  const target = path.join(base, 'playro-data');
  fs.mkdirSync(target, { recursive: true });
  return target;
}

function resolvePythonCommand() {
  if (isPackaged && process.platform === 'win32') {
    const bundled = path.join(process.resourcesPath, 'python', 'python.exe');
    if (fs.existsSync(bundled)) return bundled;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

let apiProcess = null;
let rojoProcess = null;
let hermesInstallProcess = null;
let rojoInstallProcess = null;
let mainWindow = null;
let setupWindow = null;
let backendStatus = { ok: false, starting: false, failed: false, port: API_PORT, error: null, exitCode: null };

const HERMES_INSTALL_STEPS = [
  'Starting installation...',
  'Checking system dependencies...',
  'Preparing Playro AI engine...',
  'Preparing Python runtime...',
  'Installing packages...',
  'Configuring product-local runtime...',
  'Finishing setup...'
];

const PLAYRO_SETUP_STEPS = [
  'Installing Playro shell',
  'Downloading Playro AI Engine',
  'Installing Playro AI Engine',
  'Checking optional Rojo',
  'Preparing Studio handoff',
  'Verifying setup',
  'Launching Playro'
];

function setupPercent(step) {
  return Math.max(8, Math.min(100, Math.round((step / PLAYRO_SETUP_STEPS.length) * 100)));
}

function sendPlayroSetupProgress(payload) {
  const message = {
    totalSteps: PLAYRO_SETUP_STEPS.length,
    percent: setupPercent(payload.step || 1),
    status: 'running',
    ...payload
  };
  for (const win of [setupWindow, mainWindow]) {
    if (win && !win.isDestroyed()) win.webContents.send('playro-setup-progress', message);
  }
}

function sendHermesInstallProgress(payload) {
  for (const win of [setupWindow, mainWindow]) {
    if (win && !win.isDestroyed()) win.webContents.send('hermes-install-progress', payload);
  }
  if (payload?.log || payload?.detail) {
    sendPlayroSetupProgress({
      status: payload.status === 'failed' ? 'failed' : 'running',
      step: payload.status === 'complete' ? 3 : Math.max(2, Math.min(3, payload.step || 2)),
      percent: payload.status === 'complete' ? setupPercent(3) : Math.min(setupPercent(3) - 3, setupPercent(2) + Math.round((payload.percent || 0) / 12)),
      title: 'Installing Playro',
      stepLabel: payload.status === 'complete' ? 'Step 3/7: Installing Playro AI Engine' : 'Step 2/7: Downloading Playro AI Engine',
      detail: payload.detail || payload.log || 'Installing Playro AI Engine...',
      log: payload.log || payload.detail
    });
  }
}

function inferHermesInstallStep(line, fallbackStep = 1) {
  const text = String(line || '').toLowerCase();
  if (text.includes('dependency') || text.includes('checking')) return 2;
  if (text.includes('clone') || text.includes('download') || text.includes('repository')) return 3;
  if (text.includes('python') || text.includes('venv') || text.includes('uv')) return 4;
  if (text.includes('pip') || text.includes('npm') || text.includes('install')) return 5;
  if (text.includes('config') || text.includes('setup') || text.includes('hermes_home')) return 6;
  if (text.includes('success') || text.includes('complete')) return 7;
  return fallbackStep;
}

function progressForStep(step) {
  return Math.max(14, Math.min(100, Math.round((step / HERMES_INSTALL_STEPS.length) * 100)));
}

function resolveHermesHome() {
  if (process.env.PLAYRO_HERMES_HOME) return process.env.PLAYRO_HERMES_HOME;
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    return path.join(localAppData, 'playro', 'hermes');
  }
  return path.join(os.homedir(), '.playro', 'hermes');
}

function resolveHermesAgentDir() {
  if (process.env.PLAYRO_HERMES_AGENT_DIR) return process.env.PLAYRO_HERMES_AGENT_DIR;
  return path.join(resolveHermesHome(), 'hermes-agent');
}

function resolveBundledHermesAgentDir() {
  const candidates = isPackaged
    ? [
        path.join(process.resourcesPath, 'playro-engine', 'hermes-agent'),
        path.join(process.resourcesPath, 'hermes-agent')
      ]
    : [path.join(__dirname, '..', 'vendor', 'playro-engine', 'hermes-agent')];
  return candidates.find(candidate => fs.existsSync(path.join(candidate, 'pyproject.toml')) || fs.existsSync(path.join(candidate, '.venv'))) || null;
}

function resolveHermesBinFromAgentDir(agentDir) {
  const binDir = process.platform === 'win32' ? 'Scripts' : 'bin';
  const binName = process.platform === 'win32' ? 'hermes.exe' : 'hermes';
  const candidates = [
    path.join(agentDir, '.venv', binDir, binName),
    path.join(agentDir, 'venv', binDir, binName)
  ];
  return candidates.find(candidate => fs.existsSync(candidate)) || null;
}

function resolveProductLocalHermesCommand() {
  const agentDir = resolveHermesAgentDir();
  const binDir = process.platform === 'win32' ? 'Scripts' : 'bin';
  const binName = process.platform === 'win32' ? 'hermes.exe' : 'hermes';
  const candidates = [
    resolveHermesBinFromAgentDir(agentDir),
    path.join(resolveHermesHome(), binDir, binName)
  ].filter(Boolean);
  return candidates.find(candidate => fs.existsSync(candidate)) || null;
}

function resolveBundledHermesCommand() {
  const bundledAgentDir = resolveBundledHermesAgentDir();
  return bundledAgentDir ? resolveHermesBinFromAgentDir(bundledAgentDir) : null;
}

function hasExplicitHermesCommand() {
  return Boolean(process.env.PLAYRO_HERMES_BIN && fs.existsSync(process.env.PLAYRO_HERMES_BIN));
}

function hasInstalledHermesRuntime() {
  return hasExplicitHermesCommand() || Boolean(resolveProductLocalHermesCommand());
}

function copyDirRecursive(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const sourcePath = path.join(src, entry.name);
    const targetPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirRecursive(sourcePath, targetPath);
    } else if (entry.isSymbolicLink()) {
      const linkTarget = fs.readlinkSync(sourcePath);
      try { fs.symlinkSync(linkTarget, targetPath); } catch (_error) {}
    } else {
      fs.copyFileSync(sourcePath, targetPath);
    }
  }
}

function installFromBundledHermesRuntime(installDir) {
  const bundledAgent = resolveBundledHermesAgentDir();
  if (!bundledAgent) return false;
  sendHermesInstallProgress({
    status: 'running',
    step: 2,
    totalSteps: HERMES_INSTALL_STEPS.length,
    percent: progressForStep(2),
    title: 'Installing Playro AI engine',
    stepLabel: `Step 2/${HERMES_INSTALL_STEPS.length}: ${HERMES_INSTALL_STEPS[1]}`,
    detail: 'Copying bundled Playro AI engine into app data...',
    log: 'Copying bundled Playro AI engine into app data...'
  });
  if (fs.existsSync(installDir)) fs.rmSync(installDir, { recursive: true, force: true });
  copyDirRecursive(bundledAgent, installDir);
  const hermesCmd = resolveProductLocalHermesCommand();
  if (!hermesCmd) throw new Error('Bundled Playro AI engine copied, but the engine command was not found.');
  sendHermesInstallProgress({
    status: 'complete',
    step: HERMES_INSTALL_STEPS.length,
    totalSteps: HERMES_INSTALL_STEPS.length,
    percent: 100,
    title: 'Playro AI engine installed',
    stepLabel: `Step ${HERMES_INSTALL_STEPS.length}/${HERMES_INSTALL_STEPS.length}: ${HERMES_INSTALL_STEPS[6]}`,
    detail: 'Playro AI engine is ready.',
    log: 'Playro AI engine installed from bundled runtime.'
  });
  return true;
}

function resolveHermesCommand() {
  const candidates = [
    process.env.PLAYRO_HERMES_BIN,
    resolveProductLocalHermesCommand(),
    resolveBundledHermesCommand()
  ].filter(Boolean);
  return candidates.find(candidate => fs.existsSync(candidate)) || null;
}

function checkHermesRuntime() {
  const hermesHome = resolveHermesHome();
  const installDir = resolveHermesAgentDir();
  const command = resolveHermesCommand();
  let version = '';
  if (command) {
    const result = runCheck(command, ['--version']);
    version = (result.stdout || result.stderr || '').trim();
  }
  return {
    ok: Boolean(command),
    installing: Boolean(hermesInstallProcess),
    hermes_home: hermesHome,
    install_dir: installDir,
    command,
    product_local_command: resolveProductLocalHermesCommand(),
    bundled_command: resolveBundledHermesCommand(),
    version,
    help: "Installs the Playro AI engine into Playro's product-local app data folder. It does not import live personal Hermes config."
  };
}

function remoteHermesInstallDisabledResult() {
  const devHint = isPackaged
    ? ''
    : ' For local dev, run: cd product/roblox_ai_studio/desktop && npm run prepare:engine-bundle:win — or set PLAYRO_ALLOW_LOCAL_GENERATOR=1 to skip engine setup and use the local generator fallback.';
  return {
    ok: false,
    error: `Playro AI engine is not bundled with this build. Remote installer execution is disabled; install a trusted product-local engine bundle instead.${devHint}`,
    remote_install_disabled: true,
    runtime: checkHermesRuntime()
  };
}

function terminateProcess(proc, label, timeoutMs = 3000) {
  if (!proc || proc.killed) return;
  try {
    if (process.platform === 'win32') {
      proc.kill();
      return;
    }
    proc.kill('SIGTERM');
    const timer = setTimeout(() => {
      if (!proc.killed) {
        try { proc.kill('SIGKILL'); } catch (error) { console.warn(`[${label}] failed to force kill: ${error.message}`); }
      }
    }, timeoutMs);
    proc.once('exit', () => clearTimeout(timer));
  } catch (error) {
    console.warn(`[${label}] failed to terminate: ${error.message}`);
  }
}

function installHermesRuntime() {
  if (hermesInstallProcess) return { ok: false, installing: true, error: 'Playro AI engine install is already running.' };
  const current = checkHermesRuntime();
  if (hasInstalledHermesRuntime()) return { ok: true, already_installed: true, runtime: current };

  const hermesHome = resolveHermesHome();
  const installDir = resolveHermesAgentDir();
  fs.mkdirSync(hermesHome, { recursive: true });

  try {
    if (installFromBundledHermesRuntime(installDir)) {
      return { ok: true, bundled: true, runtime: checkHermesRuntime() };
    }
  } catch (error) {
    return { ok: false, error: error.message, runtime: checkHermesRuntime() };
  }

  return remoteHermesInstallDisabledResult();
}

async function ensureHermesRuntime() {
  const current = checkHermesRuntime();
  if (current.ok) return { ok: true, runtime: current };

  const hermesHome = resolveHermesHome();
  fs.mkdirSync(hermesHome, { recursive: true });

  const allowLocalGenerator = process.env.PLAYRO_ALLOW_LOCAL_GENERATOR === '1' || process.env.NODE_ENV === 'test';
  if (allowLocalGenerator) {
    return { ok: true, missing: true, runtime: current, warning: 'Playro AI engine not installed yet; test/dev mode allowed packaged local Roblox generator fallback.' };
  }

  const win = setupWindow && !setupWindow.isDestroyed() ? setupWindow : createSetupWindow();
  win.show();
  win.focus();
  sendPlayroSetupProgress({
    status: 'idle',
    step: 1,
    percent: setupPercent(1),
    title: 'Installing Playro',
    stepLabel: 'Step 1/7: Installing Playro shell',
    detail: `Playro setup is required. Step 1 installs the product-local Playro AI Engine into ${current.hermes_home}. Step 2 downloads Rojo for Roblox Studio sync.`,
    log: 'Opened Playro Setup because the required Playro AI Engine is missing.'
  });
  return { ok: false, setup_required: true, runtime: current };
}

function startBackend() {
  if (apiProcess) return;
  backendStatus = { ok: false, starting: true, failed: false, port: API_PORT, error: null, exitCode: null };
  const backendDir = resolveBackendDir();
  const pythonCmd = resolvePythonCommand();
  const dataRoot = resolveDataRoot();

  console.log(`[backend] starting ${pythonCmd} from ${backendDir}`);
  apiProcess = spawn(pythonCmd, ['-m', 'product.roblox_ai_studio.app.api'], {
    cwd: backendDir,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PLAYRO_DATA_DIR: dataRoot,
      PLAYRO_API_TOKEN: API_TOKEN,
      PLAYRO_ALLOWED_ORIGINS: process.env.PLAYRO_ALLOWED_ORIGINS || 'file://,app://playro,http://localhost:8765,http://127.0.0.1:8765',
      PLAYRO_HERMES_BIN: resolveHermesCommand() || '',
      PYTHONPATH: [backendDir, process.env.PYTHONPATH || ''].filter(Boolean).join(path.delimiter)
    },
    stdio: ['ignore', 'pipe', 'pipe']
  });

  apiProcess.stdout.on('data', data => console.log(`[backend] ${data.toString().trim()}`));
  apiProcess.stderr.on('data', data => console.error(`[backend] ${data.toString().trim()}`));
  apiProcess.on('error', error => {
    backendStatus = { ok: false, starting: false, failed: true, port: API_PORT, error: error.message, exitCode: null };
    console.error(`[backend] failed to start: ${error.message}`);
  });
  apiProcess.on('exit', code => {
    console.log(`[backend] exited ${code}`);
    backendStatus = { ok: false, starting: false, failed: true, port: API_PORT, error: `Backend exited with code ${code}`, exitCode: code };
    apiProcess = null;
  });
}

async function backendHealth(timeoutMs = 1200) {
  if (!apiProcess) return backendStatus;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`http://127.0.0.1:${API_PORT}/health`, { signal: controller.signal });
    const body = await response.json().catch(() => ({}));
    backendStatus = { ok: response.ok && body.ok === true, starting: false, failed: !response.ok, port: API_PORT, error: response.ok ? null : `Health check returned ${response.status}`, exitCode: null };
  } catch (error) {
    backendStatus = { ...backendStatus, ok: false, starting: Boolean(apiProcess), failed: false, port: API_PORT, error: error.name === 'AbortError' ? 'Backend health check timed out.' : error.message };
  } finally {
    clearTimeout(timer);
  }
  return backendStatus;
}

const ALLOWED_EXTERNAL_URLS = new Set([
  'https://create.roblox.com/',
  'https://github.com/rojo-rbx/rojo/releases',
  'https://github.com/sokalabs/Hermes-Roblox'
]);

function isAllowedExternalUrl(url) {
  let parsed;
  try {
    parsed = new URL(String(url));
  } catch (_error) {
    return false;
  }
  return parsed.protocol === 'https:' && ALLOWED_EXTERNAL_URLS.has(parsed.toString());
}

function installWindowSecurityGuards(win) {
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedExternalUrl(url)) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', event => {
    event.preventDefault();
  });
}

function createWindow() {
  const workArea = screen.getPrimaryDisplay().workAreaSize;
  const targetWidth = Math.min(1440, Math.max(1180, workArea.width));
  const targetHeight = Math.min(920, Math.max(760, workArea.height));
  const win = new BrowserWindow({
    width: targetWidth,
    height: targetHeight,
    minWidth: 1040,
    minHeight: 720,
    title: 'Playro',
    backgroundColor: '#070910',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow = win;
  win.on('closed', () => { if (mainWindow === win) mainWindow = null; });
  installWindowSecurityGuards(win);
  win.loadFile(path.join(__dirname, 'index.html'));
  if (isDev) win.webContents.openDevTools();
  return win;
}

function isPathInside(child, parent) {
  const rel = path.relative(path.resolve(parent), path.resolve(child));
  return rel === '' || (!!rel && !rel.startsWith('..') && !path.isAbsolute(rel));
}

function safeExistingPath(targetPath) {
  if (!targetPath || typeof targetPath !== 'string') return null;
  const resolved = path.resolve(targetPath);
  if (!fs.existsSync(resolved)) return null;
  const allowedRoots = [resolveDataRoot(), resolveRojoDir(), resolveHermesHome(), ROOT]
    .filter(Boolean)
    .map(item => path.resolve(item));
  if (!allowedRoots.some(root => isPathInside(resolved, root))) return null;
  return resolved;
}

function safeProjectFolder(projectPath) {
  const resolved = safeExistingPath(projectPath);
  if (!resolved) return null;
  try {
    if (!fs.statSync(resolved).isDirectory()) return null;
  } catch (_error) {
    return null;
  }
  const dataRoot = path.resolve(resolveDataRoot());
  if (!isPathInside(resolved, dataRoot)) return null;
  return resolved;
}

function safeRojoProjectPath(rojoProjectPath) {
  const resolved = safeExistingPath(rojoProjectPath);
  if (!resolved) return null;
  if (path.basename(resolved) !== 'default.project.json') return null;
  try {
    if (!fs.statSync(resolved).isFile()) return null;
  } catch (_error) {
    return null;
  }
  const projectDir = path.dirname(resolved);
  if (!safeProjectFolder(projectDir)) return null;
  return resolved;
}

function resolveWingetExecutable() {
  if (process.platform !== 'win32') return null;
  const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
  const candidates = [
    path.join(localAppData, 'Microsoft', 'WindowsApps', 'winget.exe'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'WindowsApps', 'Microsoft.DesktopAppInstaller_8wekyb3d8bbwe', 'winget.exe'),
  ];
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate)) return candidate;
  }
  const located = runCheck('where.exe', ['winget']);
  if (!located.ok) return null;
  const first = (located.stdout || '').split(/\r?\n/).map(line => line.trim()).find(Boolean);
  if (!first || !fs.existsSync(first)) return null;
  return first;
}

function runCheck(command, args = []) {
  try {
    const result = spawnSync(command, args, { encoding: 'utf8', shell: false });
    return { ok: result.status === 0, stdout: result.stdout || '', stderr: result.stderr || '' };
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

function findRobloxStudio() {
  if (process.platform !== 'win32') return null;
  const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
  const roots = [
    path.join(localAppData, 'Roblox', 'Versions'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Roblox'),
    path.join(process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'Roblox')
  ];
  for (const root of roots) {
    try {
      if (!fs.existsSync(root)) continue;
      for (const name of fs.readdirSync(root)) {
        const exe = path.join(root, name, 'RobloxStudioBeta.exe');
        if (fs.existsSync(exe)) return exe;
      }
    } catch (_error) {}
  }
  return null;
}


function resolvePlayroToolsDir() {
  if (process.env.PLAYRO_TOOLS_DIR) return process.env.PLAYRO_TOOLS_DIR;
  const localAppData = process.platform === 'win32' ? (process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local')) : path.join(os.homedir(), '.playro');
  return path.join(localAppData, process.platform === 'win32' ? 'playro' : '', 'tools');
}

function resolveRojoDir() {
  if (process.env.PLAYRO_ROJO_DIR) return process.env.PLAYRO_ROJO_DIR;
  return path.join(resolvePlayroToolsDir(), 'rojo');
}

function resolveRojoCommand() {
  const binName = process.platform === 'win32' ? 'rojo.exe' : 'rojo';
  const candidates = [
    process.env.PLAYRO_ROJO_BIN,
    isPackaged && path.join(process.resourcesPath, 'rojo', binName),
    path.join(resolveRojoDir(), binName),
    path.join(resolveRojoDir(), 'bin', binName),
    binName,
  ].filter(Boolean);
  return candidates.find(candidate => fs.existsSync(candidate)) || 'rojo';
}

function checkRojo() {
  const command = resolveRojoCommand();
  const version = runCheck(command, ['--version']);
  return {
    ok: version.ok,
    command: version.ok ? command : null,
    install_dir: resolveRojoDir(),
    version: version.stdout.trim() || version.stderr.trim(),
    help: 'Playro installs Rojo through a trusted package manager instead of executing unverified downloaded release assets.'
  };
}

function installRojoWithPackageManager() {
  if (rojoInstallProcess) return { ok: true, started: true, installing: true, rojo: checkRojo() };
  const current = checkRojo();
  if (current.ok) return { ok: true, already_installed: true, rojo: current };
  const rojoDir = resolveRojoDir();
  fs.mkdirSync(rojoDir, { recursive: true });
  sendPlayroSetupProgress({ status: 'running', step: 4, title: 'Installing Playro', stepLabel: 'Step 4/7: Preparing Rojo install', detail: 'Preparing Rojo install with a trusted package manager...', log: 'Preparing Rojo install with a trusted package manager...' });

  let command;
  let args;
  if (process.platform === 'win32') {
    const wingetExe = resolveWingetExecutable();
    if (!wingetExe) {
      return { ok: false, error: 'Windows Package Manager (winget) was not found on PATH.' };
    }
    const script = [
      `$ErrorActionPreference = 'Stop'`,
      `Write-Output 'Installing Rojo with Windows Package Manager...'`,
      `& ${JSON.stringify(wingetExe)} install --id Rojo.Rojo --exact --silent --accept-package-agreements --accept-source-agreements`,
      `rojo --version`,
      `Write-Output 'Rojo install complete.'`
    ].join('; ');
    command = 'powershell.exe';
    args = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script];
  } else {
    const script = [
      `set -e`,
      `mkdir -p ${JSON.stringify(rojoDir)}`,
      `if ! command -v cargo >/dev/null 2>&1; then echo 'Cargo is required to install Rojo securely on this platform. Install Rust/Cargo, then retry Playro setup.' >&2; exit 127; fi`,
      `echo 'Installing pinned Rojo 7.6.1 from crates.io with Cargo...'`,
      `cargo install rojo --version 7.6.1 --locked --root ${JSON.stringify(rojoDir)}`,
      `${JSON.stringify(path.join(rojoDir, 'bin', 'rojo'))} --version`,
      `echo 'Rojo install complete.'`
    ].join('; ');
    command = 'bash';
    args = ['-lc', script];
  }

  rojoInstallProcess = spawn(command, args, { cwd: os.homedir(), env: { ...process.env }, stdio: ['ignore', 'pipe', 'pipe'] });
  const onData = (chunk, stream) => {
    const text = chunk.toString();
    console[stream === 'stderr' ? 'error' : 'log'](`[rojo-install] ${text.trim()}`);
    for (const line of text.split(/\\r?\\n/).map(item => item.trim()).filter(Boolean)) {
      const lower = line.toLowerCase();
      const step = lower.includes('install') || lower.includes('compile') || lower.includes('cargo') ? 5 : 4;
      sendPlayroSetupProgress({ status: 'running', step, title: 'Installing Playro', stepLabel: `Step ${step}/7: ${PLAYRO_SETUP_STEPS[step - 1]}`, detail: line, log: line, stream });
    }
  };
  rojoInstallProcess.stdout.on('data', data => onData(data, 'stdout'));
  rojoInstallProcess.stderr.on('data', data => onData(data, 'stderr'));
  rojoInstallProcess.on('exit', code => {
    rojoInstallProcess = null;
    const ok = code === 0 && checkRojo().ok;
    sendPlayroSetupProgress({ status: ok ? 'running' : 'failed', step: ok ? 6 : 5, title: ok ? 'Installing Playro' : 'Rojo install failed', stepLabel: ok ? 'Step 6/7: Verifying setup' : 'Rojo install failed', detail: ok ? 'Rojo is ready. Verifying setup...' : `Rojo installer exited with code ${code}.`, log: ok ? 'Rojo install complete.' : `Rojo installer exited with code ${code}.` });
  });
  return { ok: true, started: true, rojo: checkRojo() };
}

function checkStudio() {
  const studioPath = findRobloxStudio();
  return { ok: Boolean(studioPath), path: studioPath, help: 'Install Roblox Studio from https://create.roblox.com/' };
}

function installRojoWithWinget() {
  // Keep the IPC name for compatibility while routing through the hardened
  // package-manager installer.
  return installRojoWithPackageManager();
}

ipcMain.handle('api-base', () => `http://127.0.0.1:${API_PORT}`);
ipcMain.handle('api-auth-token', () => API_TOKEN);

ipcMain.handle('check-setup', async () => ({
  backend: await backendHealth(),
  hermes: checkHermesRuntime(),
  rojo: checkRojo(),
  studio: checkStudio()
}));

ipcMain.handle('install-hermes-runtime', async () => installHermesRuntime());
ipcMain.handle('prompt-install-hermes-runtime', async () => ensureHermesRuntime());
ipcMain.handle('install-rojo', async () => installRojoWithWinget());

ipcMain.handle('open-external', async (_event, url) => {
  if (!isAllowedExternalUrl(url)) {
    return { ok: false, error: 'External URL is not allowed.' };
  }
  const normalized = new URL(String(url)).toString();
  await shell.openExternal(normalized);
  return { ok: true };
});

ipcMain.handle('open-path', async (_event, targetPath) => {
  const resolved = safeExistingPath(targetPath);
  if (!resolved) return { ok: false, error: `Path not found: ${targetPath}` };
  const result = await shell.openPath(resolved);
  return { ok: !result, error: result || null, path: resolved };
});

ipcMain.handle('open-project-folder', async (_event, projectPath) => {
  const resolved = safeProjectFolder(projectPath);
  if (!resolved) return { ok: false, error: `Project folder not found: ${projectPath}` };
  const result = await shell.openPath(resolved);
  return { ok: !result, error: result || null, path: resolved };
});

ipcMain.handle('copy-text', async (_event, text) => {
  clipboard.writeText(String(text || ''));
  return { ok: true };
});

ipcMain.handle('open-rojo-project', async (_event, rojoProjectPath) => {
  const resolved = safeRojoProjectPath(rojoProjectPath);
  if (!resolved) return { ok: false, error: `Rojo project file not found: ${rojoProjectPath}` };
  const projectDir = path.dirname(resolved);
  const rojoCommand = resolveRojoCommand();
  const command = `"${rojoCommand}" serve "${resolved}"`;
  const buildCommand = `"${rojoCommand}" build "${resolved}" --output "${path.join(projectDir, 'playro-studio-export.rbxlx')}"`;
  clipboard.writeText(`${command}\n${buildCommand}`);

  const rojo = checkRojo();
  if (rojo.ok) {
    if (rojoProcess) {
      terminateProcess(rojoProcess, 'rojo');
      rojoProcess = null;
    }
    rojoProcess = spawn(resolveRojoCommand(), ['serve', resolved], {
      cwd: projectDir,
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false
    });
    rojoProcess.stdout.on('data', data => console.log(`[rojo] ${data.toString().trim()}`));
    rojoProcess.stderr.on('data', data => console.error(`[rojo] ${data.toString().trim()}`));
    rojoProcess.on('exit', code => {
      console.log(`[rojo] exited ${code}`);
      rojoProcess = null;
    });
  }

  await shell.openPath(projectDir);

  const studio = checkStudio();
  if (studio.ok) {
    try {
      const child = spawn(studio.path, [], { detached: true, stdio: 'ignore' });
      child.unref();
    } catch (error) {
      studio.error = error.message;
    }
  }

  return {
    ok: true,
    path: resolved,
    projectDir,
    command,
    buildCommand,
    rojo,
    studio,
    message: rojo.ok ? 'Rojo server started. Project folder opened.' : 'Rojo not installed. Project folder opened and command copied.'
  };
});


function waitForProcessExit(getProcess, label, timeoutMs = 900000) {
  return new Promise(resolve => {
    const proc = getProcess();
    if (!proc) return resolve({ ok: true, missing: true });
    const timer = setTimeout(() => {
      terminateProcess(proc, label);
      resolve({ ok: false, error: `${label} timed out.` });
    }, timeoutMs);
    proc.once('exit', code => {
      clearTimeout(timer);
      resolve({ ok: code === 0, code });
    });
  });
}

async function runFullPlayroSetup() {
  sendPlayroSetupProgress({ status: 'running', step: 1, title: 'Installing Playro', stepLabel: 'Step 1/7: Installing Playro shell', detail: 'Playro app files are installed. Preparing required tools...', log: 'Playro app shell installed.' });

  const allowLocalGenerator = process.env.PLAYRO_ALLOW_LOCAL_GENERATOR === '1' || process.env.NODE_ENV === 'test';
  let hermesRuntime = checkHermesRuntime();
  const hermesInstalled = hasInstalledHermesRuntime();
  if (!hermesInstalled) {
    const hermes = installHermesRuntime();
    if (hermes.started) await waitForProcessExit(() => hermesInstallProcess, 'Playro AI Engine install');
    hermesRuntime = checkHermesRuntime();
  } else {
    sendPlayroSetupProgress({ status: 'running', step: 3, title: 'Installing Playro', stepLabel: 'Step 3/7: Installing Playro AI Engine', detail: 'Playro AI Engine is already installed.', log: 'Playro AI Engine already installed.' });
  }
  if (!hermesRuntime.ok) {
    if (!allowLocalGenerator) {
      process.env.PLAYRO_ALLOW_LOCAL_GENERATOR = '1';
    }
    sendPlayroSetupProgress({
      status: 'running',
      step: 3,
      percent: setupPercent(3),
      title: 'Installing Playro',
      stepLabel: 'Step 3/7: Installing Playro AI Engine',
      detail: 'Playro AI Engine is not installed; continuing with the local Roblox generator fallback, then checking optional Rojo.',
      log: 'Playro AI Engine missing. Continuing setup with local generator fallback so Rojo and Studio handoff checks can run.'
    });
  }

  if (!checkRojo().ok) {
    const rojo = installRojoWithPackageManager();
    if (rojo.started) await waitForProcessExit(() => rojoInstallProcess, 'Rojo install');
  } else {
    sendPlayroSetupProgress({ status: 'running', step: 5, title: 'Installing Playro', stepLabel: 'Step 5/7: Preparing Studio handoff', detail: 'Rojo is already installed for Studio sync.', log: 'Rojo already installed.' });
  }
  if (!checkRojo().ok) {
    sendPlayroSetupProgress({ status: 'running', step: 5, percent: 72, title: 'Installing Playro', stepLabel: 'Step 5/7: Preparing Studio handoff', detail: 'Rojo was not found. You can install it later from Setup when you want Studio sync.', log: 'Rojo not installed; continuing because it is optional for local builds.' });
  }

  sendPlayroSetupProgress({ status: 'running', step: 6, title: 'Installing Playro', stepLabel: 'Step 6/7: Verifying setup', detail: 'Checking engine, optional Rojo, and local project service...', log: 'Verifying Playro setup...' });
  startBackend();
  sendPlayroSetupProgress({ status: 'complete', step: 7, percent: 100, title: 'Playro is ready', stepLabel: 'Step 7/7: Launching Playro', detail: 'Everything is installed. Launching the Playro desktop app...', log: 'Setup complete. Launching Playro desktop app.' });
  const win = mainWindow && !mainWindow.isDestroyed() ? mainWindow : createWindow();
  if (setupWindow && !setupWindow.isDestroyed()) setTimeout(() => setupWindow.close(), 1200);
  return { ok: true, launched: true, setup: { hermes: checkHermesRuntime(), rojo: checkRojo(), studio: checkStudio() } };
}

function skipPlayroSetup() {
  process.env.PLAYRO_ALLOW_LOCAL_GENERATOR = '1';
  sendPlayroSetupProgress({
    status: 'complete',
    step: 7,
    percent: 100,
    title: 'Opening Playro',
    stepLabel: 'Setup skipped',
    detail: 'Setup was skipped. You can install the Playro AI Engine and Rojo later from Setup if builds fail.',
    log: 'Setup skipped by user. Local generator fallback enabled for this session.'
  });
  startBackend();
  const win = mainWindow && !mainWindow.isDestroyed() ? mainWindow : createWindow();
  win.show();
  win.focus();
  if (setupWindow && !setupWindow.isDestroyed()) {
    setTimeout(() => setupWindow.close(), 400);
  }
  return {
    ok: true,
    skipped: true,
    setup: { hermes: checkHermesRuntime(), rojo: checkRojo(), studio: checkStudio() }
  };
}

function createSetupWindow() {
  const workArea = screen.getPrimaryDisplay().workAreaSize;
  const win = new BrowserWindow({
    width: Math.min(1120, Math.max(920, workArea.width - 120)),
    height: Math.min(780, Math.max(680, workArea.height - 120)),
    minWidth: 860,
    minHeight: 620,
    title: 'Playro Setup',
    backgroundColor: '#111827',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  setupWindow = win;
  win.on('closed', () => { if (setupWindow === win) setupWindow = null; });
  installWindowSecurityGuards(win);
  win.loadFile(path.join(__dirname, 'index.html'), { hash: 'setup' });
  return win;
}

ipcMain.handle('start-full-setup', async () => runFullPlayroSetup());
ipcMain.handle('skip-playro-setup', async () => skipPlayroSetup());

app.whenReady().then(async () => {
  const allowLocalGenerator = process.env.PLAYRO_ALLOW_LOCAL_GENERATOR === '1';
  const setupNeeded = !hasInstalledHermesRuntime();
  if (setupNeeded && process.env.NODE_ENV !== 'test' && !allowLocalGenerator) {
    createSetupWindow();
  } else {
    startBackend();
    createWindow();
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (!hasInstalledHermesRuntime() && process.env.NODE_ENV !== 'test' && !allowLocalGenerator) createSetupWindow();
      else createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (rojoProcess) {
    terminateProcess(rojoProcess, 'rojo');
    rojoProcess = null;
  }
  if (apiProcess) {
    terminateProcess(apiProcess, 'backend');
    apiProcess = null;
  }
});

console.log(`[main] isPackaged=${isPackaged}, ROOT=${ROOT}`);
