# Pi wiring, setup and operation

These checks require the Raspberry Pi and are pending. Do not run the OS setup
or BLAS repair script on this Mac; both modify a Debian/Pi installation.

## Wiring, with all power off

| Pi 5 physical header pin | PCA9685 marking |
|---|---|
| 1 (3.3 V) | VCC, logic power |
| 3 (GPIO2/SDA) | SDA |
| 5 (GPIO3/SCL) | SCL |
| 9 (GND) | GND |

Connect the pan servo to channel 0 and tilt servo to channel 1. Confirm each
plug's signal, power and ground order from the actual board markings. Supply
the servo V+ terminal from an appropriately rated separate 5–6 V supply within
your servos' specifications, with a common ground. Do not supply both MG996R
servos from the Pi's 5 V header or via breadboard/jumper-wire power contacts.
Size supply, wiring and protection for simultaneous stall current; the photo
does not establish a supply's rating or the pin-by-pin connections.

Camera V2 connects to the Pi 5 camera connector using the compatible 22-pin to
15-pin ribbon. Inspect the actual connector latch and contact orientation using
the Pi instructions; never plug/unplug the ribbon while powered. Both boards
are close together on the overhead carrier, so no long CSI ribbon is required.

Primary wiring reference: [Adafruit PCA9685 with Raspberry Pi](https://learn.adafruit.com/adafruit-16-channel-servo-driver-with-raspberry-pi/hooking-it-up).
Its logic/servo power distinction applies to this chip; verify your clone's
terminal markings and protection circuitry separately.

## Install on 64-bit Raspberry Pi OS

From the repository root:

```sh
bash setup_raspberry_pi.sh
# Reboot/log in again after changes to I2C group membership.
i2cdetect -y 1
./venv/bin/python check_camera.py
```

Expected default I2C address is `40`; address jumpers can change it. Setup installs
Picamera2 and rpicam-apps through apt, then creates a virtual environment that
can see the system camera packages. It installs runtime packages and downloads
CLIP weights, so first setup needs network access. A successful local syntax
check does not prove apt package availability or Pi wheel compatibility.

If you already have a venv created without `--system-site-packages`, recreate it
deliberately or adjust it before expecting system Picamera2 to import. Do not
run `fix_openblas.sh` routinely; it is retained for the specific missing BLAS
symbol error and has not been executed during this offline review.

## Calibrate first

**Current HOME is tilt 15°, confirmed by the operator, not the old nominal 90°.**
The sorter rejects the resulting unreachable forward routes before hardware
initialisation. Read [HOME and horn correction](home_calibration.md) before
running the sorter, full sweeps, or bin tests. Use `servo_control.py
--check-calibration` for a no-hardware range check. `--tilt-home` commands only
the saved tilt position; manual angle commands are absolute.

```sh
./venv/bin/python servo_control.py
```

Support the unloaded tray and remove obstructions before sending HOME: a servo
has no position feedback and the initial command may move it abruptly. Use the
manual angle menu to establish level and both diagonals. The inherited range
can reach the mechanical stops on some horns/kits; limit it to verified motion
before a full cycle. Match the numbered bins to the guide before using keys 1–4.
The calibrator is a physical control tool, not a simulation.

## Run camera preview and recognition

```sh
# Desktop + fake servos: checks live images without actuator commands.
./venv/bin/python live_smart_bin.py --driver sim
# Real hardware, only after physical calibration:
./venv/bin/python live_smart_bin.py --driver rpi-i2c
# SSH without a desktop:
./venv/bin/python live_smart_bin.py --headless --driver rpi-i2c
```

`--camera 0` selects camera index 0 (CSI enumeration index, not necessarily a
guarantee about the labelled connector); `--camera 1` requests index 1. Native
Picamera2 is tried on Linux, with OpenCV fallback. Explicit hardware driver
failure now stops startup; `auto` may fall back to simulation and reports it.
`--driver sim` still opens a real camera and loads CLIP; it is not the offline
unit test mode.

Keep the tray empty for its first 30 frames. Centre it in the scanning square;
press **C** to recalibrate the empty view after moving the camera or tray. Place
one small item, withdraw hands, and wait. Keys **1–4** manually sort; **Space**
forces a scan and bypasses confidence/stability checks, so use it only as a
supervised diagnostic. **Q** exits. Default confidence is 0.60, stable predictions
3 and cooldown 3.8 seconds after completed movement. A probability is a relative
score among these four prompts, not a calibrated accuracy or hazard detector.

Test an empty tray, representative paper/plastic/food/residual items, changing
light and false positives before enabling unattended operation. These checks
cannot be substituted by CAD validity or synthetic camera tests.

The RGB888 Picamera2 stream is already BGR byte order for OpenCV. The application
now leaves it in that order, then converts once to RGB for CLIP. Source:
[Raspberry Pi Picamera2 format mapping](https://github.com/raspberrypi/picamera2/blob/main/picamera2/request.py).
