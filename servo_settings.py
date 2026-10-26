"""Shared mechanical HOME calibration and Pi I2C buffer compatibility."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

CONFIG = Path(__file__).resolve().with_name('servo_calibration.json')


@dataclass(frozen=True)
class Calibration:
    pan_home: int = 90
    tilt_home: int = 90
    forward_tilt: int | None = None
    backward_tilt: int | None = None
    shake_degrees: int = 10
    step_delay: float = 0.009

    def __post_init__(self):
        for value in (self.pan_home, self.tilt_home):
            if type(value) is not int or not 0 <= value <= 180:
                raise ValueError('HOME angles must be integers between 0 and 180.')
        if (self.forward_tilt is None) != (self.backward_tilt is None):
            raise ValueError('Set both forward_tilt and backward_tilt, or neither.')
        if self.forward_tilt is not None:
            if any(type(v) is not int for v in (self.forward_tilt, self.backward_tilt)):
                raise ValueError('Tilt endpoints must be integer commands.')
            if not 0 <= self.forward_tilt < self.tilt_home < self.backward_tilt <= 180:
                raise ValueError('Tilt endpoints must straddle HOME inside 0..180.')
        if type(self.shake_degrees) is not int or not 0 <= self.shake_degrees <= 10:
            raise ValueError('shake_degrees must be an integer from 0 to 10.')
        if isinstance(self.step_delay, bool) or not isinstance(self.step_delay, (int, float)) or not math.isfinite(self.step_delay) or not 0.005 <= self.step_delay <= 0.2:
            raise ValueError('step_delay must be between 0.005 and 0.2 seconds.')

    @staticmethod
    def _checked(angle):
        if not 0 <= angle <= 180:
            raise ValueError(
                f'Calibrated target {angle} degrees is outside 0..180. '
                'Use measured asymmetric tilt endpoints or re-index the tilt horn; '
                'do not clamp an invalid sorting angle or force the bracket.')
        return angle

    def pan(self, logical_angle):
        return self._checked(logical_angle + self.pan_home - 90)

    def tilt(self, logical_angle):
        if self.forward_tilt is not None:
            if logical_angle < 90:
                angle = self.tilt_home - (90-logical_angle) * (self.tilt_home-self.forward_tilt)/55
            else:
                angle = self.tilt_home + (logical_angle-90) * (self.backward_tilt-self.tilt_home)/55
            return self._checked(round(angle))
        return self._checked(logical_angle + self.tilt_home - 90)

    def route(self, cfg):
        pan = self.pan(cfg['pan'])
        tilt = self.tilt(cfg['tilt'])
        shake = self._checked(tilt + (-self.shake_degrees if cfg['tilt'] < 90 else self.shake_degrees))
        return pan, tilt, shake

    def validate_routes(self, routes):
        for cfg in routes:
            self.route(cfg)


def load_calibration(path=None):
    # Missing or malformed calibration is an error, not a silent 90-degree reset.
    data = json.loads(Path(path or CONFIG).read_text())
    return Calibration(data['pan_home'], data['tilt_home'],
                       data.get('forward_tilt'), data.get('backward_tilt'),
                       data.get('shake_degrees', 10), data.get('step_delay', 0.009))


class BufferCompatibleI2C:
    """Retain transfer slicing/locking while normalising outgoing memoryviews.

    Blinka's Linux backend forwards memoryviews to PureIO 1.1.11, whose
    combined-read register argument only accepts bytes, bytearray or an int.
    This adapter affects only the ServoKit bus, not installed library files.
    """
    def __init__(self, bus):
        self.bus = bus

    def __getattr__(self, name):
        return getattr(self.bus, name)

    def writeto_then_readfrom(self, address, buffer_out, buffer_in, **kwargs):
        return self.bus.writeto_then_readfrom(
            address, bytes(buffer_out), buffer_in, **kwargs)


def prepare_servo_kit(kit):
    # ServoKit has no public bus accessor after construction. Limit this
    # compatibility adapter to the PCA9685 I2CDevice; test doubles need none.
    pca = getattr(kit, '_pca', None)
    if pca is not None:
        device = pca.i2c_device
        if not isinstance(device.i2c, BufferCompatibleI2C):
            device.i2c = BufferCompatibleI2C(device.i2c)
    return kit
