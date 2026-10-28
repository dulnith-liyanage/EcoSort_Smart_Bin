"""Offline dashboard tests: LAN access, boot sequencing, persistence and motor gating."""
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
        self.server = SimpleNamespace(app=self.app, allowed_names={'localhost', 'ecosort.local'})

    def request(self, path, method='GET', body=None, cookie=False, origin=None, custom=True, host='localhost:8080', peer='127.0.0.1'):
        payload = json.dumps(body).encode() if body is not None else b''
        headers = [f'{method} {path} HTTP/1.0', f'Host: {host}', f'Content-Length: {len(payload)}']
        if cookie:
            headers.append('Cookie: ecosort_session=test-session-token')
        if origin:
            headers.append(f'Origin: {origin}')
        if custom:
            headers.append('X-EcoSort-Request: 1')
        request = ('\r\n'.join(headers) + '\r\n\r\n').encode() + payload
        connection = FakeConnection(request)
        Handler(connection, (peer, 1234), self.server)
        head, body = connection.output.getvalue().split(b'\r\n\r\n', 1)
        return int(head.split(b' ')[1]), head.decode(), body

    def test_local_api_and_export_need_no_code_or_cookie(self):
        status, _, data = self.request('/api/state')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)['demo'])
        self.assertEqual(self.request('/api/history.csv')[0], 200)
        self.assertEqual(self.request('/api/frame.jpg')[0], 404)
        self.assertEqual(self.request('/api/login', 'POST', {'code':'anything'})[0], 404)

    def test_public_clients_and_unknown_hostnames_are_rejected(self):
        self.assertEqual(self.request('/api/state', peer='8.8.8.8')[0], 403)
        self.assertEqual(self.request('/api/state', host='evil.example:8080')[0], 403)
        self.assertEqual(self.request('/api/state', host='ecosort.local:8080')[0], 200)
        self.assertEqual(self.request('/api/state', host='192.168.8.159:8080')[0], 200)

    def test_cross_origin_and_form_posts_are_rejected(self):
        for origin, custom in [('http://evil.example',True),(None,False)]:
            self.assertEqual(self.request('/api/command','POST',{'action':'start'},cookie=True,
                                          origin=origin,custom=custom)[0],403)
        self.assertEqual(self.request('/api/command','POST',{'action':'start'},cookie=False)[0],200)

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

    def test_boot_starts_camera_without_waiting_for_a_browser(self):
        app=Dashboard(Path(self.directory.name)/'boot', allow_hardware=True)
        self.addCleanup(app.close)
        def start(*args, **kwargs):
            app.reader_thread=Mock()
            app.reached_camera=True
        with patch.object(app,'command',side_effect=start) as command:
            app._boot_loop()
            command.assert_called_once_with('start','hardware',auto_sort=True)

    def test_initial_startup_retries_are_bounded(self):
        with patch.object(self.app,'command',side_effect=OSError('not ready')) as command, \
             patch.object(self.app.closing,'wait',return_value=False):
            self.app._boot_loop()
        self.assertEqual(command.call_count,3)

    def test_operator_cancel_prevents_boot_retry(self):
        self.app.boot_cancelled.set()
        with patch.object(self.app,'command') as command:
            self.app._boot_loop()
            command.assert_not_called()

    def test_shutdown_cancels_boot_start(self):
        self.app.closing.set()
        with patch.object(self.app,'command') as command:
            self.app._boot_loop()
            command.assert_not_called()

    def test_boot_worker_gets_auto_sort_flag_and_explicit_hardware_driver(self):
        app=Dashboard(Path(self.directory.name)/'launch',allow_hardware=True)
        self.addCleanup(app.close)
        process=Mock()
        process.poll.return_value=0
        with patch('dashboard.server.subprocess.Popen',return_value=process) as spawn, \
             patch('dashboard.server.threading.Thread'):
            app.command('start','hardware',auto_sort=True)
        command=spawn.call_args.args[0]
        self.assertIn('--auto-sort',command)
        self.assertIn('rpi-i2c',command)
        self.assertTrue(app.state['paused'])
        self.assertTrue(app.state['auto_sort'])

    def test_boot_service_quotes_paths_and_uses_existing_offline_cache(self):
        from scripts.install_dashboard_service import unit_text
        unit=unit_text('/home/en12/EcoSort project','/home/en12/EcoSort project/venv/bin/python','en12','/home/en12',['i2c','video'])
        self.assertIn('WorkingDirectory=/home/en12/EcoSort project\n',unit)
        self.assertIn('--autostart --allow-hardware-controls',unit)
        self.assertIn('Environment=HF_HUB_OFFLINE=1',unit)
        self.assertIn('KillMode=mixed',unit)
        self.assertNotIn('network-online.target',unit)
        self.assertNotIn('PrivateTmp=',unit)  # driver lock must stay shared
        with self.assertRaises(ValueError):
            unit_text('/bad\npath','/python','en12','/home/en12',[])


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

    def test_autostart_waits_for_background_calibration(self):
        bridge=DashboardBridge.__new__(DashboardBridge)
        bridge.paused=True;bridge.stopping=False;bridge.auto_sort=True
        self.assertTrue(bridge.paused)
        bridge.calibrated()
        self.assertFalse(bridge.paused)

    def test_pause_during_loading_cancels_automatic_enable(self):
        bridge=DashboardBridge.__new__(DashboardBridge)
        bridge.paused=True;bridge.stopping=False;bridge.auto_sort=True
        import queue
        bridge.commands=queue.Queue()
        bridge._read_commands(io.StringIO('{"action":"pause"}\n'))
        bridge.calibrated()
        self.assertTrue(bridge.paused)
        self.assertFalse(bridge.auto_sort)

    def test_dashboard_pause_blocks_eligible_sort_in_actual_loop(self):
        self.run_runtime(paused=True)

    def test_dashboard_enabled_session_records_completed_route(self):
        self.run_runtime(paused=False)

    def test_boot_enables_routing_after_exactly_thirty_empty_frames(self):
        self.run_runtime(paused=True, auto_start=True)

    def test_dashboard_waits_for_camera_exposure_before_learning_background(self):
        self.run_runtime(paused=True, auto_start=True, warmup=60)

    def run_runtime(self, paused, auto_start=False, warmup=0):
        import numpy as np
        import live_smart_bin as live
        empty=np.zeros((480,640,3),dtype=np.uint8)
        occupied=np.full_like(empty,255)
        camera=SimpleNamespace(read=Mock(side_effect=[(True,empty.copy()) for _ in range(30+warmup)] +
                                          [(True,occupied.copy()) for _ in range(5)]+[(False,None)]),
                               is_opened=lambda:True,release=Mock())
        scores={'paper':.9,'plastic':.025,'metal':.025,'food':.025,'unknown':.025}
        classifier=SimpleNamespace(categories=list(scores),dev_desc='FAKE',predict=Mock(return_value=('paper',.9,scores)))
        controller=SimpleNamespace(trigger_sort=Mock(),close=Mock(),status_str='SIMULATION')
        bridge=SimpleNamespace(paused=paused,stopping=False,poll=lambda:[],emit=Mock(),frame=Mock(),calibrated=Mock(),warmup_frames=warmup)
        if auto_start:
            def calibrated():
                self.assertEqual(camera.read.call_count,30+warmup)
                bridge.paused=False
            bridge.calibrated=calibrated
        with patch.object(live,'ClipClassifier',return_value=classifier), \
             patch.object(live,'CameraCapture',return_value=camera), \
             patch.object(live,'init_hardware_controller',return_value=controller), \
             patch('sys.argv',['live_smart_bin.py','--headless','--driver','sim']), \
             patch.object(live.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
            live.main(bridge=bridge)
        self.assertGreaterEqual(classifier.predict.call_count,3)
        if paused and not auto_start:
            controller.trigger_sort.assert_not_called()
        else:
            controller.trigger_sort.assert_called_once()
        camera.release.assert_called_once()
        controller.close.assert_called_once()
        self.assertEqual(any(c.args[0]=='sort' for c in bridge.emit.call_args_list), not paused or auto_start)


if __name__=='__main__':
    unittest.main()
