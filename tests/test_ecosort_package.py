"""
Unit tests validating the modular ecosort package structure and exports.
"""
import io
import contextlib
import unittest
import numpy as np
import torch
from PIL import Image

import ecosort
from ecosort.config import CATEGORY_CONFIG, BINS, MODEL_NAMES, UNKNOWN_PROMPTS
from ecosort.logging import log_info, log_success, log_warning, log_warn, log_error, log_sort_event
from ecosort.compat import preload_openblas
from ecosort.hardware.calibration import Calibration, motion_steps
from ecosort.hardware.servo import SimulatedServoController
from ecosort.vision.classifier import (
    best_supported_prediction,
    prepare_classifier_image,
    build_prompt_groups,
    ensemble_text_features,
    prediction_is_eligible,
    best_window_prediction,
)


class EcosortPackageTests(unittest.TestCase):
    def test_package_exports(self):
        self.assertTrue(hasattr(ecosort, '__version__'))
        self.assertIn('CATEGORY_CONFIG', ecosort.__all__)
        self.assertIn('ClipClassifier', ecosort.__all__)
        self.assertIn('run_smart_bin', ecosort.__all__)

    def test_config_consistency(self):
        self.assertEqual(set(CATEGORY_CONFIG.keys()), {'paper', 'plastic', 'metal', 'food'})
        self.assertEqual(set(BINS.keys()), {'1', '2', '3', '4'})
        for bin_num, data in BINS.items():
            self.assertIn(data['pos'], ['Front-Left', 'Front-Right', 'Rear-Left', 'Rear-Right'])
            self.assertIn(data['mode'], ['Forward Dump', 'Backward Dump'])
        self.assertIn('clip', MODEL_NAMES)
        self.assertIn('siglip2', MODEL_NAMES)
        self.assertGreaterEqual(len(UNKNOWN_PROMPTS), 3)

    def test_logging_utilities(self):
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            log_info("info test")
            log_success("success test")
            log_warning("warning test")
            log_warn("warn test")
            log_error("error test")
            log_sort_event("paper", 0.95, "P", "test route")
        output = f.getvalue()
        self.assertIn("[INFO]", output)
        self.assertIn("info test", output)
        self.assertIn("[SUCCESS]", output)
        self.assertIn("success test", output)
        self.assertIn("[WARNING]", output)
        self.assertIn("warning test", output)
        self.assertIn("warn test", output)
        self.assertIn("[ERROR]", output)
        self.assertIn("error test", output)
        self.assertIn("SORT EVENT", output)

    def test_preload_openblas_safe(self):
        # Must execute cleanly on any OS without raising
        preload_openblas()

    def test_simulated_servo_controller(self):
        controller = SimulatedServoController()
        self.assertEqual(controller.status_str, "Hardware: SIMULATION (2x2 Grid)")
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            controller.trigger_sort('paper', CATEGORY_CONFIG['paper'])
        self.assertIn("SIMULATION TRIGGER", f.getvalue())
        controller.reset_home()
        controller.close()

    def test_classifier_helpers(self):
        # Best supported prediction
        probs = {'paper': 0.1, 'plastic': 0.7, 'metal': 0.1, 'food': 0.1}
        cat, conf = best_supported_prediction(probs)
        self.assertEqual(cat, 'plastic')
        self.assertAlmostEqual(conf, 0.7)

        # Image prep
        img = np.ones((100, 200, 3), dtype=np.uint8) * 50
        square = prepare_classifier_image(img)
        self.assertIsInstance(square, Image.Image)
        self.assertEqual(square.size, (200, 200))

        # Ensembles
        feats = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
        ens = ensemble_text_features(feats, [1, 1])
        self.assertEqual(ens.shape, (2, 2))

        # Eligibility
        self.assertTrue(prediction_is_eligible('plastic', probs, threshold=0.5, margin=0.1))
        self.assertFalse(prediction_is_eligible('plastic', probs, threshold=0.8, margin=0.1))

        # Window prediction
        hist = [
            ('plastic', 0.8, {'paper': 0.1, 'plastic': 0.8, 'metal': 0.05, 'food': 0.05}),
            ('plastic', 0.6, {'paper': 0.2, 'plastic': 0.6, 'metal': 0.1, 'food': 0.1})
        ]
        win_cat, win_conf = best_window_prediction(hist)
        self.assertEqual(win_cat, 'plastic')
        self.assertAlmostEqual(win_conf, 0.7)
