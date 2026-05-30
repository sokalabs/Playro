const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '..', '..', '..');
const outRoot = path.join(projectRoot, 'product', 'roblox_ai_studio', 'artifacts', 'testing-comparison');
fs.mkdirSync(outRoot, { recursive: true });

const started = new Date();

function rel(p) {
  return path.relative(projectRoot, p).replace(/\\/g, '/');
}

function runTool(tool) {
  const logPath = path.join(outRoot, tool.id, 'result.log');
  const resultPath = path.join(outRoot, tool.id, 'result.json');
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const env = { ...process.env, PLAYRO_ALLOW_LOCAL_GENERATOR: process.env.PLAYRO_ALLOW_LOCAL_GENERATOR || '1' };
  if (tool.env) Object.assign(env, tool.env);
  const res = spawnSync(tool.command, tool.args, {
    cwd: desktopRoot,
    env,
    encoding: 'utf8',
    timeout: tool.timeoutMs || 90000,
    shell: false,
  });
  const timedOut = Boolean(res.error && res.error.code === 'ETIMEDOUT');
  const ok = res.status === 0 && !timedOut;
  const output = [
    `$ ${[tool.command, ...tool.args].join(' ')}`,
    res.stdout || '',
    res.stderr || '',
    res.error ? `ERROR: ${res.error.message}` : '',
  ].filter(Boolean).join('\n');
  fs.writeFileSync(logPath, output, 'utf8');
  const result = {
    id: tool.id,
    tool: tool.name,
    ok,
    score: ok ? tool.score : 0,
    setupGated: Boolean(tool.setupGated),
    command: [tool.command, ...tool.args].join(' '),
    status: res.status,
    signal: res.signal,
    timedOut,
    result: rel(logPath),
  };
  fs.writeFileSync(resultPath, JSON.stringify(result, null, 2), 'utf8');
  return result;
}

const tools = [
  {
    id: 'deterministic-static-smoke',
    name: 'Deterministic static smoke',
    score: 82,
    command: process.execPath,
    args: ['scripts/smoke.js'],
  },
  {
    id: 'renderer-fake-dom-smokes',
    name: 'Renderer fake-DOM smokes',
    score: 88,
    command: process.execPath,
    args: ['scripts/sidebar-button-smoke.js'],
  },
  {
    id: 'refinement-sse-smokes',
    name: 'Refinement + SSE completion smokes',
    score: 90,
    command: process.execPath,
    args: ['-e', "require('child_process').execFileSync(process.execPath,['scripts/refinement-flow-smoke.js'],{stdio:'inherit'}); require('child_process').execFileSync(process.execPath,['scripts/sse-completion-smoke.js'],{stdio:'inherit'});"],
  },
  {
    id: 'runtime-browser-smoke',
    name: 'Runtime browser smoke',
    score: 92,
    command: process.execPath,
    args: ['scripts/desktop-runtime-smoke.js'],
    env: { ROBLOX_AI_STUDIO_SMOKE_PORT: String(12000 + Math.floor(Math.random() * 2000)) },
    timeoutMs: 120000,
  },
  {
    id: 'packaged-layout-verifier',
    name: 'Packaged layout verifier',
    score: 70,
    command: process.execPath,
    args: ['scripts/verify-packaged-layout.js'],
    setupGated: true,
  },
];

const results = tools.map(runTool);
const ranked = results.filter(r => r.ok).sort((a, b) => b.score - a.score);
const summaryPath = path.join(outRoot, 'summary.json');
const summary = {
  ok: results.some(r => r.ok) && results.filter(r => !r.ok && !r.setupGated).length === 0,
  started: started.toISOString(),
  finished: new Date().toISOString(),
  recommendation: ranked.slice(0, 3).map(r => `${r.tool} (${r.score})`).join(' > '),
  results,
};
fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), 'utf8');

console.log('# Playro desktop testing comparison');
console.log('');
console.log(`Started: ${summary.started}`);
console.log(`Finished: ${summary.finished}`);
console.log('');
console.log('| Tool | OK | Score | Setup-gated | Result |');
console.log('|---|---:|---:|---:|---|');
for (const r of results) {
  console.log(`| ${r.tool} | ${r.ok ? 'yes' : 'no'} | ${r.score} | ${r.setupGated ? 'yes' : 'no'} | ${r.result} |`);
}
console.log('');
console.log(`Recommendation: ${summary.recommendation || 'No passing desktop tool checks'}`);
console.log(`Summary: ${rel(summaryPath)}`);

if (!summary.ok) {
  const failed = results.filter(r => !r.ok && !r.setupGated).map(r => r.tool).join(', ');
  console.error(`Required desktop tool checks failed: ${failed}`);
  process.exit(1);
}
