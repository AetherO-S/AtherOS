"""
AETHER-OS Code Editor Backend
File editing and syntax support
"""

import os
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5011))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'code_editor')

# File extension to language mapping
LANGUAGES = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.html': 'html',
    '.css': 'css',
    '.json': 'json',
    '.md': 'markdown',
    '.txt': 'text',
    '.sh': 'bash',
    '.bat': 'batch',
    '.ps1': 'powershell',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.xml': 'xml',
    '.sql': 'sql',
    '.java': 'java',
    '.c': 'c',
    '.cpp': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',
    '.rs': 'rust',
    '.go': 'go',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.r': 'r',
    '.lua': 'lua'
}

# Recent files
recent_files = []
MAX_RECENT = 20

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT
    })

@app.route('/open', methods=['POST'])
def open_file():
    """Open a file for editing"""
    data = request.json or {}
    path = data.get('path')
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    path = Path(path)
    if not path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    if not path.is_file():
        return jsonify({'error': 'Not a file'}), 400
    
    try:
        # Read file
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Detect language
        ext = path.suffix.lower()
        language = LANGUAGES.get(ext, 'text')
        
        # Add to recent
        path_str = str(path)
        if path_str in recent_files:
            recent_files.remove(path_str)
        recent_files.insert(0, path_str)
        if len(recent_files) > MAX_RECENT:
            recent_files.pop()
        
        return jsonify({
            'success': True,
            'path': str(path),
            'name': path.name,
            'content': content,
            'language': language,
            'size': path.stat().st_size
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save', methods=['POST'])
def save_file():
    """Save file content"""
    data = request.json or {}
    path = data.get('path')
    content = data.get('content', '')
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'path': path,
            'size': len(content)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create', methods=['POST'])
def create_file():
    """Create a new file"""
    data = request.json or {}
    path = data.get('path')
    content = data.get('content', '')
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    path = Path(path)
    
    if path.exists():
        return jsonify({'error': 'File already exists'}), 400
    
    try:
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'path': str(path)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recent')
def get_recent():
    """Get recently opened files"""
    return jsonify({
        'recent': recent_files
    })

@app.route('/languages')
def get_languages():
    """Get supported languages"""
    return jsonify({
        'languages': LANGUAGES
    })

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Code Editor',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Code and text file editor'
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting Code Editor on port {PORT}...')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
