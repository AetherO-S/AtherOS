"""
AETHER-OS Speech-to-Text Engine
Uses OpenAI Whisper for accurate local speech recognition
Optimized for 8GB GPU

Models:
- tiny: Fastest, lower accuracy (~1GB VRAM)
- base: Good balance (~1GB VRAM)
- small: Better accuracy (~2GB VRAM)
- medium: High accuracy (~5GB VRAM)
- large-v3: Best accuracy (~10GB VRAM) - may not fit on 8GB
"""

import os
import io
import base64
import tempfile
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5006))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'stt_engine')

# Global model reference
model = None
current_model_size = None
device = None

MODELS = {
    'tiny': {'vram': '~1GB', 'speed': 'fastest', 'accuracy': 'basic'},
    'base': {'vram': '~1GB', 'speed': 'fast', 'accuracy': 'good'},
    'small': {'vram': '~2GB', 'speed': 'medium', 'accuracy': 'better'},
    'medium': {'vram': '~5GB', 'speed': 'slow', 'accuracy': 'high'},
    'large-v3': {'vram': '~10GB', 'speed': 'slowest', 'accuracy': 'best'}
}

DEFAULT_MODEL = 'base'  # Good balance for 8GB GPU

def load_model(model_size):
    """Load Whisper model"""
    global model, current_model_size, device
    
    if current_model_size == model_size and model is not None:
        return True
    
    try:
        import torch
        import whisper
        
        # Determine device
        if torch.cuda.is_available():
            device = 'cuda'
        else:
            device = 'cpu'
        
        print(f'[{TOOL_NAME}] Loading Whisper {model_size} on {device}...')
        
        # Clear old model
        if model is not None:
            del model
            if device == 'cuda':
                torch.cuda.empty_cache()
        
        model = whisper.load_model(model_size, device=device)
        current_model_size = model_size
        
        print(f'[{TOOL_NAME}] Model loaded successfully')
        return True
        
    except Exception as e:
        print(f'[{TOOL_NAME}] Error loading model: {e}')
        return False

@app.route('/health')
def health():
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else None
    except:
        gpu_available = False
        gpu_name = None
    
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'gpu': gpu_available,
        'gpu_name': gpu_name,
        'model_loaded': model is not None,
        'current_model': current_model_size
    })

@app.route('/models')
def list_models():
    return jsonify({
        'models': MODELS,
        'current': current_model_size,
        'default': DEFAULT_MODEL,
        'recommended_8gb': ['tiny', 'base', 'small', 'medium']
    })

@app.route('/load', methods=['POST'])
def load():
    """Load a specific model size"""
    data = request.json or {}
    model_size = data.get('model', DEFAULT_MODEL)
    
    if model_size not in MODELS:
        return jsonify({'error': f'Unknown model: {model_size}'}), 400
    
    success = load_model(model_size)
    return jsonify({
        'success': success,
        'model': current_model_size if success else None
    })

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Transcribe audio to text"""
    global model
    
    # Load model if not loaded
    if model is None:
        if not load_model(DEFAULT_MODEL):
            return jsonify({'error': 'Failed to load model'}), 500
    
    # Get audio data
    temp_file = None
    
    try:
        if 'file' in request.files:
            # File upload
            audio_file = request.files['file']
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            audio_file.save(temp_file.name)
            audio_path = temp_file.name
            
        elif request.json and 'audio' in request.json:
            # Base64 encoded audio
            audio_b64 = request.json['audio']
            audio_bytes = base64.b64decode(audio_b64)
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_file.write(audio_bytes)
            temp_file.close()
            audio_path = temp_file.name
            
        else:
            return jsonify({'error': 'No audio provided. Send file or base64 audio.'}), 400
        
        # Get options
        data = request.json or {}
        language = data.get('language')  # None for auto-detect
        task = data.get('task', 'transcribe')  # transcribe or translate
        
        print(f'[{TOOL_NAME}] Transcribing audio...')
        
        # Transcribe
        result = model.transcribe(
            audio_path,
            language=language,
            task=task,
            fp16=(device == 'cuda')
        )
        
        print(f'[{TOOL_NAME}] Transcription complete')
        
        return jsonify({
            'success': True,
            'text': result['text'].strip(),
            'language': result.get('language'),
            'segments': [
                {
                    'start': s['start'],
                    'end': s['end'],
                    'text': s['text'].strip()
                }
                for s in result.get('segments', [])
            ]
        })
        
    except Exception as e:
        print(f'[{TOOL_NAME}] Transcription error: {e}')
        return jsonify({'error': str(e)}), 500
        
    finally:
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except:
                pass

@app.route('/languages')
def languages():
    """List supported languages"""
    try:
        import whisper
        return jsonify({
            'languages': list(whisper.tokenizer.LANGUAGES.keys()),
            'language_names': whisper.tokenizer.LANGUAGES
        })
    except:
        return jsonify({
            'languages': ['en', 'es', 'fr', 'de', 'it', 'pt', 'nl', 'pl', 'ru', 'zh', 'ja', 'ko'],
            'note': 'Partial list - Whisper supports 99 languages'
        })

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Speech to Text',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Local speech recognition using OpenAI Whisper',
        'models': list(MODELS.keys()),
        'recommended': 'small'
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting STT Engine on port {PORT}...')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    print(f'[{TOOL_NAME}] Note: First transcription will download model')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
