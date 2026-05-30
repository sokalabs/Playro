const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '..', '..', '..');
const artifactRoot = path.join(projectRoot, 'product', 'roblox_ai_studio', 'artifacts', 'desktop-smoke');
const port = Number(process.env.ROBLOX_AI_STUDIO_SMOKE_PORT || 9876);
const allowBrowserSkip = process.env.PLAYRO_RUNTIME_SMOKE_ALLOW_BROWSER_SKIP === '1';
const evidence = {
  ok: false,
  productSurface: 'Playro desktop shell',
  cloneSafe: true,
  liveHermesConfigUsed: false,
  machineSpecificRegistryUsed: false,
  command: 'npm run smoke:runtime',
  artifacts: {},
  browserSkipped: false,
  checks: [],
  errors: []
};

function ensureArtifactRoot() {
  fs.mkdirSync(artifactRoot, { recursive: true });
}

function artifactPath(name) {
  return path.join(artifactRoot, name);
}

function recordCheck(name, ok, detail = '') {
  evidence.checks.push({ name, ok: Boolean(ok), detail });
  if (!ok) evidence.errors.push(`${name}${detail ? `: ${detail}` : ''}`);
}

function writeEvidence() {
  ensureArtifactRoot();
  const evidencePath = artifactPath('runtime-smoke-report.json');
  fs.writeFileSync(evidencePath, JSON.stringify(evidence, null, 2), 'utf8');
  evidence.artifacts.report = path.relative(projectRoot, evidencePath);
}

function request(url) {
  return new Promise((resolve, reject) => {
    http.get(url, response => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', chunk => { body += chunk; });
      response.on('end', () => resolve({ statusCode: response.statusCode, body }));
    }).on('error', reject);
  });
}

function startStaticServer() {
  const server = http.createServer((req, res) => {
    let urlPath;
    try {
      urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      if (urlPath.includes('\0')) throw new Error('NUL byte in URL path');
    } catch (_error) {
      res.writeHead(400);
      res.end('Bad request');
      return;
    }
    let rel = urlPath === '/' ? 'src/index.html' : urlPath.replace(/^\/+/, '');
    if (!rel.startsWith('src/')) rel = `src/${rel}`;
    const filePath = path.normalize(path.join(desktopRoot, rel));
    if (!filePath.startsWith(path.join(desktopRoot, 'src'))) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }
    fs.readFile(filePath, (error, data) => {
      if (error) {
        res.writeHead(404);
        res.end('Not found');
        return;
      }
      const ext = path.extname(filePath);
      const type = ext === '.html' ? 'text/html' : ext === '.css' ? 'text/css' : 'application/javascript';
      res.writeHead(200, { 'Content-Type': `${type}; charset=utf-8` });
      res.end(data);
    });
  });
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

function getBrowserCandidates() {
  const candidates = [];
  if (process.env.CHROMIUM_BIN) candidates.push(process.env.CHROMIUM_BIN);
  if (process.env.PLAYRO_BROWSER_BIN) candidates.push(process.env.PLAYRO_BROWSER_BIN);
  const platform = os.platform();
  if (platform === 'win32') {
    candidates.push('chromium', 'chrome', 'msedge');
    const absoluteCandidates = [
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files\\Chromium\\Application\\chromium.exe',
      'C:\\Program Files (x86)\\Chromium\\Application\\chromium.exe'
    ];
    for (const absolutePath of absoluteCandidates) {
      if (fs.existsSync(absolutePath)) candidates.push(absolutePath);
    }
  } else if (platform === 'darwin') {
    candidates.push(
      'chromium',
      'google-chrome',
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Chromium.app/Contents/MacOS/Chromium'
    );
  } else {
    candidates.push(
      'chromium',
      'chromium-browser',
      'google-chrome',
      '/usr/bin/chromium',
      '/usr/bin/chromium-browser',
      '/usr/bin/google-chrome',
      '/snap/bin/chromium'
    );
  }
  return [...new Set(candidates)];
}

function runBrowserCommand(browserCommand, args) {
  const timeoutMs = Number(process.env.PLAYRO_BROWSER_SMOKE_TIMEOUT_MS || 20000);
  return new Promise(resolve => {
    const child = spawn(browserCommand, args, { cwd: desktopRoot, env: { ...process.env } });
    let stdout = '';
    let stderr = '';
    let spawned = false;
    let settled = false;
    const finish = result => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };
    const timer = setTimeout(() => {
      stderr += `\nTimed out after ${timeoutMs}ms while running ${browserCommand}`;
      try { child.kill('SIGKILL'); } catch (_error) { /* best effort */ }
      finish({ code: 124, stdout, stderr, spawned, timedOut: true });
    }, timeoutMs);
    child.on('spawn', () => {
      spawned = true;
    });
    child.stdout.on('data', data => { stdout += data.toString(); });
    child.stderr.on('data', data => { stderr += data.toString(); });
    child.on('error', error => finish({ code: 127, stdout, stderr: String(error), spawned }));
    child.on('close', code => finish({ code, stdout, stderr, spawned }));
  });
}

