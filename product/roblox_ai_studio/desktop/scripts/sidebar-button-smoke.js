const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeDocument, createAppRoot, bindWindowGlobals } = require('./smoke-dom-harness');

const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '..', '..', '..');
const artifactRoot = path.join(projectRoot, 'product', 'roblox_ai_studio', 'artifacts', 'desktop-smoke');
const resultPath = path.join(artifactRoot, 'sidebar-button-smoke-result.json');

const PRIMARY_SIDEBAR_PANELS = ['build', 'sessions', 'config'];
const ADVANCED_PANELS = ['analytics', 'models', 'logs', 'build24', 'skills', 'plugins', 'crews', 'keys', 'docs'];
const EXPECTED_ACTIVE_PANEL = {
  build: null,
  sessions: 'buildHistory',
  config: 'settings',
  analytics: 'buildAnalytics',
  models: 'qualityRouting',
  logs: 'buildLogs',
  build24: 'buildMode',
  skills: 'capabilities',
  plugins: 'adapters',
  crews: 'crews',
  keys: 'keys',
  docs: 'parity',
};

function createContext() {
  const document = new FakeDocument({ parseMode: 'sidebar' });
  const app = createAppRoot(document);
  const fetchCalls = [];
  const ipcCalls = [];
  const capabilities = {
    ok: true,
    roblox_skills: [{ id: 'playro-game-designer', name: 'Game Designer', stage: 'Plan', description: 'Plans any Roblox game idea.', usable: true }],
    quality_modes: [{ id: 'balanced', label: 'Balanced', description: 'Default.' }],
    skill_packs: [{ id: 'first-build', label: 'First build', skill_id: 'playro-game-designer', quality_mode: 'balanced', default: true }],
    hermes_parity_surfaces: [
      { id: 'analytics', label: 'Build analytics', hermes_source: 'analytics', status: 'planned', playro_surface: 'Metrics for Roblox builds.', rows: [['Signal', 'Value']] },
      { id: 'models', label: 'Quality routing', hermes_source: 'models', status: 'prototype', playro_surface: 'Quality modes.', rows: [['Mode', 'Balanced']] },
      { id: 'logs', label: 'Build logs', hermes_source: 'logs', status: 'prototype', playro_surface: 'Build logs.', rows: [['Stage', 'Generate']] },
      { id: 'plugins', label: 'Roblox adapters', hermes_source: 'plugins', status: 'planned', playro_surface: 'Adapters.', rows: [['Rojo', 'Sync']] },
      { id: 'crews', label: 'Builder crews', hermes_source: 'profiles', status: 'planned', playro_surface: 'Crews.', rows: [['Planner', 'Plan']] },
      { id: 'keys', label: 'Keys and accounts', hermes_source: 'keys', status: 'planned', playro_surface: 'Keys.', rows: [['Provider keys', 'Redacted']] },
      { id: 'docs', label: 'Documentation', hermes_source: 'docs', status: 'prototype', playro_surface: 'Docs.', rows: [['First build', 'Prompt']] },
    ],
  };
  const context = {
    document,
    window: {
      robloxAIStudio: {
        checkSetup: async () => ({ hermes: { ok: false }, rojo: { ok: false }, studio: { ok: false } }),
        installHermesRuntime: async () => { ipcCalls.push('installHermesRuntime'); return { ok: true, already_installed: true }; },
        installRojo: async () => { ipcCalls.push('installRojo'); return { ok: true }; },
        openExternal: async url => { ipcCalls.push(`openExternal:${url}`); return { ok: true }; },
        copyText: async text => { ipcCalls.push(`copyText:${text}`); return { ok: true }; },
      },
      addEventListener() {},
    },
    navigator: { clipboard: { writeText: async () => {} } },
    console: { ...console, warn() {} },
    setTimeout,
    clearTimeout,
    EventSource: class {},
    fetch: async url => {
      fetchCalls.push(String(url));
      if (String(url).endsWith('/desktop/capabilities')) return { ok: true, json: async () => capabilities };
      if (String(url).endsWith('/health')) return { ok: true, json: async () => ({ ok: true }) };
      if (String(url).endsWith('/projects')) return { ok: true, json: async () => ({ ok: true, projects: [] }) };
      if (String(url).includes('/build-mode/status')) return { ok: true, json: async () => ({ ok: true, enabled: false }) };
      return { ok: true, json: async () => ({ ok: true }) };
    },
  };
  bindWindowGlobals(context);
  return { context, document, app, fetchCalls, ipcCalls };
}

