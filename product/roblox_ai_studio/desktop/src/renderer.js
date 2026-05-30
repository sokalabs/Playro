/* Playro — simple Lovable/Codex-style desktop UI */

const state = {
 apiBase: 'http://127.0.0.1:8765',
 apiToken: '',
 building: false,
 selectedIntent: null,
 buildStage: 'idle',
 setup: {
 backend: 'starting',
 hermes: 'unknown',
 rojo: 'unknown',
 studio: 'unknown'
 },
 installingHermes: false,
 installingRojo: false,
 conversation: [],
 projects: [
 { name: 'Cyber Detective City', genre: 'Roleplay Mystery', desc: 'NPC quests, apartments, vehicles, reputation.', time: '2h ago' },
 { name: 'Sky Island Survival', genre: 'Survival Adventure', desc: 'Resource loops, storms, crafting, team goals.', time: '5h ago' },
 { name: 'Pet Racing Arena', genre: 'Custom Roblox Experience', desc: 'Pets, vehicles, boosts, ranked rewards.', time: '1d ago' }
 ],
 currentProject: null,
 lastCode: '',
 activePanel: null,
 activeParityPanel: null,
 buildIntent: {
 genre: 'Adventure',
 systems: ['Economy', 'Progression'],
 quality: 'Balanced'
 },
 capabilities: null,
 selectedSkill: 'playro-game-designer',
 qualityMode: 'balanced',
  memoryPreview: [],
  pendingBuildResults: {},
  buildCompletions: {},
 // Build history panel (inspired by hermes-desktop Sessions)
  buildHistory: [],
 buildHistoryLoading: false,
 buildHistorySearch: '',
 buildHistorySearchResults: [],
 buildHistorySearching: false,
  // 24/7 Build Mode panel (inspired by hermes-desktop Schedules)
  continuousBuild: { enabled: false, intervalMin: 30, lastTickAt: null, lastTickStatus: null, tickCount: 0 },
  buildModeLoading: false,
  // Capabilities panel (inspired by hermes-desktop Skills + Tools screens)
  // Build detail panel (inspired by hermes-desktop Session Detail)
  buildDetailProjectId: null,
  buildDetail: null,
  buildDetailLoading: false,
  // Build analytics panel (inspired by hermes-desktop Analytics)
  buildAnalytics: null,
  buildAnalyticsLoading: false,
  // Build logs panel (inspired by hermes-desktop Logs)
  buildLogs: [],
  buildLogsLoading: false,
  buildLogsSearch: '',
  buildLogsFiltered: [],
  // Keys/accounts panel (inspired by hermes-desktop Keys/Auth)
  keysPanel: null,
  keysPanelLoading: false,
  // Quality routing panel (inspired by hermes-desktop Models)
  qualityRouting: null,
  qualityRoutingLoading: false,
  // Roblox adapters panel (Rojo, Studio, Open Cloud)
  adaptersPanel: null,
  adaptersPanelLoading: false,
  adaptersTestResults: {},
  // Builder crews panel (inspired by hermes-desktop Profiles)
  crewsPanel: null,
  crewsPanelLoading: false,
  hermesInstaller: { open: false, status: 'idle', percent: 0, step: 1, totalSteps: 7, title: 'Installing Playro AI engine', stepLabel: 'Step 1/7: Starting installation...', detail: 'Installing the Playro AI engine...', logs: [] },
  playroSetup: { open: false, started: false, status: 'idle', percent: 0, step: 1, totalSteps: 7, title: 'Installing Playro', stepLabel: 'Step 1/7: Installing Playro shell', detail: 'Preparing Playro...', logs: [] },
};

const api = window.PlayroApiClient.create({ apiBase: state.apiBase, apiToken: state.apiToken });
const panelState = window.PlayroPanelState.create(state);

function syncApiClientConfig() {
  api.setConfig({ apiBase: state.apiBase, apiToken: state.apiToken });
}

const intentChips = [
  { id: 'combat', label: 'Combat' },
  { id: 'economy', label: 'Economy' },
  { id: 'npcs', label: 'NPCs' },
  { id: 'vehicles', label: 'Vehicles' },
  { id: 'pets', label: 'Pets' },
  { id: 'quests', label: 'Quests' },
  { id: 'multiplayer', label: 'Multiplayer' },
  { id: 'ui', label: 'UI' },
  { id: 'worldbuilding', label: 'Worldbuilding' }
];

const demoPrompts = [
  {
    title: 'Cyber Detective City',
    genre: 'Roleplay Mystery',
    prompt: 'Make a cyberpunk detective roleplay city with NPC quests, apartments, vehicles, and a reputation system.'
  },
  {
    title: 'Sky Island Survival',
    genre: 'Survival Adventure',
    prompt: 'Make a sky island survival game with crafting, storms, team bases, resource gathering, and rescue objectives.'
  },
  {
    title: 'Restaurant Chaos Sim',
    genre: 'Restaurant Simulator',
    prompt: 'Make a chaotic restaurant game with customer NPCs, cooking stations, upgrades, delivery vehicles, and daily challenges.'
  },
  {
    title: 'Classic Obby Example',
    genre: 'Obby',
    prompt: 'Make a colorful checkpoint obby with coins, moving platforms, lava hazards, and a finish portal.'
  }
];

const launchSlides = [
  {
    hook: 'I asked AI to build a Roblox obby from one sentence',
    visual: 'Prompt screenshot + glowing checkpoint course preview',
    prompt: 'Make a neon checkpoint obby with moving platforms, lava hazards, coin trails, pets, and a finish portal for a 7-slide launch demo.'
  },
  {
    hook: 'This Roblox tycoon starts as a text prompt',
    visual: 'Before prompt → generated droppers, buttons, cash collector',
    prompt: 'Make a starter tycoon with droppers, upgrade buttons, cash collection, rebirth goals, and a clean slideshow-ready build log.'
  },
  {
    hook: 'Validate your game idea before spending a weekend in Studio',
    visual: 'Poll slide + three game concept cards',
    prompt: 'Generate three Roblox prototype concepts with a hook, core loop, monetization-safe rewards, and a TikTok slideshow validation plan.'
  }
];

function renderOverlayPanels() {
 return `
 ${panelState.isPanelActive('settings') ? renderSettings() : ''}
 ${renderCapabilitiesPanel()}
 ${renderBuildHistoryPanel()}
 ${renderBuildModePanel()}
 ${renderBuildDetailPanel()}
 ${renderBuildAnalyticsPanel()}
 ${renderBuildLogsPanel()}
 ${renderKeysPanel()}
 ${renderQualityRoutingPanel()}
 ${renderAdaptersPanel()}
 ${renderCrewsPanel()}
 ${renderParityPanel()}
 ${renderHermesInstallerOverlay()}
 `;
}

function renderMainRegion(inWorkspace) {
 return inWorkspace ? renderWorkspace() : renderLanding();
}

function hasPlayroShell() {
 return Boolean(document.getElementById('playro-main-root') && document.getElementById('playro-overlay-root'));
}

function renderOverlaysOnly() {
 if (!hasPlayroShell()) {
   render();
   return;
 }
 render({ mode: 'overlays' });
 if (!document.querySelectorAll('[data-sidebar-panel]').length) {
   renderShellAndOverlays();
 }
}

function renderShellAndOverlays() {
 if (!hasPlayroShell()) {
   render();
   return;
 }
 const app = document.getElementById('app');
 const mainRoot = document.getElementById('playro-main-root');
 const inWorkspace = state.conversation.length > 0 || state.building;
 const preservedMain = mainRoot ? mainRoot.innerHTML : renderMainRegion(inWorkspace);
 app.innerHTML = `
 ${renderSidebar()}
 ${renderHeader()}
 <div id="playro-main-root">${preservedMain}</div>
 <div id="playro-overlay-root">${renderOverlayPanels()}</div>
 `;
 bindEvents();
 if (inWorkspace) {
   scrollThreadToBottom();
 }
}

function render(options = {}) {
 const app = document.getElementById('app');
 if (isSetupRoute()) {
   app.innerHTML = renderPlayroSetupScreen();
   bindSetupScreenEvents();
   return;
 }
 const inWorkspace = state.conversation.length > 0 || state.building;
 const mode = options.mode || 'full';

 if (mode === 'main') {
   const mainRoot = document.getElementById('playro-main-root');
   if (!mainRoot || !inWorkspace) {
     render();
     return;
   }
   mainRoot.innerHTML = renderWorkspace();
   bindLandingEvents();
   bindWorkspaceEvents();
   scrollThreadToBottom();
   return;
 }

 if (mode === 'overlays') {
   const overlayRoot = document.getElementById('playro-overlay-root');
   if (!overlayRoot) {
     render();
     return;
   }
   overlayRoot.innerHTML = renderOverlayPanels();
   bindOverlayEvents();
   return;
 }

 app.innerHTML = `
 ${renderSidebar()}
 ${renderHeader()}
 <div id="playro-main-root">${renderMainRegion(inWorkspace)}</div>
 <div id="playro-overlay-root">${renderOverlayPanels()}</div>
 `;
 bindEvents();
 scrollThreadToBottom();
}


function primarySidebarItems() {
  return [
    { id: 'build', label: 'Build', icon: '◇' },
    { id: 'sessions', label: 'Projects', icon: '▤' },
    { id: 'config', label: 'Setup', icon: '⚙' }
  ];
}

function advancedSettingsTools() {
  return [
    { panel: 'sessions', label: 'Build history', hint: 'Past games and prompts' },
    { panel: 'analytics', label: 'Build analytics', hint: 'Build stats and genres' },
    { panel: 'logs', label: 'Build logs', hint: 'Stage-by-stage output' },
    { panel: 'build24', label: '24/7 Builder', hint: 'Background build passes' },
    { panel: 'skills', label: 'Build options', hint: 'Skill packs, skills, and build speed' },
    { panel: 'plugins', label: 'Roblox Adapters', hint: 'Rojo, Studio, and Open Cloud' },
    { panel: 'crews', label: 'Builder Crews', hint: 'Build style personas' },
    { panel: 'models', label: 'Quality routing', hint: 'Fast, balanced, or premium' },
    { panel: 'keys', label: 'Keys & accounts', hint: 'Provider and Roblox keys' },
    { panel: 'docs', label: 'Developer docs', hint: 'Engine and capability notes' }
  ];
}

function renderSidebar() {
 const primary = primarySidebarItems();
 return `
 <aside class="app-sidebar" data-smoke="playro-sidebar" aria-label="Playro navigation">
  <button class="sidebar-brand ${panelState.isSidebarItemActive({ id: 'build' }) ? 'active' : ''}" data-sidebar-panel="build" aria-label="Playro home">
   <img class="sidebar-logo mascot-logo" src="../assets/playro-mascot-dark.png" alt="" />
   <span><strong>PLAYRO</strong><small>ROBLOX BUILDER</small></span>
  </button>
  <div class="sidebar-divider"></div>
  <nav class="sidebar-nav sidebar-nav-primary" data-smoke="sidebar-primary-nav">
   ${primary.map(item => `<button class="sidebar-link ${panelState.isSidebarItemActive(item) ? 'active' : ''}" data-sidebar-panel="${escapeHTML(item.id)}"><span>${escapeHTML(item.icon)}</span><b>${escapeHTML(item.label)}</b></button>`).join('')}
  </nav>
  <p class="sidebar-advanced-note">More tools live in <button type="button" class="sidebar-inline-link" id="btn-open-advanced-from-sidebar">Setup → Advanced build tools</button>.</p>
 </aside>
 `;
}

function renderHeader() {
 return `
 <header class="site-header">
 <button class="brand" id="btn-home" aria-label="Playro home">
 <img class="brand-mark mascot-logo" src="../assets/playro-mascot-dark.png" alt="" />
 <span>Playro</span>
 </button>
 <nav class="top-nav" data-smoke="top-nav-primary">
 <button class="nav-link" id="btn-projects">Projects</button>
 <button class="nav-link" id="btn-settings">Setup</button>
 </nav>
 </header>
 `;
}

function renderLanding() {
  return `
    <main class="landing">
      <div class="hero-badge">Build Roblox games with AI</div>
      <h1>Build any Roblox game with a prompt.</h1>
      <p class="lead">Describe any Roblox experience: roleplay, combat, survival, racing, tycoon, obby, horror, or something completely custom. Playro drafts the plan, Luau scripts, Rojo project, and handoff steps.</p>
      <p class="lead-subtle">Playro is your Codex-like Roblox builder for turning open-ended ideas into Studio-ready prototypes.</p>
      ${renderHeroComposer()}
      ${renderLandingExtras()}
      ${renderBuildQuickPick()}
      ${shouldShowSetupBanner() ? renderSetupBanner() : ''}
      ${shouldShowStudioConnectHint() ? renderStudioConnectHint() : ''}
      ${renderFirstBuildGuide()}
      ${renderRecentProjects()}
    </main>
  `;
}

function renderLandingExtras() {
  return `
    <div class="landing-extras" data-smoke="landing-extras">
      <details class="landing-more">
        <summary>Try an example prompt</summary>
        ${renderStarterPrompts()}
      </details>
      <details class="landing-more">
        <summary>See what Playro generates</summary>
        ${renderBuildOutcomePreview()}
      </details>
    </div>
  `;
}

function renderStarterPrompts() {
  return `
    <section class="starter-prompts" data-smoke="starter-prompts" aria-label="Demo-ready starter prompts">
      ${demoPrompts.map(item => `
        <button class="starter-prompt" data-demo-prompt="${escapeHTML(item.prompt)}" data-demo-genre="${escapeHTML(item.genre)}">
          <strong>${escapeHTML(item.title)}</strong>
          <span>${escapeHTML(item.prompt)}</span>
          <small>Use prompt</small>
        </button>
      `).join('')}
    </section>
  `;
}

function renderLaunchSlideshowKit() {
  return `
    <section class="launch-slideshow-kit" data-smoke="launch-slideshow-kit" aria-label="Faceless launch slideshow kit">
      <div class="slideshow-copy">
        <span class="guide-kicker">Faceless launch kit</span>
        <h2>Turn each build into a TikTok-style slideshow.</h2>
        <p>Use prompt-to-build progress as launch content: hook, before, build steps, playable result, and a demand-check question. No face, no camera setup.</p>
      </div>
      <div class="slideshow-steps">
        <article><strong>1. Hook</strong><span>Start with the game promise or problem: “I built this Roblox obby from one prompt.”</span></article>
        <article><strong>2. Proof</strong><span>Show the prompt, generated plan, Rojo files, and Studio-ready handoff.</span></article>
        <article><strong>3. Demand check</strong><span>End with a vote: which mechanic should Playro build next?</span></article>
      </div>
      <div class="slideshow-examples">
        ${launchSlides.map((item, index) => `
          <button class="slideshow-card" data-demo-prompt="${escapeHTML(item.prompt)}" data-demo-genre="${escapeHTML(item.genre || 'Custom Roblox Experience')}">
            <small>Slide ${index + 1}</small>
            <strong>${escapeHTML(item.hook)}</strong>
            <span>${escapeHTML(item.visual)}</span>
          </button>
        `).join('')}
      </div>
    </section>
  `;
}

function renderBuildOutcomePreview() {
  const outcomes = [
    ['Game plan', 'Core loop, systems, and progression written in plain language.'],
    ['Luau scripts', 'Shared config plus starter server and client files.'],
    ['Rojo project', 'Folder mapping ready for Roblox Studio sync.'],
    ['Studio handoff', 'Open folder, start Rojo, export ZIP, or copy code.']
  ];
  return `
    <section class="outcome-preview" data-smoke="outcome-preview" aria-label="Generated project preview">
      <span class="outcome-kicker">What Playro generates</span>
      <div class="outcome-grid">
        ${outcomes.map(([title, body]) => `
          <article class="outcome-item">
            <strong>${escapeHTML(title)}</strong>
            <span>${escapeHTML(body)}</span>
          </article>
        `).join('')}
      </div>
    </section>
  `;
}

function renderHeroComposer() {
  return `
    <section class="prompt-card" aria-label="Build prompt">
      <textarea id="prompt-input" placeholder="Make a cyberpunk detective city with NPC quests, vehicles, apartments, and reputation..."></textarea>
      <div class="prompt-footer">
        <div class="chips">
          ${intentChips.map(g => `<button class="chip ${state.selectedIntent === g.label ? 'selected' : ''}" data-intent="${g.label}" aria-pressed="${state.selectedIntent === g.label ? 'true' : 'false'}">${g.label}</button>`).join('')}
        </div>
        <button class="build-btn" id="btn-build">Build Roblox Project</button>
      </div>
    </section>
  `;
}

function canBuildLocally() {
  return state.setup.backend === 'ready' || state.setup.backend === 'starting';
}

function isBuildReady() {
  return canBuildLocally() && state.setup.rojo === 'ready';
}

function shouldShowSetupBanner() {
  return !canBuildLocally();
}

function shouldShowStudioConnectHint() {
  return canBuildLocally() && state.setup.rojo !== 'ready';
}

function renderStudioConnectHint() {
  return `
    <p class="studio-connect-hint" data-smoke="studio-connect-hint">
      <span>Optional:</span> Install Rojo from Setup when you want to sync files into Roblox Studio. You can build without it.
    </p>
  `;
}

function renderBuildQuickPick() {
  const skills = state.capabilities?.roblox_skills || defaultRobloxSkills();
  const selectedSkill = skills.find(skill => skill.id === state.selectedSkill) || skills[0];
  const modes = state.capabilities?.quality_modes || defaultQualityModes();
  const selectedMode = modes.find(mode => mode.id === state.qualityMode) || modes[1] || modes[0];
  const skillStatus = friendlySkillStatus(selectedSkill);
  const activePack = findSkillPackForSelection(state.selectedSkill, state.qualityMode);
  return `
    <section class="build-quick-pick" data-smoke="build-quick-pick" aria-label="Build options">
      <div class="quick-pick-copy">
        <p class="quick-pick-line"><strong>Build pack:</strong> ${escapeHTML(activePack?.label || 'Custom')} ${activePack?.default ? '<span class="quick-pick-hint">(recommended)</span>' : ''}</p>
        <p class="quick-pick-line"><strong>Skill:</strong> ${escapeHTML(selectedSkill?.name || 'Roblox skill')} <span class="status-pill ${skillStatus.class}">${escapeHTML(skillStatus.label)}</span></p>
        <p class="quick-pick-line"><strong>Speed:</strong> ${escapeHTML(selectedMode?.label || 'Balanced')} <span class="quick-pick-hint">${escapeHTML(qualitySpeedHint(selectedMode?.id))}</span></p>
      </div>
      <button class="action-btn ghost" id="btn-open-build-options" type="button">Change build pack</button>
    </section>
  `;
}

