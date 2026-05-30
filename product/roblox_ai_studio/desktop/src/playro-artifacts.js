/**
 * Canonical Playro artifact paths (keep in sync with app/artifacts.py).
 */
(function (root) {
  const PLAYRO_CORE_ARTIFACT_FILES = Object.freeze([
    'default.project.json',
    'manifest.json',
    'game_plan.md',
    'README.md',
    'wally.toml',
    'src/ReplicatedStorage/GameConfig.lua',
    'src/ServerScriptService/Main.server.lua',
    'src/ServerScriptService/Services/PlayerDataService.lua',
    'src/ServerScriptService/Services/RewardService.lua',
    'src/ServerScriptService/Services/WorldService.lua',
    'src/StarterPlayer/StarterPlayerScripts/HUD.client.lua',
  ]);

  const PLAYRO_HANDOFF_ARTIFACT_FILES = Object.freeze(
    PLAYRO_CORE_ARTIFACT_FILES.filter(
      (file) => file.endsWith('.lua') || file === 'default.project.json' || file === 'manifest.json' || file === 'game_plan.md'
    )
  );

  const PLAYRO_SERVER_MAIN = 'src/ServerScriptService/Main.server.lua';
  const PLAYRO_SHARED_CONFIG = 'src/ReplicatedStorage/GameConfig.lua';
  const PLAYRO_CLIENT_HUD = 'src/StarterPlayer/StarterPlayerScripts/HUD.client.lua';

  root.PLAYRO_CORE_ARTIFACT_FILES = PLAYRO_CORE_ARTIFACT_FILES;
  root.PLAYRO_HANDOFF_ARTIFACT_FILES = PLAYRO_HANDOFF_ARTIFACT_FILES;
  root.PLAYRO_SERVER_MAIN = PLAYRO_SERVER_MAIN;
  root.PLAYRO_SHARED_CONFIG = PLAYRO_SHARED_CONFIG;
  root.PLAYRO_CLIENT_HUD = PLAYRO_CLIENT_HUD;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      PLAYRO_CORE_ARTIFACT_FILES,
      PLAYRO_HANDOFF_ARTIFACT_FILES,
      PLAYRO_SERVER_MAIN,
      PLAYRO_SHARED_CONFIG,
      PLAYRO_CLIENT_HUD,
    };
  }
})(typeof globalThis !== 'undefined' ? globalThis : window);
