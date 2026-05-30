const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('robloxAIStudio', {
  apiBase: () => ipcRenderer.invoke('api-base'),
  apiAuthToken: () => ipcRenderer.invoke('api-auth-token'),
  openPath: targetPath => ipcRenderer.invoke('open-path', targetPath),
  openProjectFolder: projectPath => ipcRenderer.invoke('open-project-folder', projectPath),
  openRojoProject: rojoProjectPath => ipcRenderer.invoke('open-rojo-project', rojoProjectPath),
  checkSetup: () => ipcRenderer.invoke('check-setup'),
  installHermesRuntime: () => ipcRenderer.invoke('install-hermes-runtime'),
  promptInstallHermesRuntime: () => ipcRenderer.invoke('prompt-install-hermes-runtime'),
  onHermesInstallProgress: callback => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on('hermes-install-progress', handler);
    return () => ipcRenderer.removeListener('hermes-install-progress', handler);
  },
  onPlayroSetupProgress: callback => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on('playro-setup-progress', handler);
    return () => ipcRenderer.removeListener('playro-setup-progress', handler);
  },
  startFullSetup: () => ipcRenderer.invoke('start-full-setup'),
  skipPlayroSetup: () => ipcRenderer.invoke('skip-playro-setup'),
  installRojo: () => ipcRenderer.invoke('install-rojo'),
  openExternal: url => ipcRenderer.invoke('open-external', url),
  copyText: text => ipcRenderer.invoke('copy-text', text)
});