function renderSettingsBuildPicks() {
  const skills = state.capabilities?.roblox_skills || defaultRobloxSkills();
  const selectedSkill = skills.find(skill => skill.id === state.selectedSkill) || skills[0];
  const modes = state.capabilities?.quality_modes || defaultQualityModes();
  const selectedMode = modes.find(mode => mode.id === state.qualityMode) || modes[1] || modes[0];
  const skillStatus = friendlySkillStatus(selectedSkill);
  const readyCount = skills.filter(skill => skillWorks(skill)).length;
  const activePack = findSkillPackForSelection(state.selectedSkill, state.qualityMode);
  return `
    <div class="settings-build-picks" data-smoke="settings-build-picks">
      <article class="settings-pick-card settings-pick-card-pack">
        <span class="settings-pick-label">Build pack (skill + speed)</span>
        <strong>${escapeHTML(activePack?.label || 'Custom')}</strong>
        <p>${escapeHTML(activePack?.description || 'Pick a preset on the home screen or choose skill and speed in Advanced build tools → Build options.')}</p>
      </article>
      <article class="settings-pick-card">
        <span class="settings-pick-label">Roblox skill (what Playro helps with)</span>
        <strong>${escapeHTML(selectedSkill?.name || 'Roblox skill')}</strong>
        <p>${escapeHTML(selectedSkill?.description || 'Picks how Playro plans and writes your game.')}</p>
        <span class="status-pill ${skillStatus.class}">${escapeHTML(skillStatus.label)}</span>
      </article>
      <article class="settings-pick-card">
        <span class="settings-pick-label">Build speed (how long Playro thinks)</span>
        <strong>${escapeHTML(selectedMode?.label || 'Balanced')}</strong>
        <p>${escapeHTML(qualitySpeedHint(selectedMode?.id))}</p>
      </article>
      <p class="panel-muted">${readyCount} skill${readyCount === 1 ? '' : 's'} work today. Gray ones in Build options are coming soon.</p>
    </div>
  `;
}

function renderSetupBanner() {
  return `
    <section class="setup-banner" data-smoke="setup-banner" aria-label="Setup reminder">
      <div>
        <strong>Build locally now</strong>
        <span>Playro can generate your project first. Connect Studio later when you are ready to test with Rojo.</span>
      </div>
      <button class="action-btn" id="btn-open-setup-banner" type="button">Open Setup</button>
    </section>
  `;
}

function renderSetupChecklist() {
  const hermesReady = state.setup.hermes === 'ready';
  const rojoReady = state.setup.rojo === 'ready';
  return `
    <section class="setup-card" data-smoke="setup-card" aria-label="Setup checklist">
      ${renderBuildReadinessSummary()}
      <div class="setup-head">
        <div>
          <span class="guide-kicker">Required setup</span>
          <h2>Install the Playro AI engine. Connect Studio later.</h2>
          <p>Playro needs the AI engine to generate games. Rojo is optional until you want Studio sync — you can build locally first.</p>
        </div>
        <button class="action-btn ghost" id="btn-refresh-setup">Refresh checks</button>
      </div>
      <div class="setup-flow" data-smoke="forced-setup-flow">
        <article class="setup-step ${hermesReady ? 'ready' : 'active'}">
          <span>1</span><div><strong>Install Playro AI engine</strong><small>${hermesReady ? 'Installed and ready.' : 'Required Playro backend engine for skills, memory, orchestration, and generation.'}</small></div>
        </article>
        <article class="setup-step ${rojoReady ? 'ready' : 'active'}">
          <span>2</span><div><strong>Add Rojo later</strong><small>${rojoReady ? 'Installed and ready for Studio sync.' : 'Optional CLI for syncing generated Roblox files into Studio.'}</small></div>
        </article>
      </div>
      <div class="setup-grid">
        ${setupItem('backend', 'Playro project service', 'Auto-started by this app for Roblox files and build jobs.', 'Bundled with the desktop app.')}
        ${setupItem('hermes', 'Playro AI engine', 'Required Playro engine for skills, project memory, orchestration, and generation.', 'Bundled with Playro when available, or installed on first launch into Playro app data.')}
        ${setupItem('rojo', 'Rojo CLI + Studio plugin', 'Optional for live syncing project files into Studio.', 'Install Rojo when you are ready to test with the Studio plugin.')}
        ${setupItem('studio', 'Roblox Studio', 'Required to open/test the generated place.', 'Install from create.roblox.com.')}
      </div>
      <div class="setup-actions">
        <button class="action-btn" data-action="install-hermes-runtime" ${state.installingHermes || hermesReady ? 'disabled' : ''}>${hermesReady ? 'Playro engine installed' : (state.installingHermes ? 'Installing Playro engine...' : 'Install Playro AI engine')}</button>
        <button class="action-btn" data-action="install-rojo" ${state.installingRojo || rojoReady ? 'disabled' : ''}>${rojoReady ? 'Rojo installed' : (state.installingRojo ? 'Installing Rojo...' : 'Download Rojo')}</button>
        <button class="action-btn ghost" data-action="open-rojo-docs">How to install Rojo</button>
        <button class="action-btn ghost" data-action="open-studio-download">Download Roblox Studio</button>
        <button class="action-btn ghost" data-action="copy-rojo-install">Copy Rojo command</button>
      </div>
    </section>
  `;
}

function renderBuildReadinessSummary() {
  const backendReady = state.setup.backend === 'ready';
  const hermesReady = state.setup.hermes === 'ready';
  const rojoReady = state.setup.rojo === 'ready';
  const localReady = canBuildLocally();
  const studioReady = localReady && rojoReady;
  const blockers = [
    backendReady ? null : 'Playro project service',
    rojoReady ? null : 'Rojo CLI for Studio sync'
  ].filter(Boolean);
  return `
    <div class="readiness-summary ${localReady ? 'ready' : 'locked'}" data-smoke="build-readiness-summary">
      <div class="readiness-state">
        <strong>${localReady ? 'Ready to build locally' : 'Project service starting'}</strong>
        <span>${localReady ? 'Build locally now. Playro can generate project files before Rojo is installed.' : `Waiting for: ${blockers.join(', ')}.`}</span>
      </div>
      <div class="readiness-next">${studioReady ? 'Next: build and test in Studio with Rojo.' : 'Connect Studio later: Install Rojo only when you are ready to test in Studio.'}</div>
    </div>
  `;
}

function setupItem(key, title, body, hint) {
  const status = state.setup[key] || 'unknown';
  const display = friendlySetupDisplayStatus(key, status);
  return `
    <article class="setup-item ${display.klass}">
      <span class="setup-dot"></span>
      <div><strong>${title}</strong><p>${body}</p><small>${hint}</small></div>
      <span class="setup-label">${display.label}</span>
    </article>
  `;
}

function renderFirstBuildGuide() {
  return `
    <section class="first-build-guide compact" data-smoke="first-build-guide" aria-label="First build guidance">
      <span class="guide-kicker">How it works</span>
      <ol class="guide-steps inline">
        <li><span>1</span>Type your game idea and tap <strong>Build Roblox Project</strong>.</li>
        <li><span>2</span>Review the plan and files Playro makes.</li>
        <li><span>3</span>Open in Roblox Studio with Rojo when you are ready.</li>
      </ol>
    </section>
  `;
}

function renderBuildStatus() {
  const stages = [
    ['idea', 'Read prompt'],
    ['plan', 'Plan Rojo project'],
    ['luau', 'Write Luau systems'],
    ['handoff', 'Prepare Studio handoff']
  ];
  const activeIndex = Math.max(0, stages.findIndex(([id]) => id === state.buildStage));
  const complete = state.buildStage === 'complete';
  return `
    <section class="build-status" data-smoke="build-status" aria-label="Build progress">
      <div>
        <span class="guide-kicker">Live build progress</span>
        <h2>${complete ? 'Studio handoff ready' : 'Roblox project build plan'}</h2>
      </div>
      <div class="status-rail">
        ${stages.map(([id, label], index) => `<span class="status-pill ${complete || index <= activeIndex ? 'active' : ''}" data-stage="${id}">${label}</span>`).join('')}
      </div>
    </section>
  `;
}

function renderWorkspace() {
  return `
    <main class="workspace">
      ${renderBuildStatus()}
      <section class="thread" id="thread">
        ${state.conversation.map(renderMessage).join('')}
        ${state.building ? renderTypingMessage() : ''}
      </section>
      <section class="dock">
        <label class="refinement-label" for="refinement">Optional refinement</label>
        <textarea id="refinement" placeholder="Ask for a change: add pets, tune rewards, make the boss harder..." data-selector="#refinement"></textarea>
        <button class="build-btn" id="btn-build" ${state.building ? 'disabled' : ''}>${state.building ? 'Building...' : (state.currentProject?.id ? 'Refine project' : 'Send change')}</button>
      </section>
    </main>
  `;
}

function renderMessage(msg) {
  if (msg.role === 'user') {
    return `
      <article class="message user-msg">
        <div class="avatar user-avatar">U</div>
        <div class="bubble">${escapeHTML(msg.text)}</div>
      </article>
    `;
  }

  return `
    <article class="message ai-msg">
      <div class="avatar ai-avatar">P</div>
      <div class="bubble">
        <strong>${escapeHTML(msg.title || 'Playro')}</strong>
        <p>${escapeHTML(msg.text)}</p>
        ${msg.receipt ? renderBuildReceipt(msg.receipt) : ''}
        ${msg.artifacts ? renderArtifactChecklist(msg.artifacts) : ''}
        ${msg.code ? `<div class="code-card"><div class="code-head"><span>GameConfig.lua</span><button class="copy-btn" data-copy="luau">Copy</button></div><pre><code>${escapeHTML(msg.code)}</code></pre></div>` : ''}
        ${msg.done ? renderHandoffActions() : ''}
      </div>
    </article>
  `;
}

function renderBuildReceipt(receipt) {
  if (!receipt) return '';
  const files = (receipt.files || []).slice(0, 6);
  const improvements = receipt.improvements?.length ? receipt.improvements : ['Ask for one improvement, like add pets, tune rewards, or make the map bigger.'];
  return `
    <section class="build-receipt" data-smoke="build-receipt" aria-label="Build Receipt">
      <div class="receipt-head">
        <span class="guide-kicker">Build Receipt</span>
        <strong>${escapeHTML(receipt.title || 'Your Roblox project is ready')}</strong>
        <p>${escapeHTML(receipt.summary || 'Playro made a starter Roblox game project you can open, view, and test.')}</p>
      </div>
      ${receipt.fidelity ? renderPromptFidelityMeter(receipt.fidelity) : ''}
      <div class="receipt-grid">
        <article>
          <span>What Playro made</span>
          <p>${escapeHTML(receipt.made || 'A playable starter project from your idea.')}</p>
        </article>
        <article>
          <span>Files Playro created</span>
          <ul>${files.map(file => `<li>${escapeHTML(file)}</li>`).join('')}</ul>
        </article>
        <article>
          <span>How to test it</span>
          <p>${escapeHTML(receipt.test || 'Open the generated folder, view files, then test in Roblox Studio. Set up Rojo when you want live Studio sync.')}</p>
        </article>
        <article>
          <span>What to improve next</span>
          <ul>${improvements.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul>
        </article>
      </div>
      <div class="receipt-actions">
        <button class="action-btn" data-action="open-folder">Open generated folder</button>
        <button class="action-btn ghost" data-action="open-folder">View files</button>
        <button class="action-btn ghost" data-action="open-studio">Test in Roblox Studio</button>
      </div>
      <p class="receipt-nudge">Ask for one improvement when you are ready.</p>
    </section>
  `;
}

function createBuildReceipt(prompt, project, artifacts = [], changedFiles = [], isRefining = false) {
  const projectName = project?.name || inferProjectName(prompt);
  const genre = project?.genre || inferGenre(prompt);
  const fileNames = receiptFileList(project, artifacts, changedFiles);
  const systems = state.buildIntent?.systems || [];
  const systemsText = systems.length ? ` with ${systems.join(', ').toLowerCase()}` : '';
  return {
    title: isRefining ? `${projectName} update receipt` : `${projectName} build receipt`,
    summary: isRefining ? 'Playro updated your Roblox project and kept the next steps simple.' : 'Playro finished your Roblox starter project and saved the files on your computer.',
    made: isRefining ? `An updated ${genre} Roblox project${systemsText}.` : `A ${genre} Roblox starter project${systemsText}.`,
    files: fileNames,
    test: project ? 'Open the generated folder, look through the files, then test in Roblox Studio. If Rojo is not set up yet, install it later for live sync.' : 'This is a local preview. Finish setup when you want Playro to write real Rojo files for Studio testing.',
    improvements: nextImprovementIdeas(prompt),
    fidelity: scorePromptFidelity(prompt, project)
  };
}

function renderPromptFidelityMeter(fidelity) {
  if (!fidelity) return '';
  const score = Math.max(0, Math.min(100, Number(fidelity.score) || 0));
  const requestedItems = (fidelity.items || []).filter(item => item.requested);
  const visibleItems = requestedItems.length ? requestedItems : (fidelity.items || []).slice(0, 4);
  const tone = score >= 85 ? 'strong' : score >= 60 ? 'good' : 'partial';
  return `
    <section class="prompt-fidelity-meter" data-smoke="prompt-fidelity-meter" aria-label="Prompt fidelity meter">
      <div class="fidelity-head">
        <div>
          <span class="guide-kicker">Prompt fidelity</span>
          <strong>${escapeHTML(fidelity.label || 'Match score')}</strong>
        </div>
        <div class="fidelity-score ${tone}" aria-label="Prompt match score ${score} percent">
          <span>${score}%</span>
          <small>match</small>
        </div>
      </div>
      <div class="fidelity-track" aria-hidden="true"><div class="fidelity-fill ${tone}" style="width:${score}%"></div></div>
      <p class="fidelity-summary">${escapeHTML(fidelity.summary || 'Playro compared your prompt to the generated game systems.')}</p>
      <div class="fidelity-items">
        ${visibleItems.map(item => `
          <span class="fidelity-chip ${item.matched ? 'matched' : 'missing'}">
            ${item.matched ? 'Built' : 'Missing'} · ${escapeHTML(item.label || item.id || 'Feature')}
          </span>
        `).join('')}
      </div>
      ${(fidelity.missing || []).length ? `<p class="fidelity-missing">Not in your game yet: ${escapeHTML((fidelity.missing || []).join(', '))}. Ask Playro for one of these next.</p>` : ''}
    </section>
  `;
}

const PROMPT_FIDELITY_CATALOG = [
  { id: 'mechanics', label: 'Mechanics', promptKeywords: ['combat', 'fight', 'enemy', 'wave', 'boss', 'checkpoint', 'obby', 'obstacle', 'parkour', 'tycoon', 'dropper', 'simulator', 'tower', 'race', 'lap', 'quest', 'survival', 'craft', 'arena', 'round'], systemKeywords: ['combat', 'wave', 'checkpoint', 'obby', 'tycoon', 'simulator', 'tower', 'race', 'quest', 'boss', 'survival', 'arena', 'spawn', 'progression', 'droppers', 'enemies', 'lap'] },
  { id: 'world', label: 'World & map', promptKeywords: ['world', 'map', 'zone', 'platform', 'stage', 'island', 'city', 'hub', 'apartment', 'house', 'arena', 'explore'], systemKeywords: ['platform', 'zone', 'apartment', 'hub', 'exploration', 'vehicle', 'roleplay'] },
  { id: 'rewards', label: 'Rewards', promptKeywords: ['coin', 'cash', 'money', 'reward', 'prize', 'xp', 'level', 'progression', 'rebirth'], systemKeywords: ['coin', 'economy', 'reward', 'progression', 'xp', 'level', 'sell'] },
  { id: 'ui', label: 'UI', promptKeywords: ['ui', 'hud', 'menu', 'screen', 'button', 'interface'], systemKeywords: ['hud', 'client'], alwaysMatched: true },
  { id: 'npcs', label: 'NPCs & quests', promptKeywords: ['npc', 'quest', 'mission', 'dialog', 'character', 'story'], systemKeywords: ['npc', 'quest'] },
  { id: 'multiplayer', label: 'Multiplayer', promptKeywords: ['multiplayer', 'team', 'co-op', 'coop', 'friends', 'party', 'together'], systemKeywords: ['multiplayer', 'cooperative', 'team'] },
  { id: 'reward_loops', label: 'Reward loops', promptKeywords: ['shop', 'upgrade', 'store', 'buy', 'sell', 'tycoon', 'economy', 'rebirth'], systemKeywords: ['shop', 'upgrade', 'economy', 'tycoon', 'collector', 'droppers'] }
];

function scorePromptFidelity(prompt, project) {
  if (project?.prompt_fidelity) return project.prompt_fidelity;
  const systems = project?.systems || [];
  const promptLower = String(prompt || '').toLowerCase();
  const items = PROMPT_FIDELITY_CATALOG.map(category => {
    const requested = category.promptKeywords.some(keyword => promptLower.includes(keyword));
    const matched = Boolean(category.alwaysMatched) || category.systemKeywords.some(keyword => systems.some(system => String(system).toLowerCase().includes(keyword)));
    return { id: category.id, label: category.label, requested, matched };
  });
  const requestedItems = items.filter(item => item.requested);
  if (!requestedItems.length) {
    return {
      score: 100,
      label: 'Starter match',
      summary: 'Playro turned your idea into a starter Roblox game. Add one clear feature in your next message to raise the match score.',
      items,
      missing: [],
      matched_count: items.length,
      requested_count: items.length
    };
  }
  const matchedCount = requestedItems.filter(item => item.matched).length;
  const requestedCount = requestedItems.length;
  const score = Math.round((matchedCount / requestedCount) * 100);
  const missing = requestedItems.filter(item => !item.matched).map(item => item.label);
  let label = 'Partial match';
  if (score >= 85) label = 'Strong match';
  else if (score >= 60) label = 'Good match';
  return {
    score,
    label,
    summary: `Playro built ${matchedCount} of ${requestedCount} ideas from your prompt.`,
    items,
    missing,
    matched_count: matchedCount,
    requested_count: requestedCount
  };
}

