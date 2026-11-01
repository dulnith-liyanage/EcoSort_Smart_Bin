#!/usr/bin/env python3
"""
EcoSort Smart Bin - Live Vision-Based 4-Way Waste Sorter.

Entry point for real-time camera capture, zero-shot CLIP classification,
and 2-axis servo pan-tilt actuation.
"""
import os
import sys
import time
import numpy as np
import cv2
import torch
from transformers import CLIPProcessor, CLIPModel, AutoModel, AutoProcessor

from ecosort.compat import preload_openblas
preload_openblas()

from ecosort.config import (
    CATEGORY_CONFIG,
    UNKNOWN_PROMPTS,
    MODEL_NAMES,
    C_RESET,
    C_BOLD,
    C_GREEN,
    C_BLUE,
    C_YELLOW,
    C_RED,
    C_CYAN,
    C_MAG,
)
from ecosort.logging import (
    log_info,
    log_success,
    log_warning,
    log_error,
    log_sort_event,
)
from ecosort.hardware.servo import (
    BaseServoController,
    DirectPca9685Controller,
    SimulatedServoController,
    init_hardware_controller,
)
from ecosort.hardware.camera import CameraCapture
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
from ecosort.core.sorter import main

__all__ = [
    "CATEGORY_CONFIG",
    "UNKNOWN_PROMPTS",
    "MODEL_NAMES",
    "C_RESET",
    "C_BOLD",
    "C_GREEN",
    "C_BLUE",
    "C_YELLOW",
    "C_RED",
    "C_CYAN",
    "C_MAG",
    "log_info",
    "log_success",
    "log_warning",
    "log_error",
    "log_sort_event",
    "BaseServoController",
    "DirectPca9685Controller",
    "SimulatedServoController",
    "init_hardware_controller",
    "CameraCapture",
    "ClipClassifier",
    "best_supported_prediction",
    "prepare_classifier_image",
    "build_prompt_groups",
    "ensemble_text_features",
    "prediction_is_eligible",
    "best_window_prediction",
    "configure_cpu_threads",
    "draw_hud",
    "main",
    "os",
    "sys",
    "cv2",
    "torch",
    "CLIPModel",
    "CLIPProcessor",
    "AutoModel",
    "AutoProcessor",
]

if __name__ == '__main__':
    main()
