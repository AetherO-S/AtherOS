"""
AETHER-OS Notes Board
A Milanote-style visual note-taking tool with boards and cards

Features:
- Multiple boards
- Draggable note cards
- Rich text notes
- Image cards
- Connections between cards
- Persistent storage
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5008))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'notes')

# Data storage
DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)
BOARDS_FILE = DATA_DIR / 'boards.json'

def load_boards():
    """Load all boards from disk"""
    if BOARDS_FILE.exists():
        with open(BOARDS_FILE, 'r') as f:
            return json.load(f)
    return {'boards': {}, 'active_board': None}

def save_boards(data):
    """Save all boards to disk"""
    with open(BOARDS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def create_default_board():
    """Create a default board if none exists"""
    data = load_boards()
    if not data['boards']:
        board_id = str(uuid.uuid4())[:8]
        data['boards'][board_id] = {
            'id': board_id,
            'name': 'Main Board',
            'created': datetime.now().isoformat(),
            'cards': {},
            'connections': []
        }
        data['active_board'] = board_id
        save_boards(data)
    return data

@app.route('/health')
def health():
    data = load_boards()
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'boards_count': len(data.get('boards', {}))
    })

@app.route('/boards')
def list_boards():
    """List all boards"""
    data = create_default_board()
    boards = [
        {
            'id': b['id'],
            'name': b['name'],
            'created': b['created'],
            'cards_count': len(b.get('cards', {}))
        }
        for b in data['boards'].values()
    ]
    return jsonify({
        'boards': boards,
        'active': data.get('active_board')
    })

@app.route('/boards', methods=['POST'])
def create_board():
    """Create a new board"""
    req = request.json or {}
    name = req.get('name', 'Untitled Board')
    
    data = load_boards()
    board_id = str(uuid.uuid4())[:8]
    data['boards'][board_id] = {
        'id': board_id,
        'name': name,
        'created': datetime.now().isoformat(),
        'cards': {},
        'connections': []
    }
    data['active_board'] = board_id
    save_boards(data)
    
    return jsonify({'success': True, 'board': data['boards'][board_id]})

@app.route('/boards/<board_id>')
def get_board(board_id):
    """Get a specific board with all its cards"""
    data = load_boards()
    board = data['boards'].get(board_id)
    
    if not board:
        return jsonify({'error': 'Board not found'}), 404
    
    return jsonify(board)

@app.route('/boards/<board_id>', methods=['DELETE'])
def delete_board(board_id):
    """Delete a board"""
    data = load_boards()
    
    if board_id not in data['boards']:
        return jsonify({'error': 'Board not found'}), 404
    
    del data['boards'][board_id]
    
    if data['active_board'] == board_id:
        data['active_board'] = next(iter(data['boards'].keys()), None)
    
    save_boards(data)
    return jsonify({'success': True})

@app.route('/boards/<board_id>/cards', methods=['POST'])
def create_card(board_id):
    """Create a new card on a board"""
    data = load_boards()
    board = data['boards'].get(board_id)
    
    if not board:
        return jsonify({'error': 'Board not found'}), 404
    
    req = request.json or {}
    card_id = str(uuid.uuid4())[:8]
    
    card = {
        'id': card_id,
        'type': req.get('type', 'note'),  # note, image, task, link
        'title': req.get('title', ''),
        'content': req.get('content', ''),
        'x': req.get('x', 100),
        'y': req.get('y', 100),
        'width': req.get('width', 200),
        'height': req.get('height', 150),
        'color': req.get('color', '#1a1a1a'),
        'created': datetime.now().isoformat(),
        'modified': datetime.now().isoformat()
    }
    
    board['cards'][card_id] = card
    save_boards(data)
    
    return jsonify({'success': True, 'card': card})

@app.route('/boards/<board_id>/cards/<card_id>', methods=['PUT'])
def update_card(board_id, card_id):
    """Update a card"""
    data = load_boards()
    board = data['boards'].get(board_id)
    
    if not board:
        return jsonify({'error': 'Board not found'}), 404
    
    card = board['cards'].get(card_id)
    if not card:
        return jsonify({'error': 'Card not found'}), 404
    
    req = request.json or {}
    
    # Update allowed fields
    for field in ['title', 'content', 'x', 'y', 'width', 'height', 'color', 'type']:
        if field in req:
            card[field] = req[field]
    
    card['modified'] = datetime.now().isoformat()
    save_boards(data)
    
    return jsonify({'success': True, 'card': card})

@app.route('/boards/<board_id>/cards/<card_id>', methods=['DELETE'])
def delete_card(board_id, card_id):
    """Delete a card"""
    data = load_boards()
    board = data['boards'].get(board_id)
    
    if not board:
        return jsonify({'error': 'Board not found'}), 404
    
    if card_id not in board['cards']:
        return jsonify({'error': 'Card not found'}), 404
    
    del board['cards'][card_id]
    
    # Remove any connections involving this card
    board['connections'] = [
        c for c in board['connections']
        if c['from'] != card_id and c['to'] != card_id
    ]
    
    save_boards(data)
    return jsonify({'success': True})

@app.route('/boards/<board_id>/connections', methods=['POST'])
def create_connection(board_id):
    """Create a connection between two cards"""
    data = load_boards()
    board = data['boards'].get(board_id)
    
    if not board:
        return jsonify({'error': 'Board not found'}), 404
    
    req = request.json or {}
    from_id = req.get('from')
    to_id = req.get('to')
    
    if not from_id or not to_id:
        return jsonify({'error': 'Both from and to card IDs required'}), 400
    
    if from_id not in board['cards'] or to_id not in board['cards']:
        return jsonify({'error': 'Card not found'}), 404
    
    connection = {
        'id': str(uuid.uuid4())[:8],
        'from': from_id,
        'to': to_id,
        'color': req.get('color', '#ffffff33')
    }
    
    board['connections'].append(connection)
    save_boards(data)
    
    return jsonify({'success': True, 'connection': connection})

@app.route('/boards/<board_id>/connections/<conn_id>', methods=['DELETE'])
def delete_connection(board_id, conn_id):
    """Delete a connection"""
    data = load_boards()
    board = data['boards'].get(board_id)
    
    if not board:
        return jsonify({'error': 'Board not found'}), 404
    
    board['connections'] = [c for c in board['connections'] if c['id'] != conn_id]
    save_boards(data)
    
    return jsonify({'success': True})

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Notes Board',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Visual note-taking with boards and cards'
    })

if __name__ == '__main__':
    create_default_board()
    print(f'[{TOOL_NAME}] Starting Notes Board on port {PORT}...')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
