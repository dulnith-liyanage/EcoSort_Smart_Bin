# EcoSort Smart Bin

## Current physical calibration

The operator reports a new horizontal position at **tilt command 125°** on
26 October 2026. `servo_calibration.json` stores this HOME (pan 90°).
Both control programs share it. Provisional tilt endpoints are **90° forward
and 160° backward**, equal 35° command offsets from HOME. Shake is off and
movement uses one-degree steps at 40 ms per step. The Pi was disconnected
for this update: these routes have only been checked in software. Start with
small unloaded movements to verify clearance and direction before testing
item delivery. See [HOME calibration](docs/home_calibration.md).
`--driver sim` remains available for camera/software checks; it does not prove
that the physical assembly can reach those routes.

Camera V2 observes a stationary tray. CLIP selects among four supported classes:
**paper/cardboard, rigid plastic containers, metal cans, and fruit/vegetable
scraps**. Every detected item gets a best-match bin label. Unsupported or ambiguous
guesses require manual removal instead of automatic sorting. The
PCA9685 drives two MG996R servos in the existing metal pan/tilt kit.

## Web dashboard

The simple browser screen shows the tray camera, current classification, four
bin counters and a pause/resume button. History and device details expand only
when needed. No access code or Pi display is required on your trusted Wi-Fi.

```sh
# Local demo, without camera or motors:
./venv/bin/python -m dashboard --demo --autostart
```

Open http://127.0.0.1:8080. For the Pi, the prepared systemd installer enables the
website and physical sorter on boot after the initial empty-tray calibration.
Installed and reboot-tested on the Pi on 28 October 2026. Use
http://ecosort.local:8080 on the same trusted Wi-Fi. Pan releases its holding
signal at HOME to avoid the operator-confirmed idle vibration; tilt still holds
the tray level.
See [dashboard access and boot setup](docs/dashboard.md).

## Start here

- [Existing hardware assembly and bin labels](docs/assembly.md)
- [Classification, prompt groups and image evaluation](docs/classification.md)
- [Pi setup, wiring, calibration and running](docs/pi_setup.md)
- [VNC desktop access and motor-free camera preview](docs/vnc_camera.md)
- [Diagnose power loss during sorting](docs/shutdown_troubleshooting.md)
- [Verification and remaining checks](docs/verification.md)

The project uses the existing bins, tray, centre support and purchased metal
pan/tilt bracket. It does not require 3D-printed parts. CAD sources, printable
meshes and generated CAD assemblies have been removed; earlier designs remain
recoverable from Git history.

## Repository layout

```text
live_smart_bin.py            Camera, CLIP, uncertainty checks and sorting
camera_preview.py           Desktop/VNC camera viewer without motor commands
check_camera.py             Read-only Pi camera diagnostic
servo_control.py            Manual servo calibration and bin tests
servo_settings.py           Shared calibration and hardware ownership lock
servo_calibration.json      Level HOME and provisional route commands
setup_raspberry_pi.sh       Pi dependencies and I2C setup
fix_openblas.sh             Optional repair for a specific BLAS error
requirements.txt            Runtime dependencies
dashboard/                  Local web UI, authenticated API and telemetry bridge
scripts/                    Launchers, diagnostics, image evaluation and checks
docs/                       Setup, calibration, classification and verification
tests/                      Offline software regressions using fake hardware
```

Personal images, datasets, model weights and virtual environments are not
published. Existing root entry points remain compatible with Pi launch commands.

## Check on a computer without the Pi

With the runtime dependencies installed in your Python environment:

```sh
python -m unittest discover -s tests -v
python scripts/verify.py
python live_smart_bin.py --help
bash -n setup_raspberry_pi.sh fix_openblas.sh
```

Tests use fake devices and synthetic frames. They do not open a camera, send
servo commands, download weights or evaluate classification accuracy. Camera
enumeration on a Mac reports unavailable; it is not evidence of a wiring fault.

## Start recognition without motors

```sh
./venv/bin/python live_smart_bin.py --driver sim --cpu-threads 1
```

Use the Pi's VNC desktop for a window; add `--headless` over SSH. Close the
separate camera preview first. The four supported classes are project labels,
not a claim of compliance with all municipal collection categories. CLIP has
not been retrained, and no measured accuracy improvement is claimed without
held-out photographs from this camera and tray. See the evaluation guide.

Use `--model siglip2` to compare the alternative pretrained backend without training.
The baseline remains CLIP until labelled local tests demonstrate a better choice.
