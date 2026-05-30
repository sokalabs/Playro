const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeDocument, createAppRoot, bindWindowGlobals } = require('./smoke-dom-harness');
const { PLAYRO_SERVER_MAIN } = require('../src/playro-artifacts.js');

const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '..', '..', '..');
const artifactRoot = path.join(projectRoot, 'product', 'roblox_ai_studio', 'artifacts', 'desktop-smoke');
const resultDump = path.join(artifactRoot, 'sse-completion-result.json');

function json(payload) {
  return { ok: payload.ok !== false, json: async () => payload };
}

function createContext(fetchLog, eventsByUrl) {
  const document = new FakeDocument({ parseMode: 'messages' });
  const app = createAppRoot(document);
  Object.defineProperty(app, 'innerHTML', {
    set(html) { document.setHTML(app, html); },
    get() { return app._html || ''; },
  });

  class FakeEventSource {
    constructor(url) {
      this.url = url;
      this.listeners = {};
      this.closed = false;
      setTimeout(() => {
        const frames = eventsByUrl[url] || [];
        frames.forEach(frame => this._emit(frame.type, frame.payload));
      }, 10);
    }
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
    _emit(type, payload) {
      if (this.closed) return;
      const event = { data: JSON.stringify(payload) };
      (this.listeners[type] || []).forEach(fn => fn(event));
      if (type === 'message' && typeof this.onmessage === 'function') this.onmessage(event);
    }
    close() { this.closed = true; }
  }

  const fetch = async (url, options = {}) => {
    fetchLog.push({ url, method: options.method || 'GET', body: options.body || null });
    if (String(url).endsWith('/health')) return json({ ok: true });
    if (String(url).endsWith('/desktop/capabilities')) return json({ ok: false });
    if (String(url).endsWith('/generate') && options.method === 'POST') {
      return json({ ok: true, action: 'build_started', build_id: 'build_smoke_sse', events_url: '/generate/build_smoke_sse/events' });
    }
    if (String(url).endsWith('/builds')) return json({ ok: true, builds: [] });
    if (String(url).endsWith('/projects/sse-real-project')) {
      return json({
        ok: true,
        project: {
          id: 'sse-real-project',
          name: 'SSE Real Project',
          genre: 'Obby',
          project_path: 'C:/Users/[REDACTED]/AppData/Roaming/Playro/playro-data/sse-real-project',
          rojo_project: 'C:/Users/[REDACTED]/AppData/Roaming/Playro/playro-data/sse-real-project/default.project.json',
          files: ['default.project.json', 'manifest.json', PLAYRO_SERVER_MAIN],
          artifacts: [{ path: PLAYRO_SERVER_MAIN, preview: '-- server code' }],
          skill: { name: 'Game Designer' },
          quality_mode: 'Balanced',
        },
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  };

  const context = {
    document,
    window: {
      robloxAIStudio: {
        checkSetup: async () => ({ backend: { ok: true }, hermes: { ok: true }, rojo: { ok: true }, studio: { ok: false } }),
        installHermesRuntime: async () => ({ ok: true, started: true }),
      },
      addEventListener() {},
    },
    navigator: { clipboard: { writeText: async () => {} } },
    console,
    setTimeout,
    clearTimeout,
    EventSource: FakeEventSource,
    fetch,
  };
  bindWindowGlobals(context);
  return { context, document, app };
}

async function main() {
  fs.mkdirSync(artifactRoot, { recursive: true });
  const fetchLog = [];
  const eventsByUrl = {
    'http://127.0.0.1:8765/generate/build_smoke_sse/events': [
      { type: 'stage', payload: { build_id: 'build_smoke_sse', stage: 'plan', title: 'Plan Rojo project', detail: 'Planning.' } },
      { type: 'complete', payload: { build_id: 'build_smoke_sse', stage: 'complete', title: 'Build complete', detail: 'Finished.', data: { project_id: 'sse-real-project', ok: true, files: ['default.project.json', 'manifest.json', PLAYRO_SERVER_MAIN] } } },
    ],
    'http://127.0.0.1:8765/generate/constructor_injection/events': [
      { type: 'complete', payload: { build_id: 'constructor_injection', stage: 'complete', data: { project_id: 'constructor-project', ok: true } } },
    ],
  };
  const artifactsSource = fs.readFileSync(path.join(desktopRoot, 'src', 'playro-artifacts.js'), 'utf8');
  const apiClient = fs.readFileSync(path.join(desktopRoot, 'src', 'api-client.js'), 'utf8');
  const panelState = fs.readFileSync(path.join(desktopRoot, 'src', 'panel-state.js'), 'utf8');
  const renderer = fs.readFileSync(path.join(desktopRoot, 'src', 'renderer.js'), 'utf8');
  const { context, document, app } = createContext(fetchLog, eventsByUrl);
  vm.createContext(context);
  vm.runInContext(artifactsSource, context, { filename: 'playro-artifacts.js' });
  vm.runInContext(apiClient, context, { filename: 'api-client.js' });
  const injectedClient = context.PlayroApiClient.create({
    EventSource: context.EventSource,
    fetch: context.fetch,
  });
  const injectedCompletion = await injectedClient.waitForBuildSSE('constructor_injection', { maxWaitMs: 1000 });
  if (injectedCompletion?.project_id !== 'constructor-project') {
    throw new Error(`EventSource constructor injection failed: ${JSON.stringify(injectedCompletion)}`);
  }
  vm.runInContext(panelState, context, { filename: 'panel-state.js' });
  vm.runInContext(renderer, context, { filename: 'renderer.js' });
  vm.runInContext("state.setup.hermes = 'ready'; state.setup.rojo = 'ready'; state.setup.backend = 'ready'; render()", context);

  const input = document.getElementById('prompt-input');
  if (!input) throw new Error('prompt-input missing on landing');
  input.value = 'Make an SSE response path obby with coins';
  document.getElementById('btn-build').click();
  await new Promise(resolve => setTimeout(resolve, 600));

  const aiText = document.querySelectorAll('.message.ai-msg .bubble').map(el => el.textContent.trim()).join('\n---\n');
  const payload = { aiText, fetchLog, html: app.innerHTML };
  fs.writeFileSync(resultDump, JSON.stringify(payload, null, 2), 'utf8');
  if (!aiText.includes('Generated real project files on disk')) {
    throw new Error(`SSE completion did not render real generated-files copy: ${aiText}`);
  }
  if (aiText.includes('Backend was unavailable')) {
    throw new Error(`SSE completion still rendered backend-unavailable fallback: ${aiText}`);
  }
  const buildPolls = fetchLog.filter(entry => String(entry.url).endsWith('/builds'));
  if (buildPolls.length > 0) {
    throw new Error(`SSE path should not poll /builds after completion; saw ${buildPolls.length} poll(s)`);
  }
  console.log(`SSE completion smoke passed: ${path.relative(projectRoot, resultDump)}`);
}

main().catch(error => {
  console.error(error.stack || String(error));
  process.exit(1);
});
