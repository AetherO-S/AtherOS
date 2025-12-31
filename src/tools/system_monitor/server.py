"""
AETHER-OS System Monitor
Real-time system metrics: CPU, RAM, GPU, Disk, Network
"""

import os
import time
import psutil
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('AETHER_PORT', 5009))
TOOL_NAME = os.environ.get('AETHER_TOOL', 'system_monitor')

# Try to import GPU monitoring
gpu_available = False
try:
    import GPUtil
    gpu_available = True
except:
    pass

# Store historical data for graphs
history = {
    'cpu': [],
    'ram': [],
    'gpu': [],
    'network_sent': [],
    'network_recv': [],
    'timestamps': []
}
MAX_HISTORY = 60  # Keep 60 data points

last_net_io = None
last_net_time = None

def get_network_speed():
    """Calculate network speed in bytes/sec"""
    global last_net_io, last_net_time
    
    current = psutil.net_io_counters()
    current_time = time.time()
    
    if last_net_io is None:
        last_net_io = current
        last_net_time = current_time
        return 0, 0
    
    time_delta = current_time - last_net_time
    if time_delta == 0:
        return 0, 0
    
    sent_speed = (current.bytes_sent - last_net_io.bytes_sent) / time_delta
    recv_speed = (current.bytes_recv - last_net_io.bytes_recv) / time_delta
    
    last_net_io = current
    last_net_time = current_time
    
    return sent_speed, recv_speed

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'tool': TOOL_NAME,
        'port': PORT,
        'gpu_monitoring': gpu_available
    })

@app.route('/stats')
def get_stats():
    """Get current system statistics"""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_freq = psutil.cpu_freq()
    cpu_count = psutil.cpu_count()
    cpu_count_physical = psutil.cpu_count(logical=False)
    
    # Per-core CPU
    cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
    
    # Memory
    memory = psutil.virtual_memory()
    
    # Disk
    disk = psutil.disk_usage('/')
    
    # Network
    net_sent, net_recv = get_network_speed()
    net_io = psutil.net_io_counters()
    
    # GPU (if available)
    gpu_data = None
    if gpu_available:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                gpu_data = {
                    'name': gpu.name,
                    'load': gpu.load * 100,
                    'memory_used': gpu.memoryUsed,
                    'memory_total': gpu.memoryTotal,
                    'memory_percent': (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal > 0 else 0,
                    'temperature': gpu.temperature
                }
        except:
            pass
    
    # Update history
    history['cpu'].append(cpu_percent)
    history['ram'].append(memory.percent)
    if gpu_data:
        history['gpu'].append(gpu_data['load'])
    history['network_sent'].append(net_sent)
    history['network_recv'].append(net_recv)
    history['timestamps'].append(time.time())
    
    # Trim history
    for key in history:
        if len(history[key]) > MAX_HISTORY:
            history[key] = history[key][-MAX_HISTORY:]
    
    # Processes
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            pinfo = proc.info
            if pinfo['cpu_percent'] > 0 or pinfo['memory_percent'] > 0.1:
                processes.append(pinfo)
        except:
            pass
    
    # Sort by CPU usage
    processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
    processes = processes[:10]  # Top 10
    
    return jsonify({
        'cpu': {
            'percent': cpu_percent,
            'per_core': cpu_per_core,
            'frequency': cpu_freq.current if cpu_freq else None,
            'cores': cpu_count,
            'physical_cores': cpu_count_physical
        },
        'memory': {
            'percent': memory.percent,
            'used': memory.used,
            'total': memory.total,
            'available': memory.available
        },
        'disk': {
            'percent': disk.percent,
            'used': disk.used,
            'total': disk.total,
            'free': disk.free
        },
        'network': {
            'sent_speed': net_sent,
            'recv_speed': net_recv,
            'total_sent': net_io.bytes_sent,
            'total_recv': net_io.bytes_recv
        },
        'gpu': gpu_data,
        'top_processes': processes,
        'history': {
            'cpu': history['cpu'][-30:],
            'ram': history['ram'][-30:],
            'gpu': history['gpu'][-30:] if history['gpu'] else [],
            'network_sent': history['network_sent'][-30:],
            'network_recv': history['network_recv'][-30:]
        }
    })

@app.route('/processes')
def get_processes():
    """Get all running processes"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
        try:
            pinfo = proc.info
            processes.append(pinfo)
        except:
            pass
    
    processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
    return jsonify({'processes': processes[:50]})

@app.route('/info')
def info():
    return jsonify({
        'name': TOOL_NAME,
        'displayName': 'System Monitor',
        'version': '1.0.0',
        'port': PORT,
        'description': 'Real-time system monitoring'
    })

if __name__ == '__main__':
    print(f'[{TOOL_NAME}] Starting System Monitor on port {PORT}...')
    print(f'[{TOOL_NAME}] GPU monitoring: {gpu_available}')
    print(f'[{TOOL_NAME}] Running on http://127.0.0.1:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
