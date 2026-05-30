const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const files = {
  api: path.resolve(root, '..', 'app', 'api.py'),
  index: path.join(root, 'src/index.html'),
  main: path.join(root, 'src/main.js'),
  package: path.join(root, 'package.json'),
  preload: path.join(root, 'src/preload.js'),
  apiClient: path.join(root, 'src/api-client.js'),
  panelState: path.join(root, 'src/panel-state.js'),
  renderer: path.join(root, 'src/renderer.js'),
  styles: path.join(root, 'src/styles.css'),
  engineBundle: path.join(root, 'scripts/prepare-playro-engine-bundle.js')
};

for (const [name, filePath] of Object.entries(files)) {
  if (!fs.existsSync(filePath)) throw new Error(`Missing ${name}: ${path.relative(root, filePath)}`);
}

const source = {
  api: fs.readFileSync(files.api, 'utf8'),
  css: fs.readFileSync(files.styles, 'utf8'),
  index: fs.readFileSync(files.index, 'utf8'),
  main: fs.readFileSync(files.main, 'utf8'),
  preload: fs.readFileSync(files.preload, 'utf8'),
  apiClient: fs.readFileSync(files.apiClient, 'utf8'),
  panelState: fs.readFileSync(files.panelState, 'utf8'),
  renderer: fs.readFileSync(files.renderer, 'utf8'),
  windowsAcceptance: fs.readFileSync(path.join(root, 'scripts/windows-acceptance-smoke.js'), 'utf8'),
};

function has(area, ...needles) {
  return needles.every(needle => source[area].includes(needle));
}

function lacks(area, ...needles) {
  return needles.every(needle => !source[area].includes(needle));
}

function check(name, ok) {
  return [name, Boolean(ok)];
}

async function checkHealthResponseOkFallback() {
  const { create } = require(files.apiClient);
  const client = create({
    fetch: async () => ({
      ok: true,
      json: async () => ({ status: 'healthy' }),
    }),
  });
  const health = await client.getHealth();
  if (health.ok !== true) throw new Error('Health response did not inherit HTTP ok status');
}

