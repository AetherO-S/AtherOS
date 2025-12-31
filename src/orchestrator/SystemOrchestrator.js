// src/orchestrator/SystemOrchestrator.js
// AETHER-OS System Orchestrator v2.2 - Full Plugin Support

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { EventEmitter } = require('events');

class SystemOrchestrator extends EventEmitter {
    constructor(appRoot, options = {}) {
        super();
        this.appRoot = appRoot;
        this.isPackaged = options.isPackaged || false;
        
        // Paths
        this.toolsDir = options.toolsPath || path.join(appRoot, 'src', 'tools');
        this.pluginsDir = options.pluginsPath || path.join(appRoot, 'plugins');
        
        // Data directories
        this.coreDir = path.join(appRoot, '.aether_core');
        this.envsDir = path.join(appRoot, 'envs');
        
        this.pythonPath = null;
        this.runningProcesses = new Map();
        this.isWindows = process.platform === 'win32';
        
        console.log(`[Orchestrator] Tools: ${this.toolsDir}`);
        console.log(`[Orchestrator] Plugins: ${this.pluginsDir}`);
        console.log(`[Orchestrator] Envs: ${this.envsDir}`);
        
        // Built-in tool configurations
        this.toolConfigs = {
            ollama_chat: { port: 5003, displayName: 'Ollama LLM', category: 'ai', icon: 'chat', builtIn: true },
            image_gen: { port: 5004, displayName: 'Image Gen', category: 'ai', icon: 'image', builtIn: true },
            tts_engine: { port: 5005, displayName: 'Text to Speech', category: 'ai', icon: 'speaker', builtIn: true },
            stt_engine: { port: 5006, displayName: 'Speech to Text', category: 'ai', icon: 'mic', builtIn: true },
            video_gen: { port: 5012, displayName: 'Video Gen', category: 'ai', icon: 'video', builtIn: true },
            file_manager: { port: 5007, displayName: 'File Manager', category: 'productivity', icon: 'folder', builtIn: true },
            notes: { port: 5008, displayName: 'Notes Board', category: 'productivity', icon: 'note', builtIn: true },
            system_monitor: { port: 5009, displayName: 'System Monitor', category: 'system', icon: 'cpu', builtIn: true },
            terminal: { port: 5010, displayName: 'Terminal', category: 'system', icon: 'terminal', builtIn: true },
            code_editor: { port: 5011, displayName: 'Code Editor', category: 'productivity', icon: 'code', builtIn: true },
            spreadsheet_engine: { port: 5002, displayName: 'Data Grid', category: 'productivity', icon: 'grid', builtIn: true }
        };
        
        // Track next available port for plugins
        this.nextPluginPort = 5100;
        
        // Load installed plugins
        this.loadPlugins();
    }
    
    // Load all plugins from plugins directory
    loadPlugins() {
        try {
            if (!fs.existsSync(this.pluginsDir)) {
                fs.mkdirSync(this.pluginsDir, { recursive: true });
                return;
            }
            
            const pluginDirs = fs.readdirSync(this.pluginsDir, { withFileTypes: true })
                .filter(d => d.isDirectory())
                .map(d => d.name);
            
            for (const dir of pluginDirs) {
                this._loadPluginConfig(dir);
            }
        } catch (err) {
            console.error('[PLUGIN] Error scanning plugins:', err.message);
        }
    }
    
    // Load a single plugin configuration
    _loadPluginConfig(pluginDir) {
        const configPath = path.join(this.pluginsDir, pluginDir, 'plugin.json');
        
        if (!fs.existsSync(configPath)) {
            return null;
        }
        
        try {
            const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
            const pluginId = config.name || pluginDir;
            
            // Find available port
            let port = config.port || this.nextPluginPort;
            while (this._isPortUsed(port)) {
                port++;
            }
            this.nextPluginPort = port + 1;
            
            this.toolConfigs[pluginId] = {
                port: port,
                displayName: config.displayName || config.name || pluginDir,
                description: config.description || '',
                category: config.category || 'plugin',
                icon: config.icon || 'plugin',
                version: config.version || '1.0.0',
                author: config.author || 'Unknown',
                isPlugin: true,
                pluginPath: path.join(this.pluginsDir, pluginDir)
            };
            
            console.log(`[PLUGIN] Loaded: ${config.displayName || pluginId} on port ${port}`);
            return this.toolConfigs[pluginId];
            
        } catch (err) {
            console.error(`[PLUGIN] Failed to load ${pluginDir}:`, err.message);
            return null;
        }
    }
    
