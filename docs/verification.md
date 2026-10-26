# Verification - 26 October 2026

## Current software changes

The four supported classes are paper/cardboard, rigid plastic, metal cans and
fruit/vegetable scraps. Tests cover normalised prompt grouping, unknown and
low-margin rejection, stable predictions, Space retaining checks, all four
calibrated routes, HOME return, competing-controller locks, I2C compatibility,
camera format handling and preview validation. Devices, model results and
camera frames are replaced with test doubles; these are not accuracy tests.

Run the portable checks with:

```sh
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ./venv/bin/python scripts/verify.py
./venv/bin/python servo_control.py --check-calibration
./venv/bin/python live_smart_bin.py --help
./venv/bin/python scripts/evaluate_classifier.py --help
```

The current Mac suite has **40 passing tests**, plus Python and shell syntax
checks. No camera, servo commands or model downloads are used by these checks.
3D-print/CAD files and their dedicated geometry tests have been removed because
the physical project no longer uses printed components.

## Earlier Pi observations

Before this classifier change, real Pi checks verified Camera V2 capture,
cached CLIP inference, PCA9685 communication and operator-observed unloaded
routes. HOME is now tilt 125 / pan 90, with provisional tilt endpoints 90/160.
The VNC camera-only viewer displayed live frames and its window was visually
checked. These earlier observations do not validate the new classification
accuracy or any loaded item delivery.

The Pi kernel recorded undervoltage during a recognition-only diagnostic, even
without new servo commands. CPU/display load mitigations are not a repair for
deficient power delivery. See [the diagnosis](shutdown_troubleshooting.md).

## Still required

- Deploy and test the current revision on the Pi when it is reachable.
- Correct power delivery, then verify mounting, camera framing and unloaded
  clearance before loaded motor tests.
- Collect labelled local development and held-out images. Compare raw accuracy,
  accepted accuracy, coverage and per-class errors using the evaluator.
- Test unsupported objects and hands, changing lighting, stable decisions and
  one-item delivery into each bin. Test slow light dummy items first.

No improved accuracy percentage, model retraining result, load rating or
unattended-operation readiness is claimed.
