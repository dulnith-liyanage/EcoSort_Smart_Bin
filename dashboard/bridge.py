"""Small JSON-line bridge between the camera owner and the web process."""
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time

PREFIX = '@ECOSORT@'


class DashboardBridge:
    def __init__(self, frame_path, input_stream=None, output_stream=None, auto_sort=False):
        self.frame_path = Path(frame_path)
        self.output = output_stream or sys.stdout
        self.commands = queue.Queue(maxsize=16)
        self.paused = True
        self.auto_sort = auto_sort
        self.stopping = False
        self.last_frame = 0.0
        self.warmup_frames = 60  # Let auto-exposure settle before learning the empty tray.
        threading.Thread(target=self._read_commands,
                         args=(input_stream or sys.stdin,), daemon=True).start()

    def _read_commands(self, stream):
        for line in stream:
            try:
                command = json.loads(line).get('action')
                if command in {'pause', 'stop'}:
                    self.auto_sort = False
                    self.paused = True
                if command == 'stop':
                    self.stopping = True
                if command in {'pause', 'resume', 'scan', 'recalibrate', 'stop'}:
                    self.commands.put_nowait(command)
            except (ValueError, AttributeError, queue.Full):
                continue
        # Losing the supervisor must not leave autonomous sorting enabled.
        self.paused = True
        self.stopping = True

    def calibrated(self):
        """Enable boot routing only after a complete empty-tray reference."""
        if self.auto_sort and not self.stopping:
            self.paused = False
        self.auto_sort = False

    def poll(self):
        result = []
        while True:
            try:
                action = self.commands.get_nowait()
            except queue.Empty:
                break
            if action == 'pause':
                self.paused = True
            elif action == 'resume':
                self.paused = False
            elif action == 'stop':
                self.stopping = True
                self.paused = True
            result.append(action)
        return result

    def emit(self, kind, **values):
        self.output.write(PREFIX + json.dumps({'kind': kind, **values}, allow_nan=False) + '\n')
        self.output.flush()

    def capture(self, image):
        """Snapshot the classifier crop BEFORE the motors move, not the live preview."""
        import base64
        import cv2
        ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return None
        return {'jpeg':base64.b64encode(encoded.tobytes()).decode('ascii'),'at':time.time()}

    def frame(self, frame):
        now = time.monotonic()
        if now - self.last_frame < 0.5:
            return
        import cv2
        small = cv2.resize(frame, (640, 480))
        ok, encoded = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if ok:
            temporary = self.frame_path.with_suffix('.tmp')
            temporary.write_bytes(encoded.tobytes())
            os.replace(temporary, self.frame_path)
            self.last_frame = now
            self.emit('frame', at=time.time())
