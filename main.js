// main.js - AETHER-OS Electron Main Process v2.2
// With working auto-updates, plugin marketplace, and proper boot sequence

const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');
const http = require('http');

// Determine if we're running in a packaged app
const isPackaged = app.isPackaged;

// Get the correct base paths
const APP_ROOT = isPackaged ? path.dirname(app.getPath('exe')) : __dirname;
const RESOURCES_PATH = isPackaged ? process.resourcesPath : __dirname;
const USER_DATA = app.getPath('userData');

// Tools location varies based on packaged vs dev
const TOOLS_PATH = isPackaged 
    ? path.join(RESOURCES_PATH, 'tools')
    : path.join(__dirname, 'src', 'tools');

// Plugins go in userData for both dev and packaged (user-writable)
const PLUGINS_PATH = path.join(USER_DATA, 'plugins');

// Data goes in userData for packaged apps
const DATA_PATH = isPackaged ? USER_DATA : __dirname;

console.log('[AETHER] Paths:');
console.log(`  App Root: ${APP_ROOT}`);
console.log(`  Resources: ${RESOURCES_PATH}`);
console.log(`  Tools: ${TOOLS_PATH}`);
console.log(`  Plugins: ${PLUGINS_PATH}`);
console.log(`  User Data: ${DATA_PATH}`);
console.log(`  Packaged: ${isPackaged}`);

// Ensure plugins directory exists
if (!fs.existsSync(PLUGINS_PATH)) {
    fs.mkdirSync(PLUGINS_PATH, { recursive: true });
}

const SystemOrchestrator = require('./src/orchestrator/SystemOrchestrator');

let mainWindow;
let orchestrator;

// Dev mode check
const isDev = process.argv.includes('--dev') || process.env.NODE_ENV === 'development';

