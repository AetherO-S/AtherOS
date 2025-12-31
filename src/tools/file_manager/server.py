"""
AETHER-OS File Manager
Local file management with semantic search capabilities
Uses sentence-transformers for embeddings

Features:
- File browsing
- File search (name and content)
- Semantic search using embeddings
- File operations (copy, move, delete)
"""

import os
import json
import hashlib
import shutil
import mimetypes
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5007))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'file_manager')

# Default root directories to browse
HOME_DIR = Path.home()
INDEXED_DIRS = [HOME_DIR / 'Documents', HOME_DIR / 'Downloads', HOME_DIR / 'Desktop']

# Embedding model for semantic search
embedder = None
file_index = {}  # path -> embedding
INDEX_FILE = Path(__file__).parent / 'file_index.json'

def load_embedder():
    """Load the sentence transformer model"""
    global embedder
    if embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            # all-MiniLM-L6-v2 is fast and good quality (~80MB)
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
            print(f'[{TOOL_NAME}] Embedding model loaded')
        except Exception as e:
            print(f'[{TOOL_NAME}] Could not load embedder: {e}')
    return embedder is not None

def get_file_info(path):
    """Get file information"""
    path = Path(path)
    try:
        stat = path.stat()
        return {
            'name': path.name,
            'path': str(path),
            'is_dir': path.is_dir(),
            'size': stat.st_size if not path.is_dir() else None,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'extension': path.suffix.lower() if path.is_file() else None,
            'mime_type': mimetypes.guess_type(str(path))[0]
        }
    except Exception as e:
        return {'name': path.name, 'path': str(path), 'error': str(e)}

def read_text_file(path, max_chars=10000):
    """Read text content from a file"""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(max_chars)
    except:
        return None

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'home_dir': str(HOME_DIR),
        'embedder_loaded': embedder is not None,
        'indexed_files': len(file_index)
    })

@app.route('/browse')
def browse():
    """Browse directory contents"""
    path = request.args.get('path', str(HOME_DIR))
    show_hidden = request.args.get('hidden', 'false').lower() == 'true'
    
    path = Path(path)
    if not path.exists():
        return jsonify({'error': 'Path does not exist'}), 404
    
    if not path.is_dir():
        return jsonify({'error': 'Path is not a directory'}), 400
    
    try:
        items = []
        for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if not show_hidden and item.name.startswith('.'):
                continue
            items.append(get_file_info(item))
        
        return jsonify({
            'path': str(path),
            'parent': str(path.parent) if path != path.parent else None,
            'items': items,
            'count': len(items)
        })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/info')
def file_info():
    """Get detailed file information"""
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    path = Path(path)
    if not path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    info = get_file_info(path)
    
    # Add preview for text files
    if path.is_file() and info.get('mime_type', '').startswith('text/'):
        info['preview'] = read_text_file(path, 1000)
    
    return jsonify(info)

@app.route('/search')
def search():
    """Search for files by name"""
    query = request.args.get('q', '')
    path = request.args.get('path', str(HOME_DIR))
    max_results = int(request.args.get('limit', 50))
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    path = Path(path)
    results = []
    query_lower = query.lower()
    
    try:
        for root, dirs, files in os.walk(path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for name in files + dirs:
                if query_lower in name.lower():
                    full_path = Path(root) / name
                    results.append(get_file_info(full_path))
                    
                    if len(results) >= max_results:
                        return jsonify({
                            'query': query,
                            'results': results,
                            'truncated': True
                        })
        
        return jsonify({
            'query': query,
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/semantic-search', methods=['POST'])
def semantic_search():
    """Search files by meaning using embeddings"""
    if not load_embedder():
        return jsonify({'error': 'Embedding model not available'}), 503
    
    data = request.json or {}
    query = data.get('query', '')
    path = data.get('path', str(HOME_DIR / 'Documents'))
    max_results = data.get('limit', 20)
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    # Get query embedding
    query_embedding = embedder.encode(query)
    
    # Search through text files
    results = []
    path = Path(path)
    
    text_extensions = {'.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.csv', '.log'}
    
    try:
        import numpy as np
        
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for name in files:
                if Path(name).suffix.lower() in text_extensions:
                    full_path = Path(root) / name
                    
                    try:
                        content = read_text_file(full_path, 5000)
                        if content:
                            # Create embedding for file content
                            file_embedding = embedder.encode(content[:2000])
                            
                            # Calculate similarity
                            similarity = np.dot(query_embedding, file_embedding) / (
                                np.linalg.norm(query_embedding) * np.linalg.norm(file_embedding)
                            )
                            
                            results.append({
                                **get_file_info(full_path),
                                'similarity': float(similarity),
                                'preview': content[:200]
                            })
                    except:
                        continue
        
        # Sort by similarity
        results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        results = results[:max_results]
        
        return jsonify({
            'query': query,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/read')
def read_file():
    """Read file contents"""
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    path = Path(path)
    if not path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    if not path.is_file():
        return jsonify({'error': 'Not a file'}), 400
    
    # Check if it's a text file
    mime_type = mimetypes.guess_type(str(path))[0]
    if mime_type and mime_type.startswith('text/'):
        content = read_text_file(path, 100000)
        return jsonify({
            'path': str(path),
            'content': content,
            'mime_type': mime_type
        })
    else:
        # Return file for download
        return send_file(path)

@app.route('/copy', methods=['POST'])
def copy_file():
    """Copy a file or directory"""
    data = request.json or {}
    src = data.get('src')
    dst = data.get('dst')
    
    if not src or not dst:
        return jsonify({'error': 'Source and destination required'}), 400
    
    src = Path(src)
    dst = Path(dst)
    
    if not src.exists():
        return jsonify({'error': 'Source not found'}), 404
    
    try:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        
        return jsonify({'success': True, 'path': str(dst)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/move', methods=['POST'])
def move_file():
    """Move a file or directory"""
    data = request.json or {}
    src = data.get('src')
    dst = data.get('dst')
    
    if not src or not dst:
        return jsonify({'error': 'Source and destination required'}), 400
    
    src = Path(src)
    dst = Path(dst)
    
    if not src.exists():
        return jsonify({'error': 'Source not found'}), 404
    
    try:
        shutil.move(str(src), str(dst))
        return jsonify({'success': True, 'path': str(dst)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete', methods=['POST'])
def delete_file():
    """Delete a file or directory"""
    data = request.json or {}
    path = data.get('path')
    
    if not path:
        return jsonify({'error': 'Path required'}), 400
    
    path = Path(path)
    
    if not path.exists():
        return jsonify({'error': 'Path not found'}), 404
    
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/mkdir', methods=['POST'])
def make_directory():
    """Create a new directory"""
    data = request.json or {}
    path = data.get('path')
    
    if not path:
        return jsonify({'error': 'Path required'}), 400
    
    path = Path(path)
    
    try:
        path.mkdir(parents=True, exist_ok=True)
        return jsonify({'success': True, 'path': str(path)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/info')
def api_info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'File Manager',
        'version': '1.0.0',
        'port': PORT,
        'description': 'File browser with semantic search',
        'features': ['browse', 'search', 'semantic-search', 'file-ops']
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting File Manager on port {PORT}...')
    print(f'[{TOOL_NAME}] Home directory: {HOME_DIR}')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
