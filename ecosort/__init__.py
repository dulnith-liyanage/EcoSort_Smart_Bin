"""
EcoSort Smart Bin - Autonomous Vision-Powered 4-Way Waste Segregator.

A real-time edge AI waste sorting system combining zero-shot multi-modal classification
(CLIP / SigLIP 2) with a 2-axis MG996R servo pan-tilt mechanism, automated tray
presence detection, and an integrated telemetry web dashboard.
"""

__version__ = "1.0.0"

from ecosort.config import CATEGORY_CONFIG, BINS, MODEL_NAMES, UNKNOWN_PROMPTS
from ecosort.logging import log_info, log_success, log_warning, log_error, log_sort_event
from ecosort.hardware.calibration import Calibration, load_calibration, motion_steps
from ecosort.hardware.lock import acquire_device_lock, HardwareInUseError
from ecosort.hardware.i2c_compat import BufferCompatibleI2C, prepare_servo_kit
from ecosort.hardware.servo import (
    BaseServoController,
    DirectPca9685Controller,
    SimulatedServoController,
    ServoPanTilt,
    init_hardware_controller,
)
from ecosort.hardware.camera import CameraCapture, probe_camera
from ecosort.vision.classifier import (
    ClipClassifier,
    best_supported_prediction,
    prepare_classifier_image,
    build_prompt_groups,
    ensemble_text_features,
    prediction_is_eligible,
    best_window_prediction,
    configure_cpu_threads,
)
from ecosort.vision.hud import draw_hud
from ecosort.core.sorter import main as run_smart_bin

__all__ = [
    "__version__",
    "CATEGORY_CONFIG",
    "BINS",
    "MODEL_NAMES",
    "UNKNOWN_PROMPTS",
    "log_info",
    "log_success",
    "log_warning",
    "log_error",
    "log_sort_event",
    "Calibration",
    "load_calibration",
    "motion_steps",
    "acquire_device_lock",
    "HardwareInUseError",
    "BufferCompatibleI2C",
    "prepare_servo_kit",
    "BaseServoController",
    "DirectPca9685Controller",
    "SimulatedServoController",
    "ServoPanTilt",
    "init_hardware_controller",
    "CameraCapture",
    "probe_camera",
    "ClipClassifier",
    "best_supported_prediction",
    "prepare_classifier_image",
    "build_prompt_groups",
    "ensemble_text_features",
    "prediction_is_eligible",
    "best_window_prediction",
    "configure_cpu_threads",
    "draw_hud",
    "run_smart_bin",
]