// GitHub repo info for updates
const GITHUB_OWNER = 'AetherO-S';
const GITHUB_REPO = 'AetherOS';
const UPDATE_CHECK_URL = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`;

// Plugin repository URL
const PLUGIN_REPO_URL = `https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/main/plugin-registry.json`;

async function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        frame: false,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        backgroundColor: '#0a0a0a',
        show: false
    });

    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        mainWindow.maximize();
    });

    // Load the loading screen first
    mainWindow.loadFile('src/renderer/loading.html');
    
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    // Wait for the page to be fully loaded
    await new Promise((resolve) => {
        mainWindow.webContents.once('did-finish-load', resolve);
    });
}

async function bootSystem() {
    // Create orchestrator with proper paths
    orchestrator = new SystemOrchestrator(DATA_PATH, {
        toolsPath: TOOLS_PATH,
        pluginsPath: PLUGINS_PATH,
        isPackaged: isPackaged
    });

    // Forward all orchestrator events to the renderer
    orchestrator.on('progress', (data) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('boot-progress', data);
        }
        console.log(`[${data.stage}] ${data.message} (${data.percent}%)`);
    });

    orchestrator.on('error', (data) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('boot-error', data);
        }
        console.error(`[ERROR] ${data.message}`, data.details || '');
    });

    orchestrator.on('tool-ready', (data) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('tool-ready', data);
        }
        console.log(`[TOOL READY] ${data.tool} on port ${data.port}`);
    });

    orchestrator.on('tool-output', (data) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('tool-output', data);
        }
    });

    orchestrator.on('tool-stopped', (data) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('tool-stopped', data);
        }
        console.log(`[TOOL STOPPED] ${data.tool}`);
    });

    // Start the boot sequence
    const result = await orchestrator.boot();

    if (result.success) {
        console.log('Boot sequence completed successfully');
        setTimeout(() => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.loadFile('src/renderer/index.html');
            }
        }, 1500);
    } else {
        console.error('Boot sequence failed:', result.error);
    }

    return result;
}

// ===== HTTP/HTTPS Helper =====
function fetchUrl(url, options = {}) {
    return new Promise((resolve, reject) => {
        const protocol = url.startsWith('https') ? https : http;
        const req = protocol.get(url, {
            headers: {
                'User-Agent': 'AETHER-OS-Updater/2.2',
                ...options.headers
            }
        }, (res) => {
            // Handle redirects
            if (res.statusCode === 301 || res.statusCode === 302 || res.statusCode === 307) {
                fetchUrl(res.headers.location, options).then(resolve).catch(reject);
                return;
            }
            
            if (res.statusCode !== 200) {
                reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
                return;
            }
            
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                if (options.json) {
                    try {
                        resolve(JSON.parse(data));
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                } else {
                    resolve(data);
                }
            });
        });
        
        req.on('error', reject);
        req.setTimeout(15000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
    });
}

function downloadFile(url, destPath) {
    return new Promise((resolve, reject) => {
        const protocol = url.startsWith('https') ? https : http;
        const file = fs.createWriteStream(destPath);
        
        const req = protocol.get(url, {
            headers: { 'User-Agent': 'AETHER-OS-Updater/2.2' }
        }, (res) => {
            if (res.statusCode === 301 || res.statusCode === 302 || res.statusCode === 307) {
                file.close();
                fs.unlinkSync(destPath);
                downloadFile(res.headers.location, destPath).then(resolve).catch(reject);
                return;
            }
            
            if (res.statusCode !== 200) {
                file.close();
                fs.unlinkSync(destPath);
                reject(new Error(`HTTP ${res.statusCode}`));
                return;
            }
            
            res.pipe(file);
            file.on('finish', () => {
                file.close();
                resolve(destPath);
            });
        });
        
        req.on('error', (err) => {
            file.close();
            fs.unlink(destPath, () => {});
            reject(err);
        });
    });
}

// ===== IPC Handlers =====
ipcMain.handle('get-tool-status', () => {
    return orchestrator?.getStatus() || {};
});

ipcMain.handle('restart-tool', async (event, toolName) => {
    if (orchestrator) {
        await orchestrator.stopTool(toolName);
        return await orchestrator.spawnTool(toolName);
    }
    return { success: false, error: 'Orchestrator not initialized' };
});

ipcMain.handle('stop-tool', async (event, toolName) => {
    if (orchestrator) {
        await orchestrator.stopTool(toolName);
        return { success: true };
    }
    return { success: false, error: 'Orchestrator not initialized' };
});

// Window controls
ipcMain.handle('window-minimize', () => {
    if (mainWindow) mainWindow.minimize();
});

ipcMain.handle('window-maximize', () => {
    if (mainWindow) {
        if (mainWindow.isMaximized()) {
            mainWindow.unmaximize();
        } else {
            mainWindow.maximize();
        }
    }
});

ipcMain.handle('window-close', async () => {
    if (orchestrator) {
        await orchestrator.shutdown();
    }
    app.quit();
});

// Session handling
ipcMain.handle('save-session', async (event, data) => {
    const sessionPath = path.join(USER_DATA, 'session.json');
    try {
        fs.writeFileSync(sessionPath, JSON.stringify(data, null, 2));
        return { success: true };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

ipcMain.handle('load-session', async () => {
    const sessionPath = path.join(USER_DATA, 'session.json');
    try {
        if (fs.existsSync(sessionPath)) {
            return JSON.parse(fs.readFileSync(sessionPath, 'utf8'));
        }
    } catch (err) {
        console.error('Error loading session:', err);
    }
    return null;
});

// ===== PLUGIN SYSTEM =====

// Get list of installed plugins
ipcMain.handle('get-installed-plugins', async () => {
    const plugins = [];
    
    try {
        if (!fs.existsSync(PLUGINS_PATH)) {
            return plugins;
        }
        
        const dirs = fs.readdirSync(PLUGINS_PATH, { withFileTypes: true })
            .filter(d => d.isDirectory())
            .map(d => d.name);
        
        for (const dir of dirs) {
            const configPath = path.join(PLUGINS_PATH, dir, 'plugin.json');
            if (fs.existsSync(configPath)) {
                try {
                    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
                    const status = orchestrator?.getStatus()?.[config.name || dir];
                    plugins.push({
                        ...config,
                        id: config.name || dir,
                        installed: true,
                        running: status?.running || false,
                        port: status?.port || config.port
                    });
                } catch (e) {
                    console.error(`Failed to load plugin ${dir}:`, e.message);
                }
            }
        }
    } catch (err) {
        console.error('Error getting plugins:', err);
    }
    
    return plugins;
});

// Get available plugins from registry
ipcMain.handle('get-available-plugins', async () => {
    try {
        // Try to fetch from GitHub registry
        const registry = await fetchUrl(PLUGIN_REPO_URL, { json: true });
        return registry.plugins || [];
    } catch (err) {
        console.log('Could not fetch plugin registry:', err.message);
        // Return built-in available plugins list
        return [
            {
                id: 'viral_studio',
                name: 'viral_studio',
                displayName: 'Viral Video Studio',
                description: 'AI-powered short-form video creation with stock footage, voice synthesis, and automatic captions',
                version: '1.0.0',
                author: 'AETHER-OS Team',
                category: 'ai',
                icon: '🎬',
                downloadUrl: `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/download/plugins/viral_studio.zip`,
                size: '2.5 MB'
            },
            {
                id: 'web_browser',
                name: 'web_browser',
                displayName: 'Web Browser',
                description: 'Built-in web browser with tab support',
                version: '1.0.0',
                author: 'AETHER-OS Team',
                category: 'productivity',
                icon: '🌐',
                downloadUrl: `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/download/plugins/web_browser.zip`,
                size: '1.2 MB'
            }
        ];
    }
});

// Download and install a plugin
ipcMain.handle('download-plugin', async (event, pluginInfo) => {
    try {
        const { id, name, downloadUrl } = pluginInfo;
        const pluginId = id || name;
        const pluginDir = path.join(PLUGINS_PATH, pluginId);
        const zipPath = path.join(USER_DATA, `${pluginId}.zip`);
        
        // Send progress
        mainWindow.webContents.send('plugin-download-progress', { plugin: pluginId, status: 'downloading', percent: 0 });
        
        // Download the zip file
        await downloadFile(downloadUrl, zipPath);
        
        mainWindow.webContents.send('plugin-download-progress', { plugin: pluginId, status: 'extracting', percent: 50 });
        
        // Extract the zip
        const AdmZip = require('adm-zip');
        const zip = new AdmZip(zipPath);
        
        // Create plugin directory
        if (!fs.existsSync(pluginDir)) {
            fs.mkdirSync(pluginDir, { recursive: true });
        }
        
        // Find root folder in zip
        const entries = zip.getEntries();
        let rootFolder = '';
        for (const entry of entries) {
            if (entry.entryName.endsWith('plugin.json')) {
                rootFolder = path.dirname(entry.entryName);
                break;
            }
        }
        
        // Extract files
        for (const entry of entries) {
            if (entry.isDirectory) continue;
            
            let targetPath = entry.entryName;
            if (rootFolder && targetPath.startsWith(rootFolder + '/')) {
                targetPath = targetPath.slice(rootFolder.length + 1);
            } else if (rootFolder && targetPath.startsWith(rootFolder)) {
                targetPath = targetPath.slice(rootFolder.length);
            }
            
            if (!targetPath) continue;
            
            const fullPath = path.join(pluginDir, targetPath);
            const dir = path.dirname(fullPath);
            
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            
            fs.writeFileSync(fullPath, entry.getData());
        }
        
        // Clean up zip
        fs.unlinkSync(zipPath);
        
        mainWindow.webContents.send('plugin-download-progress', { plugin: pluginId, status: 'installing', percent: 75 });
        
        // Load and start the plugin via orchestrator
        if (orchestrator) {
            await orchestrator.loadPlugin(pluginId);
        }
        
        mainWindow.webContents.send('plugin-download-progress', { plugin: pluginId, status: 'complete', percent: 100 });
        
        return { success: true, plugin: pluginId };
        
    } catch (err) {
        console.error('Plugin download error:', err);
        mainWindow.webContents.send('plugin-download-progress', { plugin: pluginInfo.id, status: 'error', error: err.message });
        return { success: false, error: err.message };
    }
});

// Uninstall a plugin
ipcMain.handle('uninstall-plugin', async (event, pluginId) => {
    try {
        // Stop the plugin if running
        if (orchestrator) {
            await orchestrator.stopTool(pluginId);
            orchestrator.unloadPlugin(pluginId);
        }
        
        // Remove plugin directory
        const pluginDir = path.join(PLUGINS_PATH, pluginId);
        if (fs.existsSync(pluginDir)) {
            fs.rmSync(pluginDir, { recursive: true, force: true });
        }
        
        // Remove venv
        const venvDir = path.join(DATA_PATH, 'envs', pluginId);
        if (fs.existsSync(venvDir)) {
            fs.rmSync(venvDir, { recursive: true, force: true });
        }
        
        return { success: true };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

// Start a plugin
ipcMain.handle('start-plugin', async (event, pluginId) => {
    if (orchestrator) {
        try {
            await orchestrator.ensureToolEnvironment(pluginId);
            const result = await orchestrator.spawnTool(pluginId);
            return { success: true, ...result };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }
    return { success: false, error: 'Orchestrator not initialized' };
});

// Install plugin from file
ipcMain.handle('install-plugin', async (event, zipPath) => {
    const AdmZip = require('adm-zip');
    
    try {
        const zip = new AdmZip(zipPath);
        const entries = zip.getEntries();
        
        let pluginJson = null;
        let rootFolder = '';
        
        for (const entry of entries) {
            if (entry.entryName.endsWith('plugin.json')) {
                pluginJson = JSON.parse(entry.getData().toString('utf8'));
                rootFolder = path.dirname(entry.entryName);
                break;
            }
        }
        
        if (!pluginJson || !pluginJson.name) {
            return { success: false, error: 'Invalid plugin: missing plugin.json or name' };
        }
        
        const pluginDir = path.join(PLUGINS_PATH, pluginJson.name);
        
        if (!fs.existsSync(pluginDir)) {
            fs.mkdirSync(pluginDir, { recursive: true });
        }
        
        for (const entry of entries) {
            if (entry.isDirectory) continue;
            
            let targetPath = entry.entryName;
            if (rootFolder && targetPath.startsWith(rootFolder + '/')) {
                targetPath = targetPath.slice(rootFolder.length + 1);
            }
            
            const fullPath = path.join(pluginDir, targetPath);
            const dir = path.dirname(fullPath);
            
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            
            fs.writeFileSync(fullPath, entry.getData());
        }
        
        // Load the plugin
        if (orchestrator) {
            await orchestrator.loadPlugin(pluginJson.name);
        }
        
        return { success: true, plugin: pluginJson };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

// ===== PC APPS =====
ipcMain.handle('get-pc-apps', async () => {
    const apps = [];
    
    if (process.platform === 'win32') {
        const locations = [
            process.env.PROGRAMFILES,
            process.env['PROGRAMFILES(X86)'],
            process.env.LOCALAPPDATA
        ].filter(Boolean);
        
        const commonApps = [
            { name: 'Chrome', exe: 'Google\\Chrome\\Application\\chrome.exe', icon: '🌐' },
            { name: 'Firefox', exe: 'Mozilla Firefox\\firefox.exe', icon: '🦊' },
            { name: 'VS Code', exe: 'Microsoft VS Code\\Code.exe', icon: '💻' },
            { name: 'Discord', exe: 'Discord\\Update.exe', args: ['--processStart', 'Discord.exe'], icon: '💬' },
            { name: 'Spotify', exe: 'Spotify\\Spotify.exe', icon: '🎵' },
            { name: 'Steam', exe: 'Steam\\steam.exe', icon: '🎮' },
            { name: 'PowerShell', path: 'powershell.exe', icon: '🔷' },
            { name: 'CMD', path: 'cmd.exe', icon: '🖥️' },
            { name: 'File Explorer', path: 'explorer.exe', icon: '📁' },
            { name: 'Task Manager', path: 'taskmgr.exe', icon: '📈' },
            { name: 'Calculator', path: 'calc.exe', icon: '🔢' },
            { name: 'Notepad', path: 'notepad.exe', icon: '📋' }
        ];
        
        for (const app of commonApps) {
            if (app.path) {
                apps.push({ name: app.name, path: app.path, icon: app.icon, args: app.args });
            } else {
                for (const loc of locations) {
                    try {
                        const fullPath = path.join(loc, app.exe);
                        if (fs.existsSync(fullPath)) {
                            apps.push({ name: app.name, path: fullPath, icon: app.icon, args: app.args });
                            break;
                        }
                    } catch {}
                }
            }
        }
    } else if (process.platform === 'darwin') {
        const appsDir = '/Applications';
        try {
            const entries = fs.readdirSync(appsDir);
            for (const entry of entries) {
                if (entry.endsWith('.app')) {
                    apps.push({
                        name: entry.replace('.app', ''),
                        path: path.join(appsDir, entry),
                        icon: '📱'
                    });
                }
            }
        } catch {}
    } else {
        const linuxApps = [
            { name: 'Firefox', cmd: 'firefox', icon: '🦊' },
            { name: 'Chrome', cmd: 'google-chrome', icon: '🌐' },
            { name: 'VS Code', cmd: 'code', icon: '💻' },
            { name: 'Terminal', cmd: 'gnome-terminal', icon: '⌨️' },
            { name: 'Files', cmd: 'nautilus', icon: '📁' }
        ];
        for (const app of linuxApps) {
            try {
                require('child_process').execSync(`which ${app.cmd}`, { stdio: 'ignore' });
                apps.push({ name: app.name, path: app.cmd, icon: app.icon });
            } catch {}
        }
    }
    
    return apps;
});

ipcMain.handle('launch-pc-app', async (event, appPath, args = []) => {
    try {
        if (process.platform === 'win32') {
            if (args && args.length > 0) {
                require('child_process').spawn(appPath, args, { detached: true, stdio: 'ignore' }).unref();
            } else {
                require('child_process').exec(`start "" "${appPath}"`);
            }
        } else if (process.platform === 'darwin') {
            require('child_process').exec(`open "${appPath}"`);
        } else {
            require('child_process').spawn(appPath, { detached: true, stdio: 'ignore' }).unref();
        }
        return { success: true };
    } catch (e) {
        return { success: false, error: e.message };
    }
});

// ===== AUTO-UPDATE SYSTEM =====
ipcMain.handle('check-for-updates', async () => {
    try {
        // Get current version
        let currentVersion = '2.2.0';
        try {
            currentVersion = require('./version.json').version;
        } catch (e) {}
        
        // Fetch latest release from GitHub API
        const release = await fetchUrl(UPDATE_CHECK_URL, { json: true });
        
        const latestVersion = release.tag_name.replace(/^v/, '');
        const updateAvailable = compareVersions(latestVersion, currentVersion) > 0;
        
        // Find download URL for current platform
        let downloadUrl = release.html_url;
        const platform = process.platform;
        const arch = process.arch;
        
        for (const asset of release.assets || []) {
            const name = asset.name.toLowerCase();
            if (platform === 'win32' && (name.includes('win') || name.includes('.exe'))) {
                downloadUrl = asset.browser_download_url;
                break;
            } else if (platform === 'darwin' && (name.includes('mac') || name.includes('.dmg'))) {
                downloadUrl = asset.browser_download_url;
                break;
            } else if (platform === 'linux' && (name.includes('linux') || name.includes('.appimage'))) {
                downloadUrl = asset.browser_download_url;
                break;
            }
        }
        
        return {
            available: updateAvailable,
            currentVersion,
            latestVersion,
            downloadUrl,
            releaseNotes: release.body || '',
            releaseName: release.name || `v${latestVersion}`
        };
        
    } catch (err) {
        console.error('Update check failed:', err);
        return { 
            available: false, 
            error: err.message,
            currentVersion: require('./version.json').version || '2.2.0'
        };
    }
});

ipcMain.handle('download-update', async (event, downloadUrl) => {
    try {
        // Open the download URL in the default browser
        shell.openExternal(downloadUrl);
        return { success: true };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

ipcMain.handle('get-version', () => {
    try {
        return require('./version.json');
    } catch {
        return { version: '2.2.0' };
    }
});

ipcMain.handle('restart-app', () => {
    app.relaunch();
    app.exit();
});

ipcMain.handle('open-external', (event, url) => {
    shell.openExternal(url);
});

// Version comparison helper
function compareVersions(a, b) {
    const partsA = a.split('.').map(Number);
    const partsB = b.split('.').map(Number);
    
    for (let i = 0; i < Math.max(partsA.length, partsB.length); i++) {
        const numA = partsA[i] || 0;
        const numB = partsB[i] || 0;
        if (numA > numB) return 1;
        if (numA < numB) return -1;
    }
    return 0;
}

// Dev mode hot reload
function setupHotReload() {
    const watchDirs = [
        path.join(__dirname, 'src', 'renderer'),
    ];
    
    for (const dir of watchDirs) {
        if (fs.existsSync(dir)) {
            fs.watch(dir, { recursive: true }, (eventType, filename) => {
                if (filename && (filename.endsWith('.html') || filename.endsWith('.css') || filename.endsWith('.js'))) {
                    console.log(`[HOT RELOAD] ${filename} changed, reloading...`);
                    if (mainWindow && !mainWindow.isDestroyed()) {
                        mainWindow.webContents.reloadIgnoringCache();
                    }
                }
            });
        }
    }
}

// App lifecycle
app.whenReady().then(async () => {
    await createWindow();
    
    if (isDev) {
        console.log('[DEV MODE] Hot reload enabled');
        setupHotReload();
    }
    
    // Delay boot to ensure renderer is ready
    setTimeout(async () => {
        await bootSystem();
    }, 500);
});

app.on('window-all-closed', async () => {
    if (orchestrator) {
        await orchestrator.shutdown();
    }
    app.quit();
});

app.on('before-quit', async (event) => {
    if (orchestrator && orchestrator.runningProcesses.size > 0) {
        event.preventDefault();
        await orchestrator.shutdown();
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
