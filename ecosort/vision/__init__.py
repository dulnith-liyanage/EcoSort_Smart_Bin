"""
Vision and multi-modal classification subpackage.
"""
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

__all__ = [
    "ClipClassifier",
    "best_supported_prediction",
    "prepare_classifier_image",
    "build_prompt_groups",
    "ensemble_text_features",
    "prediction_is_eligible",
    "best_window_prediction",
    "configure_cpu_threads",
    "draw_hud",
]
