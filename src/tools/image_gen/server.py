"""
AETHER-OS Image Generation Engine
Uses Stable Diffusion via HuggingFace diffusers
Optimized for 8GB VRAM GPUs

Models supported:
- stabilityai/stable-diffusion-xl-base-1.0 (SDXL - best quality)
- runwayml/stable-diffusion-v1-5 (SD 1.5 - faster)
- stabilityai/sdxl-turbo (SDXL Turbo - very fast)
"""

import os
import io
import base64
import gc
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5004))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'image_gen')

# Global pipeline reference
pipe = None
current_model = None
device = None

# Optimized models for 8GB GPU
MODELS = {
    'sdxl-turbo': {
        'id': 'stabilityai/sdxl-turbo',
        'steps': 4,
        'guidance': 0.0,
        'vram': '6GB'
    },
    'sd-turbo': {
        'id': 'stabilityai/sd-turbo',
        'steps': 4,
        'guidance': 0.0,
        'vram': '4GB'
    },
    'sdxl-lightning': {
        'id': 'ByteDance/SDXL-Lightning',
        'steps': 4,
        'guidance': 0.0,
        'vram': '6GB'
    },
    'sd-1.5': {
        'id': 'runwayml/stable-diffusion-v1-5',
        'steps': 25,
        'guidance': 7.5,
        'vram': '4GB'
    }
}

DEFAULT_MODEL = 'sdxl-turbo'

def load_model(model_key):
    """Load a diffusion model with memory optimization"""
    global pipe, current_model, device
    
    if current_model == model_key and pipe is not None:
        return True
    
    # Clear existing model
    if pipe is not None:
        del pipe
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except:
            pass
    
    model_config = MODELS.get(model_key, MODELS[DEFAULT_MODEL])
    
    try:
        import torch
        from diffusers import AutoPipelineForText2Image
        
        # Determine device
        if torch.cuda.is_available():
            device = 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = 'mps'
        else:
            device = 'cpu'
        
        print(f'[{TOOL_NAME}] Loading {model_key} on {device}...')
        
        # Load with memory optimizations
        pipe = AutoPipelineForText2Image.from_pretrained(
            model_config['id'],
            torch_dtype=torch.float16 if device != 'cpu' else torch.float32,
            variant="fp16" if device != 'cpu' else None,
            use_safetensors=True
        )
        
        pipe = pipe.to(device)
        
        # Enable memory optimizations
        if device == 'cuda':
            pipe.enable_attention_slicing()
            try:
                pipe.enable_xformers_memory_efficient_attention()
            except:
                pass
        
        current_model = model_key
        print(f'[{TOOL_NAME}] Model {model_key} loaded successfully')
        return True
        
    except Exception as e:
        print(f'[{TOOL_NAME}] Error loading model: {e}')
        return False

@app.route('/health')
def health():
    """Health check"""
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else None
        gpu_memory = torch.cuda.get_device_properties(0).total_memory // (1024**3) if gpu_available else 0
    except:
        gpu_available = False
        gpu_name = None
        gpu_memory = 0
    
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'gpu': gpu_available,
        'gpu_name': gpu_name,
        'gpu_memory_gb': gpu_memory,
        'model_loaded': pipe is not None,
        'current_model': current_model
    })

@app.route('/models')
def list_models():
    """List available models"""
    return jsonify({
        'models': MODELS,
        'current': current_model,
        'default': DEFAULT_MODEL
    })

@app.route('/load', methods=['POST'])
def load():
    """Load a specific model"""
    data = request.json or {}
    model = data.get('model', DEFAULT_MODEL)
    
    success = load_model(model)
    return jsonify({
        'success': success,
        'model': current_model if success else None
    })

@app.route('/unload', methods=['POST'])
def unload():
    """Unload model to free memory"""
    global pipe, current_model
    if pipe is not None:
        del pipe
        pipe = None
        current_model = None
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except:
            pass
    return jsonify({'success': True})

@app.route('/generate', methods=['POST'])
def generate():
    """Generate an image from a text prompt"""
    global pipe, current_model
    
    data = request.json or {}
    prompt = data.get('prompt', '')
    negative_prompt = data.get('negative_prompt', 'blurry, low quality, distorted')
    width = data.get('width', 512)
    height = data.get('height', 512)
    steps = data.get('steps')
    guidance = data.get('guidance')
    seed = data.get('seed')
    model = data.get('model', current_model or DEFAULT_MODEL)
    
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    # Load model if needed
    if pipe is None or current_model != model:
        if not load_model(model):
            return jsonify({'error': 'Failed to load model. Ensure you have GPU support and required packages.'}), 500
    
    model_config = MODELS.get(model, MODELS[DEFAULT_MODEL])
    steps = steps or model_config['steps']
    guidance = guidance if guidance is not None else model_config['guidance']
    
    try:
        import torch
        
        generator = None
        if seed is not None:
            generator = torch.Generator(device=device).manual_seed(seed)
        
        print(f'[{TOOL_NAME}] Generating: "{prompt[:50]}..." ({width}x{height}, {steps} steps)')
        
        # Generate image
        with torch.inference_mode():
            result = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=generator
            )
        
        image = result.images[0]
        
        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        print(f'[{TOOL_NAME}] Generation complete')
        
        return jsonify({
            'success': True,
            'image': img_base64,
            'model': current_model,
            'width': width,
            'height': height,
            'steps': steps
        })
        
    except Exception as e:
        print(f'[{TOOL_NAME}] Generation error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Image Generation',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Stable Diffusion image generation (8GB GPU optimized)',
        'models': list(MODELS.keys()),
        'recommended': 'sdxl-turbo'
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting Image Generation Engine on port {PORT}...')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    print(f'[{TOOL_NAME}] Note: First generation will download model (~2-6GB)')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
