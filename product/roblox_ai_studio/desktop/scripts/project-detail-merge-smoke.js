const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeDocument, createAppRoot, bindWindowGlobals } = require('./smoke-dom-harness');

const desktopRoot = path.resolve(__dirname, '..');

function createContext() {
  const document = new FakeDocument({ parseMode: 'sidebar' });
  const app = createAppRoot(document);
  const context = {
    document,
    window: {
      robloxAIStudio: {},
      addEventListener() {},
      location: { hash: '' },
    },
    navigator: { clipboard: { writeText: async () => {} } },
    console: { ...console, warn() {} },
    setTimeout,
    clearTimeout,
    EventSource: class {},
    fetch: async url => {
      const target = String(url);
      if (target.endsWith('/builds')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            builds: [{
              id: 'build_project_detail_smoke',
              project_path: 'C:\\tmp\\project-detail-smoke',
              prompt: 'make a cooperative obby with checkpoints and coins',
              genre: 'Obby',
              status: 'completed',
              quality: 'Balanced',
              started_at: Date.now(),
            }],
          }),
        };
      }
      return { ok: true, json: async () => ({ ok: true }) };
    },
  };
  bindWindowGlobals(context);
  return { context, app };
}

function assertIncludes(html, needle, label) {
  if (!html.includes(needle)) {
    throw new Error(`Project detail merge smoke missing ${label}: ${needle}`);
  }
}

async function main() {
  const apiClient = fs.readFileSync(path.join(desktopRoot, 'src', 'api-client.js'), 'utf8');
  const panelState = fs.readFileSync(path.join(desktopRoot, 'src', 'panel-state.js'), 'utf8');
  const renderer = fs.readFileSync(path.join(desktopRoot, 'src', 'renderer.js'), 'utf8');
  const artifacts = fs.readFileSync(path.join(desktopRoot, 'src', 'playro-artifacts.js'), 'utf8');
  const { context, app } = createContext();

  vm.createContext(context);
  vm.runInContext(artifacts, context, { filename: 'playro-artifacts.js' });
  vm.runInContext(apiClient, context, { filename: 'api-client.js' });
  vm.runInContext(panelState, context, { filename: 'panel-state.js' });
  vm.runInContext(renderer, context, { filename: 'renderer.js' });
  await vm.runInContext('fetchBuildHistory()', context);
  const mappedHistoryId = vm.runInContext('state.buildHistory[0]?.id', context);
  if (mappedHistoryId !== 'project-detail-smoke') {
    throw new Error(`Build history detail id should use project slug, got ${mappedHistoryId}`);
  }
  vm.runInContext(`
    panelState.setActivePanel('buildDetail');
    state.buildDetailLoading = false;
    state.buildDetailProjectId = 'project-detail-smoke';
    state.buildDetail = {
      id: 'project-detail-smoke',
      name: 'Project Detail Smoke',
      prompt: 'make a cooperative obby with checkpoints and coins',
      genre: 'Obby',
      quality_mode: 'Balanced',
      status: 'completed',
      skill: { name: 'Game Designer' },
      validation: { ok: true },
      timeline: [
        { title: 'Prompt received', detail: 'Captured the idea.', status: 'done' },
        { title: 'Generate project files', detail: 'Wrote Luau and Rojo files.', status: 'done' }
      ],
      history: [
        'Desktop build created for cooperative obby.',
        'Validation passed.'
      ],
      build_state: {
        logs: ['Generated 11 Rojo-ready artifacts.'],
        systems: ['checkpoints', 'coin collection economy'],
        learning_records: [{ title: 'Prompt pattern' }]
      },
      artifacts: [
        { path: 'default.project.json', bytes: 320 },
        { path: 'src/ServerScriptService/Main.server.lua', bytes: 2048 }
      ]
    };
    render();
  `, context);

  const html = app.innerHTML;
  assertIncludes(html, 'data-smoke="project-detail-analytics"', 'analytics section');
  assertIncludes(html, 'data-smoke="project-detail-timeline"', 'timeline section');
  assertIncludes(html, 'data-smoke="project-detail-logs"', 'logs section');
  assertIncludes(html, 'Project analytics', 'analytics heading');
  assertIncludes(html, 'Build timeline', 'timeline heading');
  assertIncludes(html, 'Build logs', 'logs heading');
  assertIncludes(html, 'Generated 11 Rojo-ready artifacts.', 'detail log content');
  console.log('Project detail merge smoke passed');
}

main().catch(error => { console.error(error.stack || String(error)); process.exit(1); });