async function openPanel(document, panel) {
  if (PRIMARY_SIDEBAR_PANELS.includes(panel)) {
    const btn = document.querySelectorAll('[data-sidebar-panel]').find(el => el.dataset.sidebarPanel === panel);
    if (!btn) throw new Error(`missing primary sidebar button ${panel}`);
    btn.click();
    return;
  }
  const settingsBtn = document.querySelectorAll('[data-sidebar-panel]').find(el => el.dataset.sidebarPanel === 'config');
  if (!settingsBtn) throw new Error('missing Setup sidebar button');
  settingsBtn.click();
  await new Promise(resolve => setTimeout(resolve, 20));
  const advancedBtn = document.querySelectorAll('[data-open-advanced-panel]').find(el => el.dataset.openAdvancedPanel === panel);
  if (!advancedBtn) throw new Error(`missing advanced settings button ${panel}`);
  advancedBtn.click();
}

async function main() {
  fs.mkdirSync(artifactRoot, { recursive: true });
  const apiClient = fs.readFileSync(path.join(desktopRoot, 'src', 'api-client.js'), 'utf8');
  const panelState = fs.readFileSync(path.join(desktopRoot, 'src', 'panel-state.js'), 'utf8');
  const renderer = fs.readFileSync(path.join(desktopRoot, 'src', 'renderer.js'), 'utf8');
  const artifacts = fs.readFileSync(path.join(desktopRoot, 'src', 'playro-artifacts.js'), 'utf8');
  const { context, document, app, fetchCalls, ipcCalls } = createContext();
  vm.createContext(context);
  vm.runInContext(artifacts, context, { filename: 'playro-artifacts.js' });
  vm.runInContext(apiClient, context, { filename: 'api-client.js' });
  vm.runInContext(panelState, context, { filename: 'panel-state.js' });
  vm.runInContext(renderer, context, { filename: 'renderer.js' });
  vm.runInContext('render()', context);

  const requiredPanels = [...PRIMARY_SIDEBAR_PANELS, ...ADVANCED_PANELS];
  const results = [];
  for (const panel of requiredPanels) {
    await openPanel(document, panel);
    await new Promise(resolve => setTimeout(resolve, 20));
    const html = app.innerHTML;
    const activePanel = vm.runInContext('state.activePanel', context);
    const expectedActivePanel = EXPECTED_ACTIVE_PANEL[panel];
    const activeParityPanel = vm.runInContext('state.activeParityPanel', context);
    const expectedParityPanel = expectedActivePanel === 'parity' ? panel : null;
    const visible = html.includes('PLAYRO') && (panel === 'build' || html.includes('panel') || html.includes('Setup'));
    const singleActivePanel = activePanel === expectedActivePanel;
    const selectedParityPanel = activeParityPanel === expectedParityPanel;
    results.push({ panel, ok: visible && singleActivePanel && selectedParityPanel, activePanel, expectedActivePanel, activeParityPanel, expectedParityPanel });
    if (panel !== 'build') {
      document.dispatchEvent({ type: 'keydown', key: 'Escape' });
      await new Promise(resolve => setTimeout(resolve, 20));
      const afterEscape = vm.runInContext('state.activePanel', context);
      const parityAfterEscape = vm.runInContext('state.activeParityPanel', context);
      if (afterEscape !== null || parityAfterEscape !== null) {
        results.push({ panel: `${panel}:escape`, ok: false, activePanel: afterEscape, expectedActivePanel: null, activeParityPanel: parityAfterEscape, expectedParityPanel: null });
      }
    }
  }

  await openPanel(document, 'config');
  await new Promise(resolve => setTimeout(resolve, 20));
  document.querySelectorAll('[data-action]').find(el => el.dataset.action === 'install-hermes-runtime').click();
  await new Promise(resolve => setTimeout(resolve, 30));
  document.querySelectorAll('[data-action]').find(el => el.dataset.action === 'install-rojo').click();
  await new Promise(resolve => setTimeout(resolve, 30));

  const buildOptionsBtn = document.getElementById('btn-open-build-options');
  if (!buildOptionsBtn) throw new Error('missing btn-open-build-options');
  buildOptionsBtn.click();
  let packBtn = null;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 25));
    packBtn = document.querySelectorAll('[data-skill-pack]').find(el => el.dataset.skillPack === 'first-build');
    if (packBtn) break;
  }
  if (!packBtn) throw new Error('missing skill pack button first-build');
  packBtn.click();
  await new Promise(resolve => setTimeout(resolve, 20));

  const payload = {
    ok: results.every(r => r.ok) && ipcCalls.includes('installHermesRuntime') && ipcCalls.includes('installRojo'),
    results,
    fetchCalls,
    ipcCalls
  };
  fs.writeFileSync(resultPath, JSON.stringify(payload, null, 2), 'utf8');
  if (!payload.ok) throw new Error(`Sidebar/button smoke failed: ${JSON.stringify(payload)}`);
  console.log(`Sidebar/button smoke passed: ${path.relative(projectRoot, resultPath)}`);
}

main().catch(error => { console.error(error.stack || String(error)); process.exit(1); });
