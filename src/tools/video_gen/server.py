"""
AETHER-OS Video Generation Engine
Creates smooth camera motion videos from images (Ken Burns effect)
No AI needed - pure image processing for consistent, smooth results
"""

import os
import io
import base64
import gc
import tempfile
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image
import numpy as np

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5012))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'video_gen')

# Motion presets
MOTION_PRESETS = {
    'zoom_in': {'start_scale': 1.0, 'end_scale': 1.3, 'start_x': 0.5, 'end_x': 0.5, 'start_y': 0.5, 'end_y': 0.5},
    'zoom_out': {'start_scale': 1.3, 'end_scale': 1.0, 'start_x': 0.5, 'end_x': 0.5, 'start_y': 0.5, 'end_y': 0.5},
    'pan_left': {'start_scale': 1.2, 'end_scale': 1.2, 'start_x': 0.7, 'end_x': 0.3, 'start_y': 0.5, 'end_y': 0.5},
    'pan_right': {'start_scale': 1.2, 'end_scale': 1.2, 'start_x': 0.3, 'end_x': 0.7, 'start_y': 0.5, 'end_y': 0.5},
    'pan_up': {'start_scale': 1.2, 'end_scale': 1.2, 'start_x': 0.5, 'end_x': 0.5, 'start_y': 0.7, 'end_y': 0.3},
    'pan_down': {'start_scale': 1.2, 'end_scale': 1.2, 'start_x': 0.5, 'end_x': 0.5, 'start_y': 0.3, 'end_y': 0.7},
    'zoom_pan_tl': {'start_scale': 1.0, 'end_scale': 1.4, 'start_x': 0.5, 'end_x': 0.3, 'start_y': 0.5, 'end_y': 0.3},
    'zoom_pan_tr': {'start_scale': 1.0, 'end_scale': 1.4, 'start_x': 0.5, 'end_x': 0.7, 'start_y': 0.5, 'end_y': 0.3},
    'zoom_pan_bl': {'start_scale': 1.0, 'end_scale': 1.4, 'start_x': 0.5, 'end_x': 0.3, 'start_y': 0.5, 'end_y': 0.7},
    'zoom_pan_br': {'start_scale': 1.0, 'end_scale': 1.4, 'start_x': 0.5, 'end_x': 0.7, 'start_y': 0.5, 'end_y': 0.7},
    'dramatic_zoom': {'start_scale': 1.0, 'end_scale': 2.0, 'start_x': 0.5, 'end_x': 0.5, 'start_y': 0.5, 'end_y': 0.5},
    'slow_drift': {'start_scale': 1.1, 'end_scale': 1.15, 'start_x': 0.45, 'end_x': 0.55, 'start_y': 0.48, 'end_y': 0.52},
}

def ease_in_out(t):
    """Smooth easing function for natural motion"""
    return t * t * (3 - 2 * t)

def generate_frame(img_array, frame_idx, total_frames, motion):
    """Generate a single frame with camera motion applied"""
    h, w = img_array.shape[:2]
    
    # Calculate interpolation factor with easing
    t = ease_in_out(frame_idx / max(total_frames - 1, 1))
    
    # Interpolate motion parameters
    scale = motion['start_scale'] + (motion['end_scale'] - motion['start_scale']) * t
    cx = motion['start_x'] + (motion['end_x'] - motion['start_x']) * t
    cy = motion['start_y'] + (motion['end_y'] - motion['start_y']) * t
    
    # Calculate crop region
    crop_w = int(w / scale)
    crop_h = int(h / scale)
    
    # Calculate crop position (centered on cx, cy)
    x1 = int((w - crop_w) * cx)
    y1 = int((h - crop_h) * cy)
    x2 = x1 + crop_w
    y2 = y1 + crop_h
    
    # Clamp to image bounds
    x1 = max(0, min(x1, w - crop_w))
    y1 = max(0, min(y1, h - crop_h))
    x2 = x1 + crop_w
    y2 = y1 + crop_h
    
    # Crop and resize back to original dimensions
    cropped = img_array[y1:y2, x1:x2]
    
    # Resize using PIL for better quality
    pil_img = Image.fromarray(cropped)
    pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
    
    return np.array(pil_img)

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'type': 'camera_motion',
        'presets': list(MOTION_PRESETS.keys())
    })

