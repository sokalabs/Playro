(function initPlayroPanelState(root) {
  'use strict';

  const SIDEBAR_PANEL_TO_OVERLAY = {
    sessions: 'buildHistory',
    skills: 'capabilities',
    build24: 'buildMode',
    config: 'settings',
    analytics: 'buildAnalytics',
    logs: 'buildLogs',
    keys: 'keys',
    models: 'qualityRouting',
    plugins: 'adapters',
    crews: 'crews',
  };

  function createPlayroPanelState(state, options = {}) {
    const sidebarPanelToOverlay = options.sidebarPanelToOverlay || SIDEBAR_PANEL_TO_OVERLAY;

    function isPanelActive(panel) {
      return state.activePanel === panel;
    }

    function setActivePanel(panel) {
      state.activePanel = panel || null;
      if (state.activePanel !== 'parity') state.activeParityPanel = null;
    }

    function getOverlayPanelForSidebar(panel) {
      return sidebarPanelToOverlay[panel] || 'parity';
    }

    function setActiveParityPanel(panel) {
      state.activeParityPanel = panel || null;
    }

    function isSidebarItemActive(item) {
      if (item.id === 'build') return !state.activePanel;
      const mappedPanel = sidebarPanelToOverlay[item.id];
      if (mappedPanel) return isPanelActive(mappedPanel);
      return isPanelActive('parity') && state.activeParityPanel === item.id;
    }

    return {
      getOverlayPanelForSidebar,
      isPanelActive,
      isSidebarItemActive,
      setActivePanel,
      setActiveParityPanel,
      sidebarPanelToOverlay,
    };
  }

  const panelState = {
    create: createPlayroPanelState,
    SIDEBAR_PANEL_TO_OVERLAY,
  };
  root.PlayroPanelState = panelState;
  if (root.window) root.window.PlayroPanelState = panelState;
  if (typeof module !== 'undefined' && module.exports) module.exports = panelState;
})(typeof globalThis !== 'undefined' ? globalThis : window);
