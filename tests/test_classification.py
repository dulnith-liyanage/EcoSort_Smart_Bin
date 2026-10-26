"""Prompt ensembles and rejection gates; no weights or physical hardware."""
import contextlib
import io
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import torch
import live_smart_bin as live


class ClassificationTests(unittest.TestCase):
    def test_prompt_groups_and_invalid_old_keys(self):
        groups = live.build_prompt_groups({'paper': ['a photo of paper', 'a photo of cardboard']})
        self.assertEqual(list(groups), ['paper', 'plastic', 'metal', 'food', 'unknown'])
        self.assertEqual(len(groups['paper']), 2)
        for custom in ({'organic': 'food'}, {'paper': []}, {'paper': [None]}, ['paper']):
            with self.subTest(custom=custom), self.assertRaises(ValueError):
                live.build_prompt_groups(custom)

    def test_ensembles_normalise_each_prompt_and_each_class(self):
        features = torch.tensor([[10., 0.], [1., 0.], [0., 5.]])
        actual = live.ensemble_text_features(features, [2, 1])
        torch.testing.assert_close(actual, torch.eye(2))

    def test_uncertainty_gate_rejects_unknown_ties_and_small_margin(self):
        self.assertTrue(live.prediction_is_eligible('paper', {'paper': .8, 'unknown': .2}))
        for cat, scores in [('unknown', {'unknown': .9, 'paper': .1}),
                            ('paper', {'paper': .59, 'plastic': .41}),
                            ('paper', {'paper': .65, 'plastic': .60}),
                            ('paper', {'paper': .5, 'plastic': .5}),
                            ('paper', {'paper': float('nan'), 'plastic': .1})]:
            self.assertFalse(live.prediction_is_eligible(cat, scores))

    def run_sequence(self, predictions, space=False):
        empty = np.zeros((480, 640, 3), dtype=np.uint8)
        occupied = np.full_like(empty, 255)
        camera = SimpleNamespace(read=Mock(side_effect=[(True, empty.copy()) for _ in range(30)] +
                                  [(True, occupied.copy()) for _ in predictions] + [(False, None)]),
                                 is_opened=lambda: True, release=Mock())
        classifier = SimpleNamespace(categories=list(live.build_prompt_groups()), dev_desc='FAKE',
                                     predict=Mock(side_effect=predictions))
        controller = SimpleNamespace(trigger_sort=Mock(), close=Mock(), status_str='SIMULATION')
        with patch.object(live, 'ClipClassifier', return_value=classifier), \
             patch.object(live, 'CameraCapture', return_value=camera), \
             patch.object(live, 'init_hardware_controller', return_value=controller), \
             patch.object(live.cv2, 'imshow'), patch.object(live.cv2, 'destroyAllWindows'), \
             patch.object(live.cv2, 'waitKey', return_value=ord(' ') if space else 0), \
             patch.object(sys, 'argv', ['live_smart_bin.py', '--driver', 'sim']), \
             patch.dict('os.environ', {'DISPLAY': ':test'}), \
             contextlib.redirect_stdout(io.StringIO()):
            live.main()
        return controller

    def test_space_cannot_force_uncertain_or_unknown_sort(self):
        for result in [('unknown', .9, {'unknown': .9, 'paper': .1, 'plastic': 0., 'metal': 0., 'food': 0.}),
                       ('paper', .55, {'paper': .55, 'plastic': .4, 'metal': .02, 'food': .02, 'unknown': .01})]:
            self.run_sequence([result] * 4, space=True).trigger_sort.assert_not_called()

    def test_rejection_breaks_stability_then_three_good_frames_sort_once(self):
        good = ('metal', .9, {'paper': .02, 'plastic': .03, 'metal': .9, 'food': .03, 'unknown': .02})
        bad = ('unknown', .9, {'paper': .02, 'plastic': .03, 'metal': .03, 'food': .02, 'unknown': .9})
        self.run_sequence([good, good, bad, good, good]).trigger_sort.assert_not_called()
        controller = self.run_sequence([good, good, bad, good, good, good])
        controller.trigger_sort.assert_called_once_with('metal', live.CATEGORY_CONFIG['metal'])
