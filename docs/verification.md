# Verification - 28 October 2026

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

The current Mac suite has **83 passing tests**, plus Python and shell syntax
checks. No camera, servo commands or model downloads are used by these checks.
3D-print/CAD files and their dedicated geometry tests have been removed because
the physical project no longer uses printed components.

## Earlier Pi observations

Earlier real Pi checks verified Camera V2 capture,
cached CLIP inference, PCA9685 communication and operator-observed unloaded
routes. HOME is now tilt 125 / pan 90, with provisional tilt endpoints 90/160.
The VNC camera-only viewer displayed live frames and its window was visually
checked. These earlier observations do not validate the new classification
accuracy or any loaded item delivery.

The Pi kernel recorded undervoltage during a recognition-only diagnostic, even
without new servo commands. CPU/display load mitigations are not a repair for
deficient power delivery. See [the diagnosis](shutdown_troubleshooting.md).

## Still required

- Confirm the chosen pretrained backend and classification behaviour on labelled local images.
- Correct power delivery, then verify mounting, camera framing and unloaded
  clearance before loaded motor tests.
- Collect labelled local development and held-out images. Compare raw accuracy,
  accepted accuracy, coverage and per-class errors using the evaluator.
- Test unsupported objects and hands, changing lighting, stable decisions and
  one-item delivery into each bin. Test slow light dummy items first.

No improved accuracy percentage, model retraining result, load rating or
unattended-operation readiness is claimed.

## Pretrained backend update

Both backend integration paths have mocked-device/model tests. The new
four-way selection test confirms that a supported label is returned even when
unknown has the largest score, while motor eligibility still rejects it. The
preprocessing test verifies both edges of a wide object remain visible and BGR
is converted to RGB correctly. CLIP remains the default until comparative
labelled-image tests justify switching. No model is trained by this update.

Real cached-weight smoke checks on this Mac also completed for both the default
CLIP checkpoint and the official SigLIP 2 checkpoint, including image inference
after releasing the text encoder. Synthetic blank input still received a
supported best-match label and did not pass motor eligibility. These are
functional checks, not accuracy measurements. SigLIP 2 weights (about 1.5 GB)
are cached in a temporary Mac directory, not in Git or on the Pi. The installed
Transformers version emits upstream BOS/EOS configuration warnings for SigLIP;
the text processor and image inference checks nevertheless completed.

## Dashboard merge and sorting timing

The dark dashboard, code-free local access, systemd boot service and quiet HOME
control are merged into main, preserving the newer team assembly-document
update. Reboot startup was checked on the Pi; the web service, camera and
hardware-mode controller came back automatically. Pi power flags were `0x0`
during the checks; this does not measure the separate servo supply.

The operator reported sorting vibration remained. A slow eased trial and a
brief pan release while tilted did not remove it. A second unloaded front-left
trial with faster continuous easing and a 0.2-second tip pause reduced, but did
not eliminate, vibration. This second timing is configured; loaded delivery
is not established by that empty-tray observation. Tilt remains powered and
pan releases at HOME and, with the new opt-in dump setting, during tipping.
The new dump release has only one operator-observed unloaded route test; loaded
alignment and the remaining routes need physical validation. See [the diagnosis](servo_vibration.md).
