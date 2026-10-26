"""Record Pi health; optionally test camera/CLIP without initialising servos."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback


def firmware(command):
    try:
        result = subprocess.run(['vcgencmd', command], capture_output=True,
                                text=True, timeout=5, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        return f'unavailable: {error}'


def health():
    memory = Path('/proc/meminfo')
    return {
        'time_utc': datetime.now(timezone.utc).isoformat(),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'uptime': Path('/proc/uptime').read_text().split()[0],
        'throttled': firmware('get_throttled'),
        'temperature': firmware('measure_temp'),
        'supply': [line.strip() for line in firmware('pmic_read_adc').splitlines()
                   if 'EXT5V' in line],
        'memory': [line for line in memory.read_text().splitlines()
                   if line.startswith(('MemAvailable:', 'SwapFree:'))],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inference', action='store_true', help='Test live camera and CLIP; no motor controller.')
    parser.add_argument('--frames', type=int, default=20)
    parser.add_argument('--log', type=Path,
                        default=Path.home()/'.local/state/ecosort/diagnostics.jsonl')
    args = parser.parse_args()
    if args.frames < 1:
        parser.error('--frames must be positive')
    args.log.parent.mkdir(parents=True, exist_ok=True)
    camera = None
    with args.log.open('a') as output:
        def record(**extra):
            data = health()
            data.update(extra)
            line = json.dumps(data)
            output.write(line + '\n')
            output.flush()
            os.fsync(output.fileno())
            print(line, flush=True)

        try:
            record(event='start', inference=args.inference)
            if args.inference:
                sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
                from live_smart_bin import CameraCapture, ClipClassifier
                model = ClipClassifier()
                camera = CameraCapture(0)
                if not camera.is_opened():
                    raise RuntimeError('Camera unavailable; close the preview/sorter before this test.')
                for index in range(args.frames):
                    ok, frame = camera.read()
                    if not ok:
                        raise RuntimeError('Live camera frame read failed.')
                    category, confidence, _ = model.predict(frame)
                    record(event='inference', frame=index+1,
                           category=category, confidence=float(confidence))
            record(event='completed')
            return 0
        except Exception:
            record(event='error', traceback=traceback.format_exc())
            return 1
        finally:
            if camera is not None:
                camera.release()


if __name__ == '__main__':
    raise SystemExit(main())
