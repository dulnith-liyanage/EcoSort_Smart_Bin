"""
Camera capture abstraction supporting Raspberry Pi CSI (Picamera2) and OpenCV.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import cv2
from ecosort.logging import log_info, log_success, log_warning, log_error


class CameraCapture:
    """Unified camera capture supporting Raspberry Pi CSI cameras (Picamera2) and USB/standard cameras (OpenCV)."""
    def __init__(self, camera_idx=0):
        self.use_picam2 = False
        self.picam2 = None
        self.cap = None

        # 1. On Raspberry Pi / Linux, prioritize native Picamera2 for CSI camera (CAM 0 / CAM 1)
        if sys.platform.startswith('linux'):
            try:
                from picamera2 import Picamera2
                log_info("[CAMERA] Probing Raspberry Pi CSI Camera via Picamera2...")
                self.picam2 = Picamera2(camera_idx)
                config = self.picam2.create_preview_configuration(
                    main={"size": (640, 480), "format": "RGB888"},
                    controls={"FrameRate": 15}
                )
                self.picam2.configure(config)
                self.picam2.start()
                self.use_picam2 = True
                log_success("[CAMERA] Raspberry Pi CSI Camera online via Picamera2 (640x480)!")
                return
            except Exception as e:
                if self.picam2 is not None:
                    self.picam2.close()
                    self.picam2 = None
                log_info(f"[CAMERA] Picamera2 not active ({e}). Falling back to OpenCV VideoCapture...")

        # 2. Fallback to OpenCV (USB cameras, libcamerify wrapper, or desktop)
        log_info(f"[CAMERA] Opening OpenCV VideoCapture (Index {camera_idx})...")
        if sys.platform.startswith('linux'):
            self.cap = cv2.VideoCapture(camera_idx, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(camera_idx)
        else:
            self.cap = cv2.VideoCapture(camera_idx)

        if not self.cap.isOpened() and camera_idx != 0:
            log_warning(f"[CAMERA] Index {camera_idx} failed. Falling back to Index 0...")
            self.cap = cv2.VideoCapture(0)

        if self.cap is not None and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            log_success(f"[CAMERA] OpenCV VideoCapture ready on index {camera_idx}.")

    def is_opened(self):
        if self.use_picam2:
            return True
        return self.cap is not None and self.cap.isOpened()

    def read(self):
        if self.use_picam2 and self.picam2 is not None:
            try:
                # libcamera RGB888 is B,G,R byte order, as OpenCV expects.
                return True, self.picam2.capture_array()
            except Exception:
                return False, None
        elif self.cap is not None:
            return self.cap.read()
        return False, None

    def release(self):
        if self.use_picam2 and self.picam2 is not None:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
        if self.cap is not None:
            self.cap.release()


def probe_camera():
    """Read-only camera diagnostics; reports observations without guessing faults."""
    config = Path('/boot/firmware/config.txt')
    if config.exists():
        print('Camera settings:', '\n'.join(line for line in config.read_text().splitlines()
              if not line.lstrip().startswith('#') and ('camera' in line or 'imx219' in line)))
    else:
        print('Pi boot configuration unavailable on this machine.')
    command = shutil.which('rpicam-hello') or shutil.which('libcamera-hello')
    if command is None:
        print('Camera probe unavailable: run this on the Pi with rpicam-apps installed.')
        return 2
    result = subprocess.run([command, '--list-cameras'], capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    print(output)
    if result.returncode or 'imx219' not in output.lower():
        print('IMX219 not confirmed. Check configuration and cable with power disconnected.')
        return 1
    print('IMX219 enumerated. Live frames, focus and colour still need a preview check.')
    return 0
