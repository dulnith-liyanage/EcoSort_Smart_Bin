#!/usr/bin/env python3
"""Desktop/VNC preview of Camera V2. Never imports or initialises motor code."""
import argparse
import math
import os
import signal
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=0,
                        help='Close after this many seconds; 0 keeps the window open.')
    args = parser.parse_args()
    if args.seconds < 0 or not math.isfinite(args.seconds):
        parser.error('--seconds must be a finite non-negative number')
    if not os.environ.get('DISPLAY'):
        print('Open this from the Pi desktop through VNC, not a plain SSH terminal.', file=sys.stderr)
        return 2

    camera = root = None
    started = False
    try:
        import tkinter as tk
        from tkinter import messagebox
        from PIL import Image, ImageDraw, ImageTk
        from picamera2 import Picamera2

        root = tk.Tk()
        root.title('EcoSort - Camera Preview (motors inactive)')
        root.resizable(False, False)
        tk.Label(root, text='EcoSort | Camera V2 | VIEW ONLY',
                 font=('Sans', 16, 'bold')).pack(pady=8)
        image_label = tk.Label(root)
        image_label.pack()
        status = tk.Label(root, text='Starting camera...')
        status.pack(pady=6)
        tk.Label(root, text='Centre the tray under the crosshair. No sorting or motor commands.').pack()

        camera = Picamera2()
        camera.configure(camera.create_preview_configuration(
            main={'size': (640, 480), 'format': 'RGB888'},
            controls={'FrameRate': 15}))
        camera.start()
        started = True
        beginning = time.monotonic()
        frames = 0
        closing = False
        stream_failed = False

        def close(*_):
            nonlocal closing
            closing = True

        def update():
            nonlocal frames, stream_failed
            if closing or (args.seconds and time.monotonic() - beginning >= args.seconds):
                root.quit()
                return
            try:
                # libcamera RGB888 buffers use B,G,R byte order on this Pi.
                frame = camera.capture_array()
                picture = Image.fromarray(frame[:, :, ::-1])
                draw = ImageDraw.Draw(picture)
                x, y = picture.width // 2, picture.height // 2
                draw.line((x - 16, y, x + 16, y), fill='#00ff80', width=2)
                draw.line((x, y - 16, x, y + 16), fill='#00ff80', width=2)
                photo = ImageTk.PhotoImage(picture, master=root)
                image_label.configure(image=photo)
                image_label.image = photo
                frames += 1
                if frames == 1:
                    print('Camera preview displaying live 640x480 frames; motors untouched.', flush=True)
                status.configure(text=f'LIVE | Frame {frames} | Q / Esc / Close to release camera')
                root.after(67, update)
            except Exception as error:
                stream_failed = True
                print(f'Camera stream failed: {error}', file=sys.stderr, flush=True)
                messagebox.showerror('EcoSort camera', str(error), parent=root)
                close()
                root.quit()

        root.protocol('WM_DELETE_WINDOW', close)
        root.bind('<Escape>', close)
        root.bind('q', close)
        signal.signal(signal.SIGTERM, close)
        signal.signal(signal.SIGINT, close)
        tk.Button(root, text='Close preview', command=close).pack(pady=8)
        root.after(0, update)
        root.mainloop()
        print(f'Camera preview closed after {frames} frames.', flush=True)
        return 1 if stream_failed else 0
    except Exception as error:
        print(f'Cannot start preview: {error}\nClose any other camera application first. '
              'Required Pi packages: python3-picamera2 python3-tk python3-pil.imagetk.',
              file=sys.stderr)
        return 1
    finally:
        if camera is not None:
            try:
                if started:
                    camera.stop()
            finally:
                camera.close()
        if root is not None:
            root.destroy()


if __name__ == '__main__':
    raise SystemExit(main())
