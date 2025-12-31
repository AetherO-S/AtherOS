"""
AETHER-OS Text-to-Speech Engine
Uses Piper TTS for fast, high-quality local speech synthesis
Optimized for low latency

Alternative: Coqui TTS for more voices/languages
"""

import os
import io
import base64
import subprocess
import tempfile
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5005))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'tts_engine')

# Piper voice models directory
VOICES_DIR = Path(__file__).parent / 'voices'
VOICES_DIR.mkdir(exist_ok=True)

# Available voices (will be downloaded on first use)
PIPER_VOICES = {
    'amy': {
        'model': 'en_US-amy-medium',
        'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/'
    },
    'lessac': {
        'model': 'en_US-lessac-medium',
        'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/'
    },
    'ryan': {
        'model': 'en_US-ryan-medium',
        'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/'
    },
    'danny': {
        'model': 'en_GB-danny-low',
        'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/danny/low/'
    }
}

DEFAULT_VOICE = 'amy'

# Try to use Coqui TTS if available
tts_engine = None
try:
    from TTS.api import TTS
    tts_engine = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
    print(f'[{TOOL_NAME}] Coqui TTS loaded')
except:
    print(f'[{TOOL_NAME}] Coqui TTS not available, will use Piper')

def synthesize_piper(text, voice=DEFAULT_VOICE, speed=1.0):
    """Synthesize speech using Piper TTS"""
    voice_config = PIPER_VOICES.get(voice, PIPER_VOICES[DEFAULT_VOICE])
    model_path = VOICES_DIR / f"{voice_config['model']}.onnx"
    
    # Check if we need to download
    if not model_path.exists():
        return None, f"Voice '{voice}' not downloaded. Use /voices/download endpoint."
    
    try:
        # Create temp file for output
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            output_path = f.name
        
        # Run piper
        cmd = [
            'piper',
            '--model', str(model_path),
            '--output_file', output_path,
            '--length_scale', str(1.0 / speed)
        ]
        
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        proc.communicate(input=text.encode())
        
        if proc.returncode == 0 and os.path.exists(output_path):
            with open(output_path, 'rb') as f:
                audio_data = f.read()
            os.unlink(output_path)
            return audio_data, None
        else:
            return None, "Piper synthesis failed"
            
    except FileNotFoundError:
        return None, "Piper not installed. Install with: pip install piper-tts"
    except Exception as e:
        return None, str(e)

def synthesize_coqui(text, speed=1.0):
    """Synthesize speech using Coqui TTS"""
    if tts_engine is None:
        return None, "Coqui TTS not available"
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            output_path = f.name
        
        tts_engine.tts_to_file(text=text, file_path=output_path, speed=speed)
        
        with open(output_path, 'rb') as f:
            audio_data = f.read()
        os.unlink(output_path)
        
        return audio_data, None
    except Exception as e:
        return None, str(e)

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'engines': {
            'coqui': tts_engine is not None,
            'piper': True  # Assume available, will error if not
        },
        'voices': list(PIPER_VOICES.keys())
    })

@app.route('/voices')
def list_voices():
    """List available voices"""
    voices = []
    for name, config in PIPER_VOICES.items():
        model_path = VOICES_DIR / f"{config['model']}.onnx"
        voices.append({
            'name': name,
            'model': config['model'],
            'downloaded': model_path.exists()
        })
    
    return jsonify({
        'voices': voices,
        'default': DEFAULT_VOICE,
        'coqui_available': tts_engine is not None
    })

@app.route('/voices/download', methods=['POST'])
def download_voice():
    """Download a Piper voice"""
    data = request.json or {}
    voice = data.get('voice')
    
    if voice not in PIPER_VOICES:
        return jsonify({'error': f'Unknown voice: {voice}'}), 400
    
    config = PIPER_VOICES[voice]
    model_path = VOICES_DIR / f"{config['model']}.onnx"
    config_path = VOICES_DIR / f"{config['model']}.onnx.json"
    
    if model_path.exists():
        return jsonify({'success': True, 'message': 'Voice already downloaded'})
    
    try:
        import urllib.request
        
        # Download model
        model_url = config['url'] + f"{config['model']}.onnx"
        print(f'[{TOOL_NAME}] Downloading {voice} voice...')
        urllib.request.urlretrieve(model_url, model_path)
        
        # Download config
        config_url = config['url'] + f"{config['model']}.onnx.json"
        urllib.request.urlretrieve(config_url, config_path)
        
        return jsonify({'success': True, 'message': f'Voice {voice} downloaded'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/synthesize', methods=['POST'])
def synthesize():
    """Synthesize speech from text"""
    data = request.json or {}
    text = data.get('text', '')
    voice = data.get('voice', DEFAULT_VOICE)
    speed = data.get('speed', 1.0)
    engine = data.get('engine', 'auto')
    output_format = data.get('format', 'base64')  # base64 or file
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    # Choose engine
    audio_data = None
    error = None
    
    if engine == 'coqui' and tts_engine is not None:
        audio_data, error = synthesize_coqui(text, speed)
    elif engine == 'piper':
        audio_data, error = synthesize_piper(text, voice, speed)
    else:
        # Auto: try Coqui first, then Piper
        if tts_engine is not None:
            audio_data, error = synthesize_coqui(text, speed)
        if audio_data is None:
            audio_data, error = synthesize_piper(text, voice, speed)
    
    if audio_data is None:
        return jsonify({'error': error or 'Synthesis failed'}), 500
    
    if output_format == 'file':
        return send_file(
            io.BytesIO(audio_data),
            mimetype='audio/wav',
            as_attachment=True,
            download_name='speech.wav'
        )
    else:
        return jsonify({
            'success': True,
            'audio': base64.b64encode(audio_data).decode(),
            'format': 'wav',
            'engine': 'coqui' if tts_engine and engine != 'piper' else 'piper'
        })

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Text to Speech',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Local TTS using Piper/Coqui',
        'engines': ['piper', 'coqui'],
        'voices': list(PIPER_VOICES.keys())
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting TTS Engine on port {PORT}...')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
