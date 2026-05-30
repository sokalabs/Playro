const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeDocument, createAppRoot, bindWindowGlobals } = require('./smoke-dom-harness');
const desktopRoot = path.resolve(__dirname, '..');

const document = new FakeDocument({ parseMode: 'messages' });
const app = createAppRoot(document);
Object.defineProperty(app, 'innerHTML', {
  set(html) { document.setHTML(app, html); },
  get() { return app._html || ''; }
});
const context = {
  document,
  window: {
    robloxAIStudio: {
      checkSetup: async () => ({ hermes: { ok: true }, rojo: { ok: false }, studio: { ok: false } })
    },
    addEventListener() {}
  },
  navigator: { clipboard: { writeText: async () => {} } },
  console,
  setTimeout,
  clearTimeout,
  EventSource: class {},
  fetch: async () => ({ ok: true, json: async () => ({ ok: true }) })
};
bindWindowGlobals(context);
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(desktopRoot, 'src/playro-artifacts.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(desktopRoot, 'src/api-client.js'), 'utf8'), context, { filename: 'api-client.js' });
vm.runInContext(fs.readFileSync(path.join(desktopRoot, 'src/panel-state.js'), 'utf8'), context, { filename: 'panel-state.js' });
vm.runInContext(fs.readFileSync(path.join(desktopRoot, 'src/renderer.js'), 'utf8'), context, { filename: 'renderer.js' });
vm.runInContext("state.setup.backend = 'ready'; state.setup.hermes = 'ready'; state.setup.rojo = 'missing'; render()", context);
const html = app.innerHTML;
const result = {
  hasOrangeSetupBanner: html.includes('setup-banner'),
  hasStudioConnectHint: html.includes('studio-connect-hint'),
  pass: !html.includes('setup-banner') && html.includes('studio-connect-hint')
};
console.log(JSON.stringify(result, null, 2));
if (!result.pass) process.exit(1);
