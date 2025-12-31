"""
AETHER-OS Ollama LLM Interface
Connects to local Ollama instance for LLM inference
Supports: llama3.2, mistral, codellama, phi3, etc.
"""

import os
import json
import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5003))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'ollama_chat')
OLLAMA_BASE = 'http://127.0.0.1:11434'

# Default model - user can change this
current_model = 'llama3.2:3b'  # Good for 8GB GPU
conversation_history = []

@app.route('/health')
def health():
    """Health check - also verifies Ollama connection"""
    try:
        r = requests.get(f'{OLLAMA_BASE}/api/tags', timeout=2)
        ollama_status = 'connected' if r.status_code == 200 else 'error'
        models = r.json().get('models', []) if r.status_code == 200 else []
    except:
        ollama_status = 'disconnected'
        models = []
    
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'ollama': ollama_status,
        'models': [m['name'] for m in models],
        'current_model': current_model
    })

@app.route('/models')
def list_models():
    """List available Ollama models"""
    try:
        r = requests.get(f'{OLLAMA_BASE}/api/tags')
        models = r.json().get('models', [])
        return jsonify({
            'models': [{'name': m['name'], 'size': m.get('size', 0)} for m in models],
            'current': current_model
        })
    except Exception as e:
        return jsonify({'error': str(e), 'models': []}), 500

@app.route('/model', methods=['POST'])
def set_model():
    """Change the active model"""
    global current_model
    data = request.json or {}
    model = data.get('model')
    
    if model:
        current_model = model
        return jsonify({'success': True, 'model': current_model})
    return jsonify({'error': 'No model specified'}), 400

@app.route('/chat', methods=['POST'])
def chat():
    """Send a chat message to Ollama"""
    global conversation_history
    
    data = request.json or {}
    message = data.get('message', '')
    stream = data.get('stream', False)
    
    if not message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Add user message to history
    conversation_history.append({'role': 'user', 'content': message})
    
    # Keep history manageable (last 10 exchanges)
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
    
    try:
        payload = {
            'model': current_model,
            'messages': conversation_history,
            'stream': stream
        }
        
        if stream:
            def generate():
                response_text = ''
                with requests.post(f'{OLLAMA_BASE}/api/chat', json=payload, stream=True) as r:
                    for line in r.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            if 'message' in chunk:
                                content = chunk['message'].get('content', '')
                                response_text += content
                                yield f"data: {json.dumps({'content': content})}\n\n"
                            if chunk.get('done'):
                                conversation_history.append({'role': 'assistant', 'content': response_text})
                                yield f"data: {json.dumps({'done': True})}\n\n"
            
            return Response(generate(), mimetype='text/event-stream')
        else:
            r = requests.post(f'{OLLAMA_BASE}/api/chat', json=payload)
            result = r.json()
            
            assistant_message = result.get('message', {}).get('content', '')
            conversation_history.append({'role': 'assistant', 'content': assistant_message})
            
            return jsonify({
                'response': assistant_message,
                'model': current_model,
                'tokens': result.get('eval_count', 0)
            })
            
    except requests.exceptions.ConnectionError:
        return jsonify({
            'error': 'Ollama not running. Start Ollama first: ollama serve',
            'response': 'ERROR: Cannot connect to Ollama. Please ensure Ollama is running.'
        }), 503
    except Exception as e:
        return jsonify({'error': str(e), 'response': f'Error: {str(e)}'}), 500

@app.route('/clear', methods=['POST'])
def clear_history():
    """Clear conversation history"""
    global conversation_history
    conversation_history = []
    return jsonify({'success': True, 'message': 'History cleared'})

@app.route('/pull', methods=['POST'])
def pull_model():
    """Pull/download a new model from Ollama"""
    data = request.json or {}
    model = data.get('model')
    
    if not model:
        return jsonify({'error': 'No model specified'}), 400
    
    def stream_pull():
        with requests.post(f'{OLLAMA_BASE}/api/pull', json={'name': model}, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    yield f"data: {line.decode()}\n\n"
    
    return Response(stream_pull(), mimetype='text/event-stream')

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Ollama LLM',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Local LLM interface via Ollama',
        'recommended_models': [
            'llama3.2:3b',      # Fast, good quality
            'mistral:7b',       # Great reasoning
            'codellama:7b',     # Code generation
            'phi3:mini',        # Very fast, small
            'gemma2:2b'         # Compact and fast
        ]
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting Ollama Interface on port {PORT}...')
    print(f'[{TOOL_NAME}] Default model: {current_model}')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
