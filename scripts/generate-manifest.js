// scripts/generate-manifest.js
// Generates manifest.json for the update system

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const appRoot = path.join(__dirname, '..');
const version = process.argv[2] || require('../version.json').version;
const changelog = process.argv.slice(3);

function hashFile(filePath) {
    const content = fs.readFileSync(filePath);
    return crypto.createHash('md5').update(content).digest('hex');
}

function scanDir(dir, base = '') {
    const files = {};
    const items = fs.readdirSync(dir, { withFileTypes: true });
    
    for (const item of items) {
        // Skip these directories
        if (['node_modules', 'envs', '.aether_core', '.git', 'dist', '__pycache__', 'venv'].includes(item.name)) {
            continue;
        }
        
        const fullPath = path.join(dir, item.name);
        const relativePath = path.join(base, item.name).replace(/\\/g, '/');
        
        if (item.isDirectory()) {
            Object.assign(files, scanDir(fullPath, relativePath));
        } else {
            const stats = fs.statSync(fullPath);
            files[relativePath] = {
                hash: hashFile(fullPath),
                size: stats.size,
                modified: stats.mtime.toISOString()
            };
        }
    }
    
    return files;
}

console.log(`Generating manifest for version ${version}...`);

const files = scanDir(appRoot);
const manifest = {
    version: version,
    build: Date.now(),
    published: new Date().toISOString(),
    changelog: changelog,
    files: files
};

const manifestPath = path.join(appRoot, 'manifest.json');
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

// Update version.json
const versionPath = path.join(appRoot, 'version.json');
const versionData = {
    version: version,
    name: 'AetherOS',
    description: 'Desktop productivity suite with AI tools'
};
fs.writeFileSync(versionPath, JSON.stringify(versionData, null, 2));

console.log(`✓ Manifest generated: ${Object.keys(files).length} files`);
console.log(`✓ Version updated to ${version}`);