function receiptFileList(project, artifacts = [], changedFiles = []) {
  const names = [];
  for (const item of [...(changedFiles || []), ...(artifacts || []), ...(project?.files || [])]) {
    const name = typeof item === 'string' ? item : (item?.path || item?.name || '');
    if (name && !names.includes(name)) names.push(name);
  }
  const defaults = PLAYRO_HANDOFF_ARTIFACT_FILES.slice(0, 6);
  for (const name of defaults) {
    if (names.length >= 6) break;
    if (!names.includes(name)) names.push(name);
  }
  return names.slice(0, 6);
}

function nextImprovementIdeas(prompt) {
  const p = String(prompt || '').toLowerCase();
  const ideas = [];
  if (!p.includes('pet')) ideas.push('Add a pet, helper, or companion system.');
  if (!p.includes('shop') && !p.includes('upgrade')) ideas.push('Add a shop or upgrade path.');
  if (!p.includes('quest') && !p.includes('mission')) ideas.push('Add one clear quest or mission.');
  ideas.push('Playtest once, then ask Playro to fix the first confusing part.');
  return ideas.slice(0, 3);
}
function renderArtifactChecklist(artifacts = []) {
  const paths = artifacts.map(item => typeof item === 'string' ? item : item.path).filter(Boolean);
  const available = new Set(paths);
  const required = PLAYRO_HANDOFF_ARTIFACT_FILES;
  return `
    <div class="artifact-checklist" aria-label="Studio handoff files">
      <strong>Studio handoff files</strong>
      <div>
        ${required.map(file => `<span class="artifact-chip ${available.has(file) ? 'ready' : 'missing'}">${available.has(file) ? 'Ready' : 'Pending'} ${escapeHTML(file)}</span>`).join('')}
      </div>
    </div>
  `;
}

function renderTypingMessage() {
  const stageLabels = { idea: 'Reading prompt...', plan: 'Planning project...', luau: 'Writing Luau scripts...', handoff: 'Preparing handoff...' };
  const label = stageLabels[state.buildStage] || 'Building...';
  return `
    <article class="message ai-msg typing-msg">
      <div class="avatar ai-avatar">P</div>
      <div class="bubble typing"><span></span><span></span><span></span><small class="typing-label">${escapeHTML(label)}</small></div>
    </article>
  `;
}

function renderHandoffActions() {
  return `
    <div class="handoff-guide" data-smoke="handoff-guide" aria-label="Roblox Studio handoff steps">
      <strong>Next in Roblox Studio</strong>
      <ol>
        <li>Open the project folder and review the generated plan.</li>
        <li>Start Rojo, then connect from the Rojo Studio plugin.</li>
        <li>If live sync is not ready, export the Rojo ZIP or use the copied .rbxlx command.</li>
      </ol>
    </div>
    <div class="handoff-actions">
      <button class="action-btn" data-action="open-studio">Start Rojo & Open Studio</button>
      <button class="action-btn ghost" data-action="open-folder">Open folder</button>
      <button class="action-btn ghost" data-action="export-rojo">Export Rojo ZIP</button>
      <button class="action-btn ghost" data-action="copy-luau">Copy Luau</button>
    </div>
    <p class="handoff-note">This starts Rojo when available, opens Studio when detected, and copies both live-sync and .rbxlx fallback commands. Use the Rojo Studio plugin to connect to the running server.</p>
  `;
}

function renderRecentProjects() {
  return `
    <section class="recent-projects" id="recent-projects">
      <h2>Recent builds</h2>
      <div class="project-list">
        ${state.projects.slice(0, 3).map(p => `
          <button class="project-row" data-project="${escapeHTML(p.name)}">
            <span class="project-icon">${genreIcon(p.genre)}</span>
            <span class="project-copy"><strong>${escapeHTML(p.name)}</strong><small>${escapeHTML(p.desc)}</small></span>
            <span class="project-time">${escapeHTML(p.time)}</span>
          </button>
        `).join('')}
      </div>
    </section>
  `;
}

function renderSettings() {
  const localReady = canBuildLocally();
  const studioReady = state.setup.rojo === 'ready';
  return `
    <div class="settings-scrim" id="settings-scrim"></div>
    <aside class="slide-panel settings-panel" data-smoke="settings-panel" aria-label="Setup and settings">
      <div class="panel-head">
        <h2>Setup &amp; settings</h2>
        <button class="icon-btn" id="btn-close-settings" type="button" aria-label="Close settings">×</button>
      </div>
      <div class="panel-body settings-panel-body">
        <p class="panel-description">Everything you need to get Playro working. Green means ready. Yellow means still installing. Gray means optional for your first build.</p>

        <h3 class="panel-section-title">Can I build yet?</h3>
        <div class="readiness-summary ${localReady ? 'ready' : 'locked'} compact">
          <div class="readiness-state">
            <strong>${localReady ? 'Yes — you can build locally' : 'Not yet — finish setup below'}</strong>
            <span>${localReady
    ? (studioReady
      ? 'Type a prompt on the home screen and tap Build Roblox Project. Rojo is ready for Studio sync.'
      : 'Type a prompt on the home screen and tap Build Roblox Project. Install Rojo later when you want Studio sync.')
    : 'Wait for the Playro project service to start, or install the Playro AI engine below.'}</span>
          </div>
        </div>

        <h3 class="panel-section-title">What each tool does</h3>
        <ul class="settings-tool-list">
          ${settingsStatusRow('Playro project service', 'Runs in the background and saves your builds.', state.setup.backend)}
          ${settingsStatusRow('Playro AI engine', 'The brain that plans your game and writes Luau code.', state.setup.hermes)}
          ${settingsStatusRow('Rojo', 'Syncs files from your computer into Roblox Studio.', state.setup.rojo, 'rojo')}
          ${settingsStatusRow('Roblox Studio', 'Where you play-test the game after Playro generates files.', state.setup.studio, 'studio')}
        </ul>

        <h3 class="panel-section-title">Install missing tools</h3>
        <div class="settings-actions">
          <button class="action-btn" data-action="install-hermes-runtime" type="button" ${state.installingHermes || state.setup.hermes === 'ready' ? 'disabled' : ''}>${state.setup.hermes === 'ready' ? 'Playro AI engine installed' : (state.installingHermes ? 'Installing Playro AI engine...' : 'Install Playro AI engine')}</button>
          <button class="action-btn" data-action="install-rojo" type="button" ${state.installingRojo || state.setup.rojo === 'ready' ? 'disabled' : ''}>${state.setup.rojo === 'ready' ? 'Rojo installed' : (state.installingRojo ? 'Installing Rojo...' : 'Download Rojo')}</button>
          <button class="action-btn ghost" id="btn-refresh-setup" type="button">Check again</button>
          <button class="action-btn ghost" data-action="open-rojo-docs" type="button">Rojo install guide</button>
          <button class="action-btn ghost" data-action="open-studio-download" type="button">Get Roblox Studio</button>
        </div>

        <h3 class="panel-section-title">Your build picks</h3>
        ${renderSettingsBuildPicks()}
        <p class="panel-muted">Change your build pack from the home screen, or open Advanced build tools below.</p>

        ${renderAdvancedSettingsTools()}

        <details class="settings-expert-block settings-experimental-block">
          <summary>Hidden experimental features</summary>
          <p class="settings-note">Optional launch and validation experiments live here so the main screen stays focused on building Roblox games.</p>
          <details class="settings-nested-block">
            <summary>Faceless launch slideshow ideas</summary>
            ${renderLaunchSlideshowKit()}
          </details>
        </details>

        <details class="settings-expert-block">
          <summary>Expert settings (optional)</summary>
          <label for="api-base-input">Backend address</label>
          <input id="api-base-input" value="${escapeHTML(state.apiBase)}" />
          <p class="settings-note">Only change this if support told you to. Playro usually starts the backend for you automatically.</p>
        </details>
      </div>
    </aside>
`;
}

function renderAdvancedSettingsTools() {
  return `
    <details class="settings-expert-block settings-advanced-block" data-smoke="settings-advanced-tools">
      <summary>Advanced build tools</summary>
      <p class="settings-note">Optional power features for logs, skills, adapters, and developer settings. You do not need these for your first build.</p>
      <div class="settings-advanced-grid">
        ${advancedSettingsTools().map(tool => `
          <button type="button" class="settings-advanced-btn" data-open-advanced-panel="${escapeHTML(tool.panel)}">
            <strong>${escapeHTML(tool.label)}</strong>
            <span>${escapeHTML(tool.hint)}</span>
          </button>
        `).join('')}
      </div>
    </details>
  `;
}

function settingsStatusRow(title, help, status, key = '') {
  const display = friendlySetupDisplayStatus(key, status);
  const label = display.label;
  const klass = display.klass;
  return `
    <li class="settings-tool-row ${klass}">
      <span class="settings-tool-dot" aria-hidden="true"></span>
      <div>
        <strong>${escapeHTML(title)}</strong>
        <span>${escapeHTML(help)}</span>
      </div>
      <em class="settings-tool-status">${escapeHTML(label)}</em>
    </li>
  `;
}

function renderCapabilitiesPanel() {
 if (!panelState.isPanelActive('capabilities')) return '';
 const skills = state.capabilities?.roblox_skills || defaultRobloxSkills();
 const readySkills = skills.filter(skill => skillWorks(skill));
 const comingSoonSkills = skills.filter(skill => !skillWorks(skill));
 const modes = state.capabilities?.quality_modes || defaultQualityModes();
 const packs = getSkillPacks();
 const activePack = findSkillPackForSelection(state.selectedSkill, state.qualityMode);
 const memoryItems = state.memoryPreview.length ? state.memoryPreview : defaultMemoryPreview();
 const caps = state.capabilities?.capabilities || {};
 const selected = skills.find(skill => skill.id === state.selectedSkill) || skills[0];
 const selectedMode = modes.find(mode => mode.id === state.qualityMode) || modes[1] || modes[0];
 return `
 <div class="panel-scrim" id="capabilities-scrim"></div>
 <aside class="slide-panel capabilities-panel wide-panel" data-smoke="capabilities-panel" aria-label="Build options">
 <div class="panel-head">
 <h2>Build options</h2>
 <button class="icon-btn" id="btn-close-capabilities" type="button" aria-label="Close build options">×</button>
 </div>
 <div class="panel-body">
 <p class="panel-description">Pick a <strong>build pack</strong> for clear defaults, or customize skill and speed below. Packs map to the same Roblox skills Playro already uses — not genre templates.</p>

 <div class="cap-current-pick">
 <span class="hub-label">Your pick for the next build</span>
 <strong>${escapeHTML(activePack?.label || 'Custom')}</strong>
 <p>${escapeHTML(activePack?.description || `${selected?.name || 'Roblox skill'} at ${selectedMode?.label || 'Balanced'} speed.`)}</p>
 </div>

 <h3 class="panel-section-title">Skill packs</h3>
 <p class="panel-muted">Recommended combos for common build goals. <strong>First build</strong> is the default.</p>
 <div class="cap-skill-pack-list" data-smoke="skill-packs">
 ${packs.map(pack => renderSkillPackCard(pack)).join('')}
 </div>

 <details class="cap-customize-block">
 <summary>Customize skill &amp; speed</summary>
 <p class="panel-muted">Advanced: pick one skill (what Playro helps with) and one speed (how long it thinks). Green badges work today.</p>

 <h3 class="panel-section-title">Skills that work now</h3>
 <div class="cap-skill-list">
 ${readySkills.length ? readySkills.map(skill => renderSkillCard(skill)).join('') : '<p class="panel-muted">No ready skills loaded yet. Tap Refresh list below.</p>'}
 </div>

 ${comingSoonSkills.length ? `
 <h3 class="panel-section-title">Coming soon</h3>
 <div class="cap-skill-list dimmed">
 ${comingSoonSkills.map(skill => renderSkillCard(skill, { disabled: true })).join('')}
 </div>
 ` : ''}

 <h3 class="panel-section-title">Build speed</h3>
 <p class="panel-muted">How hard Playro thinks before it writes your game files.</p>
 <div class="cap-quality-list">
 ${modes.map(mode => `
 <button class="cap-quality-pill ${state.qualityMode === mode.id ? 'selected' : ''}" data-quality="${escapeHTML(mode.id)}" type="button">
 <strong>${escapeHTML(mode.label)}</strong>
 <span>${escapeHTML(qualitySpeedHint(mode.id))}</span>
 <em>${escapeHTML(mode.description)}</em>
 </button>
 `).join('')}
 </div>
 </details>

 <h3 class="panel-section-title">What Playro remembers</h3>
 <p class="panel-muted">Notes saved with your project so the next build stays on track.</p>
 <ul class="cap-memory-list">
 ${memoryItems.map(item => `
 <li>
 <strong>${escapeHTML(item.title)}</strong>
 <span>${escapeHTML(item.summary)}</span>
 </li>
 `).join('')}
 </ul>

 ${Object.keys(caps).length > 0 ? `
 <details class="cap-tools-details">
 <summary>All Playro tools (${Object.keys(caps).length})</summary>
 <div class="cap-tool-cards">
 ${Object.entries(caps).map(([key, cap]) => renderCapabilityToolCard(key, cap)).join('')}
 </div>
 </details>
 ` : ''}
 <p class="panel-note">Your API keys stay on your computer. Playro does not share them.</p>
 </div>
 <div class="panel-foot">
 <button class="action-btn ghost" id="btn-refresh-capabilities-panel" type="button">Refresh list</button>
 </div>
 </aside>
 `;
}

function renderSkillPackCard(pack) {
  const skills = state.capabilities?.roblox_skills || defaultRobloxSkills();
  const modes = state.capabilities?.quality_modes || defaultQualityModes();
  const skill = skills.find(item => item.id === pack.skill_id);
  const mode = modes.find(item => item.id === pack.quality_mode);
  const selected = findSkillPackForSelection(state.selectedSkill, state.qualityMode)?.id === pack.id;
  return `
    <button class="cap-skill-pack-card ${selected ? 'selected' : ''}" data-skill-pack="${escapeHTML(pack.id)}" type="button">
      <div class="cap-skill-pack-head">
        <strong>${escapeHTML(pack.label)}</strong>
        ${pack.default ? '<span class="status-pill ready">Default</span>' : ''}
      </div>
      <p>${escapeHTML(pack.description)}</p>
      <small class="cap-skill-pack-meta">${escapeHTML(skill?.name || 'Roblox skill')} · ${escapeHTML(mode?.label || 'Balanced')}</small>
    </button>
  `;
}

function renderSkillCard(skill, options = {}) {
  const status = friendlySkillStatus(skill);
  const stage = friendlyStageLabel(skill.stage);
  const selected = state.selectedSkill === skill.id;
  const disabled = options.disabled || !skillWorks(skill);
  return `
    <button class="cap-skill-card ${selected ? 'selected' : ''} ${disabled ? 'disabled' : ''}" data-skill="${escapeHTML(skill.id)}" type="button" ${disabled ? 'disabled' : ''}>
      <div class="cap-skill-card-head">
        <strong>${escapeHTML(skill.name)}</strong>
        <span class="status-pill ${status.class}">${escapeHTML(status.label)}</span>
        <span class="stage-pill">${escapeHTML(stage)}</span>
      </div>
      <p>${escapeHTML(skill.description || 'Helps with a Roblox build step.')}</p>
      ${skill.bucket ? `<small class="cap-skill-meta">${escapeHTML(friendlyBucketLabel(skill.bucket))}</small>` : ''}
    </button>
  `;
}

function renderCapabilityToolCard(key, cap) {
  const status = friendlyCapabilityStatus(cap.status);
  return `
    <article class="cap-tool-card">
      <div class="cap-tool-card-head">
        <strong>${escapeHTML(cap.surface_label || key)}</strong>
        <span class="status-pill ${status.class}">${escapeHTML(status.label)}</span>
      </div>
      <p>${escapeHTML(cap.description || 'Playro feature.')}</p>
      ${cap.desktop_panel ? `<small>Opens in: ${escapeHTML(cap.desktop_panel)}</small>` : ''}
    </article>
  `;
}


function parityPanelContent(panel) {
 const selectedMode = (state.capabilities?.quality_modes || defaultQualityModes()).find(mode => mode.id === state.qualityMode) || defaultQualityModes()[1];
 const fromBackend = (state.capabilities?.hermes_parity_surfaces || []).find(item => item.id === panel);
 const fallback = {
  id: 'analytics',
  label: 'Build analytics',
  hermes_source: 'analytics',
  playro_surface: 'Build analytics provides Roblox build intelligence: success rate, validation failures, generated systems, build time, and playtest readiness.',
  rows: [['Validation focus', 'Rojo files, Luau references, economy balance, Studio handoff'], ['Current signal', `${state.buildHistory.length || state.projects.length} known builds tracked`], ['Selected quality', selectedMode?.label || 'Balanced']]
 };
 const item = fromBackend || fallback;
 return {
  title: item.label || 'Playro capability',
  hermesSource: item.hermes_source || 'Hermes capability',
  status: item.status || 'prototype',
  description: item.playro_surface || item.description || fallback.playro_surface,
  rows: item.rows || fallback.rows
 };
}

function renderParityPanel() {
 if (!panelState.isPanelActive('parity') || !state.activeParityPanel) return '';
 const panel = parityPanelContent(state.activeParityPanel);
 return `
 <div class="panel-scrim" id="parity-scrim"></div>
 <aside class="slide-panel parity-panel" data-smoke="hermes-parity-panel" aria-label="${escapeHTML(panel.title)}">
  <div class="panel-head">
   <h2>${escapeHTML(panel.title)}</h2>
   <button class="icon-btn" id="btn-close-parity">×</button>
  </div>
  <div class="panel-body">
   <p class="panel-description">${escapeHTML(panel.description)}</p>
   <div class="parity-map-card">
    <span class="hub-label">Playro ${escapeHTML(panel.hermesSource)} for Roblox · ${escapeHTML(panel.status)}</span>
    ${panel.rows.map(([k, v]) => `<div class="detail-row"><strong>${escapeHTML(k)}</strong><span>${escapeHTML(v)}</span></div>`).join('')}
   </div>
   <p class="panel-note">This panel shows how Playro uses its AI engine for Roblox creation.</p>
  </div>
 </aside>
 `;
}

