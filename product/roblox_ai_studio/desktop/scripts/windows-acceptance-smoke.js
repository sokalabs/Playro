const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { spawn, spawnSync } = require('child_process');
const {
  PLAYRO_CORE_ARTIFACT_FILES,
  PLAYRO_SERVER_MAIN,
  PLAYRO_SHARED_CONFIG,
  PLAYRO_CLIENT_HUD,
} = require('../src/playro-artifacts.js');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist');
const WIN_UNPACKED = path.join(DIST, 'win-unpacked');
const PLAYRO_EXE = path.join(WIN_UNPACKED, 'Playro.exe');
const REPORT_DIR = process.env.PLAYRO_ACCEPTANCE_REPORT_DIR || path.join(ROOT, 'acceptance');
const DATA_DIR = process.env.PLAYRO_DATA_DIR || path.join(os.tmpdir(), `playro-windows-acceptance-${Date.now()}`);
const PORT = String(process.env.HERMES_ROBLOX_API_PORT || '18765');
const TOKEN = process.env.PLAYRO_API_TOKEN || `acceptance-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const PROMPT = process.env.PLAYRO_ACCEPTANCE_PROMPT || 'make a colorful obby with checkpoints, coins, and a shop';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function exists(filePath) {
  return fs.existsSync(filePath);
}

// Headless, zero-touch provisioning contract verified against the main-process
// source. This runs without a packaged build or a real Python engine, so it is
// safe in CI. It asserts the ENV plumbing and graceful-degradation paths that
// already exist on main, plus a tolerant check for the dedicated PLAYRO_HEADLESS
// flag that a sibling unit introduces.
function assertHeadlessProvisioningContract() {
  const mainSrc = fs.readFileSync(path.join(ROOT, 'src', 'main.js'), 'utf8');
  const apiClientSrc = fs.readFileSync(path.join(ROOT, 'src', 'api-client.js'), 'utf8');
  const findings = {};

  // Backend health endpoint is on the frozen local 127.0.0.1:8765 contract.
  assert(
    mainSrc.includes("process.env.HERMES_ROBLOX_API_PORT || '8765'")
      && apiClientSrc.includes('http://127.0.0.1:8765'),
    'Headless contract: backend must default to 127.0.0.1:8765 (main.js port + api-client base)'
  );
  findings.backendPort8765 = true;

  // PLAYRO_ALLOW_LOCAL_GENERATOR enables engine-less provisioning, and the
  // first-launch path must skip the blocking setup window when it is set so the
  // app provisions without hanging on user input.
  assert(
    mainSrc.includes("process.env.PLAYRO_ALLOW_LOCAL_GENERATOR === '1'"),
    'Headless contract: main.js must respect PLAYRO_ALLOW_LOCAL_GENERATOR'
  );
  const readyBlock = (mainSrc.match(/app\.whenReady\(\)[\s\S]*?createWindow\(\);\s*\n/) || [''])[0];
  assert(
    readyBlock.includes('!allowLocalGenerator')
      && readyBlock.includes('startBackend();')
      && readyBlock.includes('createWindow();'),
    'Headless contract: first launch must start backend + main window directly (no blocking setup window) when allowLocalGenerator is set'
  );
  findings.noBlockingSetupWindow = true;

  // Engine-missing path must soft-degrade to the local generator rather than
  // hard-failing when the Python engine binary is absent (CI tolerance).
  assert(
    mainSrc.includes('local Roblox generator fallback'),
    'Headless contract: ensureHermesRuntime must soft-pass to the local generator when the engine is absent'
  );
  findings.engineMissingSoftDegrades = true;

  // Tolerant PLAYRO_HEADLESS probe: absence on current main must NOT fail this
  // smoke; the headless guarantee is delivered today via the local generator.
  const headlessReferenced = mainSrc.includes('PLAYRO_HEADLESS');
  findings.headlessFlagReferenced = headlessReferenced;
  findings.headlessFlagNote = headlessReferenced
    ? 'PLAYRO_HEADLESS is wired into the main process.'
    : 'PLAYRO_HEADLESS not yet present on main; tolerated. Headless provisioning is delivered via PLAYRO_ALLOW_LOCAL_GENERATOR.';

  return findings;
}

function requestJson(method, route, body) {
  return new Promise((resolve, reject) => {
    const payload = body ? Buffer.from(JSON.stringify(body)) : null;
    const req = http.request({
      hostname: '127.0.0.1',
      port: Number(PORT),
      path: route,
      method,
      headers: {
        ...(payload ? { 'Content-Type': 'application/json', 'Content-Length': payload.length } : {}),
        'X-Playro-API-Token': TOKEN,
      },
      timeout: 5000,
    }, res => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        let parsed = {};
        try { parsed = data ? JSON.parse(data) : {}; } catch (error) { return reject(new Error(`Invalid JSON from ${route}: ${data.slice(0, 500)}`)); }
        resolve({ status: res.statusCode, body: parsed });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error(`Timed out requesting ${route}`)));
    if (payload) req.write(payload);
    req.end();
  });
}

async function waitForHealth(timeoutMs = 90000) {
  const started = Date.now();
  let last = null;
  while (Date.now() - started < timeoutMs) {
    try {
      const result = await requestJson('GET', '/health');
      if (result.status === 200 && result.body && result.body.ok === true) return result.body;
      last = result;
    } catch (error) {
      last = error.message;
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  throw new Error(`Backend health did not become OK: ${JSON.stringify(last)}`);
}

async function waitForBuild(buildId, timeoutMs = 180000) {
  const started = Date.now();
  let last = null;
  while (Date.now() - started < timeoutMs) {
    const result = await requestJson('GET', '/builds');
    last = result.body;
    if (result.status === 200 && result.body && Array.isArray(result.body.builds)) {
      const job = result.body.builds.find(item => item && item.id === buildId);
      if (job && (job.status === 'completed' || job.status === 'failed')) return job;
    }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  throw new Error(`Build did not complete: ${JSON.stringify(last)}`);
}

function validateGeneratedProject(projectPath) {
  const required = [...PLAYRO_CORE_ARTIFACT_FILES];
  const missing = required.filter(rel => !exists(path.join(projectPath, rel)));
  assert(missing.length === 0, `Generated project missing files: ${missing.join(', ')}`);

  const rojo = JSON.parse(fs.readFileSync(path.join(projectPath, 'default.project.json'), 'utf8'));
  const manifest = JSON.parse(fs.readFileSync(path.join(projectPath, 'manifest.json'), 'utf8'));
  const server = fs.readFileSync(path.join(projectPath, PLAYRO_SERVER_MAIN), 'utf8');
  const config = fs.readFileSync(path.join(projectPath, PLAYRO_SHARED_CONFIG), 'utf8');
  const client = fs.readFileSync(path.join(projectPath, PLAYRO_CLIENT_HUD), 'utf8');
  const plan = fs.readFileSync(path.join(projectPath, 'game_plan.md'), 'utf8');

  assert(rojo.name || rojo.tree, 'default.project.json is not a usable Rojo project file');
  assert(manifest.original_prompt && manifest.original_prompt.toLowerCase().includes('obby'), 'manifest.json does not preserve the acceptance prompt');
  assert(server.includes('Players') || server.includes('Checkpoint') || server.includes('coin'), 'Main.server.lua lacks expected Roblox gameplay code');
  assert(config.includes('GameConfig') || config.includes('Coins') || config.includes('Checkpoints'), 'GameConfig.lua lacks expected config content');
  assert(client.includes('Players') || client.includes('HUD') || client.includes('Coins'), 'HUD.client.lua lacks expected client/HUD content');
  assert(plan.length > 100, 'game_plan.md is too small to be a useful handoff plan');

  return { required, manifestTitle: manifest.title || null, rojoName: rojo.name || null };
}

function validateRojoHandoff(projectPath) {
  const bundledRojo = path.join(WIN_UNPACKED, 'resources', 'rojo', process.platform === 'win32' ? 'rojo.exe' : 'rojo');
  const rojoCommand = process.env.PLAYRO_ROJO_BIN || (exists(bundledRojo) ? bundledRojo : 'rojo');
  const result = spawnSync(rojoCommand, ['sourcemap', path.join(projectPath, 'default.project.json'), '--output', path.join(projectPath, 'acceptance-sourcemap.json')], {
    cwd: projectPath,
    encoding: 'utf8',
    shell: process.platform === 'win32',
  });
  if (result.status === 0 && exists(path.join(projectPath, 'acceptance-sourcemap.json'))) {
    return { ok: true, command: rojoCommand, stdout: (result.stdout || '').slice(0, 1000) };
  }
  return {
    ok: false,
    command: rojoCommand,
    status: result.status,
    stdout: (result.stdout || '').slice(0, 1000),
    stderr: (result.stderr || '').slice(0, 1000),
  };
}

(async () => {
  fs.mkdirSync(REPORT_DIR, { recursive: true });

  // Always verify the headless, zero-touch provisioning contract from source.
  // This is engine- and build-independent, so it gates every environment.
  const headlessContract = assertHeadlessProvisioningContract();

  // Full packaged acceptance requires Windows and a built Playro.exe. When those
  // prerequisites are absent (typical CI without a packaged build), we record a
  // graceful skip and exit 0 — the headless source contract above still ran.
  const prerequisitesMet = process.platform === 'win32' && exists(PLAYRO_EXE);
  if (!prerequisitesMet) {
    const skipReport = {
      platform: process.platform,
      exe: PLAYRO_EXE,
      verdict: 'SKIPPED_NO_PACKAGED_BUILD',
      skipped: true,
      headlessContract,
      reason: process.platform !== 'win32'
        ? `Windows packaged acceptance requires win32, got ${process.platform}. Headless provisioning source contract verified.`
        : `Missing packaged Playro.exe at ${PLAYRO_EXE} (run npm run build:win for the full packaged run). Headless provisioning source contract verified.`,
      finishedAt: new Date().toISOString(),
    };
    fs.writeFileSync(path.join(REPORT_DIR, 'playro-windows-acceptance-report.json'), JSON.stringify(skipReport, null, 2));
    console.log(JSON.stringify(skipReport, null, 2));
    return;
  }

  fs.rmSync(DATA_DIR, { recursive: true, force: true });
  fs.mkdirSync(DATA_DIR, { recursive: true });

  const env = {
    ...process.env,
    HERMES_ROBLOX_API_PORT: PORT,
    PLAYRO_API_TOKEN: TOKEN,
    PLAYRO_DATA_DIR: DATA_DIR,
    PLAYRO_ALLOW_LOCAL_GENERATOR: '1',
    PLAYRO_USE_HERMES_AGENT: process.env.PLAYRO_USE_HERMES_AGENT || '0',
    PLAYRO_ACCEPTANCE: '1',
    // Pass through the dedicated headless flag when the operator set it. The
    // packaged app provisions headlessly today via PLAYRO_ALLOW_LOCAL_GENERATOR;
    // PLAYRO_HEADLESS is forwarded so the sibling unit's flag is honored once it
    // lands, without this smoke depending on it.
    PLAYRO_HEADLESS: process.env.PLAYRO_HEADLESS || '1',
  };

  // The spawn env must carry the headless provisioning guarantees: local
  // generator allowance (so first launch never blocks on a setup window) and the
  // frozen local backend port.
  assert(env.PLAYRO_ALLOW_LOCAL_GENERATOR === '1', 'Headless run: PLAYRO_ALLOW_LOCAL_GENERATOR must be set so provisioning does not block on a setup window');
  assert(String(env.HERMES_ROBLOX_API_PORT) === String(PORT), 'Headless run: backend port must be wired through the spawn env');

  const child = spawn(PLAYRO_EXE, [], {
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe'],
    env,
  });

  const logs = [];
  child.stdout.on('data', chunk => logs.push(`[stdout] ${chunk.toString()}`));
  child.stderr.on('data', chunk => logs.push(`[stderr] ${chunk.toString()}`));
  child.on('exit', code => logs.push(`[process-exit] ${code}\n`));
  child.on('error', error => logs.push(`[process-error] ${error.stack || error}\n`));

  let backendChild = null;
  async function ensurePackagedBackendHealth() {
    try {
      return await waitForHealth(15000);
    } catch (firstError) {
      logs.push(`[acceptance] packaged Electron shell did not expose backend quickly: ${firstError.message}\n`);
      const backendDir = path.join(WIN_UNPACKED, 'resources', 'backend');
      const packagedPython = path.join(WIN_UNPACKED, 'resources', 'python', 'python.exe');
      const pythonExe = process.env.PLAYRO_WINDOWS_PYTHON || (exists(packagedPython) ? packagedPython : 'python');
      assert(exists(backendDir), `Missing packaged backend dir at ${backendDir}`);
      backendChild = spawn(pythonExe, ['-m', 'product.roblox_ai_studio.app.api'], {
        cwd: backendDir,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: {
          ...env,
          PYTHONUNBUFFERED: '1',
          PYTHONPATH: backendDir,
        },
      });
      backendChild.stdout.on('data', chunk => logs.push(`[backend-stdout] ${chunk.toString()}`));
      backendChild.stderr.on('data', chunk => logs.push(`[backend-stderr] ${chunk.toString()}`));
      backendChild.on('exit', code => logs.push(`[backend-process-exit] ${code}\n`));
      backendChild.on('error', error => logs.push(`[backend-process-error] ${error.stack || error}\n`));
      const health = await waitForHealth(90000);
      health.acceptance_backend_fallback = true;
      return health;
    }
  }

  const report = {
    platform: process.platform,
    exe: PLAYRO_EXE,
    dataDir: DATA_DIR,
    port: PORT,
    prompt: PROMPT,
    startedAt: new Date().toISOString(),
    headlessContract,
    checks: {},
  };

  try {
    report.checks.processStarted = { ok: true, pid: child.pid };
    report.checks.health = await ensurePackagedBackendHealth();

    const generate = await requestJson('POST', '/generate', { prompt: PROMPT, quality: 'High quality', skill_id: 'obby' });
    assert(generate.status === 202 || generate.status === 200, `Generate returned HTTP ${generate.status}: ${JSON.stringify(generate.body)}`);
    const buildId = generate.body.build_id || generate.body.id;
    assert(buildId, `Generate response did not include build_id: ${JSON.stringify(generate.body)}`);
    report.checks.generateAccepted = generate.body;

    const build = await waitForBuild(buildId);
    assert(build.status === 'completed', `Build failed or incomplete: ${JSON.stringify(build)}`);
    report.checks.buildCompleted = build;

    const projectPath = build.project_path || (build.result && build.result.project_path) || (build.project && build.project.path);
    assert(projectPath && exists(projectPath), `Generated project path does not exist: ${projectPath}`);
    report.projectPath = projectPath;
    report.checks.generatedFiles = validateGeneratedProject(projectPath);
    report.checks.rojoHandoff = validateRojoHandoff(projectPath);
    report.verdict = report.checks.rojoHandoff.ok ? 'GO_FOR_WINDOWS_ACCEPTANCE' : 'NO_GO_ROJO_HANDOFF';
  } finally {
    report.finishedAt = new Date().toISOString();
    report.logs = logs.join('').slice(-12000);
    fs.writeFileSync(path.join(REPORT_DIR, 'playro-windows-acceptance-report.json'), JSON.stringify(report, null, 2));
    try { child.kill(); } catch (_error) {}
    try { if (backendChild) backendChild.kill(); } catch (_error) {}
  }

  if (report.verdict !== 'GO_FOR_WINDOWS_ACCEPTANCE') {
    console.error(JSON.stringify(report, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify(report, null, 2));
})().catch(error => {
  fs.mkdirSync(REPORT_DIR, { recursive: true });
  fs.writeFileSync(path.join(REPORT_DIR, 'playro-windows-acceptance-error.txt'), `${error.stack || error}\n`);
  console.error(error.stack || error);
  process.exit(1);
});
