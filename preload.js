// preload.js - IPC Bridge between renderer and main process
// AETHER-OS v2.2 - Full Plugin & Update Support

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('aether', {
    // ===== TOOL MANAGEMENT =====
    getToolStatus: () => ipcRenderer.invoke('get-tool-status'),
    restartTool: (name) => ipcRenderer.invoke('restart-tool', name),
    stopTool: (name) => ipcRenderer.invoke('stop-tool', name),
    
    // ===== WINDOW CONTROLS =====
    minimizeWindow: () => ipcRenderer.invoke('window-minimize'),
    maximizeWindow: () => ipcRenderer.invoke('window-maximize'),
    closeWindow: () => ipcRenderer.invoke('window-close'),
    
    // ===== SESSION =====
    saveSession: (data) => ipcRenderer.invoke('save-session', data),
    loadSession: () => ipcRenderer.invoke('load-session'),
    
    // ===== PLUGIN SYSTEM =====
    // Get installed plugins
    getInstalledPlugins: () => ipcRenderer.invoke('get-installed-plugins'),
    
    // Get available plugins from registry
    getAvailablePlugins: () => ipcRenderer.invoke('get-available-plugins'),
    
    // Download and install a plugin
    downloadPlugin: (pluginInfo) => ipcRenderer.invoke('download-plugin', pluginInfo),
    
    // Uninstall a plugin
    uninstallPlugin: (pluginId) => ipcRenderer.invoke('uninstall-plugin', pluginId),
    
    // Start a plugin
    startPlugin: (pluginId) => ipcRenderer.invoke('start-plugin', pluginId),
    
    // Install from local zip file
    installPlugin: (zipPath) => ipcRenderer.invoke('install-plugin', zipPath),
    
    // Plugin download progress
    onPluginDownloadProgress: (callback) => {
        ipcRenderer.on('plugin-download-progress', (_, data) => callback(data));
    },
    
    // ===== PC APPS =====
    getPcApps: () => ipcRenderer.invoke('get-pc-apps'),
    launchPcApp: (path, args) => ipcRenderer.invoke('launch-pc-app', path, args),
    
    // ===== AUTO-UPDATE =====
    checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
    downloadUpdate: (url) => ipcRenderer.invoke('download-update', url),
    getVersion: () => ipcRenderer.invoke('get-version'),
    restartApp: () => ipcRenderer.invoke('restart-app'),
    
    // ===== UTILITY =====
    openExternal: (url) => ipcRenderer.invoke('open-external', url),
    
    // ===== BOOT EVENTS =====
    onBootProgress: (callback) => {
        ipcRenderer.on('boot-progress', (_, data) => callback(data));
    },
    onBootError: (callback) => {
        ipcRenderer.on('boot-error', (_, data) => callback(data));
    },
    onToolReady: (callback) => {
        ipcRenderer.on('tool-ready', (_, data) => callback(data));
    },
    onToolStopped: (callback) => {
        ipcRenderer.on('tool-stopped', (_, data) => callback(data));
    },
    onToolOutput: (callback) => {
        ipcRenderer.on('tool-output', (_, data) => callback(data));
    }
});