function renderBuildHistoryPanel() {
 if (!panelState.isPanelActive('buildHistory')) return '';
  const items = state.buildHistorySearch
    ? state.buildHistorySearchResults
    : state.buildHistory;
  const grouped = groupBuildsByDate(items);
  return `
  <div class="panel-scrim" id="build-history-scrim"></div>
  <aside class="slide-panel build-history-panel" data-smoke="build-history-panel" aria-label="Build history">
    <div class="panel-head">
      <h2>Build history</h2>
      <button class="icon-btn" id="btn-close-build-history">×</button>
    </div>
    <div class="panel-search">
      <input id="build-history-search" type="search" placeholder="Search builds by name, genre, or prompt..." value="${escapeHTML(state.buildHistorySearch)}" aria-label="Search builds" />
    </div>
    <div class="panel-body">
      ${state.buildHistoryLoading ? '<p class="panel-muted">Loading builds...</p>' : ''}
      ${!state.buildHistoryLoading && items.length === 0 ? '<p class="panel-muted">' + (state.buildHistorySearch ? 'No builds match your search.' : 'No builds yet. Build your first Roblox game to see history here.') + '</p>' : ''}
      ${Object.entries(grouped).map(([dateLabel, builds]) => `
        <div class="history-date-group">
          <span class="history-date-label">${escapeHTML(dateLabel)}</span>
          ${builds.map(b => `
            <button class="history-row" data-resume-build="${escapeHTML(b.id || b.build_id || '')}" data-open-detail="${escapeHTML(b.id || b.build_id || '')}">
              <span class="history-icon">${genreIcon(b.genre || 'Adventure')}</span>
              <span class="history-copy">
                <strong>${escapeHTML(b.name || b.project_name || inferProjectName(b.prompt || ''))}</strong>
                <small>${escapeHTML(b.genre || 'Adventure')} · ${escapeHTML(b.quality || 'Balanced')} · ${escapeHTML(b.status || 'completed')}</small>
              </span>
              <span class="history-time">${escapeHTML(b.time_label || relativeTime(b.created_at || b.started_at))}</span>
            </button>
          `).join('')}
        </div>
      `).join('')}
    </div>
    <div class="panel-foot">
      <button class="action-btn ghost" id="btn-refresh-build-history">Refresh builds</button>
    </div>
  </aside>
  `;
}

function renderBuildModePanel() {
  if (!panelState.isPanelActive('buildMode')) return '';
  const cb = state.continuousBuild;
  return `
  <div class="panel-scrim" id="build-mode-scrim"></div>
  <aside class="slide-panel build-mode-panel" data-smoke="build-mode-panel" aria-label="24/7 Build Mode">
    <div class="panel-head">
      <h2>24/7 Build mode</h2>
      <button class="icon-btn" id="btn-close-build-mode">×</button>
    </div>
    <div class="panel-body">
      <p class="panel-description">Playro can iterate on your game around the clock. Enable 24/7 build mode to run periodic generation passes that expand systems, tune balance, and add content while you are away.</p>
      <div class="build-mode-toggle-row">
        <span class="build-mode-status ${cb.enabled ? 'active' : 'inactive'}">${cb.enabled ? 'Running' : 'Off'}</span>
        <button class="action-btn ${cb.enabled ? 'ghost' : ''}" id="btn-toggle-continuous-build">${cb.enabled ? 'Disable 24/7 build' : 'Enable 24/7 build'}</button>
      </div>
      <div class="build-mode-details">
        <div class="detail-row"><strong>Interval</strong><span>Every ${cb.intervalMin} minutes</span></div>
        <div class="detail-row"><strong>Build ticks</strong><span>${cb.tickCount}</span></div>
        <div class="detail-row"><strong>Last tick</strong><span>${cb.lastTickAt ? relativeTime(cb.lastTickAt) : 'Not yet'}</span></div>
        <div class="detail-row"><strong>Last status</strong><span>${cb.lastTickStatus || 'Waiting'}</span></div>
      </div>
      <label class="build-mode-interval-label" for="build-mode-interval">Tick interval (minutes)</label>
      <input id="build-mode-interval" type="number" min="5" max="120" step="5" value="${cb.intervalMin}" />
      <p class="panel-note">24/7 build mode uses the selected skill and quality routing from the home screen. Each tick runs a generation pass on the current project.</p>
    </div>
    <div class="panel-foot">
      <button class="action-btn ghost" id="btn-refresh-build-mode">Check status</button>
    </div>
  </aside>
  `;

}


// Guards for the zero-touch setup flow so auto-start/auto-launch fire at most once
// per session even though the setup view re-renders (and re-binds) repeatedly.
let setupAutoStarted = false;
let setupAutoLaunched = false;

function isSetupRoute() {
  return window.location?.hash === '#setup';
}

function setupSteps() {
  return [
    'Installing Playro shell',
    'Downloading Playro AI Engine',
    'Installing Playro AI Engine',
    'Checking optional Rojo',
    'Preparing Studio handoff',
    'Verifying setup',
    'Launching Playro'
  ];
}

function renderPlayroSetupScreen() {
  const setup = state.playroSetup;
  const steps = setupSteps();
  const active = Math.max(1, setup.step || 1);
  const percent = Math.max(0, Math.min(100, setup.percent || Math.round((active / steps.length) * 100)));
  const logs = (setup.logs || []).slice(-80);
  const failed = setup.status === 'failed';
  const complete = setup.status === 'complete';
  return `
    <main class="setup-only-screen" data-smoke="playro-full-installer-screen" aria-label="Playro Setup">
      <section class="setup-installer-window">
        <div class="setup-installer-titlebar">
          <span class="installer-icon">◆</span>
          <span>Playro Setup</span>
        </div>
        <div class="setup-installer-content">
          <div class="setup-installer-hero">
            <img class="setup-installer-mascot" src="../assets/playro-mascot-dark.png" alt="" />
            <div>
              <h1>${escapeHTML(setup.title || 'Installing Playro')}</h1>
              <p>Playro prepares the desktop app, Playro AI Engine, optional Rojo handoff checks, verification, then launch.</p>
            </div>
          </div>
          <div class="setup-installer-progress-row">
            <div class="installer-progress-track"><div class="installer-progress-fill" style="width:${percent}%"></div></div>
            <strong>${percent}%</strong>
          </div>
          <p class="installer-step">${escapeHTML(setup.stepLabel || `Step ${active}/7: ${steps[active - 1]}`)}</p>
          <p class="installer-detail">${escapeHTML(setup.detail || 'Preparing Playro...')}</p>
          <div class="windows-style-steps">
            ${steps.map((label, index) => {
              const step = index + 1;
              const klass = step < active || complete ? 'done' : step === active ? (failed ? 'failed' : 'active') : 'pending';
              const mark = klass === 'done' ? '✓' : klass === 'failed' ? '!' : step;
              return `<article class="windows-style-step ${klass}"><span>${mark}</span><b>${escapeHTML(label)}</b></article>`;
            }).join('')}
          </div>
          <pre class="installer-log setup-installer-log" aria-label="Playro setup log">${logs.map(escapeHTML).join('\n') || 'Ready to install Playro requirements...'}</pre>
          <div class="setup-installer-actions">
            ${!complete ? '<button class="action-btn ghost setup-skip-btn" id="btn-skip-playro-setup" type="button">Skip setup for now</button>' : ''}
            <div class="setup-installer-actions-primary">
              ${!setup.started || failed ? `<button class="action-btn" id="btn-start-full-setup">${failed ? 'Retry setup' : 'Install Playro'}</button>` : ''}
              ${complete ? '<button class="action-btn" id="btn-launch-playro">Launch Playro</button>' : ''}
              ${failed ? '<button class="action-btn ghost" id="btn-open-rojo-docs-setup">Rojo help</button>' : ''}
            </div>
          </div>
          ${!complete ? '<p class="setup-skip-note">Skip only if setup keeps failing. You can install tools later from <strong>Setup</strong> in the app.</p>' : ''}
        </div>
      </section>
    </main>
  `;
}

function bindSetupScreenEvents() {
  document.getElementById('btn-start-full-setup')?.addEventListener('click', startFullSetupFlow);
  document.getElementById('btn-skip-playro-setup')?.addEventListener('click', skipPlayroSetupFlow);
  document.getElementById('btn-launch-playro')?.addEventListener('click', launchPlayroFromSetup);
  document.getElementById('btn-open-rojo-docs-setup')?.addEventListener('click', () => window.robloxAIStudio?.openExternal?.('https://rojo.space/docs/v7/getting-started/installation/'));
  // Headless, zero-touch setup: kick off the full install automatically as soon as
  // the setup view loads. No click is required for the happy path; the buttons above
  // remain as fallbacks (retry on failure, skip, manual launch).
  maybeAutoStartSetup();
  // If progress (from startFullSetupFlow or onPlayroSetupProgress) has reported
  // completion, auto-dismiss the setup screen and launch the app.
  maybeAutoLaunchSetup();
}

function maybeAutoStartSetup() {
  if (!isSetupRoute()) return;
  const setup = state.playroSetup || {};
  // Only auto-start once, and never override a run already in flight, completed, or failed.
  if (setupAutoStarted || setup.started || setup.status === 'running' || setup.status === 'complete' || setup.status === 'failed') {
    return;
  }
  if (!window.robloxAIStudio?.startFullSetup) return;
  setupAutoStarted = true;
  startFullSetupFlow();
}

function maybeAutoLaunchSetup() {
  if (!isSetupRoute()) return;
  if (state.playroSetup?.status !== 'complete') return;
  if (setupAutoLaunched) return;
  setupAutoLaunched = true;
  // Give the user a brief moment to see the "ready" state, then auto-advance.
  setTimeout(() => {
    if (isSetupRoute() && state.playroSetup?.status === 'complete') {
      launchPlayroFromSetup();
    }
  }, 900);
}

function launchPlayroFromSetup() {
  window.location.hash = '';
  render();
  refreshSetup();
  refreshCapabilities();
}

async function skipPlayroSetupFlow() {
  if (!window.robloxAIStudio?.skipPlayroSetup) return toast('Skip setup is unavailable in this build.');
  const confirmed = window.confirm(
    'Skip Playro setup?\n\nThe app will open anyway. AI builds may not work until you install the Playro AI Engine and Rojo from Setup inside the app.'
  );
  if (!confirmed) return;
  const result = await window.robloxAIStudio.skipPlayroSetup();
  if (!result?.ok) {
    toast(result?.error || 'Could not skip setup.');
    return;
  }
  state.playroSetup = {
    open: true,
    started: true,
    status: 'complete',
    percent: 100,
    step: 7,
    totalSteps: 7,
    title: 'Opening Playro',
    stepLabel: 'Setup skipped',
    detail: 'Setup was skipped. Install missing tools from Setup if builds fail.',
    logs: [...(state.playroSetup.logs || []), 'Setup skipped. Opening Playro desktop app.']
  };
  if (isSetupRoute()) {
    window.location.hash = '';
    render();
    await refreshSetup();
    await refreshCapabilities();
  } else {
    render();
  }
  toast('Setup skipped. Open Setup anytime to install the Playro AI Engine and Rojo.');
}

async function startFullSetupFlow() {
  if (!window.robloxAIStudio?.startFullSetup) return toast('Full Playro setup is unavailable in this build.');
  state.playroSetup = { open: true, started: true, status: 'running', percent: 8, step: 1, totalSteps: 7, title: 'Installing Playro', stepLabel: 'Step 1/7: Installing Playro shell', detail: 'Preparing Playro app shell...', logs: ['Playro Setup started.'] };
  render();
  const result = await window.robloxAIStudio.startFullSetup();
  if (!result?.ok) {
    state.playroSetup.status = 'failed';
    state.playroSetup.title = 'Playro setup failed';
    state.playroSetup.detail = result?.error || 'Setup failed. Check your internet connection and retry.';
    state.playroSetup.logs.push(state.playroSetup.detail);
    render();
    return;
  }
  state.playroSetup.status = 'complete';
  state.playroSetup.percent = 100;
  state.playroSetup.step = 7;
  state.playroSetup.title = 'Playro is ready';
  state.playroSetup.stepLabel = 'Step 7/7: Launching Playro';
  state.playroSetup.detail = 'Everything is installed. Launching the Playro desktop app.';
  state.playroSetup.logs.push('Setup complete. Launching Playro desktop app.');
  render();
}


function renderHermesInstallerOverlay() {
  const installer = state.hermesInstaller;
  if (!installer?.open) return '';
  const logs = (installer.logs || []).slice(-80);
  const percent = Math.max(0, Math.min(100, installer.percent || 0));
  const done = installer.status === 'complete';
  const failed = installer.status === 'failed';
  return `
  <div class="installer-scrim" data-smoke="hermes-installer-overlay">
    <section class="hermes-installer-modal" aria-label="Playro AI engine installer">
      <div class="installer-titlebar"><span class="installer-icon">◆</span><span>Playro AI engine</span></div>
      <div class="installer-body">
        <h1>${escapeHTML(installer.title || 'Installing Playro AI engine')}</h1>
        <div class="installer-progress-row">
          <div class="installer-progress-track"><div class="installer-progress-fill" style="width: ${percent}%"></div></div>
          <span class="installer-percent">${percent}%</span>
        </div>
        <p class="installer-step">${escapeHTML(installer.stepLabel || `Step ${installer.step || 1}/${installer.totalSteps || 7}: Starting installation...`)}</p>
        <p class="installer-detail">${escapeHTML(installer.detail || 'Installing the Playro AI engine...')}</p>
        <pre class="installer-log" aria-label="Playro engine installer log">${logs.map(escapeHTML).join('\\n') || 'Installing the Playro AI engine...'}</pre>
        ${(done || failed) ? `<div class="installer-actions"><button class="action-btn ${failed ? 'ghost' : ''}" id="btn-close-installer">${done ? 'Continue to Playro' : 'Close installer'}</button></div>` : ''}
      </div>
    </section>
  </div>
  `;
}

function projectDetailArtifactItems(detail) {
 const artifacts = detail?.artifacts || detail?.files || [];
 return artifacts.map(item => {
  if (typeof item === 'string') return { path: item, bytes: null };
  return { path: item.path || item.name || String(item), bytes: item.bytes || item.size || null };
 }).filter(item => item.path);
}

function projectDetailTimelineItems(detail) {
 const timeline = detail?.timeline || detail?.build_state?.timeline || detail?.manifest?.build_job?.stages || [];
 return timeline.map((item, index) => ({
  title: item.title || item.key || `Step ${index + 1}`,
  detail: item.detail || item.stage || '',
  status: item.status || 'done',
  index: item.index || index + 1
 }));
}

function projectDetailLogItems(detail) {
 const sources = [
  ...(detail?.history || []),
  ...(detail?.build_state?.logs || []),
  ...(detail?.logs || []),
 ];
 const seen = new Set();
 return sources.map(item => {
  const log = typeof item === 'string'
   ? { message: item, stage: 'history', level: 'info', time: '' }
   : {
    message: item.message || item.text || item.detail || '',
    stage: item.stage || item.level || 'history',
    level: item.level || item.stage || 'info',
    time: item.time || item.timestamp || '',
   };
  const key = [log.time, log.stage, log.message].join('|');
  if (!log.message || seen.has(key)) return null;
  seen.add(key);
  return log;
 }).filter(Boolean);
}

function projectDetailAnalytics(detail) {
 const artifacts = projectDetailArtifactItems(detail);
 const timeline = projectDetailTimelineItems(detail);
 const systems = detail?.systems || detail?.build_state?.systems || detail?.manifest?.systems || [];
 const learning = detail?.learning_records || detail?.build_state?.learning_records || [];
 const validation = detail?.validation || detail?.build_state?.validation || detail?.manifest?.build_job?.validation || null;
 return [
  { label: 'Files', value: artifacts.length, detail: 'generated artifacts' },
  { label: 'Systems', value: Array.isArray(systems) ? systems.length : 0, detail: 'gameplay systems' },
  { label: 'Steps', value: timeline.length, detail: 'recorded stages' },
  { label: 'Learning', value: detail?.learning_count ?? (Array.isArray(learning) ? learning.length : 0), detail: 'build notes' },
  { label: 'Validation', value: validation ? (validation.ok ? 'Pass' : 'Needs fix') : (detail?.status || 'Generated'), detail: 'artifact check' },
 ];
}

function renderProjectDetailAnalytics(detail) {
 return `
 <section class="project-detail-section project-detail-analytics" data-smoke="project-detail-analytics" aria-label="Project analytics">
  <h3 class="panel-section-title">Project analytics</h3>
  <div class="project-detail-stat-grid">
   ${projectDetailAnalytics(detail).map(stat => `
    <article class="project-detail-stat">
     <strong>${escapeHTML(stat.value)}</strong>
     <span>${escapeHTML(stat.label)}</span>
     <small>${escapeHTML(stat.detail)}</small>
    </article>
   `).join('')}
  </div>
 </section>
 `;
}

function renderProjectDetailTimeline(detail) {
 const timeline = projectDetailTimelineItems(detail);
 return `
 <section class="project-detail-section" data-smoke="project-detail-timeline" aria-label="Build timeline">
  <h3 class="panel-section-title">Build timeline</h3>
  <div class="project-detail-timeline">
   ${timeline.map(item => `
    <article class="project-timeline-row ${escapeHTML(item.status)}">
     <span>${escapeHTML(item.index)}</span>
     <div>
      <strong>${escapeHTML(item.title)}</strong>
      ${item.detail ? `<small>${escapeHTML(item.detail)}</small>` : ''}
     </div>
    </article>
   `).join('')}
   ${timeline.length === 0 ? '<p class="panel-muted compact">No timeline recorded for this build.</p>' : ''}
  </div>
 </section>
 `;
}

function renderProjectDetailLogs(detail) {
 const logs = projectDetailLogItems(detail);
 return `
 <section class="project-detail-section" data-smoke="project-detail-logs" aria-label="Build logs">
  <h3 class="panel-section-title">Build logs</h3>
  <div class="project-detail-log-list">
   ${logs.slice(0, 12).map(log => `
    <div class="log-entry log-${escapeHTML(log.level || log.stage || 'info')}">
     <span class="log-time">${escapeHTML(log.time || '')}</span>
     <span class="log-stage">${escapeHTML(log.stage || log.level || 'info')}</span>
     <span class="log-msg">${escapeHTML(log.message || '')}</span>
    </div>
   `).join('')}
   ${logs.length === 0 ? '<p class="panel-muted compact">No logs recorded for this build.</p>' : ''}
  </div>
 </section>
 `;
}

