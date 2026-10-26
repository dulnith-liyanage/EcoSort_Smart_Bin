"""Offline regressions: fake devices, no model weights or physical outputs."""
import contextlib
import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import live_smart_bin as live
import servo_control as calibration
import servo_settings

class Servo:
    def __init__(self, channel, events): self.channel, self.events = channel, events
    def set_pulse_width_range(self, *args): pass
    @property
    def angle(self): return None
    @angle.setter
    def angle(self, value): self.events.append((self.channel, value))

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        kit = SimpleNamespace(servo=[Servo(i, self.events) for i in range(16)])
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.dict(sys.modules, {'adafruit_servokit': SimpleNamespace(ServoKit=lambda **kw: kit)}))
        stack.enter_context(patch('time.sleep'))
        stack.enter_context(patch.object(servo_settings, 'acquire_device_lock', return_value=None))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(patch.object(servo_settings, 'load_calibration',
                                       return_value=servo_settings.Calibration()))

    def test_saved_tilt_home_is_used_by_manual_controller(self):
        with patch.object(servo_settings, 'load_calibration',
                          return_value=servo_settings.Calibration(90, 15)), \
             patch.object(sys, 'platform', 'darwin'):
            c = calibration.ServoPanTilt()
        c.go_home()
        self.assertEqual(self.events[-2:], [(1, 15), (0, 90)])

    def test_unreachable_sorting_is_rejected_before_any_output(self):
        with patch.object(servo_settings, 'load_calibration',
                          return_value=servo_settings.Calibration(90, 15)):
            with self.assertRaisesRegex(ValueError, 'outside'):
                live.DirectPca9685Controller()
            with self.assertRaises(ValueError):
                live.init_hardware_controller('auto')
        self.assertEqual(self.events, [])

    def test_missing_calibration_does_not_fall_back_to_simulation(self):
        with patch.object(servo_settings, 'load_calibration', side_effect=FileNotFoundError('missing calibration')):
            with self.assertRaises(FileNotFoundError):
                live.init_hardware_controller('auto')
            self.assertIsInstance(live.init_hardware_controller('sim'), live.SimulatedServoController)

    def test_read_only_calibration_check_does_not_initialise_hardware(self):
        with patch.object(servo_settings, 'load_calibration', return_value=servo_settings.Calibration(90, 15)), \
             patch.object(sys, 'argv', ['servo_control.py', '--check-calibration']), \
             patch.object(calibration.ServoPanTilt, '_init_hardware') as hardware:
            with self.assertRaises(SystemExit) as result:
                calibration.main()
        self.assertEqual(result.exception.code, 2)
        hardware.assert_not_called()

    def test_sorter_refuses_invalid_calibration_before_loading_model(self):
        with patch.object(servo_settings, 'load_calibration', return_value=servo_settings.Calibration(90, 15)), \
             patch.object(sys, 'argv', ['live_smart_bin.py', '--driver', 'rpi-i2c']), \
             patch.object(live, 'ClipClassifier') as model, \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                live.main()
        self.assertEqual(result.exception.code, 2)
        model.assert_not_called()

    def test_manual_dump_rejects_unreachable_target_without_moving(self):
        with patch.object(sys, 'platform', 'darwin'):
            c = calibration.ServoPanTilt()
        c.calibration = servo_settings.Calibration(90, 15)
        self.events.clear()
        with self.assertRaises(ValueError):
            c.dump_bin('1')
        self.assertEqual(self.events, [])

    def test_shifted_home_changes_route_shake_and_return_consistently(self):
        with patch.object(servo_settings, 'load_calibration',
                          return_value=servo_settings.Calibration(95, 85)):
            c = live.DirectPca9685Controller()
        self.events.clear()
        c.trigger_sort('paper', live.CATEGORY_CONFIG['paper'])
        self.assertIn((0, 140), self.events)
        self.assertIn((1, 30), self.events)
        self.assertIn((1, 20), self.events)
        self.assertEqual((c.current_pan, c.current_tilt), (95, 85))

    def test_asymmetric_routes_use_both_axes_and_return_to_level(self):
        saved = servo_settings.Calibration(90,15,5,70,0,0.04)
        with patch.object(servo_settings, 'load_calibration', return_value=saved):
            c = live.DirectPca9685Controller()
        for cfg in live.CATEGORY_CONFIG.values():
            self.events.clear()
            c.trigger_sort('test',cfg)
            expected = 5 if cfg['tilt'] < 90 else 70
            self.assertIn((0,cfg['pan']),self.events)
            self.assertIn((1,expected),self.events)
            self.assertTrue(all(5 <= angle <= 70 for ch,angle in self.events if ch==1))
            self.assertEqual((c.current_pan,c.current_tilt),(90,15))

    def test_competing_controller_does_not_fall_back_to_simulation(self):
        with patch.object(servo_settings, 'acquire_device_lock', side_effect=servo_settings.HardwareInUseError('busy')):
            with self.assertRaises(servo_settings.HardwareInUseError):
                live.init_hardware_controller('auto')
        self.assertEqual(self.events, [])

    def test_new_home_routes_in_both_controllers_return_level_before_pan(self):
        saved = servo_settings.Calibration(90, 125, 90, 160, 0, 0.04)
        with patch.object(servo_settings, 'load_calibration', return_value=saved):
            controllers = [live.DirectPca9685Controller(), calibration.ServoPanTilt()]
        for controller in controllers:
            for num, (key, cfg) in enumerate(live.CATEGORY_CONFIG.items(), 1):
                with self.subTest(controller=type(controller).__name__, route=key):
                    self.events.clear()
                    if isinstance(controller, calibration.ServoPanTilt):
                        controller.dump_bin(str(num))
                    else:
                        controller.trigger_sort(key, cfg)
                    self.assertIn((0, cfg['pan']), self.events)
                    target = 90 if cfg['tilt'] < 90 else 160
                    self.assertIn((1, target), self.events)
                    self.assertTrue(all(90 <= angle <= 160 for ch, angle in self.events if ch == 1))
                    self.assertEqual((controller.current_pan, controller.current_tilt), (90, 125))
                    last_tilt = max(i for i, event in enumerate(self.events) if event[0] == 1)
                    self.assertEqual(self.events[last_tilt], (1, 125))
                    self.assertGreater(len(self.events) - 1, last_tilt)

    def test_startup_emits_home(self):
        live.DirectPca9685Controller()
        self.assertEqual(self.events[-2:], [(1,90),(0,90)])

    def test_four_routes_and_return_home(self):
        c = live.DirectPca9685Controller()
        for key,cfg in live.CATEGORY_CONFIG.items():
            self.events.clear()
            c.trigger_sort(key,cfg)
            self.assertIn((0,cfg['pan']),self.events)
            self.assertIn((1,cfg['tilt']),self.events)
            self.assertTrue(all(0 <= a <= 180 for _,a in self.events))
            self.assertEqual((c.current_pan,c.current_tilt),(90,90))

    def test_level_before_pan_after_interruption(self):
        c = live.DirectPca9685Controller()
        c.current_tilt = 35
        self.events.clear()
        c.trigger_sort('paper',live.CATEGORY_CONFIG['paper'])
        first_pan = next(i for i,e in enumerate(self.events) if e[0] == 0)
        self.assertEqual(self.events[first_pan-1],(1,90))

    def test_explicit_driver_failure_is_not_simulation(self):
        with patch.object(live,'DirectPca9685Controller',side_effect=OSError('no I2C')):
            with self.assertRaises(RuntimeError): live.init_hardware_controller('rpi-i2c')
            self.assertIsInstance(live.init_hardware_controller('auto'),live.SimulatedServoController)

    def test_channel_validation(self):
        for pan,tilt in [(0,0),(-1,1),(0,16)]:
            with self.assertRaises(ValueError): live.DirectPca9685Controller(pan,tilt)
            with self.assertRaises(ValueError): calibration.ServoPanTilt(pan,tilt)

    def test_camera_rgb888_is_already_bgr(self):
        c = live.CameraCapture.__new__(live.CameraCapture)
        frame = np.array([[[7,31,230]]],dtype=np.uint8)
        c.use_picam2 = True
        c.picam2 = SimpleNamespace(capture_array=lambda:frame)
        ok,actual = c.read()
        self.assertTrue(ok)
        np.testing.assert_array_equal(actual,frame)

    def test_route_mapping_matches_calibrator(self):
        for cfg,b in zip(live.CATEGORY_CONFIG.values(),calibration.BINS.values()):
            self.assertEqual((cfg['pan'],cfg['tilt'],cfg['bin_pos']),(b['pan'],b['tilt'],b['pos']))

    def test_calibrator_emits_home(self):
        with patch.object(sys,'platform','darwin'):
            c = calibration.ServoPanTilt()
        c.go_home()
        self.assertEqual(self.events[-2:],[(1,90),(0,90)])

    def test_manual_sort_discards_pre_movement_frame(self):
        # Exercise the actual main loop: 30 empty calibration frames, then a
        # manual trigger on a large detected object, then quit. No ML download.
        empty = np.zeros((480,640,3),dtype=np.uint8)
        occupied = np.full_like(empty,255)
        camera = SimpleNamespace(read=unittest.mock.Mock(side_effect=[(True,empty.copy()) for _ in range(30)] + [(True,occupied.copy()),(True,occupied.copy())]),
                                 is_opened=lambda:True,release=unittest.mock.Mock())
        classifier = SimpleNamespace(categories=list(live.CATEGORY_CONFIG),dev_desc='FAKE',predict=unittest.mock.Mock())
        controller = SimpleNamespace(trigger_sort=unittest.mock.Mock(),close=unittest.mock.Mock(),status_str='SIMULATION')
        with patch.object(live,'ClipClassifier',return_value=classifier), \
             patch.object(live,'CameraCapture',return_value=camera), \
             patch.object(live,'init_hardware_controller',return_value=controller), \
             patch.object(live.cv2,'waitKey',side_effect=[0]*30+[ord('1'),ord('q')]), \
             patch.object(live.cv2,'imshow'),patch.object(live.cv2,'destroyAllWindows'), \
             patch.dict('os.environ',{'DISPLAY':':test'}), \
             patch.object(sys,'argv',['live_smart_bin.py','--driver','sim']):
            live.main()
        controller.trigger_sort.assert_called_once()
        classifier.predict.assert_not_called()
        camera.release.assert_called_once()
        controller.close.assert_called_once()

if __name__ == '__main__': unittest.main()
