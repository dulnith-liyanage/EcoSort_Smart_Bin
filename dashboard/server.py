"""Dependency-free LAN dashboard; no motors or camera are opened at startup."""
import argparse
import csv
from dataclasses import asdict
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

from .bridge import PREFIX
import servo_settings

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).with_name('web')
CATEGORIES = [
    {'key': 'paper', 'name': 'Paper & cardboard', 'position': 'Front-left', 'logical_pan': 135, 'logical_tilt': 35},
    {'key': 'plastic', 'name': 'Rigid plastic', 'position': 'Front-right', 'logical_pan': 45, 'logical_tilt': 35},
    {'key': 'metal', 'name': 'Metal cans', 'position': 'Rear-left', 'logical_pan': 45, 'logical_tilt': 145},
    {'key': 'food', 'name': 'Fruit & veg scraps', 'position': 'Rear-right', 'logical_pan': 135, 'logical_tilt': 145},
]


class EventStore:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at REAL NOT NULL, category TEXT NOT NULL, score REAL, mode TEXT NOT NULL, status TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def add(self, category, score, mode, status='command_completed'):
        if category not in {c['key'] for c in CATEGORIES}:
            raise ValueError('Invalid category')
        with self.connect() as db:
            db.execute('INSERT INTO events (at,category,score,mode,status) VALUES (?,?,?,?,?)',
                       (time.time(), category, score, mode, status))

    def rows(self, limit=250):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (limit,))]

    def counts(self, mode):
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        with self.connect() as db:
            counts = dict(db.execute('SELECT category,COUNT(*) FROM events WHERE at >= ? AND mode = ? GROUP BY category', (midnight, mode)))
        return {c['key']: counts.get(c['key'], 0) for c in CATEGORIES}