function renderBuildDetailPanel() {
 if (!panelState.isPanelActive('buildDetail')) return '';
 const d = state.buildDetail;
 const loading = state.buildDetailLoading;
 const artifacts = projectDetailArtifactItems(d);
 return `
 <div class="panel-scrim" id="build-detail-scrim"></div>
 <aside class="slide-panel build-detail-panel" data-smoke="build-detail-panel" aria-label="Build detail">
 <div class="panel-head">
 <h2>${d ? escapeHTML(d.name || d.id || 'Build detail') : 'Build detail'}</h2>
 <button class="icon-btn" id="btn-close-build-detail">×</button>
 </div>
 <div class="panel-body">
 ${loading ? '<p class="panel-muted">Loading build details...</p>' : ''}
 ${!loading && !d ? '<p class="panel-muted">Could not load build details. The project service may still be starting.</p>' : ''}
 ${!loading && d ? `
 <h3 class="panel-section-title">Original prompt</h3>
 <p class="build-detail-prompt">${escapeHTML(d.prompt || 'Generated Roblox project')}</p>

 ${renderProjectDetailAnalytics(d)}
 ${renderProjectDetailTimeline(d)}
 ${renderProjectDetailLogs(d)}

 <h3 class="panel-section-title">Build details</h3>
 <div class="build-detail-meta">
 <div class="detail-row"><strong>Genre</strong><span>${escapeHTML(d.genre || 'Adventure')}</span></div>
 <div class="detail-row"><strong>Quality mode</strong><span>${escapeHTML(d.quality_mode || d.quality || 'Balanced')}</span></div>
 <div class="detail-row"><strong>Skill</strong><span>${escapeHTML(d.skill?.name || d.skill || '—')}</span></div>
 <div class="detail-row"><strong>Status</strong><span>${escapeHTML(d.status || 'Generated')}</span></div>
 <div class="detail-row"><strong>Mode</strong><span>${escapeHTML(d.mode || 'one-shot')}</span></div>
 <div class="detail-row"><strong>Created</strong><span>${d.created_at ? relativeTime(d.created_at * 1000) : '—'}</span></div>
 <div class="detail-row"><strong>Updated</strong><span>${d.updated_at ? relativeTime(d.updated_at * 1000) : '—'}</span></div>
 <div class="detail-row"><strong>Iterations</strong><span>${d.iteration_count != null ? d.iteration_count : (d.learning_count || 0)}</span></div>
 </div>

 <h3 class="panel-section-title">Artifacts</h3>
 <div class="build-detail-artifacts">
 ${artifacts.map(a => {
 const path = a.path;
 const bytes = a.bytes;
 const sizeLabel = bytes ? formatBytes(bytes) : '';
 return `<div class="detail-row artifact-row"><strong>${escapeHTML(path)}</strong>${sizeLabel ? `<span>${sizeLabel}</span>` : ''}</div>`;
 }).join('')}
 ${artifacts.length === 0 ? '<p class="panel-muted compact">No artifacts recorded.</p>' : ''}
 </div>
 ` : ''}
 </div>
 <div class="panel-foot build-detail-actions">
 <button class="action-btn" id="btn-detail-resume" ${!d ? 'disabled' : ''}>Resume & refine</button>
 <button class="action-btn ghost" id="btn-detail-export" ${!d ? 'disabled' : ''}>Export Rojo ZIP</button>
 </div>
 </aside>
`;
}

function renderBuildAnalyticsPanel() {
 if (!panelState.isPanelActive('buildAnalytics')) return '';
 const a = state.buildAnalytics;
 const loading = state.buildAnalyticsLoading;
 const totalBuilds = a?.total_builds ?? state.buildHistory.length;
 const successRate = a?.success_rate ?? 100;
 const avgBuildTime = a?.avg_build_time_sec ?? '—';
 const topGenres = a?.top_genres ?? inferTopGenres();
 const commonErrors = a?.common_errors ?? defaultCommonErrors();
 return `
 <div class="panel-scrim" id="build-analytics-scrim"></div>
 <aside class="slide-panel build-analytics-panel" data-smoke="build-analytics-panel" aria-label="Build analytics">
 <div class="panel-head">
 <h2>Build analytics</h2>
 <button class="icon-btn" id="btn-close-build-analytics">×</button>
 </div>
 <div class="panel-body">
 <p class="panel-description">Success rate, validation metrics, common Luau errors, build times, and systems generated across your Roblox builds.</p>
 ${loading ? '<p class="panel-muted">Loading analytics...</p>' : ''}
 ${!loading ? `
 <h3 class="panel-section-title">Overview</h3>
 <div class="analytics-grid">
 <div class="analytics-stat"><strong>${totalBuilds}</strong><span>Total builds</span></div>
 <div class="analytics-stat"><strong>${typeof successRate === 'number' ? successRate.toFixed(0) + '%' : successRate}</strong><span>Success rate</span></div>
 <div class="analytics-stat"><strong>${avgBuildTime !== '—' ? avgBuildTime + 's' : '—'}</strong><span>Avg build time</span></div>
 <div class="analytics-stat"><strong>${topGenres.length}</strong><span>Genres used</span></div>
 </div>

 <h3 class="panel-section-title">Top genres</h3>
 <div class="analytics-genre-list">
 ${topGenres.map(g => `
 <div class="detail-row"><strong>${escapeHTML(g.genre || g.label || 'Genre')}</strong><span>${g.count ?? g.value ?? 0} builds</span></div>
 `).join('')}
 ${topGenres.length === 0 ? '<p class="panel-muted">No genre data yet.</p>' : ''}
 </div>

 <h3 class="panel-section-title">Common Luau issues</h3>
 <div class="analytics-error-list">
 ${commonErrors.map(e => `
 <div class="detail-row analytics-error-row"><strong>${escapeHTML(e.type || e.label || 'Issue')}</strong><span>${escapeHTML(e.description || e.detail || '')}</span></div>
 `).join('')}
 ${commonErrors.length === 0 ? '<p class="panel-muted">No common issues recorded.</p>' : ''}
 </div>
 ` : ''}
 <p class="panel-note">Analytics cover build quality, Luau validation, and Roblox artifact completeness.</p>
 </div>
 <div class="panel-foot">
 <button class="action-btn ghost" id="btn-refresh-build-analytics">Refresh analytics</button>
 </div>
 </aside>
 `;
}

function inferTopGenres() {
 const counts = {};
 for (const build of state.buildHistory || []) {
  const genre = build.genre || inferGenre(build.prompt || '') || 'Adventure';
  counts[genre] = (counts[genre] || 0) + 1;
 }
 return Object.entries(counts)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 6)
  .map(([genre, count]) => ({ genre, count }));
}

function defaultCommonErrors() {
 return [
  { type: 'Rojo handoff', description: 'Install Rojo and the Studio plugin before live sync.' },
  { type: 'Validation', description: 'Generated projects should include default.project.json plus server, client, and shared Luau files.' },
  { type: 'Playtest', description: 'Open in Roblox Studio and verify checkpoints, rewards, spawns, and remotes.' }
 ];
}

function defaultProviderKeys() {
 return [
  { id: 'quality-provider', label: 'Quality generation provider', set: false, last4: '' },
  { id: 'fallback-provider', label: 'Fallback generation provider', set: false, last4: '' }
 ];
}

function defaultRobloxKeys() {
 return [
  { id: 'open-cloud', label: 'Roblox Open Cloud', set: false, last4: '' },
  { id: 'marketplace-assets', label: 'Marketplace / asset import', set: false, last4: '' }
 ];
}

function renderBuildLogsPanel() {
 if (!panelState.isPanelActive('buildLogs')) return '';
 const logs = state.buildLogsSearch ? state.buildLogsFiltered : state.buildLogs;
 return `
 <div class="panel-scrim" id="build-logs-scrim"></div>
 <aside class="slide-panel build-logs-panel" data-smoke="build-logs-panel" aria-label="Build logs">
 <div class="panel-head">
 <h2>Build logs</h2>
 <button class="icon-btn" id="btn-close-build-logs">×</button>
 </div>
 <div class="panel-search">
 <input id="build-logs-search" type="search" placeholder="Search logs by stage, message, or error..." value="${escapeHTML(state.buildLogsSearch)}" aria-label="Search build logs" />
 </div>
 <div class="panel-body">
 ${state.buildLogsLoading ? '<p class="panel-muted">Loading build logs...</p>' : ''}
 ${!state.buildLogsLoading && logs.length === 0 ? '<p class="panel-muted">' + (state.buildLogsSearch ? 'No logs match your search.' : 'No build logs yet. Build a Roblox game to see stage logs here.') + '</p>' : ''}
 ${logs.slice(-80).map(log => `
 <div class="log-entry log-${escapeHTML(log.level || log.stage || 'info')}">
 <span class="log-time">${escapeHTML(log.time || log.timestamp || '')}</span>
 <span class="log-stage">${escapeHTML(log.stage || log.level || 'info')}</span>
 <span class="log-msg">${escapeHTML(log.message || log.text || log.detail || '')}</span>
 </div>
 `).join('')}
 </div>
 <div class="panel-foot">
 <button class="action-btn ghost" id="btn-refresh-build-logs">Refresh logs</button>
 <button class="action-btn ghost" id="btn-export-build-logs">Export logs</button>
 </div>
 </aside>
 `;
}

function renderKeysPanel() {
 if (!panelState.isPanelActive('keys')) return '';
 const k = state.keysPanel;
 const loading = state.keysPanelLoading;
 const providerKeys = k?.provider_keys ?? defaultProviderKeys();
 const robloxKeys = k?.roblox_keys ?? defaultRobloxKeys();
 return `
 <div class="panel-scrim" id="keys-panel-scrim"></div>
 <aside class="slide-panel keys-panel" data-smoke="keys-panel" aria-label="Keys and accounts">
 <div class="panel-head">
 <h2>Keys & accounts</h2>
 <button class="icon-btn" id="btn-close-keys-panel">×</button>
 </div>
 <div class="panel-body">
 <p class="panel-description">Manage AI provider keys and Roblox Open Cloud credentials. Values are redacted in the UI and stored in Playro app data.</p>
 ${loading ? '<p class="panel-muted">Loading keys...</p>' : ''}
 ${!loading ? `
 <h3 class="panel-section-title">Provider keys</h3>
 <div class="keys-list">
 ${providerKeys.map(key => `
 <div class="detail-row key-row">
 <strong>${escapeHTML(key.label || key.id || 'Provider')}</strong>
 <span class="key-value">${key.set ? '••••••••' + (key.last4 || '') : 'Not set'}</span>
 <button class="action-btn ghost compact" data-key-action="edit" data-key-id="${escapeHTML(key.id)}">${key.set ? 'Edit' : 'Add'}</button>
 </div>
 `).join('')}
 </div>

 <h3 class="panel-section-title">Roblox Open Cloud</h3>
 <div class="keys-list">
 ${robloxKeys.map(key => `
 <div class="detail-row key-row">
 <strong>${escapeHTML(key.label || key.id || 'Roblox key')}</strong>
 <span class="key-value">${key.set ? '••••••••' + (key.last4 || '') : 'Not set'}</span>
 <button class="action-btn ghost compact" data-key-action="edit" data-key-id="${escapeHTML(key.id)}">${key.set ? 'Edit' : 'Add'}</button>
 </div>
 `).join('')}
 </div>

 <p class="panel-note">Keys are stored locally and redacted in the UI. Provider keys control which AI models are available for each quality mode.</p>
 ` : ''}
 </div>
 <div class="panel-foot">
 <button class="action-btn ghost" id="btn-refresh-keys-panel">Refresh keys</button>
 </div>
 </aside>
 `;
}



function renderQualityRoutingPanel() {
 if (!panelState.isPanelActive('qualityRouting')) return '';
 const modes = (state.qualityRouting?.quality_modes || state.capabilities?.quality_modes || defaultQualityModes());
 const current = state.qualityMode || 'balanced';
 const loading = state.qualityRoutingLoading;
 return `
 <div class="panel-scrim" id="quality-routing-scrim"></div>
 <aside class="slide-panel quality-routing-panel" data-smoke="quality-routing-panel" aria-label="Quality routing">
 <div class="panel-head">
 <h2>Quality routing</h2>
 <button class="icon-btn" id="btn-close-quality-routing">×</button>
 </div>
 <div class="panel-body">
 <p class="panel-description">Select generation quality for your Roblox builds. Higher quality produces more detailed Luau, richer game systems, and better Rojo project scaffolding.</p>
 ${loading ? '<p class="panel-muted">Loading quality modes...</p>' : ''}
 ${!loading ? `
 <div class="quality-modes-list">
 ${modes.map(mode => `
 <div class="quality-mode-card ${current === mode.id ? 'active' : ''}" data-quality-mode="${escapeHTML(mode.id)}">
 <div class="quality-mode-header">
 <strong>${escapeHTML(mode.label)}</strong>
 <span class="quality-mode-badge ${current === mode.id ? 'selected' : ''}">${current === mode.id ? 'Active' : 'Select'}</span>
 </div>
 <p class="quality-mode-desc">${escapeHTML(mode.description)}</p>
 <div class="detail-row"><strong>Model</strong><span>${escapeHTML(mode.model || 'auto')}</span></div>
 <div class="detail-row"><strong>Provider</strong><span>${escapeHTML(mode.provider || 'default')}</span></div>
 </div>
 `).join('')}
 </div>
 ` : ''}
 <p class="panel-note">Quality routing controls which AI models generate your Roblox project. Manage provider keys in the Keys panel.</p>
 </div>
 <div class="panel-foot">
 <button class="action-btn ghost" id="btn-refresh-quality-routing">Refresh modes</button>
 </div>
 </aside>
 `;
}

function renderAdaptersPanel() {
 if (!panelState.isPanelActive('adapters')) return '';
 const a = state.adaptersPanel;
 const loading = state.adaptersPanelLoading;
 const hermes = a?.hermes || state.setup.hermes || 'unknown';
 const rojo = a?.rojo || state.setup.rojo || 'unknown';
 const studio = a?.studio || state.setup.studio || 'unknown';
 const cloud = a?.open_cloud || 'not configured';
 function statusBadge(s) {
 if (s === 'ok' || s === 'ready' || s === 'configured') return '<span class="adapter-badge ok">Ready</span>';
 if (s === 'required' || s === 'missing' || s === 'not found' || s === 'not configured') return '<span class="adapter-badge missing">Not set up</span>';
 return '<span class="adapter-badge unknown">Unknown</span>';
 }
 return `
 <div class="panel-scrim" id="adapters-panel-scrim"></div>
 <aside class="slide-panel adapters-panel" data-smoke="adapters-panel" aria-label="Roblox adapters">
 <div class="panel-head">
 <h2>Roblox adapters</h2>
 <button class="icon-btn" id="btn-close-adapters-panel">×</button>
 </div>
 <div class="panel-body">
 <p class="panel-description">Setup status for tools that connect Playro to Roblox Studio, Rojo, and Open Cloud. Install and configure them here before building.</p>
 ${loading ? '<p class="panel-muted">Loading adapter status...</p>' : ''}
 ${!loading ? `
 <h3 class="panel-section-title">Playro AI engine</h3>
 <div class="adapter-card">
 <div class="detail-row"><strong>Playro AI engine</strong>${statusBadge(hermes)}</div>
 <p class="panel-muted compact">Required engine for Playro builds. Install via the setup wizard.</p>
 </div>

 <h3 class="panel-section-title">Roblox Studio</h3>
 <div class="adapter-card">
 <div class="detail-row"><strong>Studio detection</strong>${statusBadge(studio)}</div>
 <p class="panel-muted compact">Detects RobloxStudioBeta.exe for direct project handoff. Required for live preview.</p>
 </div>

 <h3 class="panel-section-title">Rojo</h3>
 <div class="adapter-card">
 <div class="detail-row"><strong>Rojo CLI</strong>${statusBadge(rojo)}</div>
 <p class="panel-muted compact">Enables live sync between generated Luau files and Roblox Studio. Install: <code>winget install --id Rojo.Rojo --exact</code></p>
 </div>

 <h3 class="panel-section-title">Open Cloud</h3>
 <div class="adapter-card">
 <div class="detail-row"><strong>Open Cloud API</strong>${statusBadge(cloud)}</div>
 <p class="panel-muted compact">Publish assets and manage places via the Roblox Open Cloud API. Add your API key in the Keys panel.</p>
 </div>
 ` : ''}
 <p class="panel-note">Adapters connect Playro to the Roblox ecosystem for building, syncing, and publishing.</p>
 </div>
 <div class="panel-foot">
 <button class="action-btn ghost" id="btn-refresh-adapters">Refresh adapters</button>
 </div>
 </aside>
 `;
}

function renderCrewsPanel() {
 if (!panelState.isPanelActive('crews')) return '';
 const c = state.crewsPanel;
 const loading = state.crewsPanelLoading;
 const crews = c?.crews || defaultCrews();
 const activeCrew = c?.active_crew || 'adventurer';
 return `
 <div class="panel-scrim" id="crews-panel-scrim"></div>
 <aside class="slide-panel crews-panel" data-smoke="crews-panel" aria-label="Builder crews">
 <div class="panel-head">
 <h2>Builder crews</h2>
 <button class="icon-btn" id="btn-close-crews-panel">×</button>
 </div>
 <div class="panel-body">
 <p class="panel-description">Build personas control generation style and quality. Each crew has a different approach to Roblox game creation.</p>
 ${loading ? '<p class="panel-muted">Loading crews...</p>' : ''}
 ${!loading ? `
 <div class="crews-list">
 ${crews.map(crew => `
 <div class="crew-card ${activeCrew === crew.id ? 'active' : ''}" data-crew-id="${escapeHTML(crew.id)}">
 <div class="crew-header">
 <strong>${escapeHTML(crew.label)}</strong>
 <span class="crew-badge ${activeCrew === crew.id ? 'selected' : ''}">${activeCrew === crew.id ? 'Active' : 'Switch'}</span>
 </div>
 <p class="crew-desc">${escapeHTML(crew.description)}</p>
 <div class="detail-row"><strong>Quality</strong><span>${escapeHTML(crew.quality_mode)}</span></div>
 <div class="detail-row"><strong>Builds</strong><span>${crew.recent_builds ?? 0}</span></div>
 </div>
 `).join('')}
 </div>
 ` : ''}
 <p class="panel-note">Crews are build personas that control quality routing and generation style for your Roblox projects.</p>
 </div>
 <div class="panel-foot">
 <button class="action-btn ghost" id="btn-refresh-crews">Refresh crews</button>
 </div>
 </aside>
 `;
}

function defaultCrews() {
 return [
 { id: 'adventurer', label: 'Adventurer', description: 'Balanced and fast. Great for prototyping and iterating on Roblox games quickly.', quality_mode: 'balanced', default_model: 'auto', recent_builds: 0 },
 { id: 'architect', label: 'Architect', description: 'Premium detail. Complex systems, full Luau, rich economies, and polished game loops.', quality_mode: 'premium', default_model: 'auto', recent_builds: 0 },
 { id: 'speedrunner', label: 'Speedrunner', description: 'Fastest iteration. Lightweight models for quick sketches and concept validation.', quality_mode: 'fast', default_model: 'auto', recent_builds: 0 }
 ];
}

