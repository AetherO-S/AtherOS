"""
AETHER-OS Terminal
Execute system commands and scripts
"""

import os
import subprocess
import threading
import queue
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5010))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'terminal')

# Current working directory
cwd = os.path.expanduser('~')

# Command history
command_history = []
MAX_HISTORY = 100

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'cwd': cwd,
        'platform': os.name
    })

@app.route('/execute', methods=['POST'])
def execute():
    """Execute a command"""
    global cwd
    
    data = request.json or {}
    command = data.get('command', '').strip()
    
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    
    # Add to history
    command_history.append(command)
    if len(command_history) > MAX_HISTORY:
        command_history.pop(0)
    
    # Handle built-in commands
    if command.startswith('cd '):
        new_dir = command[3:].strip()
        if new_dir == '~':
            new_dir = os.path.expanduser('~')
        elif not os.path.isabs(new_dir):
            new_dir = os.path.join(cwd, new_dir)
        
        new_dir = os.path.normpath(new_dir)
        
        if os.path.isdir(new_dir):
            cwd = new_dir
            return jsonify({
                'success': True,
                'output': f'Changed directory to {cwd}',
                'cwd': cwd
            })
        else:
            return jsonify({
                'success': False,
                'output': f'Directory not found: {new_dir}',
                'cwd': cwd
            })
    
    if command == 'pwd':
        return jsonify({
            'success': True,
            'output': cwd,
            'cwd': cwd
        })
    
    if command == 'clear' or command == 'cls':
        return jsonify({
            'success': True,
            'output': '',
            'clear': True,
            'cwd': cwd
        })
    
    try:
        # Determine shell
        shell = True
        if os.name == 'nt':
            # Windows
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
        else:
            # Unix
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
                executable='/bin/bash'
            )
        
        output = result.stdout
        if result.stderr:
            output += '\n' + result.stderr if output else result.stderr
        
        return jsonify({
            'success': result.returncode == 0,
            'output': output.strip() if output else '(no output)',
            'return_code': result.returncode,
            'cwd': cwd
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'output': 'Command timed out (30s limit)',
            'cwd': cwd
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'output': f'Error: {str(e)}',
            'cwd': cwd
        })

@app.route('/history')
def get_history():
    """Get command history"""
    return jsonify({
        'history': command_history,
        'count': len(command_history)
    })

@app.route('/cwd')
def get_cwd():
    """Get current working directory"""
    return jsonify({'cwd': cwd})

@app.route('/cwd', methods=['POST'])
def set_cwd():
    """Set current working directory"""
    global cwd
    data = request.json or {}
    new_cwd = data.get('path', '')
    
    if os.path.isdir(new_cwd):
        cwd = new_cwd
        return jsonify({'success': True, 'cwd': cwd})
    return jsonify({'error': 'Invalid directory'}), 400

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Terminal',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Command line interface'
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting Terminal on port {PORT}...')
    print(f'[{TOOL_NAME}] Working directory: {cwd}')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
