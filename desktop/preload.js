const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('novelflowDesktop', {
  isDesktop: true,
  platform: process.platform,
  getVersion: () => ipcRenderer.invoke('novelflow:get-version'),
  selectFolder: () => ipcRenderer.invoke('novelflow:select-folder'),
  checkForUpdates: () => ipcRenderer.invoke('novelflow:check-for-updates'),
  downloadUpdate: () => ipcRenderer.invoke('novelflow:download-update'),
  quitAndInstall: () => ipcRenderer.invoke('novelflow:quit-and-install'),
  openExternal: (url) => ipcRenderer.invoke('novelflow:open-external', url),
  onUpdateStatus: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on('novelflow:update-status', handler)
    return () => ipcRenderer.removeListener('novelflow:update-status', handler)
  },
})