function groupBuildsByDate(builds) {
  const groups = {};
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();
  for (const b of builds) {
    const ts = b.created_at || b.started_at || Date.now();
    const d = new Date(typeof ts === 'number' ? ts : Date.parse(ts) || Date.now());
    const ds = d.toDateString();
    const label = ds === today ? 'Today' : ds === yesterday ? 'Yesterday' : ds;
    if (!groups[label]) groups[label] = [];
    groups[label].push(b);
  }
  return groups;
}

function relativeTime(ts) {
  if (!ts) return '';
  const now = Date.now();
  const then = typeof ts === 'number' ? ts : Date.parse(ts);
  if (isNaN(then)) return '';
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return 'Just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}


function closeAllPanels() {
 panelState.setActivePanel(null);
}

function openAdvancedPanel(panel) {
  if (!panel) return;
  openSidebarPanel(panel);
}

function openSidebarPanel(panel) {
 closeAllPanels();
 if (panel === 'build') {
 state.conversation = [];
 state.building = false;
 state.selectedIntent = null;
 state.buildStage = 'idle';
 render();
 return;
 }
 const overlayPanel = panelState.getOverlayPanelForSidebar(panel);
 if (overlayPanel === 'parity') panelState.setActiveParityPanel(panel);
 panelState.setActivePanel(overlayPanel);
 if (overlayPanel === 'buildHistory') {
 fetchBuildHistory();
 } else if (overlayPanel === 'buildMode') {
 fetchBuildModeStatus();
 } else if (overlayPanel === 'buildAnalytics') {
 fetchBuildAnalytics();
 } else if (overlayPanel === 'buildLogs') {
 fetchBuildLogs();
 } else if (overlayPanel === 'keys') {
 fetchKeysPanel();
 } else if (overlayPanel === 'qualityRouting') {
 fetchQualityRouting();
 } else if (overlayPanel === 'adapters') {
 fetchAdaptersPanel();
 } else if (overlayPanel === 'crews') {
 fetchCrewsPanel();
 }
 renderShellAndOverlays();
}

function bindShellEvents() {
 document.getElementById('btn-home')?.addEventListener('click', () => {
 closeAllPanels();
 state.conversation = [];
 state.building = false;
 state.selectedIntent = null;
 state.buildStage = 'idle';
 render();
 });

 document.getElementById('btn-settings')?.addEventListener('click', () => openSidebarPanel('config'));

 document.querySelectorAll('[data-sidebar-panel]').forEach(btn => btn.addEventListener('click', () => openSidebarPanel(btn.dataset.sidebarPanel)));
 document.getElementById('btn-projects')?.addEventListener('click', () => openSidebarPanel('sessions'));
 document.getElementById('btn-open-advanced-from-sidebar')?.addEventListener('click', () => openSidebarPanel('config'));
}

function bindOverlayEvents() {
 document.getElementById('btn-close-build-history')?.addEventListener('click', closeBuildHistory);
 document.getElementById('build-history-scrim')?.addEventListener('click', closeBuildHistory);
 document.getElementById('btn-close-build-mode')?.addEventListener('click', closeBuildMode);
 document.getElementById('build-mode-scrim')?.addEventListener('click', closeBuildMode);
 document.getElementById('btn-refresh-build-history')?.addEventListener('click', () => { fetchBuildHistory(); });
 document.getElementById('btn-refresh-build-mode')?.addEventListener('click', () => { fetchBuildModeStatus(); });
 document.getElementById('btn-toggle-continuous-build')?.addEventListener('click', toggleContinuousBuild);
 document.getElementById('btn-close-parity')?.addEventListener('click', closeActivePanel);
 document.getElementById('parity-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-close-build-analytics')?.addEventListener('click', closeActivePanel);
 document.getElementById('build-analytics-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-refresh-build-analytics')?.addEventListener('click', fetchBuildAnalytics);
 document.getElementById('btn-close-build-logs')?.addEventListener('click', closeActivePanel);
 document.getElementById('build-logs-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-refresh-build-logs')?.addEventListener('click', fetchBuildLogs);
 document.getElementById('build-logs-search')?.addEventListener('input', event => { state.buildLogsSearch = event.target.value; filterBuildLogs(); renderOverlaysOnly(); });
 document.getElementById('btn-close-keys-panel')?.addEventListener('click', closeActivePanel);
 document.getElementById('keys-panel-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-refresh-keys-panel')?.addEventListener('click', fetchKeysPanel);
 document.getElementById('btn-close-quality-routing')?.addEventListener('click', closeActivePanel);
 document.getElementById('quality-routing-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-refresh-quality-routing')?.addEventListener('click', fetchQualityRouting);
 document.querySelectorAll('[data-quality-mode]').forEach(btn => btn.addEventListener('click', () => {
  state.qualityMode = btn.dataset.qualityMode;
  const mode = (state.qualityRouting?.quality_modes || state.capabilities?.quality_modes || defaultQualityModes()).find(item => item.id === state.qualityMode);
  state.buildIntent.quality = mode?.label || 'Balanced';
  renderOverlaysOnly();
 }));
 document.getElementById('btn-close-adapters-panel')?.addEventListener('click', closeActivePanel);
 document.getElementById('adapters-panel-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-refresh-adapters')?.addEventListener('click', fetchAdaptersPanel);
 document.getElementById('btn-close-crews-panel')?.addEventListener('click', closeActivePanel);
 document.getElementById('crews-panel-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-refresh-crews')?.addEventListener('click', fetchCrewsPanel);
 document.querySelectorAll('[data-crew-id]').forEach(btn => btn.addEventListener('click', () => {
  state.activeCrew = btn.dataset.crewId;
  renderOverlaysOnly();
 }));

 // Capabilities panel bindings
 document.getElementById('btn-close-capabilities')?.addEventListener('click', closeActivePanel);
 document.getElementById('capabilities-scrim')?.addEventListener('click', closeActivePanel);
 document.getElementById('btn-refresh-capabilities-panel')?.addEventListener('click', refreshCapabilities);
 document.querySelectorAll('.cap-skill-card:not(.disabled)').forEach(btn => {
 btn.addEventListener('click', () => {
 state.selectedSkill = btn.dataset.skill;
 renderOverlaysOnly();
 });
 });
 document.querySelectorAll('.cap-quality-pill').forEach(btn => {
 btn.addEventListener('click', () => {
 state.qualityMode = btn.dataset.quality;
 renderOverlaysOnly();
 });
 });

 const searchInput = document.getElementById('build-history-search');
 if (searchInput) {
 let debounceTimer = null;
 searchInput.addEventListener('input', () => {
 clearTimeout(debounceTimer);
 debounceTimer = setTimeout(() => {
 state.buildHistorySearch = searchInput.value.trim();
 if (state.buildHistorySearch) {
 searchBuildHistory(state.buildHistorySearch);
 } else {
 state.buildHistorySearchResults = [];
 renderOverlaysOnly();
 }
 }, 300);
 });
 }

 document.querySelectorAll('[data-resume-build]').forEach(btn => {
 btn.addEventListener('click', () => openBuildDetail(btn.dataset.resumeBuild));
 });
 document.querySelectorAll('[data-open-detail]').forEach(btn => {
 btn.addEventListener('click', () => openBuildDetail(btn.dataset.openDetail));
 });

 const intervalInput = document.getElementById('build-mode-interval');
 if (intervalInput) {
 intervalInput.addEventListener('change', () => {
 const val = parseInt(intervalInput.value, 10);
 if (val >= 5 && val <= 120) {
 state.continuousBuild.intervalMin = val;
 renderOverlaysOnly();
 }
 });
 }

  document.getElementById('btn-close-settings')?.addEventListener('click', closeSettings);
  document.getElementById('settings-scrim')?.addEventListener('click', closeSettings);
  document.getElementById('btn-refresh-setup')?.addEventListener('click', refreshSetup);
  document.querySelectorAll('[data-open-advanced-panel]').forEach(btn => {
    btn.addEventListener('click', () => openAdvancedPanel(btn.dataset.openAdvancedPanel));
  });
  document.getElementById('btn-open-build-options')?.addEventListener('click', openCapabilitiesPanel);
  document.getElementById('btn-open-setup-banner')?.addEventListener('click', () => {
    panelState.setActivePanel('settings');
    renderShellAndOverlays();
    refreshSetup();
  });

 // Build detail panel bindings
 document.getElementById('btn-close-build-detail')?.addEventListener('click', closeBuildDetail);
 document.getElementById('build-detail-scrim')?.addEventListener('click', closeBuildDetail);
 document.getElementById('btn-detail-resume')?.addEventListener('click', () => {
 if (state.buildDetailProjectId) resumeBuild(state.buildDetailProjectId);
 });
 document.getElementById('btn-detail-export')?.addEventListener('click', () => {
 if (state.buildDetailProjectId) exportRojoZIP(state.buildDetailProjectId);
 });
}

function bindLandingEvents() {
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const input = document.getElementById('prompt-input');
      const intent = chip.dataset.intent;
      if (state.selectedIntent === intent) {
        state.selectedIntent = null;
        render();
        document.getElementById('prompt-input')?.focus();
        return;
      }
      state.selectedIntent = intent;
      input.value = input.value ? `${input.value} with ${intent}` : `Make a Roblox game with ${intent} `;
      input.focus();
      render();
      document.getElementById('prompt-input')?.focus();
    });
  });

  document.querySelectorAll('[data-demo-prompt]').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById('prompt-input');
      if (!input) return;
      input.value = btn.dataset.demoPrompt || '';
      state.selectedIntent = btn.dataset.demoGenre || state.selectedIntent;
      state.buildIntent = inferBuildIntent(input.value);
      render();
      const nextInput = document.getElementById('prompt-input');
      nextInput?.focus();
      if (nextInput) nextInput.selectionStart = nextInput.selectionEnd = nextInput.value.length;
    });
  });

  document.querySelectorAll('[data-skill-pack]').forEach(btn => {
    btn.addEventListener('click', () => {
      applySkillPack(btn.dataset.skillPack);
      render();
    });
  });

  document.querySelectorAll('[data-skill]').forEach(btn => {
    btn.addEventListener('click', () => {
      state.selectedSkill = btn.dataset.skill;
      render();
    });
  });

  document.querySelectorAll('[data-quality]').forEach(btn => {
    btn.addEventListener('click', () => {
      state.qualityMode = btn.dataset.quality;
      const mode = (state.capabilities?.quality_modes || defaultQualityModes()).find(item => item.id === state.qualityMode);
      state.buildIntent.quality = mode?.label || 'Balanced';
      render();
    });
  });

  const landingPrompt = document.getElementById('prompt-input');
  landingPrompt?.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      triggerBuild();
    }
  });
}

function bindWorkspaceEvents() {
  document.getElementById('btn-close-installer')?.addEventListener('click', () => handleAction('close-installer'));
  document.getElementById('btn-build')?.addEventListener('click', triggerBuild);
  document.querySelectorAll('[data-action]').forEach(btn => btn.addEventListener('click', () => handleAction(btn.dataset.action)));
  document.querySelectorAll('.copy-btn').forEach(btn => btn.addEventListener('click', () => handleAction('copy-luau')));
  const refinement = document.getElementById('refinement');
  refinement?.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      triggerBuild();
    }
  });
}

function bindEvents() {
  bindShellEvents();
  bindOverlayEvents();
  bindLandingEvents();
  bindWorkspaceEvents();
}

if (typeof document.addEventListener === 'function') {
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (state.activePanel === 'buildDetail') { closeBuildDetail(); return; }
      if (state.activePanel) { closeActivePanel(); return; }
      if (state.hermesInstaller?.open) { state.hermesInstaller.open = false; renderOverlaysOnly(); return; }
    }
  });
}

function closeActivePanel() {
 panelState.setActivePanel(null);
 renderOverlaysOnly();
}

function closeSettings() {
 closeActivePanel();
}

function closeBuildHistory() {
 closeActivePanel();
}

function closeBuildMode() {
 closeActivePanel();
}

async function fetchBuildHistory() {
 state.buildHistoryLoading = true;
 renderOverlaysOnly();
 try {
 const data = await api.getBuilds();
 state.buildHistory = (data.builds || []).map(b => {
 const projectId = b.project_id || projectIdFromJob(b);
 const buildId = b.build_id || b.id;
 return {
 id: projectId || buildId,
 project_id: projectId || '',
 build_id: buildId,
 name: b.project_name || b.name || '',
 genre: b.genre || 'Adventure',
 quality: b.quality || 'Balanced',
 status: b.status || 'completed',
 prompt: b.prompt || '',
 created_at: b.created_at || b.started_at || Date.now(),
 time_label: relativeTime(b.created_at || b.started_at)
 };
 });
 } catch (_error) {
 // Fallback: seed from recent projects if backend unavailable
 state.buildHistory = state.projects.map(p => ({
 id: p.id || p.name,
 name: p.name,
 genre: p.genre,
 quality: 'Balanced',
 status: 'completed',
 prompt: p.desc || '',
 created_at: Date.now() - (p.time === 'Just now' ? 60000 : p.time === '2h ago' ? 7200000 : p.time === '5h ago' ? 18000000 : 86400000),
 time_label: p.time
 }));
 }
 state.buildHistoryLoading = false;
 renderOverlaysOnly();
}

async function searchBuildHistory(query) {
 state.buildHistorySearching = true;
 const q = query.toLowerCase();
 // Client-side FTS-like filtering over cached build history
 state.buildHistorySearchResults = state.buildHistory.filter(b =>
 (b.name || '').toLowerCase().includes(q) ||
 (b.genre || '').toLowerCase().includes(q) ||
 (b.prompt || '').toLowerCase().includes(q) ||
 (b.status || '').toLowerCase().includes(q)
 );
 state.buildHistorySearching = false;
 renderOverlaysOnly();
}

async function fetchBuildAnalytics() {
 state.buildAnalyticsLoading = true;
 renderOverlaysOnly();
 try {
 const data = await api.getDesktopAnalytics();
 if (data.ok) {
 state.buildAnalytics = data;
 state.buildAnalyticsLoading = false;
 renderOverlaysOnly();
 return;
 }
 } catch (_error) { /* fallback to client-side computation */ }
 if (!state.buildHistory.length) {
 await fetchBuildHistory();
 }
 const builds = state.buildHistory || [];
 const completedBuilds = builds.filter(b => String(b.status || '').toLowerCase().includes('complete')).length;
 const failedBuilds = builds.filter(b => /fail|error/i.test(String(b.status || ''))).length;
 state.buildAnalytics = {
 total_builds: builds.length,
 completed_builds: completedBuilds,
 failed_builds: failedBuilds,
 success_rate: builds.length ? (completedBuilds / builds.length) * 100 : 100,
 top_genres: inferTopGenres(),
 common_errors: defaultCommonErrors()
 };
 state.buildAnalyticsLoading = false;
 renderOverlaysOnly();
}

function buildLogSearchText(log) {
  if (typeof log === 'string') return log;
  return [log.time, log.timestamp, log.stage, log.level, log.message, log.text, log.detail]
    .filter(Boolean)
    .join(' ');
}

function filterBuildLogs() {
  const q = (state.buildLogsSearch || '').toLowerCase();
  state.buildLogsFiltered = q ? (state.buildLogs || []).filter(log => buildLogSearchText(log).toLowerCase().includes(q)) : [];
}

async function fetchBuildLogs() {
 state.buildLogsLoading = true;
 renderOverlaysOnly();
 try {
 const data = await api.getDesktopLogs();
 if (data.ok && Array.isArray(data.logs)) {
 state.buildLogs = data.logs;
 filterBuildLogs();
 state.buildLogsLoading = false;
 renderOverlaysOnly();
 return;
 }
 } catch (_error) { /* fallback to client-side computation */ }
 if (!state.buildHistory.length) {
 await fetchBuildHistory();
 }
 state.buildLogs = (state.buildHistory || []).map(b => ({
 time: b.time_label || relativeTime(b.created_at),
 stage: b.status || 'completed',
 level: /fail|error/i.test(String(b.status || '')) ? 'error' : 'info',
 message: `${b.name || b.id || 'Roblox build'} · ${b.genre || 'Adventure'}`
 }));
 filterBuildLogs();
 state.buildLogsLoading = false;
 renderOverlaysOnly();
}

async function fetchKeysPanel() {
 state.keysPanelLoading = true;
 renderOverlaysOnly();
 try {
 const data = await api.getDesktopKeys();
 if (data.ok) {
 state.keysPanel = data;
 state.setup.hermes = data.hermes === 'ok' ? 'ready' : (data.hermes === 'required' ? 'missing' : data.hermes);
 state.setup.studio = data.studio === 'ok' ? 'ready' : (data.studio === 'not found' ? 'missing' : data.studio);
 state.setup.rojo = data.rojo === 'ok' ? 'ready' : (data.rojo === 'not found' ? 'missing' : data.rojo);
 state.keysPanelLoading = false;
 renderOverlaysOnly();
 return;
 }
 } catch (_error) { /* fallback to refreshSetup */ }
 await refreshSetup();
 state.keysPanel = { note: 'Playro AI engine is required for generation.' };
 state.keysPanelLoading = false;
 renderOverlaysOnly();
}

async function fetchBuildModeStatus() {
 state.buildModeLoading = true;
 renderOverlaysOnly();
 try {
 const projectId = state.currentProject?.project_id || state.currentProject?.id;
 if (!projectId) {
 state.continuousBuild.lastTickStatus = 'Select or generate a project before enabling 24/7 mode.';
 } else {
 const data = await api.updateBuildStatus({ project_id: projectId, status: state.continuousBuild.enabled ? 'running' : 'paused' });
 if (data.ok) {
 const mission = data.build_mission || {};
 state.continuousBuild = {
 ...state.continuousBuild,
 enabled: mission.continuous ?? state.continuousBuild.enabled,
 lastTickAt: mission.updated_at ?? state.continuousBuild.lastTickAt,
 lastTickStatus: mission.status || state.continuousBuild.lastTickStatus
 };
 }
 }
 } catch (_error) { /* keep current state */ }
 state.buildModeLoading = false;
 renderOverlaysOnly();
}

