"""Shared mechanical HOME calibration and Pi I2C buffer compatibility."""
from dataclasses import dataclass
import json
from pathlib import Path

CONFIG = Path(__file__).resolve().with_name('servo_calibration.json')


@dataclass(frozen=True)
class Calibration:
    pan_home: int = 90
    tilt_home: int = 90

    def __post_init__(self):
        for value in (self.pan_home, self.tilt_home):
            if type(value) is not int or not 0 <= value <= 180:
                raise ValueError('HOME angles must be integers between 0 and 180.')

    @staticmethod
    def _checked(angle):
        if not 0 <= angle <= 180:
            raise ValueError(
                f'Calibrated target {angle} degrees is outside 0..180. '
                'Re-index the tilt horn so the plate is level near servo 90 degrees; '
                'do not clamp an invalid sorting angle or force the bracket.')
        return angle

    def pan(self, logical_angle):
        return self._checked(logical_angle + self.pan_home - 90)

    def tilt(self, logical_angle):
        return self._checked(logical_angle + self.tilt_home - 90)

    def route(self, cfg):
        pan = self.pan(cfg['pan'])
        tilt = self.tilt(cfg['tilt'])
        shake = self.tilt(cfg['tilt'] + (-10 if cfg['tilt'] < 90 else 10))
        return pan, tilt, shake

    def validate_routes(self, routes):
        for cfg in routes:
            self.route(cfg)


def load_calibration(path=None):
    # Missing or malformed calibration is an error, not a silent 90-degree reset.
    data = json.loads(Path(path or CONFIG).read_text())
    return Calibration(data['pan_home'], data['tilt_home'])


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
