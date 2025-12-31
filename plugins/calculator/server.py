"""
AETHER-OS Calculator Plugin
Example plugin demonstrating the plugin system
"""

import os
import math
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5100))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'calculator')

# History of calculations
history = []

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT
    })

@app.route('/calculate', methods=['POST'])
def calculate():
    """Evaluate a mathematical expression"""
    data = request.json or {}
    expression = data.get('expression', '')
    
    if not expression:
        return jsonify({'error': 'No expression provided'}), 400
    
    try:
        # Safe evaluation with math functions
        allowed_names = {
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
            'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10,
            'exp': math.exp, 'pow': pow, 'pi': math.pi, 'e': math.e,
            'floor': math.floor, 'ceil': math.ceil
        }
        
        # Sanitize and evaluate
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        
        # Add to history
        history.append({'expression': expression, 'result': result})
        if len(history) > 50:
            history.pop(0)
        
        return jsonify({
            'success': True,
            'expression': expression,
            'result': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/history')
def get_history():
    """Get calculation history"""
    return jsonify({'history': history})

@app.route('/clear', methods=['POST'])
def clear_history():
    """Clear calculation history"""
    global history
    history = []
    return jsonify({'success': True})

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Calculator',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Mathematical calculator with history',
        'functions': ['sin', 'cos', 'tan', 'sqrt', 'log', 'log10', 'exp', 'pow', 'pi', 'e']
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting Calculator on port {PORT}...')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