async function fetchQualityRouting() {
 state.qualityRoutingLoading = true;
 renderOverlaysOnly();
 try {
 const data = await api.getDesktopCapabilities();
 if (data.ok) {
 state.capabilities = data;
 const providerRouting = data.capabilities?.provider_routing || {};
 state.qualityRouting = {
 ok: true,
 quality_modes: data.quality_modes || defaultQualityModes(),
 provider_routing: providerRouting,
 note: providerRouting.description || 'Routes Roblox generation jobs by selected quality mode.'
 };
 }
 } catch (_error) {
 state.qualityRouting = { ok: false, quality_modes: defaultQualityModes(), note: 'Using default quality modes until the project service is available.' };
 }
 state.qualityRoutingLoading = false;
 renderOverlaysOnly();
}

async function fetchAdaptersPanel() {
 state.adaptersPanelLoading = true;
 renderOverlaysOnly();
 try {
 const setup = await window.robloxAIStudio?.checkSetup?.();
 state.adaptersPanel = {
 ok: true,
 hermes: setup?.hermes?.ok ? 'ready' : 'required',
 rojo: setup?.rojo?.ok ? 'ready' : 'not found',
 studio: setup?.studio?.ok ? 'ready' : 'not found',
 open_cloud: state.keysPanel?.roblox_keys?.some(key => key.id === 'open-cloud' && key.set) ? 'configured' : 'not configured'
 };
 state.setup.hermes = state.adaptersPanel.hermes === 'ready' ? 'ready' : 'missing';
 state.setup.rojo = state.adaptersPanel.rojo === 'ready' ? 'ready' : 'missing';
 state.setup.studio = state.adaptersPanel.studio === 'ready' ? 'ready' : 'missing';
 } catch (_error) {
 state.adaptersPanel = { ok: false, hermes: state.setup.hermes || 'unknown', rojo: state.setup.rojo || 'unknown', studio: state.setup.studio || 'unknown', open_cloud: 'not configured' };
 }
 state.adaptersPanelLoading = false;
 renderOverlaysOnly();
}

async function fetchCrewsPanel() {
 state.crewsPanelLoading = true;
 renderOverlaysOnly();
 try {
 const data = await api.getDesktopCapabilities();
 const modes = data.ok ? (data.quality_modes || []) : [];
 state.crewsPanel = {
 ok: true,
 active_crew: state.activeCrew || 'adventurer',
 crews: defaultCrews().map((crew, index) => ({
 ...crew,
 quality_mode: modes[index]?.label || crew.quality_mode,
 recent_builds: state.buildHistory.filter(build => String(build.quality || build.quality_mode || '').toLowerCase().includes(String(crew.quality_mode || '').toLowerCase())).length
 }))
 };
 } catch (_error) {
 state.crewsPanel = { ok: false, active_crew: state.activeCrew || 'adventurer', crews: defaultCrews() };
 }
 state.crewsPanelLoading = false;
 renderOverlaysOnly();
}

async function toggleContinuousBuild() {
 const nextEnabled = !state.continuousBuild.enabled;
 const projectId = state.currentProject?.project_id || state.currentProject?.id;
 if (!projectId) {
 toast('Generate or open a project before enabling 24/7 build mode.');
 return;
 }
 try {
 const data = await api.setContinuousBuild({ project_id: projectId, enabled: nextEnabled, interval_min: state.continuousBuild.intervalMin });
 if (!data.ok) throw new Error(data.error || '24/7 build mode update failed');
 state.continuousBuild.enabled = nextEnabled;
 state.continuousBuild.lastTickStatus = nextEnabled ? 'enabled' : 'paused';
 toast(nextEnabled ? '24/7 build mode enabled.' : '24/7 build mode disabled.');
 } catch (_error) {
 toast('Could not update 24/7 build mode.');
 }
 renderOverlaysOnly();
}

async function resumeBuild(buildId) {
 if (!buildId) return toast('No build ID to resume.');
 closeBuildHistory();
 try {
 const data = await api.getProject(buildId);
 if (data.project) {
 state.currentProject = data.project;
 const artifacts = data.project.artifacts || [];
 const configArtifact = artifacts.find(item => item.path === PLAYRO_SHARED_CONFIG);
 const serverArtifact = artifacts.find(item => item.path === PLAYRO_SERVER_MAIN);
 state.lastCode = configArtifact?.preview || serverArtifact?.preview || '';
 state.conversation = [{ role: 'ai', title: `${data.project.name || 'Project'} resumed`, text: 'Resumed from build history. Use the refinement dock to iterate further.', code: state.lastCode, done: true }];
 state.buildStage = 'complete';
 render();
 toast('Build resumed from history.');
 }
 } catch (_error) {
 toast('Could not load build details. The project service may still be starting.');
 }
}

async function triggerBuild() {
  if (state.building) return;
  const input = document.getElementById('prompt-input') || document.getElementById('refinement');
  const prompt = input?.value.trim();
  if (!prompt) return toast('Type a Roblox game idea first.');

  if (state.setup.rojo !== 'ready') {
    toast('Building locally first. Install Rojo only when you are ready to test in Studio.');
  }

  // Refinement mode: if we have a current project and are in the workspace dock,
  // send project_id to /generate so the backend iterates on the existing project
  // instead of starting fresh. This routes refinements through the async build
  // pipeline (with SSE stage events) rather than the synchronous /refine endpoint.
  const isRefining = (state.currentProject?.id || state.conversation.some(msg => msg.role === 'ai' && msg.done)) && document.getElementById('refinement') !== null;
  const projectId = state.currentProject?.id || null;

  const intent = inferBuildIntent(prompt);
  state.buildIntent = intent;

  state.conversation.push({ role: 'user', text: prompt });
  state.building = true;
  state.buildStage = 'idea';
  render();

  // When the backend is available and returns a build_id, SSE events drive
  // the stage updates and conversation messages. Skip hardcoded addStep calls
  // to avoid duplicate messages. Only use addStep as a fallback preview when
  // the backend is unreachable (generateProject returns null).
  const result = await generateProject(prompt, projectId);

  if (result === null) {
    // Backend unreachable — show fallback preview steps
    if (isRefining) {
      await addStep('Reading refinement', `Iterating on ${state.currentProject?.name || projectId || 'the current preview'} with your changes.`, 'plan');
      await addStep('Updating project', 'Applying refinement to existing Luau systems, config, and scripts.', 'luau');
    } else {
      await addStep('Reading your idea', `Detected ${inferGenre(prompt)} with Roblox-specific gameplay systems.`, 'plan');
      await addStep('Planning the project', 'Preparing Rojo folders, shared config, server scripts, client HUD, and validation checks.', 'luau');
      await addStep('Writing Luau', 'Generating server-authoritative mechanics and safe client UI.', 'handoff');
    }
    _finishBuild(prompt, null, null, isRefining);
    return;
  }

  // Backend returned a result — SSE events already drove stage updates.
  // Fetch final project details and render the completion message.
  const project = result.project || null;
  const changedFiles = result.files || [];
  _finishBuild(prompt, project, changedFiles, isRefining);
}

function _finishBuild(prompt, project, changedFiles, isRefining) {
  if (!project && typeof prompt === 'string' && state.pendingBuildResults?.[prompt]) {
    const pending = state.pendingBuildResults[prompt];
    project = pending.project || null;
    changedFiles = changedFiles?.length ? changedFiles : (pending.files || []);
  }
  const projectName = project?.name || inferProjectName(prompt);
  const genre = project?.genre || inferGenre(prompt);
  const artifacts = project?.artifacts || [];
  const configArtifact = artifacts.find(item => item.path === PLAYRO_SHARED_CONFIG);
  const serverArtifact = artifacts.find(item => item.path === PLAYRO_SERVER_MAIN);
  const code = configArtifact?.preview || serverArtifact?.preview || fallbackConfig(projectName, genre);
  const receipt = createBuildReceipt(prompt, project, artifacts, changedFiles || [], isRefining);

  if (isRefining && project) {
    // Update current project with latest data from refinement
    state.currentProject = { ...state.currentProject, ...project, artifacts };
  } else {
    state.currentProject = project ? { ...project, artifacts } : null;
  }
  state.lastCode = code;

  if (isRefining && project) {
    // Refinement: show changed files in the conversation thread
    const fileList = changedFiles.length
      ? changedFiles.map(f => typeof f === 'string' ? f : (f.path || f.name || String(f)))
      : [PLAYRO_SHARED_CONFIG, PLAYRO_SERVER_MAIN, PLAYRO_CLIENT_HUD];
    const diffSummary = fileList.map(f => ` \u2022 ${f}`).join('\n');
    state.buildStage = 'handoff';
    render();
    state.conversation.push({
      role: 'ai',
      title: `${projectName} refined`,
      text: `Refinement applied to existing project.\n\nChanged files:\n${diffSummary}`,
      code,
      receipt,
      artifacts,
      done: true
    });
    // Update existing project in recent list
    const existing = state.projects.find(p => p.id === state.currentProject.id);
    if (existing) {
      existing.time = 'Just now';
      existing.desc = `Refined: ${prompt.slice(0, 56)}`;
    }
  } else if (project) {
    // New build with backend available
    state.conversation.push({
      role: 'ai',
      title: `${projectName} is ready`,
      text: `Generated real project files on disk with default.project.json, Luau scripts, manifest, and README. Used ${escapeHTML(project.skill?.name || getSelectedSkillName())} at ${escapeHTML(project.quality_mode || state.buildIntent.quality)} quality. Use Open folder now, or connect Studio later with Rojo when you are ready to test.`,
      code,
      receipt,
      artifacts,
      done: true
    });
    state.projects.unshift({
      name: projectName,
      genre,
      desc: prompt.slice(0, 72),
      time: 'Just now',
      project_path: project.project_path,
      rojo_project: project.rojo_project,
      id: project.id
    });
  } else if (isRefining) {
    // Backend unavailable refinement fallback. Keep the existing project context
    // visible instead of presenting the refinement as a brand-new generated game.
    state.conversation.push({
      role: 'ai',
      title: `${projectName} preview updated`,
      text: 'The project service is offline, so this is a preview update. Once setup is complete, refinements update real Rojo files.',
      code,
      receipt,
      done: true
    });
    const existing = state.projects.find(p => p.id && p.id === state.currentProject?.id);
    if (existing) {
      existing.time = 'Just now';
      existing.desc = `Preview refinement: ${prompt.slice(0, 56)}`;
    }
  } else {
    // Backend unavailable fallback
    state.conversation.push({
      role: 'ai',
      title: `${projectName} is ready`,
      text: 'The project service is offline, so this is a preview. Once setup is complete, builds generate real Rojo files you can open in Studio.',
      code,
      receipt,
      done: true
    });
    state.projects.unshift({
      name: projectName,
      genre,
      desc: prompt.slice(0, 72),
      time: 'Just now'
    });
  }

  state.building = false;
  state.buildStage = 'complete';
  render();
}

async function triggerRefinement(refinement) {
  if (state.building) return;
  const projectId = state.currentProject?.id;
  if (!projectId) return toast('No current project to refine. Build one first.');

  state.conversation.push({ role: 'user', text: refinement });
  state.building = true;
  state.buildStage = 'idea';
  render();

  await addStep('Reading refinement', `Iterating on ${state.currentProject.name || projectId} with your changes.`, 'plan');
  await addStep('Updating project', 'Applying refinement to existing Luau systems, config, and scripts.', 'luau');

  const result = await refineProject(projectId, refinement);
  if (result) {
    const project = result.project || state.currentProject;
    const changedFiles = result.files || [];
    const projectName = project.name || state.currentProject.name || inferProjectName(refinement);

    // Update the current project with latest data
    state.currentProject = { ...state.currentProject, ...project };

    // Build a changed-files summary for the conversation thread
    const fileList = changedFiles.length
      ? changedFiles.map(f => {
          if (typeof f === 'string') return f;
          return f.path || f.name || String(f);
        })
      : [PLAYRO_SHARED_CONFIG, PLAYRO_SERVER_MAIN, PLAYRO_CLIENT_HUD];
    const diffSummary = fileList.map(f => `  • ${f}`).join('\n');

    // Fetch the latest code preview for the code card
    let code = state.lastCode;
    try {
      const detailData = await api.getProject(projectId);
      const artifacts = detailData.project?.artifacts || [];
      const configArtifact = artifacts.find(item => item.path === PLAYRO_SHARED_CONFIG);
      const serverArtifact = artifacts.find(item => item.path === PLAYRO_SERVER_MAIN);
      code = configArtifact?.preview || serverArtifact?.preview || code;
    } catch (_e) { /* keep lastCode */ }

    state.lastCode = code;
    const receipt = createBuildReceipt(refinement, project, [], changedFiles, true);
    state.buildStage = 'handoff';
    render();

    await addStep('Preparing Studio handoff', 'Refined project files written. Rojo sync ready.', 'complete');

    state.conversation.push({
      role: 'ai',
      title: `${projectName} refined`,
      text: `Refinement applied to existing project.\n\nChanged files:\n${diffSummary}`,
      code,
      receipt,
      done: true
    });

    // Update the matching project in the recent list
    const existing = state.projects.find(p => p.id === projectId);
    if (existing) {
      existing.time = 'Just now';
      existing.desc = `Refined: ${refinement.slice(0, 56)}`;
    }
  } else {
    state.conversation.push({
      role: 'ai',
      title: 'Refinement failed',
      text: 'Could not reach the project service. Make sure Playro is fully set up, then try again.',
      done: false
    });
  }

  state.building = false;
  state.buildStage = 'complete';
  render();
}

async function generateProject(prompt, projectId) {
  try {
    const mode = (state.capabilities?.quality_modes || defaultQualityModes()).find(item => item.id === state.qualityMode);
    const body = { prompt, quality: mode?.label || 'Balanced', skill_id: state.selectedSkill };
    // When refining an existing project, send project_id so the backend
    // iterates on the existing project directory instead of starting fresh.
    if (projectId) {
      body.project_id = projectId;
      body.refine = prompt;
    } else {
      body.continuous = false;
    }
    const data = await api.generateProject(body);
    if (!data.ok) throw new Error(data.error || 'Generation failed');

    // If the backend returned a build_id, connect to SSE for real-time
    // stage updates, then wait for the async build to complete before
    // fetching the final project details (including changed files for
    // refinement iterations).
    if (data.build_id && data.events_url) {
      let pollAborted = false;
      const sseCompletion = waitForBuildSSE(data.build_id);
      const pollCompletion = waitForBuildComplete(data.build_id, data.project_id || projectId, 120000, {
        shouldAbort: () => pollAborted,
      });
      const completed = await firstBuildCompletion([sseCompletion, pollCompletion], {
        onWinner: () => { pollAborted = true; },
      });
      const resolvedProjectId = completed?.project_id || data.project_id || projectId;
      if (resolvedProjectId) {
        const detailData = await api.getProject(resolvedProjectId);
        const project = detailData.project;
        // For refinements, the backend may return a list of changed files
        // in the project record. Also accept files from the build result or SSE complete payload.
        const files = project?.files || completed?.files || data.files || [];
        return { ...data, complete: completed, project, files };
      }
    }

    // Fallback: if the response already has a project (sync mode), fetch details
    if (data.project?.id) {
      const detailData = await api.getProject(data.project.id);
      return { ...data, project: detailData.project || data.project, files: detailData.project?.files || data.files || [] };
    }
    return data;
  } catch (error) {
    console.warn('Backend generation unavailable:', error);
    return null;
  }
}

async function firstBuildCompletion(waiters, options = {}) {
  return api.firstBuildCompletion(waiters, options);
}

function normalizeBuildCompletion(raw, buildId) {
  // Keep this renderer wrapper for smoke harness globals; API parsing lives in api-client.js.
  return api.normalizeBuildCompletion(raw, buildId);
}

function waitForBuildSSE(buildId, maxWaitMs = 120000) {
  return api.waitForBuildSSE(buildId, {
    maxWaitMs,
    onStage: handleBuildStageEvent,
    onComplete: (normalized) => { state.lastComplete = normalized; },
  });
}

async function waitForBuildComplete(buildId, projectId, maxWaitMs = 120000, options = {}) {
  const completed = await api.waitForBuildComplete(buildId, projectId, {
    maxWaitMs,
    shouldAbort: options.shouldAbort,
    getLastComplete: () => state.lastComplete,
    sleep,
  });
  if (!completed) console.warn(`Build ${buildId} did not complete within ${maxWaitMs}ms`);
  return completed;
}

function projectIdFromJob(job) {
  return api.projectIdFromJob(job);
}

async function refineProject(projectId, refinement) {
 try {
 const data = await api.refineProject({ project_id: projectId, refinement, quality: state.buildIntent?.quality || 'Balanced' });
 if (!data.ok) throw new Error(data.error || 'Refinement failed');
 return data;
 } catch (error) {
 console.warn('Backend refinement unavailable:', error);
 return null;
 }
}

async function refreshSetup() {
  try {
    const health = await api.getHealth();
    state.setup.backend = health.ok ? 'ready' : 'starting';
  } catch (_error) {
    state.setup.backend = 'starting';
  }
  if (window.robloxAIStudio?.checkSetup) {
    const setup = await window.robloxAIStudio.checkSetup();
    state.setup.hermes = setup.hermes?.ok ? 'ready' : (setup.hermes?.installing ? 'starting' : 'missing');
    state.setup.rojo = setup.rojo?.ok ? 'ready' : 'missing';
    state.setup.studio = setup.studio?.ok ? 'ready' : 'missing';
  }
  render();
}


async function refreshCapabilities() {
  try {
    const data = await api.getDesktopCapabilities();
    if (data?.ok) {
      state.capabilities = data;
      const skills = data.roblox_skills || [];
      if (skills.length && !skills.find(skill => skill.id === state.selectedSkill)) state.selectedSkill = skills[0].id;
      const modes = data.quality_modes || [];
      if (modes.length && !modes.find(mode => mode.id === state.qualityMode)) state.qualityMode = modes[0].id;
      const packs = data.skill_packs || [];
      const skillIds = new Set(skills.map(skill => skill.id));
      const modeIds = new Set(modes.map(mode => mode.id));
      if (packs.length && !findSkillPackForSelection(state.selectedSkill, state.qualityMode)) {
        const fallback = packs.find(pack => pack.default) || packs[0];
        if (skillIds.has(fallback.skill_id) && modeIds.has(fallback.quality_mode)) applySkillPack(fallback.id);
      }
    }
  } catch (_error) {
    state.capabilities = state.capabilities || {
      ok: true,
      capabilities: {},
      roblox_skills: defaultRobloxSkills(),
      quality_modes: defaultQualityModes(),
      skill_packs: defaultSkillPacks(),
      default_skill_pack: 'first-build'
    };
  }
  render();
}

function skillWorks(skill) {
  return skill?.usable !== false;
}

