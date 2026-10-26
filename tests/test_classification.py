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
    def test_always_chooses_supported_bin_without_renormalising_unknown_away(self):
        scores = {'paper': .04, 'plastic': .03, 'metal': .02, 'food': .01, 'unknown': .90}
        self.assertEqual(live.best_supported_prediction(scores), ('paper', .04))
        self.assertFalse(live.prediction_is_eligible('paper', scores))

    def test_letterbox_keeps_both_item_edges_and_rgb_order(self):
        frame = np.zeros((2, 6, 3), dtype=np.uint8)
        frame[:, 0] = (0, 0, 255)
        frame[:, -1] = (255, 0, 0)
        actual = np.array(live.prepare_classifier_image(frame))
        self.assertEqual(actual.shape, (6, 6, 3))
        np.testing.assert_array_equal(actual[2, 0], (255, 0, 0))
        np.testing.assert_array_equal(actual[2, -1], (0, 0, 255))

    def test_both_pretrained_backends_use_prompt_groups_and_return_four_way_choice(self):
        class Batch(dict):
            def to(self, device): return self

        for backend in live.MODEL_NAMES:
            calls = []
            def processor(**kwargs):
                calls.append(kwargs)
                return Batch(input_ids=torch.zeros((17, 1))) if 'text' in kwargs else Batch(pixel_values=torch.zeros((1, 3, 4, 4)))
            model = Mock()
            model.to.return_value = model
            model.logit_scale = torch.tensor(4.)
            model.get_text_features.return_value = torch.tensor([[1., 0.]]*12 + [[0., 1.]]*5)
            model.get_image_features.return_value = torch.tensor([[.6, .8]])
            model_class = live.AutoModel if backend == 'siglip2' else live.CLIPModel
            processor_class = live.AutoProcessor if backend == 'siglip2' else live.CLIPProcessor
            with self.subTest(backend=backend), \
                 patch.object(model_class, 'from_pretrained', return_value=model) as load, \
                 patch.object(processor_class, 'from_pretrained', return_value=processor), \
                 patch.object(live.torch.backends.mps, 'is_available', return_value=False), \
                 patch.object(live.torch.cuda, 'is_available', return_value=False), \
                 patch.object(live, 'configure_cpu_threads', return_value=1), \
                 contextlib.redirect_stdout(io.StringIO()):
                classifier = live.ClipClassifier(model_name=live.MODEL_NAMES[backend])
                category, score, probabilities = classifier.predict(np.zeros((4, 8, 3), dtype=np.uint8))
            self.assertIn(category, live.CATEGORY_CONFIG)
            self.assertGreater(probabilities['unknown'], score)
            self.assertFalse(live.prediction_is_eligible(category, probabilities))
            self.assertEqual(calls[0]['max_length'], 64 if backend == 'siglip2' else 77)
            self.assertTrue(load.call_args.kwargs['use_safetensors'])

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
