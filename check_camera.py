#!/usr/bin/env python3
"""Read-only camera diagnostics; reports observations without guessing faults."""
from pathlib import Path
import shutil
import subprocess

def main():
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
    result = subprocess.run([command,'--list-cameras'],capture_output=True,text=True,timeout=20)
    output = result.stdout + result.stderr
    print(output)
    if result.returncode or 'imx219' not in output.lower():
        print('IMX219 not confirmed. Check configuration and cable with power disconnected.')
        return 1
    print('IMX219 enumerated. Live frames, focus and colour still need a preview check.')
    return 0

if __name__ == '__main__': raise SystemExit(main())