function friendlySkillStatus(skill) {
  if (!skillWorks(skill)) return { label: 'Coming soon', class: 'status-soon' };
  return { label: 'Works now', class: 'status-ready' };
}

function friendlyCapabilityStatus(status) {
  const raw = String(status || 'prototype').toLowerCase();
  if (raw === 'live') return { label: 'Works now', class: 'status-ready' };
  if (raw.includes('planned') && !raw.includes('prototype')) return { label: 'Coming soon', class: 'status-soon' };
  return { label: 'Beta', class: 'status-beta' };
}

function friendlyStageLabel(stage) {
  const map = {
    Plan: 'Planning',
    Generate: 'Writing game code',
    Validate: 'Checking code',
    Handoff: 'Studio files',
    Package: 'Rojo package',
    Remember: 'Memory',
    Mobile: 'Phone builds',
    Assets: 'Art and media'
  };
  return map[stage] || stage || 'Build step';
}

function friendlyBucketLabel(bucket) {
  const map = { core: 'Main Playro skill', toolbox: 'Extra tool', conditional: 'Special unlock' };
  return map[bucket] || bucket;
}

function qualitySpeedHint(id) {
  const map = {
    fast_draft: 'Fastest — good for quick tests',
    balanced: 'Best for most games',
    high_quality: 'Slowest — more detail and checks'
  };
  return map[id] || 'Balanced default';
}

function setupStatusLabel(status) {
  if (status === 'ready') return 'Ready';
  if (status === 'missing') return 'Missing';
  if (status === 'starting') return 'Starting';
  return 'Check';
}

function setupStatusClass(status) {
  if (status === 'ready') return 'ready';
  if (status === 'missing') return 'missing';
  if (status === 'starting') return 'starting';
  return 'unknown';
}

function friendlySetupDisplayStatus(key, status) {
  if (status === 'ready') return { label: 'Ready', klass: 'ready' };
  if (key === 'rojo' && canBuildLocally() && status !== 'ready') {
    return { label: 'Optional', klass: 'optional' };
  }
  if (key === 'studio' && canBuildLocally() && status !== 'ready') {
    return { label: 'Later', klass: 'optional' };
  }
  return { label: setupStatusLabel(status), klass: setupStatusClass(status) };
}

function openCapabilitiesPanel() {
  panelState.setActivePanel('capabilities');
  refreshCapabilities();
}

function defaultRobloxSkills() {
  return [
    { id: 'playro-game-designer', name: 'Game Designer', stage: 'Plan', description: 'Turns any Roblox idea into a core loop, mechanics, progression, world plan, and build steps.', usable: true, bucket: 'core' },
    { id: 'playro-luau-coder', name: 'Luau Coder', stage: 'Generate', description: 'Writes server, client, and shared Luau for custom Roblox mechanics from the prompt.', usable: true, bucket: 'core' },
    { id: 'playro-world-builder', name: 'World Builder', stage: 'Generate', description: 'Creates prototype worlds, interaction pads, NPC spaces, vehicles, arenas, hubs, and themed layouts.', usable: true, bucket: 'core' },
    { id: 'playro-systems-builder', name: 'Systems Builder', stage: 'Generate', description: 'Builds economies, quests, combat, reputation, pets, rounds, teams, inventory, and progression systems.', usable: true, bucket: 'core' },
    { id: 'playro-playtest-fixer', name: 'Playtest Fixer', stage: 'Validate', description: 'Checks generated scripts for missing services, unsafe remotes, broken config references, and mechanic gaps.', usable: true, bucket: 'toolbox' },
    { id: 'playro-rojo-packager', name: 'Rojo Packager', stage: 'Handoff', description: 'Checks default.project.json, generated folders, README, and Studio sync instructions.', usable: true, bucket: 'toolbox' }
  ];
}

function getSelectedSkillName() {
  const skill = (state.capabilities?.roblox_skills || defaultRobloxSkills()).find(item => item.id === state.selectedSkill);
  return skill?.name || 'Roblox build skill';
}

function defaultQualityModes() {
  return [
    { id: 'fast_draft', label: 'Fast draft', description: 'Quick starter project with simple systems.' },
    { id: 'balanced', label: 'Balanced', description: 'Good default for playable prototypes.' },
    { id: 'high_quality', label: 'High quality', description: 'Deeper planning, more validation, better polish.' }
  ];
}

function defaultSkillPacks() {
  return [
    { id: 'first-build', label: 'First build', description: 'Best default for any new game idea: plan the loop, then generate a playable prototype.', skill_id: 'playro-game-designer', quality_mode: 'balanced', default: true },
    { id: 'quick-start', label: 'Quick start', description: 'Fast draft when you want something playable sooner with lighter systems.', skill_id: 'playro-game-designer', quality_mode: 'fast_draft', default: false },
    { id: 'polished', label: 'Polished prototype', description: 'More planning, validation, and polish before files are written.', skill_id: 'playro-game-designer', quality_mode: 'high_quality', default: false },
    { id: 'big-systems', label: 'Systems focus', description: 'Economies, quests, combat, pets, rounds, inventory, and progression systems.', skill_id: 'playro-systems-builder', quality_mode: 'balanced', default: false },
    { id: 'worlds', label: 'World focus', description: 'Hubs, arenas, maps, NPC spaces, vehicles, pads, and themed layouts.', skill_id: 'playro-world-builder', quality_mode: 'balanced', default: false },
    { id: 'scripts', label: 'Luau focus', description: 'Server, client, and shared scripts for custom mechanics from your prompt.', skill_id: 'playro-luau-coder', quality_mode: 'balanced', default: false },
    { id: 'fix-build', label: 'Fix & validate', description: 'Check generated scripts for broken references, unsafe remotes, and mechanic gaps.', skill_id: 'playro-playtest-fixer', quality_mode: 'balanced', default: false }
  ];
}

function getSkillPacks() {
  return state.capabilities?.skill_packs || defaultSkillPacks();
}

function findSkillPackForSelection(skillId, qualityMode) {
  return getSkillPacks().find(pack => pack.skill_id === skillId && pack.quality_mode === qualityMode) || null;
}

function applySkillPack(packId) {
  const pack = getSkillPacks().find(item => item.id === packId);
  if (!pack) return;
  state.selectedSkill = pack.skill_id;
  state.qualityMode = pack.quality_mode;
  const mode = (state.capabilities?.quality_modes || defaultQualityModes()).find(item => item.id === state.qualityMode);
  state.buildIntent.quality = mode?.label || 'Balanced';
}

function defaultMemoryPreview() {
  return [
    { title: 'Prompt pattern', summary: 'Game intent, mechanics, world theme, and core loop are recorded per project.' },
    { title: 'System pattern', summary: 'Generated quests, NPCs, vehicles, economies, combat, shops, bosses, and UI choices are reusable.' },
    { title: 'Artifact checklist', summary: 'Rojo mapping, Luau files, README, and validation output stay attached to the build.' }
  ];
}

function applyPlayroSetupProgress(payload) {
  if (!payload) return;
  const log = payload.log || payload.detail;
  state.playroSetup = {
    ...state.playroSetup,
    open: true,
    started: true,
    status: payload.status || state.playroSetup.status || 'running',
    percent: payload.percent ?? state.playroSetup.percent,
    step: payload.step ?? state.playroSetup.step,
    totalSteps: payload.totalSteps ?? state.playroSetup.totalSteps,
    title: payload.title || state.playroSetup.title,
    stepLabel: payload.stepLabel || state.playroSetup.stepLabel,
    detail: payload.detail || state.playroSetup.detail,
    logs: log ? [...(state.playroSetup.logs || []), log].slice(-120) : (state.playroSetup.logs || [])
  };
  render();
}

async function installHermesRuntime() {
  if (!window.robloxAIStudio?.installHermesRuntime) return toast('Playro AI engine installer is unavailable in this build.');
  state.installingHermes = true;
  state.hermesInstaller = { open: true, status: 'running', percent: 14, step: 1, totalSteps: 7, title: 'Installing Playro AI engine', stepLabel: 'Step 1/7: Starting installation...', detail: 'Installing the Playro AI engine...', logs: ['Installing the Playro AI engine...'] };
  render();
  try {
    const result = await window.robloxAIStudio.installHermesRuntime();
    if (result?.ok) {
      if (result.already_installed) {
        state.hermesInstaller = { ...state.hermesInstaller, open: true, status: 'complete', percent: 100, step: 7, totalSteps: 7, title: 'Playro AI engine already installed', stepLabel: 'Step 7/7: Finishing setup...', detail: 'Playro AI engine is ready.', logs: ['Playro AI engine already installed.'] };
        render();
      } else {
        state.hermesInstaller = { ...state.hermesInstaller, open: true, status: 'complete', percent: 100, step: 7, totalSteps: 7, title: 'Playro AI engine installed', stepLabel: 'Step 7/7: Finishing setup...', detail: 'Playro AI engine is ready.', logs: [...(state.hermesInstaller.logs || []), 'Playro AI engine installed.'] };
        render();
      }
      toast('Playro AI engine is installed.');
    } else {
      const error = result?.error || 'Playro AI engine install could not start.';
      state.hermesInstaller = { ...state.hermesInstaller, open: true, status: 'failed', title: 'Playro AI engine install failed', detail: error, logs: [...(state.hermesInstaller.logs || []), error] };
      render();
      toast(result?.error || 'Playro AI engine install could not start.');
    }
  } catch (error) {
    toast(`Playro AI engine install failed: ${error.message}`);
  } finally {
    state.installingHermes = false;
    await refreshSetup();
  }
}

async function handleAction(action) {
  const project = state.currentProject;
  if (action === 'close-installer') {
    state.hermesInstaller.open = false;
    render();
    return;
  }
  if (action === 'open-rojo-docs') {
    await window.robloxAIStudio?.openExternal?.('https://rojo.space/docs/v7/getting-started/installation/');
    return;
  }
  if (action === 'open-studio-download') {
    await window.robloxAIStudio?.openExternal?.('https://create.roblox.com/');
    return;
  }
  if (action === 'install-hermes-runtime') return installHermesRuntime();
  if (action === 'install-rojo') {
    state.installingRojo = true;
    render();
    const result = await window.robloxAIStudio?.installRojo?.();
    state.installingRojo = false;
    if (result?.ok) {
      toast('Rojo installed. Setup checks refreshed.');
    } else {
      await copyText('winget install --id Rojo.Rojo --exact');
      toast(result?.error || 'Auto install failed. Rojo command copied.');
      await window.robloxAIStudio?.openExternal?.('https://rojo.space/docs/v7/getting-started/installation/');
    }
    await refreshSetup();
    await refreshCapabilities();
    return;
  }
  if (action === 'copy-rojo-install') {
    await copyText('Playro installs Rojo through trusted package managers. Windows fallback: winget install --id Rojo.Rojo --exact. macOS/Linux fallback: cargo install rojo --version 7.6.1 --locked');
    toast('Rojo install command copied.');
    return;
  }
  if (action === 'copy-luau') {
    await copyText(state.lastCode || '');
    toast('Luau copied.');
    return;
  }
  if (!project) {
    toast('No real generated project yet. Build with the desktop backend running.');
    return;
  }
  if (action === 'open-folder') {
    const result = await window.robloxAIStudio?.openProjectFolder?.(project.project_path);
    toast(result?.ok ? 'Project folder opened.' : (result?.error || 'Could not open folder.'));
    return;
  }
  if (action === 'open-studio') {
    const result = await window.robloxAIStudio?.openRojoProject?.(project.rojo_project);
    if (result?.rojo?.ok && result?.studio?.ok) {
      toast('Rojo server started and Roblox Studio launched. Use the Rojo plugin to connect.');
    } else if (result?.rojo?.ok) {
      toast('Rojo server started. Studio not detected; .rbxlx fallback command copied.');
    } else {
      toast('Folder opened. Rojo live-sync and .rbxlx fallback commands copied.');
    }
    await refreshSetup();
    return;
  }
  if (action === 'export-rojo') {
    try {
      const data = await api.exportProject(project.id);
      if (!data.ok) throw new Error(data.error || 'Export failed');
      await window.robloxAIStudio?.openPath?.(data.bundle_path);
      toast('Rojo export bundle created.');
    } catch (error) {
      toast(error.message || 'Could not export project.');
    }
  }
}

async function copyText(text) {
  if (window.robloxAIStudio?.copyText) return window.robloxAIStudio.copyText(text);
  return navigator.clipboard?.writeText(text);
}

function fallbackConfig(projectName, genre) {
  return `-- GameConfig.lua\nlocal GameConfig = {\n  title = "${projectName}",\n  genre = "${genre}",\n  systems = { "Economy", "Progression", "Bosses", "Rewards" },\n}\n\nreturn GameConfig`;
}

async function addStep(title, text, nextStage) {
 await sleep(520);
 state.conversation.push({ role: 'ai', title, text });
 if (nextStage) state.buildStage = nextStage;
 render();
}

function handleBuildStageEvent(event) {
  try {
    const data = JSON.parse(event.data);
    const stageMap = { idea: 'idea', plan: 'plan', luau: 'luau', handoff: 'handoff', complete: 'complete', error: 'error' };
    if (data.stage && stageMap[data.stage]) {
      state.buildStage = stageMap[data.stage];
    }
    if (data.title || data.message || data.detail) {
      const lastMsg = state.conversation[state.conversation.length - 1];
      if (!(lastMsg && lastMsg.role === 'ai' && lastMsg.title === data.title)) {
        state.conversation.push({ role: 'ai', title: data.title || data.stage, text: data.message || data.detail || '' });
      }
    }
    render({ mode: 'main' });
  } catch (_e) { /* ignore malformed SSE data */ }
}

function inferBuildIntent(prompt) {
  const p = prompt.toLowerCase();
  const systems = [];
  if (p.includes('coin') || p.includes('cash') || p.includes('money')) systems.push('Economy');
  if (p.includes('pet')) systems.push('Pets');
  if (p.includes('boss')) systems.push('Bosses');
  if (p.includes('upgrade') || p.includes('shop')) systems.push('Upgrades');
  if (p.includes('wave') || p.includes('enemy')) systems.push('Enemy waves');
  if (p.includes('checkpoint')) systems.push('Checkpoints');
  return {
    genre: inferGenre(prompt),
    systems: systems.length ? systems : ['Economy', 'Progression'],
    quality: p.includes('polish') || p.includes('premium') ? 'High polish' : 'Balanced'
  };
}

function inferGenre(prompt) {
  const p = prompt.toLowerCase();
  if (p.includes('tower')) return 'Tower Defense';
  if (p.includes('tycoon')) return 'Tycoon';
  if (p.includes('simulator')) return 'Simulator';
  if (p.includes('rpg') || p.includes('quest')) return 'RPG';
  if (p.includes('racing') || p.includes('lap')) return 'Racing';
  if (p.includes('obby') || p.includes('parkour')) return 'Obby';
  return 'Custom Roblox Experience';
}

function inferProjectName(prompt) {
  const ignored = new Set(['make','with','and','the','for','game','roblox','create','build']);
  const words = prompt.split(/\s+/).map(w => w.replace(/[^a-z0-9]/gi, '')).filter(w => w.length > 2 && !ignored.has(w.toLowerCase()));
  return words.slice(0, 3).map(w => w[0].toUpperCase() + w.slice(1).toLowerCase()).join(' ') || 'New Roblox Game';
}

function genreIcon(genre) {
  return ({ 'Tower Defense': '🏰', Tycoon: '🏭', Simulator: '🐾', RPG: '⚔️', Racing: '🏎️', Obby: '🏃', Adventure: '✨' })[genre] || '✨';
}

function scrollThreadToBottom() {
  const thread = document.getElementById('thread');
  if (thread) thread.scrollTop = thread.scrollHeight;
}

function toast(text) {
  document.querySelector('.toast')?.remove();
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function escapeHTML(value) { return String(value || '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c])); }
function formatBytes(bytes) { if (!bytes || bytes <= 0) return '0 B'; const units = ['B','KB','MB','GB']; const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1); return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`; }

async function openBuildDetail(projectId) {
 if (!projectId) return toast('No build ID to inspect.');
 panelState.setActivePanel('buildDetail');
 state.buildDetailProjectId = projectId;
 state.buildDetail = null;
 state.buildDetailLoading = true;
 renderShellAndOverlays();
 await fetchProjectDetail(projectId);
}

function closeBuildDetail() {
  panelState.setActivePanel(null);
  state.buildDetailProjectId = null;
  state.buildDetail = null;
  state.buildDetailLoading = false;
  renderOverlaysOnly();
}

async function fetchProjectDetail(projectId) {
  state.buildDetailLoading = true;
  renderOverlaysOnly();
  try {
    const data = await api.getProject(projectId);
    if (data.ok && data.project) {
      state.buildDetail = data.project;
    } else {
      state.buildDetail = null;
    }
  } catch (_error) {
    state.buildDetail = null;
  }
  state.buildDetailLoading = false;
  renderOverlaysOnly();
}

async function exportRojoZIP(projectId) {
  if (!projectId) return toast('No project to export.');
  try {
    const data = await api.exportProject(projectId);
    if (!data.ok) throw new Error(data.error || 'Export failed');
    await window.robloxAIStudio?.openPath?.(data.bundle_path);
    toast('Rojo export bundle created.');
  } catch (error) {
    toast(error.message || 'Could not export project.');
  }
}

async function boot() {
  window.robloxAIStudio?.onPlayroSetupProgress?.(applyPlayroSetupProgress);
  window.robloxAIStudio?.onHermesInstallProgress?.(payload => {
    const log = payload?.log || payload?.detail;
    if (!log) return;
    state.hermesInstaller = {
      ...state.hermesInstaller,
      open: true,
      status: payload.status || state.hermesInstaller.status,
      percent: payload.percent ?? state.hermesInstaller.percent,
      step: payload.step ?? state.hermesInstaller.step,
      totalSteps: payload.totalSteps ?? state.hermesInstaller.totalSteps,
      title: payload.title || state.hermesInstaller.title,
      stepLabel: payload.stepLabel || state.hermesInstaller.stepLabel,
      detail: payload.detail || state.hermesInstaller.detail,
      logs: [...(state.hermesInstaller.logs || []), log].slice(-120)
    };
    if (!isSetupRoute()) render();
  });
  if (window.robloxAIStudio?.apiBase) {
    try { state.apiBase = await window.robloxAIStudio.apiBase(); } catch (_error) {}
    try { state.apiToken = await window.robloxAIStudio.apiAuthToken?.() || ''; } catch (_error) {}
    syncApiClientConfig();
  }
  render();
  await refreshSetup();
}

boot();
