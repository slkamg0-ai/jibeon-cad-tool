import psutil
import platform
import time
import socket
from datetime import datetime

try:
    import GPUtil
    HAS_GPU = True
except ImportError:
    HAS_GPU = False

# Track previous network/disk I/O for delta calculation
_prev_net_io = None
_prev_disk_io = None
_prev_time = None

def get_cpu_info():
    """Returns dict with: percent (overall float), per_core (list of floats), 
    freq_current (MHz float), freq_max (MHz float), 
    cores_physical (int), cores_logical (int)"""
    freq = psutil.cpu_freq()
    return {
        'percent': psutil.cpu_percent(interval=0),
        'per_core': psutil.cpu_percent(interval=0, percpu=True),
        'freq_current': round(freq.current, 0) if freq else 0,
        'freq_max': round(freq.max, 0) if freq else 0,
        'cores_physical': psutil.cpu_count(logical=False) or 0,
        'cores_logical': psutil.cpu_count(logical=True) or 0
    }

def get_memory_info():
    """Returns dict with: total (bytes), used (bytes), available (bytes), 
    percent (float), swap_total, swap_used, swap_percent"""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        'total': vm.total,
        'used': vm.used,
        'available': vm.available,
        'percent': vm.percent,
        'swap_total': sw.total,
        'swap_used': sw.used,
        'swap_percent': sw.percent
    }

def get_disk_info():
    """Returns dict with: partitions (list of {device, mountpoint, total, used, free, percent}),
    io (dict with read_speed, write_speed in bytes/sec)"""
    global _prev_disk_io, _prev_time
    
    partitions = []
    for p in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(p.mountpoint)
            partitions.append({
                'device': p.device,
                'mountpoint': p.mountpoint,
                'fstype': p.fstype,
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': usage.percent
            })
        except (PermissionError, OSError):
            continue
    
    # Calculate I/O speed
    current_io = psutil.disk_io_counters()
    current_time = time.time()
    read_speed = 0.0
    write_speed = 0.0
    
    if _prev_disk_io and _prev_time:
        dt = current_time - _prev_time
        if dt > 0:
            read_speed = (current_io.read_bytes - _prev_disk_io.read_bytes) / dt
            write_speed = (current_io.write_bytes - _prev_disk_io.write_bytes) / dt
    
    _prev_disk_io = current_io
    _prev_time = current_time
    
    return {
        'partitions': partitions,
        'io': {
            'read_speed': round(read_speed, 0),
            'write_speed': round(write_speed, 0)
        }
    }

def get_network_info():
    """Returns dict with: upload_speed, download_speed (bytes/sec),
    bytes_sent, bytes_recv (total), connections (int)"""
    global _prev_net_io
    
    current_io = psutil.net_io_counters()
    current_time = time.time()
    upload_speed = 0.0
    download_speed = 0.0
    
    if _prev_net_io:
        dt = current_time - _prev_net_io['time']
        if dt > 0:
            upload_speed = (current_io.bytes_sent - _prev_net_io['bytes_sent']) / dt
            download_speed = (current_io.bytes_recv - _prev_net_io['bytes_recv']) / dt
    
    _prev_net_io = {
        'bytes_sent': current_io.bytes_sent,
        'bytes_recv': current_io.bytes_recv,
        'time': current_time
    }
    
    try:
        connections = len(psutil.net_connections(kind='inet'))
    except (psutil.AccessDenied, PermissionError):
        connections = -1
    
    return {
        'upload_speed': round(upload_speed, 0),
        'download_speed': round(download_speed, 0),
        'bytes_sent': current_io.bytes_sent,
        'bytes_recv': current_io.bytes_recv,
        'connections': connections
    }

def get_gpu_info():
    """Returns list of dicts with: id, name, load (%), memory_used (MB), memory_total (MB),
    memory_percent (%), temperature (C). Returns empty list if no NVIDIA GPU."""
    if not HAS_GPU:
        return []
    try:
        gpus = GPUtil.getGPUs()
        return [{
            'id': gpu.id,
            'name': gpu.name,
            'load': round(gpu.load * 100, 1),
            'memory_used': round(gpu.memoryUsed, 0),
            'memory_total': round(gpu.memoryTotal, 0),
            'memory_percent': round(gpu.memoryUsed / gpu.memoryTotal * 100, 1) if gpu.memoryTotal > 0 else 0,
            'temperature': gpu.temperature
        } for gpu in gpus]
    except Exception:
        return []

def get_process_info(sort_by='cpu', limit=10):
    """Returns list of top processes sorted by cpu or memory.
    Each dict: pid, name, cpu_percent, memory_percent, status"""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            info = p.info
            if info['cpu_percent'] is not None:
                procs.append({
                    'pid': info['pid'],
                    'name': info['name'] or 'Unknown',
                    'cpu_percent': round(info['cpu_percent'], 1),
                    'memory_percent': round(info['memory_percent'] or 0, 1),
                    'status': info['status']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    key = 'cpu_percent' if sort_by == 'cpu' else 'memory_percent'
    procs.sort(key=lambda x: x[key], reverse=True)
    return procs[:limit]

def get_system_info():
    """Returns dict with static system info: os, hostname, username, boot_time, 
    python_version, architecture, processor"""
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime_seconds = time.time() - psutil.boot_time()
    hours, rem = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(rem, 60)
    
    return {
        'os': f"{platform.system()} {platform.release()}",
        'os_version': platform.version(),
        'hostname': socket.gethostname(),
        'username': psutil.users()[0].name if psutil.users() else 'N/A',
        'boot_time': boot.strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': f"{hours}h {minutes}m {seconds}s",
        'uptime_seconds': int(uptime_seconds),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version()
    }

def get_all(sort_by='cpu'):
    """Collect all system information and return as a single dict."""
    return {
        'timestamp': datetime.now().isoformat(),
        'cpu': get_cpu_info(),
        'memory': get_memory_info(),
        'disk': get_disk_info(),
        'network': get_network_info(),
        'gpu': get_gpu_info(),
        'processes': get_process_info(sort_by=sort_by),
        'system': get_system_info()
    }
