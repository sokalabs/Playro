const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeDocument, createAppRoot, bindWindowGlobals } = require('./smoke-dom-harness');
const { PLAYRO_SERVER_MAIN } = require('../src/playro-artifacts.js');

const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '..', '..', '..');
const artifactRoot = path.join(projectRoot, 'product', 'roblox_ai_studio', 'artifacts', 'desktop-smoke');
const resultPath = path.join(artifactRoot, 'handoff-smoke-result.json');

function createContext() {
  const document = new FakeDocument({ parseMode: 'sidebar' });
  const app = createAppRoot(document);
  const calls = [];
  const project = {
    id: 'qa-obby',
    name: 'QA Obby',
    project_path: 'C:/Users/Soka/AppData/Roaming/Playro/playro-data/qa-obby',
    rojo_project: 'C:/Users/Soka/AppData/Roaming/Playro/playro-data/qa-obby/default.project.json',
    artifacts: [{ path: PLAYRO_SERVER_MAIN, preview: 'print("loaded")' }],
    files: ['default.project.json', PLAYRO_SERVER_MAIN],
  };
  const context = {
    document,
    window: {
      robloxAIStudio: {
        checkSetup: async () => ({ backend: { ok: true }, hermes: { ok: true }, rojo: { ok: false }, studio: { ok: false } }),
        openProjectFolder: async target => { calls.push({ method: 'openProjectFolder', target }); return { ok: true, path: target }; },
        openRojoProject: async target => { calls.push({ method: 'openRojoProject', target }); return { ok: true, command: `rojo serve "${target}"`, buildCommand: `rojo build "${target}" --output "C:/Users/Soka/Desktop/qa-obby.rbxlx"`, rojo: { ok: true }, studio: { ok: false } }; },
        openPath: async target => { calls.push({ method: 'openPath', target }); return { ok: true, path: target }; },
        copyText: async text => { calls.push({ method: 'copyText', text }); return { ok: true }; },
        installRojo: async () => { calls.push({ method: 'installRojo' }); return { ok: true }; },
        openExternal: async url => { calls.push({ method: 'openExternal', url }); return { ok: true }; },
      },
      addEventListener() {},
    },
    navigator: { clipboard: { writeText: async text => { calls.push({ method: 'clipboard', text }); } } },
    console: { ...console, warn() {} },
    setTimeout,
    clearTimeout,
    EventSource: class {},
    fetch: async (url, options = {}) => {
      calls.push({ method: 'fetch', url: String(url), httpMethod: options.method || 'GET' });
      if (String(url).endsWith('/export')) return { ok: true, json: async () => ({ ok: true, bundle_path: 'C:/Users/Soka/Desktop/qa-obby.zip' }) };
      return { ok: true, json: async () => ({ ok: true }) };
    },
  };
  bindWindowGlobals(context);
  return { context, document, app, calls, project };
}

function clickAction(document, action) {
  const btn = document.querySelectorAll('[data-action]').find(el => el.dataset.action === action);
  if (!btn) throw new Error(`Missing handoff action ${action}`);
  btn.click();
}

function loadRenderer(context) {
  const artifacts = fs.readFileSync(path.join(desktopRoot, 'src', 'playro-artifacts.js'), 'utf8');
  const apiClient = fs.readFileSync(path.join(desktopRoot, 'src', 'api-client.js'), 'utf8');
  const panelState = fs.readFileSync(path.join(desktopRoot, 'src', 'panel-state.js'), 'utf8');
  const renderer = fs.readFileSync(path.join(desktopRoot, 'src', 'renderer.js'), 'utf8');
  vm.runInContext(artifacts, context, { filename: 'playro-artifacts.js' });
  vm.runInContext(apiClient, context, { filename: 'api-client.js' });
  vm.runInContext(panelState, context, { filename: 'panel-state.js' });
  vm.runInContext(renderer, context, { filename: 'renderer.js' });
}

async function main() {
  fs.mkdirSync(artifactRoot, { recursive: true });
  const { context, document, app, calls, project } = createContext();
  vm.createContext(context);
  loadRenderer(context);
  context.__handoffProject = project;
  vm.runInContext('state.currentProject = __handoffProject; state.conversation = [{ role: "ai", done: true, code: "print(\\"loaded\\")" }]; state.lastCode = "print(\\"loaded\\")"; state.buildStage = "complete"; render();', context);

  if (!app.innerHTML.includes('Start Rojo & Open Studio')) throw new Error('Handoff button missing after generated project');
  clickAction(document, 'open-folder');
  await new Promise(resolve => setTimeout(resolve, 20));
  clickAction(document, 'open-studio');
  await new Promise(resolve => setTimeout(resolve, 20));
  clickAction(document, 'export-rojo');
  await new Promise(resolve => setTimeout(resolve, 20));
  clickAction(document, 'copy-luau');
  await new Promise(resolve => setTimeout(resolve, 20));

  const payload = { calls };
  fs.writeFileSync(resultPath, JSON.stringify(payload, null, 2), 'utf8');
  const folder = calls.find(call => call.method === 'openProjectFolder');
  const studio = calls.find(call => call.method === 'openRojoProject');
  const exportCall = calls.find(call => call.method === 'fetch' && call.url.includes('/projects/qa-obby/export') && call.httpMethod === 'POST');
  const openZip = calls.find(call => call.method === 'openPath' && call.target.endsWith('qa-obby.zip'));
  const copyLuau = calls.find(call => call.method === 'copyText' && call.text.includes('print'));
  if (!folder || folder.target !== project.project_path) throw new Error('Open folder did not use project_path');
  if (!studio || studio.target !== project.rojo_project) throw new Error('Start Rojo did not use rojo_project path');
  if (!exportCall || !openZip) throw new Error('Export Rojo ZIP did not call backend export and open bundle');
  if (!copyLuau) throw new Error('Copy Luau did not copy generated code');
  console.log(`Handoff smoke passed: ${path.relative(projectRoot, resultPath)}`);
}

main().catch(error => { console.error(error.stack || String(error)); process.exit(1); });
