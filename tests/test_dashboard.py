"""Offline dashboard tests: request parsing, persistence and motor gating."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dashboard.bridge import DashboardBridge, PREFIX
from dashboard.server import Dashboard, DashboardServer, Handler, EventStore


class FakeConnection:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()
    def makefile(self, *_):
        return self.input
    def sendall(self, data):
        self.output.write(data)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = Dashboard(self.directory.name, demo=True)
        self.addCleanup(self.app.close)
        self.server = SimpleNamespace(app=self.app, access_code='test-access-code',
                                      session_token='test-session-token', login_failures={})

    def request(self, path, method='GET', body=None, cookie=False, origin=None, custom=True):
        payload = json.dumps(body).encode() if body is not None else b''
        headers = [f'{method} {path} HTTP/1.0', 'Host: localhost:8080', f'Content-Length: {len(payload)}']
        if cookie:
            headers.append('Cookie: ecosort_session=test-session-token')
        if origin:
            headers.append(f'Origin: {origin}')
        if custom:
            headers.append('X-EcoSort-Request: 1')
        request = ('\r\n'.join(headers) + '\r\n\r\n').encode() + payload
        connection = FakeConnection(request)
        Handler(connection, ('127.0.0.1', 1234), self.server)
        head, body = connection.output.getvalue().split(b'\r\n\r\n', 1)
        return int(head.split(b' ')[1]), head.decode(), body

    def test_api_camera_and_export_require_authentication(self):
        for path in ['/api/state', '/api/frame.jpg', '/api/history.csv']:
            self.assertEqual(self.request(path)[0], 401)
        status, _, data = self.request('/api/state', cookie=True)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)['demo'])

    def test_login_cookie_and_rate_limit(self):
        status, headers, _ = self.request('/api/login', 'POST', {'code':'test-access-code'})
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly; SameSite=Strict', headers)
        for _ in range(10):
            self.assertEqual(self.request('/api/login','POST',{'code':'wrong'})[0], 401)
        self.assertEqual(self.request('/api/login','POST',{'code':'wrong'})[0], 429)

    def test_cross_origin_and_form_posts_are_rejected(self):
        for origin, custom in [('http://evil.example',True),(None,False)]:
            self.assertEqual(self.request('/api/command','POST',{'action':'start'},cookie=True,
                                          origin=origin,custom=custom)[0],403)
        self.assertEqual(self.request('/api/command','POST',{'action':'start'},cookie=False)[0],401)

    def test_simulated_cycles_are_persistent_and_separate_from_hardware(self):
        self.app.command('start')
        self.app.command('scan')
        self.assertEqual(self.app.store.rows(), [])  # observation alone does not count
        self.app.command('resume')
        self.app.command('scan')
        self.assertEqual(sum(self.app.store.counts('demo').values()), 1)
        self.assertEqual(sum(self.app.store.counts('hardware').values()), 0)
        reopened = EventStore(Path(self.directory.name) / 'history.sqlite3')
        self.assertEqual(reopened.rows()[0]['mode'], 'demo')
        _, _, export = self.request('/api/history.csv',cookie=True)
        self.assertIn(b'simulated', export)
        self.assertIn(b'Relative match score', export)

    def test_static_allowlist_blocks_traversal_and_sets_csp(self):
        self.assertEqual(self.request('/../servo_calibration.json',cookie=True)[0],404)
        status, headers, body=self.request('/')
        self.assertEqual(status,200)
        self.assertIn('frame-ancestors',headers)
        self.assertIn(b'EcoSort',body)

    def test_hardware_is_opt_in_and_startup_does_not_launch_worker(self):
        with patch('dashboard.server.subprocess.Popen') as process:
            app=Dashboard(Path(self.directory.name)/'real')
            try:
                process.assert_not_called()
                with self.assertRaisesRegex(ValueError,'disabled'):
                    app.command('start','hardware')
                process.assert_not_called()
            finally:
                app.close()

    def test_failed_worker_launch_allows_retry(self):
        app=Dashboard(Path(self.directory.name)/'launch-error')
        self.addCleanup(app.close)
        with patch('dashboard.server.subprocess.Popen', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError):
                app.command('start','observe')
        self.assertEqual(app.state['phase'],'error')

    def test_worker_errors_survive_shutdown_and_do_not_increment_counts(self):
        app=Dashboard(Path(self.directory.name)/'errors')
        self.addCleanup(app.close)
        process=SimpleNamespace(stdout=[PREFIX+'{"kind":"error","message":"camera failed"}\n',
                                         PREFIX+'{"kind":"state","phase":"idle"}\n'],
                                wait=lambda **kw:1,poll=lambda:1)
        app.process=process
        app._reader(process)
        self.assertEqual(app.state['phase'],'error')
        self.assertEqual(app.store.rows(),[])


class BridgeTests(unittest.TestCase):
    def test_eof_disables_routing_and_requests_stop(self):
        bridge=DashboardBridge.__new__(DashboardBridge)
        bridge.paused=False;bridge.stopping=False
        import queue
        bridge.commands=queue.Queue()
        bridge._read_commands(io.StringIO())
        self.assertTrue(bridge.stopping)
        self.assertTrue(bridge.paused)

    def test_pause_received_during_inference_is_immediate(self):
        bridge=DashboardBridge.__new__(DashboardBridge)
        bridge.paused=False;bridge.stopping=False
        import queue
        bridge.commands=queue.Queue()
        # The command reader sets the pause flag before the main-loop poll.
        bridge._read_commands(io.StringIO('{"action":"pause"}\n'))
        self.assertTrue(bridge.paused)
        self.assertIn('pause',bridge.poll())

    def test_dashboard_pause_blocks_eligible_sort_in_actual_loop(self):
        self.run_runtime(paused=True)

    def test_dashboard_enabled_session_records_completed_route(self):
        self.run_runtime(paused=False)

    def run_runtime(self, paused):
        import numpy as np
        import live_smart_bin as live
        empty=np.zeros((480,640,3),dtype=np.uint8)
        occupied=np.full_like(empty,255)
        camera=SimpleNamespace(read=Mock(side_effect=[(True,empty.copy()) for _ in range(30)] +
                                          [(True,occupied.copy()) for _ in range(5)]+[(False,None)]),
                               is_opened=lambda:True,release=Mock())
        scores={'paper':.9,'plastic':.025,'metal':.025,'food':.025,'unknown':.025}
        classifier=SimpleNamespace(categories=list(scores),dev_desc='FAKE',predict=Mock(return_value=('paper',.9,scores)))
        controller=SimpleNamespace(trigger_sort=Mock(),close=Mock(),status_str='SIMULATION')
        bridge=SimpleNamespace(paused=paused,stopping=False,poll=lambda:[],emit=Mock(),frame=Mock())
        with patch.object(live,'ClipClassifier',return_value=classifier), \
             patch.object(live,'CameraCapture',return_value=camera), \
             patch.object(live,'init_hardware_controller',return_value=controller), \
             patch('sys.argv',['live_smart_bin.py','--headless','--driver','sim']), \
             patch.object(live.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
            live.main(bridge=bridge)
        self.assertGreaterEqual(classifier.predict.call_count,3)
        if paused:
            controller.trigger_sort.assert_not_called()
        else:
            controller.trigger_sort.assert_called_once()
        camera.release.assert_called_once()
        controller.close.assert_called_once()
        self.assertEqual(any(c.args[0]=='sort' for c in bridge.emit.call_args_list), not paused)


if __name__=='__main__':
    unittest.main()