    _isPortUsed(port) {
        for (const config of Object.values(this.toolConfigs)) {
            if (config.port === port) return true;
        }
        return false;
    }
    
    // Load a single plugin at runtime (for new installations)
    async loadPlugin(pluginId) {
        const pluginDir = path.join(this.pluginsDir, pluginId);
        
        if (!fs.existsSync(pluginDir)) {
            throw new Error(`Plugin directory not found: ${pluginId}`);
        }
        
        // Load config
        const config = this._loadPluginConfig(pluginId);
        if (!config) {
            throw new Error(`Could not load plugin config: ${pluginId}`);
        }
        
        // Set up environment
        await this.ensureToolEnvironment(pluginId);
        
        // Spawn the tool
        await this.spawnTool(pluginId);
        
        return { success: true, port: config.port };
    }
    
    // Unload a plugin (remove from config)
    unloadPlugin(pluginId) {
        if (this.toolConfigs[pluginId]?.isPlugin) {
            delete this.toolConfigs[pluginId];
            console.log(`[PLUGIN] Unloaded: ${pluginId}`);
        }
    }

    // Emit progress event
    emitProgress(stage, message, percent, tool = null) {
        this.emit('progress', { stage, message, percent, tool, timestamp: Date.now() });
    }

    // Emit error event
    emitError(message, details = null) {
        this.emit('error', { message, details, timestamp: Date.now() });
    }

    // Detect Python
    async detectPython() {
        this.emitProgress('detection', 'Scanning for Python installation...', 5);
        
        const pythonCommands = this.isWindows 
            ? ['python', 'python3', 'py -3', 'py'] 
            : ['python3', 'python'];

        for (const cmd of pythonCommands) {
            try {
                const result = execSync(`${cmd} --version`, { 
                    encoding: 'utf8',
                    stdio: ['pipe', 'pipe', 'pipe'],
                    shell: true,
                    timeout: 10000
                }).trim();
                
                const match = result.match(/Python (\d+)\.(\d+)/);
                if (match) {
                    const major = parseInt(match[1]);
                    const minor = parseInt(match[2]);
                    
                    if (major >= 3 && minor >= 8) {
                        if (this.isWindows && !cmd.includes(' ')) {
                            try {
                                const wherePython = execSync(`where ${cmd}`, { encoding: 'utf8', timeout: 5000 });
                                const pythonPaths = wherePython.trim().split('\n');
                                this.pythonPath = pythonPaths[0]?.trim() || cmd;
                            } catch {
                                this.pythonPath = cmd;
                            }
                        } else {
                            this.pythonPath = cmd;
                        }
                        
                        this.emitProgress('detection', `Found Python ${major}.${minor}`, 10);
                        return { success: true, version: result, command: this.pythonPath };
                    }
                }
            } catch (err) {
                continue;
            }
        }

        this.emitError('Python 3.8+ not found', 'Please install Python 3.8 or newer');
        return { success: false };
    }

    // Initialize core structure
    async initializeCoreStructure() {
        this.emitProgress('init', 'Initializing AETHER core structure...', 15);
        
        const dirs = [this.coreDir, this.envsDir, this.pluginsDir];
        for (const dir of dirs) {
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
        }

        const statePath = path.join(this.coreDir, 'state.json');
        if (!fs.existsSync(statePath)) {
            fs.writeFileSync(statePath, JSON.stringify({
                initialized: true,
                initDate: new Date().toISOString(),
                pythonCommand: this.pythonPath,
                platform: process.platform
            }, null, 2));
        }

        this.emitProgress('init', 'Core structure initialized', 20);
    }

