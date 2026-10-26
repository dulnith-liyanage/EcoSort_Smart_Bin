"""Calibration and I2C compatibility regressions without hardware."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from servo_settings import Calibration, BufferCompatibleI2C, load_calibration, prepare_servo_kit


class CalibrationTests(unittest.TestCase):
    def test_default_preserves_logical_routes(self):
        self.assertEqual(Calibration().route({'pan': 135, 'tilt': 35}), (135, 35, 25))

    def test_asymmetric_endpoints_reach_all_four_routes_without_shake(self):
        c = Calibration(90, 15, 5, 70, 0, 0.04)
        for pan, tilt in [(135,35),(45,35),(45,145),(135,145)]:
            with self.subTest(pan=pan,tilt=tilt):
                physical = c.route({'pan':pan,'tilt':tilt})
                expected = 5 if tilt < 90 else 70
                self.assertEqual(physical,(pan,expected,expected))
        self.assertEqual(c.tilt(90),15)

    def test_invalid_asymmetric_settings_are_rejected(self):
        for kwargs in [{'forward_tilt':5},
                       {'forward_tilt':20,'backward_tilt':70},
                       {'forward_tilt':5,'backward_tilt':10},
                       {'shake_degrees':11}, {'step_delay':float('nan')}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Calibration(90,15,**kwargs)

    def test_shake_cannot_escape_asymmetric_limits(self):
        c = Calibration(90,15,5,70,10)
        with self.assertRaises(ValueError):
            c.route({'pan':135,'tilt':35})

    def test_offset_does_not_silently_clip(self):
        with self.assertRaises(ValueError):
            Calibration(90, 15).route({'pan': 135, 'tilt': 35})

    def test_shake_is_checked_even_if_dump_is_in_range(self):
        with self.assertRaises(ValueError):
            Calibration(90, 30).route({'pan': 45, 'tilt': 65})

    def test_invalid_home_is_rejected(self):
        for value in (-1, 181, True, 90.5, '15'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Calibration(90, value)

    def test_loader_uses_explicit_file_and_does_not_default_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            with self.assertRaises(FileNotFoundError):
                load_calibration(path)
            path.write_text(json.dumps({'pan_home': 90, 'tilt_home': 15}))
            self.assertEqual(load_calibration(path).tilt_home, 15)
            path.write_text('invalid')
            with self.assertRaises(ValueError):
                load_calibration(path)

    def test_actual_checked_in_configuration_is_valid(self):
        c = load_calibration()
        self.assertTrue(0 <= c.pan_home <= 180 and 0 <= c.tilt_home <= 180)


class I2CCompatibilityTests(unittest.TestCase):
    def test_memoryview_normalisation_preserves_slices_and_output_alias(self):
        class OldBackend:
            def writeto_then_readfrom(self, address, out, inp, **kwargs):
                self.args = address, out, kwargs
                assert isinstance(out, bytes)
                start = kwargs['in_start']
                inp[start:kwargs['in_end']] = out[kwargs['out_start']:kwargs['out_end']]
        backend = OldBackend()
        adapter = BufferCompatibleI2C(backend)
        buf = bytearray([9, 10, 11, 12])
        view = memoryview(buf)
        adapter.writeto_then_readfrom(0x40, view, view,
                                     out_start=0, out_end=2, in_start=2, in_end=4)
        self.assertEqual(buf, bytearray([9, 10, 9, 10]))
        self.assertEqual(backend.args[0], 0x40)

    def test_lock_and_write_are_forwarded(self):
        backend = SimpleNamespace(try_lock=Mock(return_value=True), writeto=Mock())
        adapter = BufferCompatibleI2C(backend)
        self.assertTrue(adapter.try_lock())
        adapter.writeto(0x40, b'abc')
        backend.writeto.assert_called_once_with(0x40, b'abc')

    def test_prepare_is_idempotent_and_does_not_write(self):
        backend = Mock()
        kit = SimpleNamespace(_pca=SimpleNamespace(i2c_device=SimpleNamespace(i2c=backend)))
        prepare_servo_kit(kit)
        adapter = kit._pca.i2c_device.i2c
        prepare_servo_kit(kit)
        self.assertIs(kit._pca.i2c_device.i2c, adapter)
        self.assertEqual(backend.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