@app.route('/presets')
def presets():
    """List available motion presets"""
    return jsonify({
        'presets': list(MOTION_PRESETS.keys()),
        'descriptions': {
            'zoom_in': 'Slowly zoom into center',
            'zoom_out': 'Slowly zoom out from center',
            'pan_left': 'Pan from right to left',
            'pan_right': 'Pan from left to right',
            'pan_up': 'Pan from bottom to top',
            'pan_down': 'Pan from top to bottom',
            'zoom_pan_tl': 'Zoom into top-left corner',
            'zoom_pan_tr': 'Zoom into top-right corner',
            'zoom_pan_bl': 'Zoom into bottom-left corner',
            'zoom_pan_br': 'Zoom into bottom-right corner',
            'dramatic_zoom': 'Dramatic 2x zoom in',
            'slow_drift': 'Subtle slow drift effect'
        }
    })

@app.route('/generate', methods=['POST'])
def generate():
    """Generate video with camera motion from an image"""
    data = request.json or {}
    
    # Get image data (base64)
    image_b64 = data.get('image')
    if not image_b64:
        return jsonify({'error': 'No image provided. Send base64 image in "image" field.'}), 400
    
    # Motion parameters
    preset = data.get('preset', 'zoom_in')
    duration = min(max(data.get('duration', 3), 1), 10)  # 1-10 seconds
    fps = min(max(data.get('fps', 24), 12), 60)  # 12-60 fps
    output_format = data.get('format', 'gif')  # gif or mp4
    
    # Custom motion (overrides preset)
    custom_motion = data.get('motion')
    
    if custom_motion:
        motion = {
            'start_scale': custom_motion.get('start_scale', 1.0),
            'end_scale': custom_motion.get('end_scale', 1.3),
            'start_x': custom_motion.get('start_x', 0.5),
            'end_x': custom_motion.get('end_x', 0.5),
            'start_y': custom_motion.get('start_y', 0.5),
            'end_y': custom_motion.get('end_y', 0.5),
        }
    else:
        motion = MOTION_PRESETS.get(preset, MOTION_PRESETS['zoom_in'])
    
    try:
        # Decode image
        if ',' in image_b64:
            image_b64 = image_b64.split(',')[1]
        
        img_data = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(img_data)).convert('RGB')
        img_array = np.array(img)
        
        # Target dimensions (ensure even for video encoding)
        target_w = (img.width // 2) * 2
        target_h = (img.height // 2) * 2
        
        if target_w != img.width or target_h != img.height:
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            img_array = np.array(img)
        
        total_frames = int(duration * fps)
        
        print(f'[{TOOL_NAME}] Generating {total_frames} frames ({duration}s @ {fps}fps), motion: {preset}')
        
        # Generate frames
        frames = []
        for i in range(total_frames):
            frame = generate_frame(img_array, i, total_frames, motion)
            frames.append(Image.fromarray(frame))
        
        # Export
        with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as f:
            output_path = f.name
        
        if output_format == 'gif':
            # Save as GIF
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=int(1000 / fps),
                loop=0,
                optimize=True
            )
        else:
            # Save as MP4 using imageio
            try:
                import imageio
                writer = imageio.get_writer(output_path, fps=fps, codec='libx264', quality=8)
                for frame in frames:
                    writer.append_data(np.array(frame))
                writer.close()
            except ImportError:
                # Fallback to GIF if imageio not available
                output_path = output_path.replace('.mp4', '.gif')
                output_format = 'gif'
                frames[0].save(
                    output_path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=int(1000 / fps),
                    loop=0
                )
        
        # Read output
        with open(output_path, 'rb') as f:
            video_b64 = base64.b64encode(f.read()).decode()
        
        # Cleanup
        os.unlink(output_path)
        del frames, img_array
        gc.collect()
        
        print(f'[{TOOL_NAME}] Video generated successfully')
        
        return jsonify({
            'success': True,
            'video': video_b64,
            'format': output_format,
            'duration': duration,
            'fps': fps,
            'frames': total_frames,
            'preset': preset
        })
        
    except Exception as e:
        print(f'[{TOOL_NAME}] Generation error: {e}')
        gc.collect()
        return jsonify({'error': str(e)}), 500

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Video Gen (Camera Motion)',
        'version': '2.0.0',
        'port': PORT,
        'description': 'Create smooth camera motion videos from images',
        'features': [
            'Ken Burns effect',
            'Multiple motion presets',
            'Custom motion paths',
            'GIF and MP4 output',
            'No GPU required'
        ],
        'presets': list(MOTION_PRESETS.keys())
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting Camera Motion Video Engine on port {PORT}...')
    print(f'[{TOOL_NAME}] Available presets: {", ".join(MOTION_PRESETS.keys())}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