    // Ensure tool environment exists
    async ensureToolEnvironment(toolName) {
        const config = this.toolConfigs[toolName];
        if (!config) {
            throw new Error(`Unknown tool: ${toolName}`);
        }

        const venvPath = path.join(this.envsDir, toolName);
        const toolPath = config.isPlugin ? config.pluginPath : path.join(this.toolsDir, toolName);
        const requirementsPath = path.join(toolPath, 'requirements.txt');

        const venvPython = this.isWindows
            ? path.join(venvPath, 'Scripts', 'python.exe')
            : path.join(venvPath, 'bin', 'python');

        const venvPip = this.isWindows
            ? path.join(venvPath, 'Scripts', 'pip.exe')
            : path.join(venvPath, 'bin', 'pip');

        // Fast path: already set up
        const markerPath = path.join(venvPath, '.aether_ready');
        if (fs.existsSync(markerPath) && fs.existsSync(venvPython)) {
            return { venvPath, venvPython, venvPip, port: config.port };
        }

        // Check if tool directory exists
        if (!fs.existsSync(toolPath)) {
            console.log(`[SETUP] Tool path not found: ${toolPath}`);
            return { venvPath, venvPython, venvPip, port: config.port, skipped: true };
        }

        // Create venv
        if (!fs.existsSync(venvPython)) {
            this.emitProgress('venv', `Creating environment for ${config.displayName}...`, 25, toolName);
            
            try {
                await this.runCommand(this.pythonPath, ['-m', 'venv', venvPath]);
                this.emitProgress('venv', `Environment created for ${config.displayName}`, 35, toolName);
            } catch (err) {
                throw new Error(`Failed to create venv for ${toolName}: ${err.message}`);
            }
        }

        // Install requirements
        if (fs.existsSync(requirementsPath)) {
            this.emitProgress('install', `Installing dependencies for ${config.displayName}...`, 40, toolName);
            
            try {
                await this.runCommand(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip', '-q']);
            } catch (err) {}
            
            try {
                await this.runCommand(venvPip, ['install', '-r', requirementsPath, '-q'], {
                    onProgress: (data) => {
                        if (data.includes('Collecting') || data.includes('Installing')) {
                            this.emitProgress('install', data.trim().slice(0, 60), 50, toolName);
                        }
                    }
                });
                this.emitProgress('install', `Dependencies installed for ${config.displayName}`, 60, toolName);
            } catch (err) {
                throw new Error(`Failed to install deps for ${toolName}: ${err.message}`);
            }
        }

        // Mark as ready
        fs.writeFileSync(markerPath, JSON.stringify({
            toolName,
            setupDate: new Date().toISOString(),
            pythonPath: venvPython
        }));

        return { venvPath, venvPython, venvPip, port: config.port };
    }

    // Spawn a tool
    async spawnTool(toolName) {
        const config = this.toolConfigs[toolName];
        if (!config) {
            throw new Error(`Unknown tool: ${toolName}`);
        }

        if (this.runningProcesses.has(toolName)) {
            await this.stopTool(toolName);
        }

        const venvPath = path.join(this.envsDir, toolName);
        const toolPath = config.isPlugin ? config.pluginPath : path.join(this.toolsDir, toolName);
        const serverScript = path.join(toolPath, 'server.py');

        const venvPython = this.isWindows
            ? path.join(venvPath, 'Scripts', 'python.exe')
            : path.join(venvPath, 'bin', 'python');

        if (!fs.existsSync(serverScript)) {
            return { skipped: true, reason: 'No server.py found' };
        }

        if (!fs.existsSync(venvPython)) {
            return { skipped: true, reason: 'Virtual environment not ready' };
        }

        this.emitProgress('spawn', `Launching ${config.displayName} on port ${config.port}...`, 75, toolName);

        const proc = spawn(venvPython, [serverScript], {
            cwd: toolPath,
            env: {
                ...process.env,
                AETHER_PORT: config.port.toString(),
                AETHER_TOOL: toolName,
                PYTHONUNBUFFERED: '1'
            },
            stdio: ['pipe', 'pipe', 'pipe'],
            shell: false,
            windowsHide: true
        });

        this.runningProcesses.set(toolName, {
            process: proc,
            port: config.port,
            startTime: Date.now()
        });

        proc.stdout.on('data', (data) => {
            const message = data.toString().trim();
            this.emit('tool-output', { tool: toolName, type: 'stdout', message });
            
            if (message.includes('Running on') || message.includes('Starting') || message.includes('Listening')) {
                this.emit('tool-ready', { tool: toolName, port: config.port });
            }
        });

        proc.stderr.on('data', (data) => {
            const message = data.toString().trim();
            this.emit('tool-output', { tool: toolName, type: 'stderr', message });
            
            if (message.includes('Running on') || message.includes('Starting')) {
                this.emit('tool-ready', { tool: toolName, port: config.port });
            }
        });

        proc.on('close', (code) => {
            this.runningProcesses.delete(toolName);
            this.emit('tool-stopped', { tool: toolName, exitCode: code });
        });

        proc.on('error', (err) => {
            this.emitError(`Failed to spawn ${toolName}`, err.message);
        });

        await new Promise(r => setTimeout(r, 300));

        return { pid: proc.pid, port: config.port };
    }

    // Stop a tool
    async stopTool(toolName) {
        const entry = this.runningProcesses.get(toolName);
        if (entry) {
            if (this.isWindows) {
                try {
                    execSync(`taskkill /pid ${entry.process.pid} /f /t`, { stdio: 'ignore' });
                } catch (err) {
                    entry.process.kill();
                }
            } else {
                entry.process.kill('SIGTERM');
            }
            
            await new Promise((resolve) => {
                const timeout = setTimeout(() => resolve(), 3000);
                entry.process.on('close', () => {
                    clearTimeout(timeout);
                    resolve();
                });
            });

            this.runningProcesses.delete(toolName);
        }
    }

    // Shutdown all tools
    async shutdown() {
        this.emitProgress('shutdown', 'Shutting down all tools...', 0);
        
        const tools = Array.from(this.runningProcesses.keys());
        for (const tool of tools) {
            await this.stopTool(tool);
        }
        
        this.emitProgress('shutdown', 'All tools stopped', 100);
    }

    // Run command helper
    runCommand(command, args, options = {}) {
        return new Promise((resolve, reject) => {
            const proc = spawn(command, args, {
                stdio: ['pipe', 'pipe', 'pipe'],
                shell: this.isWindows,
                windowsHide: true
            });

            let stdout = '';
            let stderr = '';

            proc.stdout.on('data', (data) => {
                stdout += data.toString();
                if (options.onProgress) {
                    options.onProgress(data.toString());
                }
            });

            proc.stderr.on('data', (data) => {
                stderr += data.toString();
                if (options.onProgress) {
                    options.onProgress(data.toString());
                }
            });

            proc.on('close', (code) => {
                if (code === 0) {
                    resolve({ stdout, stderr });
                } else {
                    reject(new Error(`Exit code ${code}: ${stderr || stdout}`));
                }
            });

            proc.on('error', reject);
        });
    }

    // Boot sequence
    async boot(toolsToLoad = null) {
        // Only boot built-in tools by default
        const tools = toolsToLoad || Object.keys(this.toolConfigs).filter(k => this.toolConfigs[k].builtIn);
        
        try {
            const pythonResult = await this.detectPython();
            if (!pythonResult.success) {
                return { success: false, error: 'Python 3.8+ not found' };
            }

            await this.initializeCoreStructure();

            const totalTools = tools.length;
            for (let i = 0; i < totalTools; i++) {
                const tool = tools[i];
                const percent = 20 + Math.floor((i / totalTools) * 50);
                
                this.emitProgress('setup', `Configuring ${this.toolConfigs[tool]?.displayName || tool}...`, percent, tool);
                
                try {
                    await this.ensureToolEnvironment(tool);
                } catch (err) {
                    this.emitError(`Failed to set up ${tool}`, err.message);
                }
            }

            this.emitProgress('launch', 'Launching all subsystems...', 75);
            
            const launchResults = [];
            for (const tool of tools) {
                try {
                    const result = await this.spawnTool(tool);
                    launchResults.push({ tool, ...result, success: !result.skipped });
                } catch (err) {
                    launchResults.push({ tool, success: false, error: err.message });
                }
            }

            // Also start installed plugins
            const plugins = Object.keys(this.toolConfigs).filter(k => this.toolConfigs[k].isPlugin);
            for (const plugin of plugins) {
                try {
                    await this.ensureToolEnvironment(plugin);
                    const result = await this.spawnTool(plugin);
                    launchResults.push({ tool: plugin, ...result, success: !result.skipped });
                } catch (err) {
                    launchResults.push({ tool: plugin, success: false, error: err.message });
                }
            }

            this.emitProgress('ready', 'AETHER-OS fully operational', 100);
            
            return { 
                success: true, 
                python: pythonResult,
                tools: launchResults
            };

        } catch (err) {
            this.emitError('Boot sequence failed', err.message);
            return { success: false, error: err.message };
        }
    }

    // Get status
    getStatus() {
        const status = {};
        for (const [toolName, config] of Object.entries(this.toolConfigs)) {
            const running = this.runningProcesses.get(toolName);
            status[toolName] = {
                displayName: config.displayName,
                description: config.description || '',
                port: config.port,
                category: config.category,
                icon: config.icon,
                isPlugin: config.isPlugin || false,
                builtIn: config.builtIn || false,
                version: config.version,
                author: config.author,
                running: !!running,
                pid: running?.process?.pid,
                uptime: running ? Date.now() - running.startTime : 0
            };
        }
        return status;
    }
}

module.exports = SystemOrchestrator;
