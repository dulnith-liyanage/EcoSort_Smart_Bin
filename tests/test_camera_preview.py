"""Check that a plain SSH invocation cannot start camera or motor hardware."""
import contextlib
import io
import os
import sys
import unittest
from unittest.mock import patch

import camera_preview


class CameraPreviewTests(unittest.TestCase):
    def test_no_display_exits_before_camera_access(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(sys, 'argv', ['camera_preview.py']), \
             patch.dict(sys.modules, {'picamera2': None}), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(camera_preview.main(), 2)
        self.assertIn('VNC', errors.getvalue())

    def test_invalid_duration_is_rejected_before_hardware_access(self):
        for value in ['-1', 'nan', 'inf']:
            with self.subTest(value=value), \
                 patch.object(sys, 'argv', ['camera_preview.py', '--seconds', value]), \
                 patch.dict(sys.modules, {'picamera2': None}), \
                 contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as result:
                camera_preview.main()
            self.assertEqual(result.exception.code, 2)
