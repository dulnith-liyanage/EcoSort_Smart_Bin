"""
Shared mechanical HOME calibration and Pi I2C buffer compatibility.

Re-exports core hardware configuration from ecosort.hardware for backward compatibility.
"""
from ecosort.hardware.lock import acquire_device_lock, HardwareInUseError
from ecosort.hardware.i2c_compat import BufferCompatibleI2C, prepare_servo_kit
from ecosort.hardware.calibration import Calibration, load_calibration, motion_steps, CONFIG

__all__ = [
    "CONFIG",
    "Calibration",
    "load_calibration",
    "motion_steps",
    "BufferCompatibleI2C",
    "prepare_servo_kit",
    "acquire_device_lock",
    "HardwareInUseError",
]
