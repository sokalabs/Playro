const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeDocument, createAppRoot, bindWindowGlobals } = require('./smoke-dom-harness');

const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '..', '..', '..');
const artifactRoot = path.join(projectRoot, 'product', 'roblox_ai_studio', 'artifacts', 'desktop-smoke');
const resultDump = path.join(artifactRoot, 'refinement-flow-result.json');

function createContext() {
  const document = new FakeDocument({ parseMode: 'messages' });
  const app = createAppRoot(document);
  Object.defineProperty(app, 'innerHTML', {
    set(html) {
      if (!html.includes('prompt-input')) {
        fs.writeFileSync(path.join(artifactRoot, 'refinement-debug-html.html'), html, 'utf8');
      }
      document.setHTML(app, html);
    },
    get() { return app._html || ''; },
  });
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
    console: { ...console, warn() {} },
    setTimeout,
    clearTimeout,
    EventSource: class {},
    fetch: async () => null,
  };
  bindWindowGlobals(context);
  return { context, document, app };
}

async function main() {
  fs.mkdirSync(artifactRoot, { recursive: true });
  const artifactsSource = fs.readFileSync(path.join(desktopRoot, 'src', 'playro-artifacts.js'), 'utf8');
  const apiClient = fs.readFileSync(path.join(desktopRoot, 'src', 'api-client.js'), 'utf8');
  const panelState = fs.readFileSync(path.join(desktopRoot, 'src', 'panel-state.js'), 'utf8');
  const renderer = fs.readFileSync(path.join(desktopRoot, 'src', 'renderer.js'), 'utf8');
  const { context, document, app } = createContext();
  vm.createContext(context);
  vm.runInContext(artifactsSource, context, { filename: 'playro-artifacts.js' });
  vm.runInContext(apiClient, context, { filename: 'api-client.js' });
  vm.runInContext(panelState, context, { filename: 'panel-state.js' });
  vm.runInContext(renderer, context, { filename: 'renderer.js' });
  vm.runInContext("state.setup.hermes = 'ready'; state.setup.rojo = 'ready'; state.setup.backend = 'ready'; render()", context);

  const build = document.getElementById('prompt-input');
  if (!build) throw new Error('prompt-input missing on landing');
  build.value = 'Make a smoke test obby with checkpoints and coins';
  document.getElementById('btn-build').click();
  await new Promise(resolve => setTimeout(resolve, 2200));

  const refinement = document.getElementById('refinement');
  if (!refinement) throw new Error('refinement input missing after first build');
  refinement.value = 'Add sky islands, a moving platform, and a finish portal';
  document.getElementById('btn-build').click();
  await new Promise(resolve => setTimeout(resolve, 2200));

  const messages = document.querySelectorAll('.message.user-msg .bubble').map(el => el.textContent.trim());
  const aiText = document.querySelectorAll('.message.ai-msg .bubble').map(el => el.textContent.trim()).join('\n---\n');
  const payload = { messages, aiText, hasRefinement: messages.some(text => text.includes('Add sky islands')) };
  fs.writeFileSync(resultDump, JSON.stringify(payload, null, 2), 'utf8');
  if (!payload.hasRefinement) throw new Error(`Refinement submit did not append user message: ${JSON.stringify(payload)}`);
  console.log(`Refinement flow smoke passed: ${path.relative(projectRoot, resultDump)}`);
}

main().catch(error => {
  console.error(error.stack || String(error));
  process.exit(1);
});
