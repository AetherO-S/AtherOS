"""
AETHER-OS Data Grid Server
A Flask server for spreadsheet/CSV operations
"""

import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5002))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'spreadsheet_engine')

# In-memory storage for demo purposes
spreadsheets = {}

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT
    })

@app.route('/sheets', methods=['GET'])
def list_sheets():
    """List all loaded spreadsheets"""
    return jsonify({
        'sheets': list(spreadsheets.keys()),
        'count': len(spreadsheets)
    })

@app.route('/sheets/<name>', methods=['GET'])
def get_sheet(name):
    """Get a spreadsheet by name"""
    if name not in spreadsheets:
        return jsonify({'error': 'Sheet not found'}), 404
    return jsonify(spreadsheets[name])

@app.route('/sheets/<name>', methods=['POST'])
def create_sheet(name):
    """Create a new spreadsheet"""
    data = request.json or {}
    rows = data.get('rows', 10)
    cols = data.get('cols', 10)
    
    # Create empty grid
    grid = [['' for _ in range(cols)] for _ in range(rows)]
    spreadsheets[name] = {
        'name': name,
        'rows': rows,
        'cols': cols,
        'data': grid
    }
    
    return jsonify({'success': True, 'sheet': spreadsheets[name]})

@app.route('/sheets/<name>/cell', methods=['PUT'])
def update_cell(name):
    """Update a cell value"""
    if name not in spreadsheets:
        return jsonify({'error': 'Sheet not found'}), 404
    
    data = request.json or {}
    row = data.get('row', 0)
    col = data.get('col', 0)
    value = data.get('value', '')
    
    try:
        spreadsheets[name]['data'][row][col] = value
        return jsonify({'success': True})
    except IndexError:
        return jsonify({'error': 'Cell out of bounds'}), 400

@app.route('/load/csv', methods=['POST'])
def load_csv():
    """Load a CSV file (expects file path or raw data)"""
    try:
        import pandas as pd
        data = request.json or {}
        
        if 'path' in data:
            df = pd.read_csv(data['path'])
        elif 'content' in data:
            from io import StringIO
            df = pd.read_csv(StringIO(data['content']))
        else:
            return jsonify({'error': 'No path or content provided'}), 400
        
        name = data.get('name', 'imported')
        spreadsheets[name] = {
            'name': name,
            'rows': len(df),
            'cols': len(df.columns),
            'columns': df.columns.tolist(),
            'data': df.values.tolist()
        }
        
        return jsonify({'success': True, 'sheet': spreadsheets[name]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/info')
def info():
    """Get tool information"""
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'Data Grid',
        'version': '1.0.0',
        'port': PORT,
        'endpoints': ['/health', '/sheets', '/load/csv', '/info']
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting Data Grid on port {PORT}...')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