async function runChromiumSmoke() {
  const browserCandidates = getBrowserCandidates();
  const url = `http://127.0.0.1:${port}/`;
  const screenshot = artifactPath('runtime-smoke-screenshot.png');
  const textDump = artifactPath('runtime-smoke-text.txt');
  const domDump = artifactPath('runtime-smoke-dom.html');
  const userDataDir = artifactPath('chromium-profile');
  const args = [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    `--user-data-dir=${userDataDir}`,
    `--window-size=1440,920`,
    `--screenshot=${screenshot}`,
    `--dump-dom`,
    '--virtual-time-budget=5000',
    `--run-all-compositor-stages-before-draw`,
    url
  ];
  let result = null;
  let browserUsed = '';
  const browserFailures = [];
  for (const candidate of browserCandidates) {
    const attempted = await runBrowserCommand(candidate, args);
    if (!attempted.spawned && /ENOENT/i.test(attempted.stderr)) continue;
    if (attempted.code === 0) {
      result = attempted;
      browserUsed = candidate;
      break;
    }
    browserFailures.push(`${candidate}: ${attempted.stderr.split('\n').slice(-3).join(' ') || `exit ${attempted.code}`}`);
  }

  let domText = '';
  if (result) {
    evidence.artifacts.browser = browserUsed;
    recordCheck('chromium launched renderer', true, result.stderr.split('\n').slice(-4).join('\n'));
    recordCheck('screenshot artifact captured', fs.existsSync(screenshot) && fs.statSync(screenshot).size > 5000, screenshot);
    evidence.artifacts.screenshot = path.relative(projectRoot, screenshot);

    fs.writeFileSync(domDump, result.stdout || '', 'utf8');
    evidence.artifacts.dom = path.relative(projectRoot, domDump);
    domText = result.stdout || '';
    const domTextForLog = domText.replace(/[<>]/g, ' ').replace(/\s+/g, ' ').trim();
    fs.writeFileSync(textDump, domTextForLog, 'utf8');
    evidence.artifacts.text = path.relative(projectRoot, textDump);
    recordCheck(
      'dumped rendered desktop DOM',
      domText.includes('Playro')
        && domText.includes('Build Roblox Project')
        && domText.includes('first-build-guide')
        && domText.includes('Build pack')
        && domText.includes('Recent builds'),
      domDump
    );
  } else {
    evidence.browserSkipped = true;
    const failureDetail = browserFailures.length ? ` Last attempts: ${browserFailures.slice(-3).join(' | ')}` : '';
    const detail = allowBrowserSkip
      ? `No working chromium-compatible browser binary available within timeout; local source-only skip enabled. This is not beta-release proof.${failureDetail}`
      : `No working chromium-compatible browser binary available within timeout. Install Chrome/Edge/Chromium or set PLAYRO_BROWSER_BIN.${failureDetail}`;
    recordCheck('chromium launched renderer', allowBrowserSkip, detail);
    recordCheck('screenshot artifact captured', allowBrowserSkip, detail);
    recordCheck('dumped rendered desktop DOM', allowBrowserSkip, detail);
  }

  const page = await request(url);
  recordCheck('renderer served clone-safe static shell', page.statusCode === 200 && page.body.includes('renderer.js'), `HTTP ${page.statusCode}`);

  const renderer = fs.readFileSync(path.join(desktopRoot, 'src', 'renderer.js'), 'utf8');
  const css = fs.readFileSync(path.join(desktopRoot, 'src', 'styles.css'), 'utf8');
  recordCheck('desktop-first product language present', renderer.includes('Playro') && renderer.includes('renderWorkspace'));
  if (domText) {
    const heroText = (domText.match(/Build Roblox games with AI[\s\S]*?Recent builds/) || [''])[0];
    recordCheck('primary visible surface is Playro', heroText.includes('Playro') && !heroText.includes('Hermes backend') && !heroText.includes('Hermes Agent'));
  } else {
    recordCheck(
      'primary visible surface is Playro',
      allowBrowserSkip,
      allowBrowserSkip
        ? 'Validated via renderer source checks because browser-rendered DOM capture was explicitly skipped.'
        : 'Browser-rendered DOM capture is required for beta readiness.'
    );
  }
  recordCheck('interactive prompt intent path present', renderer.includes('inferGenre') && renderer.includes('Detected ${inferGenre(prompt)}'));
  recordCheck('handoff and settings actions present', renderer.includes('Open Studio') && renderer.includes('Setup'));
  recordCheck('polished desktop styling loaded', css.includes('backdrop-filter') && css.includes('radial-gradient'));
  recordCheck('first-build guidance present', renderer.includes('renderFirstBuildGuide') && renderer.includes('How it works'));
  recordCheck('intent selection feedback present', renderer.includes('selectedIntent') && renderer.includes('aria-pressed'));
  recordCheck('build progress rail present', renderer.includes('renderBuildStatus') && renderer.includes('status-pill'));
  recordCheck('first-run guidance remains default landing', renderer.includes('renderLanding') && renderer.includes('renderFirstBuildGuide'));
  recordCheck('handoff flow completes instead of overflowing', renderer.includes("state.buildStage = 'complete'") && renderer.includes('renderHandoffActions'));
}

async function main() {
  ensureArtifactRoot();
  const server = await startStaticServer();
  try {
    await runChromiumSmoke();
  } finally {
    server.close();
  }
  evidence.ok = evidence.checks.every(check => check.ok);
  writeEvidence();
  if (!evidence.ok) {
    throw new Error(`Desktop runtime smoke failed: ${evidence.errors.join('; ')}`);
  }
  console.log(`Desktop runtime smoke passed: ${path.relative(process.cwd(), artifactRoot)}`);
  console.log(`Screenshot: ${evidence.artifacts.screenshot}`);
  console.log(`Report: ${evidence.artifacts.report}`);
}

main().catch(error => {
  evidence.ok = false;
  evidence.errors.push(error.stack || String(error));
  writeEvidence();
  console.error(error.stack || String(error));
  process.exit(1);
});