const checks = [
  check('Playro brand', has('renderer', 'Playro')),
  check('simple prompt-first headline', has('renderer', 'Build any Roblox game with a prompt', 'Playro is your Codex-like Roblox builder')),
  check('prompt input', has('renderer', 'prompt-input')),
  check('demo prompt templates', has('renderer', 'demoPrompts', 'starter-prompts', 'data-demo-prompt', 'Use prompt') && has('css', '.starter-prompts', '.starter-prompt')),
  check('generated outcome preview', has('renderer', 'renderBuildOutcomePreview', 'What Playro generates', 'Game plan', 'Luau scripts', 'Rojo project', 'Studio handoff') && has('css', '.outcome-preview', '.outcome-grid')),
  check('intent chips', has('renderer', 'intentChips', 'Combat', 'Worldbuilding', 'data-intent')),
  check('chat workspace', has('renderer', 'conversation', 'workspace', 'thread')),
  check('post-build dock composer', has('renderer', 'dock')),
  check('handoff buttons', has('renderer', 'Start Rojo & Open Studio', 'Export Rojo ZIP', '.rbxlx fallback commands', 'Next in Roblox Studio', 'handoff-guide') && has('css', '.handoff-guide') && has('main', 'buildCommand')),
  check('setup checklist', has('renderer', 'renderSetupChecklist', 'Install the Playro AI engine. Connect Studio later.', 'Install Playro AI engine', 'Add Rojo later', 'Playro AI engine') && has('main', 'check-setup')),
  check('build readiness summary', has('renderer', 'renderBuildReadinessSummary', 'Ready to build locally', 'Connect Studio later', 'data-smoke="build-readiness-summary"') && has('css', '.readiness-summary', '.readiness-state')),
  check('compact build options on home', has('renderer', 'renderBuildQuickPick', 'build-quick-pick', 'Build pack', 'Change build pack', 'btn-open-build-options') && lacks('renderer', 'renderHermesRobloxHub', 'Roblox build tools', 'Refresh capabilities')),
  check('skill packs in build options panel', has('renderer', 'defaultSkillPacks', 'renderSkillPackCard', 'data-skill-pack', 'skill-packs', 'First build', 'applySkillPack', 'cap-customize-block') && has('css', '.cap-skill-pack-list', '.cap-skill-pack-card')),
  check('labeled build options panel', has('renderer', 'renderSkillCard', 'Build options', 'Skills that work now', 'Works now', 'Coming soon', 'Build speed', 'cap-skill-card') && has('apiClient', '/desktop/capabilities')),
  check('mascot branding wired through shell', has('renderer', 'playro-mascot-dark.png') && has('index', 'playro-mascot-tiny.png', 'playro-app-icon.png', 'apple-touch-icon')),
  check('simple default sidebar navigation', has('renderer', 'primarySidebarItems', 'Projects', 'sidebar-nav-primary', 'btn-open-advanced-from-sidebar') && lacks('renderer', 'sidebar-section-label">ADAPTERS', '{ id: \'analytics\', label: \'Analytics\'', '{ id: \'logs\', label: \'Build Logs\'') && has('css', '.app-sidebar', '.sidebar-link')),
  check('advanced panels behind settings', has('renderer', 'renderAdvancedSettingsTools', 'Advanced build tools', 'data-open-advanced-panel', 'settings-advanced-tools', 'openAdvancedPanel', 'Build options') && lacks('renderer', 'settings-advanced-tools" open') && has('css', '.settings-advanced-grid', '.settings-advanced-btn')),
  check('simple top header navigation', has('renderer', 'top-nav-primary', 'btn-projects', 'btn-settings') && lacks('renderer', 'btn-skills', 'btn-build-history', 'btn-build-mode')),
  check('AI-engine parity panels', has('renderer', 'hermes_parity_surfaces', 'hermes_source', 'playro_surface', 'Playro ${escapeHTML(panel.hermesSource)} for Roblox')),
  check('Roblox skill routing', has('renderer', 'skill_id: state.selectedSkill', 'defaultRobloxSkills', 'playro-game-designer', 'Systems Builder', 'friendlySkillStatus') && has('css', '.cap-skill-card', '.status-pill')),
  check('quality mode selector', has('renderer', 'qualityMode', 'defaultQualityModes', 'High quality') && has('css', '.quality-option.selected')),
  check('build now connect later setup gate',
    has('renderer', 'shouldShowSetupBanner', 'shouldShowStudioConnectHint', 'studio-connect-hint', 'Optional:') &&
    has('renderer', 'canBuildLocally', 'Build locally now', 'Install Rojo only when you are ready to test in Studio') &&
    lacks('renderer', 'await installHermesRuntime();') &&
    has('preload', 'installHermesRuntime', 'installRojo') &&
    has('main', 'ensureHermesRuntime', 'createSetupWindow', 'runFullPlayroSetup', 'setup_required', 'PLAYRO_ALLOW_LOCAL_GENERATOR', 'local generator fallback', 'remoteHermesInstallDisabledResult', 'Remote installer execution is disabled', 'resolveBundledHermesAgentDir') &&
    lacks('main', 'install.ps1', 'install.sh', 'raw.githubusercontent.com/NousResearch/hermes-agent') &&
    lacks('main', 'Continue with local generator', 'Complete required Playro setup', "buttons: ['Open setup', 'Quit Playro']", 'dialog.showMessageBox')
  ),
  check('Hermes Desktop-style installer overlay', has('renderer', 'renderHermesInstallerOverlay', 'Installing Playro AI engine', 'Step 1/7: Starting installation', 'installer-progress-fill') && has('css', '.hermes-installer-modal', '.installer-log') && has('preload', 'onHermesInstallProgress')),
  check('full Playro setup installer screen before desktop launch', has('renderer', 'renderPlayroSetupScreen', 'Installing Playro shell', 'Downloading Playro AI Engine', 'Checking optional Rojo', 'Launching Playro', 'startFullSetupFlow', 'btn-skip-playro-setup', 'Skip setup for now', 'skipPlayroSetupFlow') && has('preload', 'startFullSetup', 'skipPlayroSetup', 'onPlayroSetupProgress') && has('main', 'createSetupWindow', 'runFullPlayroSetup', 'start-full-setup', 'skip-playro-setup', 'skipPlayroSetup') && has('css', '.setup-only-screen', '.windows-style-step', '.setup-skip-btn')),
  check('auto install rojo button', has('renderer', 'Download Rojo', 'install-rojo', 'Rojo.Rojo', 'cargo install rojo --version 7.6.1 --locked') && has('preload', 'installRojo') && has('main', 'installRojoWithWinget', 'installRojoWithPackageManager', 'cargo install rojo --version 7.6.1 --locked') && lacks('main', 'browser_' + 'download_url', 'https://api.github.com/repos/rojo-rbx/rojo/releases/latest')),
  check('Rojo setup is independent of AI engine install',
    has('main', 'Continuing setup with local generator fallback so Rojo and Studio handoff checks can run') &&
    has('main', 'resolveProductLocalHermesCommand', 'resolveBundledHermesCommand', 'hasExplicitHermesCommand', 'hasInstalledHermesRuntime') &&
    has('renderer', 'Playro AI engine install failed') &&
    lacks('main', 'Playro AI Engine verification failed.') &&
    lacks('renderer', 'state.installingRojo || !hermesReady || rojoReady', "state.installingRojo || state.setup.hermes !== 'ready' || state.setup.rojo === 'ready'")
  ),
  check('desktop API client module', has('apiClient', 'createPlayroApiClient', 'requestJson', 'apiEventUrl', 'X-Playro-API-Token') && has('index', './api-client.js')),
  check('desktop panel state module', has('panelState', 'createPlayroPanelState', 'SIDEBAR_PANEL_TO_OVERLAY', 'root.PlayroPanelState', 'module.exports') && has('renderer', 'window.PlayroPanelState.create') && has('index', './panel-state.js')),
  check('real backend generate route', has('apiClient', '/generate', '/projects/')),
  check('refinement fallback keeps current preview context', has('renderer', 'preview update', 'the current preview')),
  check('landing prompt CTA fits shorter VM viewport', has('css', 'padding: clamp(32px, 7vh, 92px)') && has('main', 'workAreaSize', 'targetHeight')),
  check('real handoff ipc', has('renderer', 'openRojoProject', 'openProjectFolder') && has('main', 'open-rojo-project')),
  check('first-build guidance panel', has('renderer', 'renderFirstBuildGuide', 'How it works', 'Build Roblox Project')),
  check('intent selection feedback', has('renderer', 'selectedIntent', 'data-intent', 'aria-pressed') && has('css', '.chip.selected')),
  check('build status rail', has('renderer', 'renderBuildStatus', 'Live build progress', 'status-pill')),
  check('post-build artifact checklist', has('renderer', 'renderArtifactChecklist', 'artifact-checklist', 'default.project.json', 'Studio handoff files') && has('css', '.artifact-checklist', '.artifact-chip')),
  check('post-build build receipt', has('renderer', 'renderBuildReceipt', 'Build Receipt', 'What Playro made', 'Files Playro created', 'How to test it', 'What to improve next', 'Ask for one improvement', 'View files') && has('css', '.build-receipt', '.receipt-grid', '.receipt-actions')),
  check('prompt fidelity meter', has('renderer', 'renderPromptFidelityMeter', 'scorePromptFidelity', 'Prompt fidelity', 'prompt-fidelity-meter', 'Not in your game yet', 'project?.prompt_fidelity') && has('css', '.prompt-fidelity-meter', '.fidelity-track', '.fidelity-chip')),
  check('SSE named event listeners', has('apiClient', "addEventListener('stage'", "addEventListener('complete'", "addEventListener('error'")),
  check('SSE complete payload fallback project id', has('renderer', 'state.lastComplete') && has('apiClient', 'nested.project_id', 'projectIdFromJob')),
  check('SSE completion promise prevents preview fallback race', has('apiClient', 'waitForBuildSSE', 'firstBuildCompletion', 'normalizeBuildCompletion')),
  check('SSE onmessage fallback for data-only frames', has('apiClient', 'es.onmessage', 'data.stage') && has('renderer', 'stageMap')),
  check('understandable setup settings panel', has('renderer', "activePanel: null", "isPanelActive('settings')", "setActivePanel('settings')", "openSidebarPanel('config')", 'Can I build yet', 'What each tool does', 'Your build picks', 'settings-build-picks', 'Works now', 'Expert settings', 'Advanced build tools') && has('css', '.settings-tool-list', '.settings-expert-block', '.landing-more')),
  check('no onboarding gate', lacks('renderer', 'onboarding-overlay', 'onboardingStep')),
  check('no visible internal Hermes tooling', lacks('renderer', 'Hermes powers', 'Unraid', 'cron')),
  check('aurora background', has('css', 'radial-gradient')),
  check('dark glass panels', has('css', 'backdrop-filter', '--panel')),
  check('electron backend integration', has('main', 'product.roblox_ai_studio.app.api')),
  check('backend API honors configured port env', has('api', 'HERMES_ROBLOX_API_PORT', 'run(host=_configured_api_host(), port=_configured_api_port())')),
  check('build history panel JS + CSS', has('renderer', 'renderBuildHistoryPanel', 'build-history-panel', 'history-row') && has('css', '.build-history-panel', '.panel-scrim', '.history-row', '.history-date-group')),
  check('24/7 build mode panel JS + CSS', has('renderer', 'renderBuildModePanel', 'build-mode-panel', 'build-mode-status') && has('css', '.build-mode-panel', '.build-mode-toggle-row', '.build-mode-status', '.detail-row')),
  check('slide panel shared CSS', has('css', '.slide-panel', '.panel-head', '.panel-body', '.panel-foot', '.panel-search')),
  check('build detail panel JS + CSS', has('renderer', 'renderBuildDetailPanel', 'build-detail-panel', "isPanelActive('buildDetail')", "setActivePanel('buildDetail')", 'openBuildDetail', 'closeBuildDetail', 'fetchProjectDetail', 'btn-detail-resume', 'btn-detail-export') && has('css', '.build-detail-panel', '.build-detail-meta', '.build-detail-artifacts', '.artifact-row', '.build-detail-actions')),
  check('windows acceptance uses canonical artifact paths', has('windowsAcceptance', 'playro-artifacts.js', 'PLAYRO_CORE_ARTIFACT_FILES', 'PLAYRO_SERVER_MAIN') && lacks('windowsAcceptance', 'src/server/', 'src/client/', 'src/shared/'))
];

const failed = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) throw new Error(`Smoke checks failed: ${failed.join(', ')}`);

checkHealthResponseOkFallback()
  .then(() => console.log('Desktop shell smoke passed'))
  .catch(error => { console.error(error.stack || String(error)); process.exit(1); });