def read_health():
    result = {'temperature': None, 'memory_percent': None, 'load': None,
              'uptime': None, 'throttled': None, 'disk_percent': None}
    try:
        result['temperature'] = round(float(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000, 1)
    except (OSError, ValueError):
        pass
    try:
        memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        result['memory_percent'] = round(100 * (1 - int(memory['MemAvailable'].split()[0]) / int(memory['MemTotal'].split()[0])), 1)
        result['uptime'] = float(Path('/proc/uptime').read_text().split()[0])
    except (OSError, ValueError, KeyError, ZeroDivisionError):
        pass
    try:
        result['load'] = round(os.getloadavg()[0], 2)
        disk = shutil.disk_usage(ROOT)
        result['disk_percent'] = round(100 * disk.used / disk.total, 1)
    except (OSError, AttributeError):
        pass
    executable = shutil.which('vcgencmd')
    if executable:
        try:
            raw = subprocess.run([executable, 'get_throttled'], capture_output=True,
                                 text=True, timeout=2, check=True).stdout.strip().split('=')[-1]
            flags = int(raw, 16)
            result['throttled'] = {'raw': raw, 'undervoltage_now': bool(flags & 1),
                                   'undervoltage_recorded': bool(flags & (1 << 16)),
                                   'throttled_now': bool(flags & 4),
                                   'throttled_recorded': bool(flags & (1 << 18))}
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return result


class Dashboard:
    def __init__(self, data_dir, demo=False, allow_hardware=False):
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.store = EventStore(data_dir / 'history.sqlite3')
        ram = '/dev/shm' if Path('/dev/shm').is_dir() else None
        self.runtime = Path(tempfile.mkdtemp(prefix='ecosort-dashboard-', dir=ram))
        self.frame_path = self.runtime / 'frame.jpg'
        self.demo = demo
        self.allow_hardware = allow_hardware and not demo
        self.lock = threading.RLock()
        self.process = None
        self.session_mode = 'demo' if demo else 'observe'
        self.state = {'phase': 'idle', 'paused': True, 'scores': {}, 'category': None,
                      'score': None, 'fps': 0, 'frame_at': None, 'message': 'Start a camera session to observe the tray.',
                      'inference_ms': None, 'stable': 0, 'model': 'clip'}
        self.health = {}
        self.health_at = 0.0
        self.started = time.time()
        self.demo_index = 0

    def snapshot(self):
        with self.lock:
            if time.monotonic() - self.health_at > 10:
                self.health = read_health()
                self.health_at = time.monotonic()
            try:
                calibration = servo_settings.load_calibration()
                routes = [{**c, 'pan': calibration.pan(c['logical_pan']),
                           'tilt': calibration.tilt(c['logical_tilt'])} for c in CATEGORIES]
                config = asdict(calibration)
                config['error'] = None
            except (OSError, ValueError, KeyError) as error:
                config = {'error': str(error)}
                routes = CATEGORIES
            return {'demo': self.demo, 'hardware_allowed': self.allow_hardware,
                    'mode': self.session_mode, 'state': dict(self.state), 'health': dict(self.health),
                    'calibration': config, 'categories': routes,
                    'counts': self.store.counts(self.session_mode), 'events': self.store.rows(),
                    'server_uptime': time.time() - self.started, 'hostname': socket.gethostname(),
                    'settings': {'threshold': 0.60, 'margin': 0.15, 'stable_frames': 3, 'cooldown': 3.8}}

    def _reader(self, process, mode=None):
        error_seen = False
        mode = mode or self.session_mode
        for line in process.stdout:
            if PREFIX not in line:
                continue
            try:
                message = json.loads(line.split(PREFIX, 1)[1])
                kind = message.pop('kind')
                with self.lock:
                    if self.process is not process:
                        continue
                    if kind == 'state' and not error_seen:
                        self.state.update(message)
                    elif kind == 'frame':
                        self.state['frame_at'] = message['at']
                    elif kind == 'sort':
                        self.store.add(message['category'], message['score'], mode)
                    elif kind == 'error':
                        error_seen = True
                        self.state.update(phase='error', paused=True, message=message['message'])
            except (ValueError, KeyError):
                continue
        code = process.wait()
        with self.lock:
            if self.process is process:
                self.state.update(paused=True, fps=0, frame_at=None)
                if not error_seen:
                    self.state.update(phase='idle' if code == 0 else 'error',
                                      message='Session stopped. Camera released.' if code == 0 else 'Session exited. Check the Pi terminal for details.')

    def command(self, action, mode=None):
        with self.lock:
            if self.demo:
                return self._demo_command(action)
            active = self.process is not None and self.process.poll() is None
            if action == 'start':
                if active:
                    raise ValueError('A session is already running.')
                if mode not in {'observe', 'hardware'}:
                    raise ValueError('Choose observe or hardware mode.')
                if mode == 'hardware' and not self.allow_hardware:
                    raise ValueError('Physical control is disabled on this server.')
                self.session_mode = mode
                self.frame_path.unlink(missing_ok=True)
                self.state.update(phase='loading', paused=True, scores={}, category=None,
                                  score=None, frame_at=None, inference_ms=None, stable=0,
                                  message='Loading cached CLIP model; keep the tray empty.')
                args = [sys.executable, '-u', '-m', 'dashboard.worker', '--frame-path', str(self.frame_path),
                        '--headless', '--driver', 'rpi-i2c' if mode == 'hardware' else 'sim', '--cpu-threads', '1']
                try:
                    self.process = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE,
                                                    stdout=subprocess.PIPE, text=True, bufsize=1)
                except OSError:
                    self.state.update(phase='error', paused=True, message='Could not start the camera worker. Check the Pi terminal.')
                    raise
                threading.Thread(target=self._reader, args=(self.process, mode), daemon=True).start()
            elif action in {'pause', 'resume', 'scan', 'recalibrate', 'stop'}:
                if not active:
                    raise ValueError('Start a session first.')
                if self.state['phase'] in {'loading', 'stopping'} and action != 'stop':
                    raise ValueError('Wait for the current transition to finish.')
                if action == 'recalibrate' and (not self.state['paused'] or self.state['phase'] in {'sorting', 'cooldown'}):
                    raise ValueError('Pause routing and wait for the current cycle to finish before resetting the tray reference.')
                if action == 'stop':
                    self.state.update(phase='stopping', message='Stopping at the next cycle boundary; a running cycle finishes first.')
                elif action == 'pause':
                    self.state['message'] = 'Pause requested; a running cycle finishes first.'
                self.process.stdin.write(json.dumps({'action': action}) + '\n')
                self.process.stdin.flush()
            else:
                raise ValueError('Unknown action.')
            return {'ok': True}

    def _demo_command(self, action):
        if action == 'start':
            self.state.update(phase='observing', paused=True, message='Sample session ready. No camera or motors are connected.')
        elif action == 'resume':
            self.state.update(paused=False, phase='ready', message='Demo routes enabled. Use Run sample to add a simulated event.')
        elif action == 'pause':
            self.state.update(paused=True, phase='observing', message='Demo routing paused.')
        elif action == 'stop':
            self.state.update(phase='idle', paused=True, scores={}, category=None, score=None,
                              message='Demo session stopped.')
        elif action == 'recalibrate':
            self.state.update(message='Sample empty-tray reference reset.', scores={}, category=None, score=None)
        elif action == 'scan':
            key = CATEGORIES[self.demo_index % 4]['key']
            self.demo_index += 1
            scores = {c['key']: (0.82 if c['key'] == key else 0.04) for c in CATEGORIES}
            scores['unknown'] = 0.06
            self.state.update(category=key, score=.82, scores=scores, inference_ms=246,
                              stable=3, message='Sample classification. Relative match score, not measured accuracy.')
            if not self.state['paused']:
                self.store.add(key, .82, 'demo', 'simulated')
        else:
            raise ValueError('Unknown action.')
        return {'ok': True}

    def close(self):
        with self.lock:
            process = self.process
            if process is not None and process.poll() is None:
                try:
                    process.stdin.write('{"action":"stop"}\n')
                    process.stdin.flush()
                except (OSError, ValueError):
                    pass
        if process is not None:
            try:
                process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                # Never kill an in-flight motor cycle. Closing stdin also requests a stop.
                process.stdin.close()
                print('Worker is still finishing; wait for its shutdown message before restarting.')
                return
        shutil.rmtree(self.runtime, ignore_errors=True)


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app, access_code):
        self.app = app
        self.access_code = access_code
        self.session_token = secrets.token_urlsafe(32)
        self.login_failures = {}
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = 'EcoSort/1.0'

    def log_message(self, *_):
        pass  # Do not log access codes, session cookies or camera URLs.

    def _send(self, data, content_type='application/json', status=200, extra=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, allow_nan=False).encode()
        elif isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _authenticated(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            value = cookie.get('ecosort_session')
            return value is not None and secrets.compare_digest(value.value, self.server.session_token)
        except Exception:
            return False

    def do_GET(self):
        path = urlsplit(self.path).path
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path in files:
            name, mime = files[path]
            return self._send((WEB / name).read_bytes(), mime)
        if not self._authenticated():
            return self._send({'error': 'Sign in with the access code from the Pi terminal.'}, status=401)
        if path == '/api/state':
            return self._send(self.server.app.snapshot())
        if path == '/api/frame.jpg':
            frame = self.server.app.frame_path
            if not frame.exists():
                return self._send({'error': 'No camera frame available.'}, status=404)
            return self._send(frame.read_bytes(), 'image/jpeg')
        if path == '/api/history.csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Time (local ISO 8601)', 'Category', 'Relative match score', 'Mode', 'Outcome'])
            for row in self.server.app.store.rows(limit=10000):
                writer.writerow([datetime.fromtimestamp(row['at']).astimezone().isoformat(), row['category'], row['score'], row['mode'], row['status']])
            return self._send(output.getvalue(), 'text/csv; charset=utf-8', extra={'Content-Disposition': 'attachment; filename="ecosort-history.csv"'})
        return self._send({'error': 'Not found'}, status=404)

    def do_POST(self):
        # A custom header blocks cross-site form posts even on browsers without Origin.
        origin = self.headers.get('Origin')
        expected = 'http://' + self.headers.get('Host', '')
        if self.headers.get('X-EcoSort-Request') != '1' or (origin and origin != expected):
            return self._send({'error': 'Same-origin request required.'}, status=403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2048:
                raise ValueError('Invalid request size.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Expected a JSON object.')
        except (ValueError, json.JSONDecodeError):
            return self._send({'error': 'Invalid JSON request.'}, status=400)
        path = urlsplit(self.path).path
        if path == '/api/login':
            ip = self.client_address[0]
            attempts, since = self.server.login_failures.get(ip, (0, time.monotonic()))
            if time.monotonic() - since > 60:
                attempts, since = 0, time.monotonic()
            if attempts >= 10:
                return self._send({'error': 'Too many attempts. Wait one minute.'}, status=429)
            code = body.get('code', '')
            if not isinstance(code, str) or not secrets.compare_digest(code.encode(), self.server.access_code.encode()):
                self.server.login_failures[ip] = (attempts + 1, since)
                return self._send({'error': 'Access code does not match.'}, status=401)
            self.server.login_failures.pop(ip, None)
            return self._send({'ok': True}, extra={'Set-Cookie': 'ecosort_session=' + self.server.session_token + '; HttpOnly; SameSite=Strict; Path=/'})
        if not self._authenticated():
            return self._send({'error': 'Sign in first.'}, status=401)
        if path == '/api/command':
            try:
                return self._send(self.server.app.command(body.get('action'), body.get('mode')))
            except (ValueError, OSError) as error:
                return self._send({'error': str(error)}, status=409)
        return self._send({'error': 'Not found'}, status=404)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1', help='Use 0.0.0.0 for trusted local Wi-Fi access.')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--demo', action='store_true', help='Interactive sample data, no model, camera or motors.')
    parser.add_argument('--allow-hardware-controls', action='store_true', help='Permit explicitly requested physical sessions; starting one commands HOME.')
    parser.add_argument('--data-dir', default=str(Path.home() / '.local/share/ecosort-dashboard'))
    args = parser.parse_args()
    access_code = os.environ.get('ECOSORT_DASHBOARD_CODE') or secrets.token_urlsafe(9)
    if len(access_code) < 8:
        parser.error('ECOSORT_DASHBOARD_CODE must have at least eight characters.')
    app = Dashboard(args.data_dir, args.demo, args.allow_hardware_controls)
    server = DashboardServer((args.host, args.port), app, access_code)
    print(f'EcoSort dashboard: http://{args.host}:{server.server_port}', flush=True)
    print(f'Access code: {access_code}', flush=True)
    print('Dashboard started; no camera or motor session started. Use a trusted LAN or SSH tunnel.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()


if __name__ == '__main__':
    main()
