"""
Hardware subpackage: servo controllers, I2C adapter, device locks, calibration, and camera capture.
"""
from ecosort.hardware.lock import acquire_device_lock, HardwareInUseError
from ecosort.hardware.i2c_compat import BufferCompatibleI2C, prepare_servo_kit
from ecosort.hardware.calibration import Calibration, load_calibration, motion_steps, CONFIG
from ecosort.hardware.servo import (
    BaseServoController,
    DirectPca9685Controller,
    SimulatedServoController,
    ServoPanTilt,
    init_hardware_controller,
)
from ecosort.hardware.camera import CameraCapture, probe_camera

__all__ = [
    "acquire_device_lock",
    "HardwareInUseError",
    "BufferCompatibleI2C",
    "prepare_servo_kit",
    "Calibration",
    "load_calibration",
    "motion_steps",
    "CONFIG",
    "BaseServoController",
    "DirectPca9685Controller",
    "SimulatedServoController",
    "ServoPanTilt",
    "init_hardware_controller",
    "CameraCapture",
    "probe_camera",
]
