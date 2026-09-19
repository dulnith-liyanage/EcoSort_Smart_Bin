# EcoSort Smart Bin: AI-Powered Automated Waste Segregation System

**EcoSort** is an intelligent, edge-computed municipal waste segregation system. It combines real-time computer vision powered by **OpenAI's Zero-Shot CLIP (Contrastive Language-Image Pre-Training)** with a high-torque **2-Axis Pan-Tilt Robotic Mechanism** to automatically classify and sort solid waste into four separate bins arranged in a **2x2 grid**.

The system is designed to run directly on a **Raspberry Pi 5** using hardware I2C without needing an external microcontroller, aligned with the **Colombo Municipal Council (CMC)** and national solid waste segregation standards.

---

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Hardware Requirements](#hardware-requirements)
3. [Software Requirements](#software-requirements)
4. [Physical 2x2 Grid Layout & Kinematics](#physical-2x2-grid-layout--kinematics)
5. [Wiring & Hardware Connections](#wiring--hardware-connections)
6. [Installation & Setup](#installation--setup)
7. [Hardware Diagnostics & Verification](#hardware-diagnostics--verification)
8. [Usage & Operation](#usage--operation)
9. [CLI Options & Hotkeys](#cli-options--hotkeys)

---

## System Architecture

```
                                    +------------------------------+
                                    |     Optical Input Sensor     |
                                    |  (Pi Camera v2.1 on CAM/0    |
                                    |     or 720p/1080p USB Cam)   |
                                    +--------------+---------------+
                                                   | Raw video stream
                                                   v
+-------------------------------+   +------------------------------+
|   Background Subtraction ROI  |-->|  OpenAI Zero-Shot CLIP Model |
| (Gaussian blur + accumulation |   | (clip-vit-base-patch32 CPU)  |
|   motion / object isolation)  |   | Softmax category inference   |
+-------------------------------+   +--------------+---------------+
                                                   | Confidence >= threshold
                                                   v (across N stable frames)
                                    +------------------------------+
                                    |  Decision & Motion Planner   |
                                    | Kinematic angle calculation  |
                                    | (Direction-aware dump+jitter)|
                                    +--------------+---------------+
                                                   | I2C Bus (/dev/i2c-1)
                                                   v
                                    +------------------------------+
                                    | PCA9685 16-Channel PWM Board |
                                    +--------------+---------------+
                                                   | PWM Pulses (50 Hz)
                         +-------------------------+-------------------------+
                         |                                                   |
                         v                                                   v
           +---------------------------+                       +---------------------------+
           |   MG996R Pan Servo (Ch 0) |                       |  MG996R Tilt Servo (Ch 1) |
           | Base Azimuth: 45° / 135°  |                       | Pitch: 35° Fwd / 145° Rev |
           +---------------------------+                       +---------------------------+
```

---

## Hardware Requirements

### 1. Primary Computing Unit
* **Raspberry Pi 5** (4GB or 8GB recommended for on-device PyTorch inference) or **Raspberry Pi 4 Model B** (4GB/8GB).
* *Note: Can also run on macOS (Apple Silicon MPS accelerated) or x86_64 Linux/Windows for development and simulation mode.*
* **MicroSD Card**: 32 GB minimum (Class 10 / A2 rated) or NVMe SSD for fast model loading.
* **Power Supply for Pi**: Official 27W USB-C Power Supply (5.1V / 5.0A).

### 2. Optical Sensor (Camera)
* **Raspberry Pi Camera Module v2.1** (8MP Sony IMX219) connected to **CAM/0** (using a 22-pin to 15-pin mini-CSI ribbon cable for Pi 5), OR
* **Standard UVC USB Webcam** (720p / 1080p, plugged into USB 3.0 port).

### 3. Motor Controller & Actuators
* **Servo Driver Board**: **PCA9685 16-Channel 12-Bit PWM I2C Driver** (Default I2C address `0x40`).
* **Servo Motors**: **2× MG996R High-Torque Metal Gear Servos**:
  * Operating Voltage: 4.8V – 6.6V
  * Stall Torque: 9.4 kg·cm (at 4.8V) to 11.0 kg·cm (at 6.0V)
  * Rotation: 0° to 180° standard range
  * Channel 0: Horizontal Azimuth (Pan)
  * Channel 1: Vertical Pitch (Tilt Dump)
* **2-Axis Pan-Tilt Bracket Assembly**: Heavy-duty aluminum or reinforced 3D-printed Pan-Tilt gimbal bracket.
* **Waste Chute / Tray**: Lightweight sorting pan/chute mounted on the tilt horn.

### 4. Dedicated Servo Power Supply
* **External 5V–6V DC 3A–5A Power Supply**: Connects directly to the PCA9685 green screw terminal (`V+` and `GND`).
* *Crucial: High-torque servos draw up to 2.5A peak during stall or acceleration. Never power the MG996R servos from the Raspberry Pi 5V header pins.*

### 5. Collection Bins & Interconnects
* **4× Waste Bins**: Arranged in a 2x2 square formation beneath the central pan-tilt tray.
* **Jumper Wires**: 4× Female-to-Female jumper wires for Raspberry Pi GPIO to PCA9685 logic header (`VCC`, `GND`, `SDA`, `SCL`).

---

## Software Requirements

### 1. Operating System
* **Raspberry Pi OS 64-bit** (Debian 12 Bookworm or Debian 13 Trixie, `aarch64` / `arm64`).
* *macOS 12+ or Ubuntu 22.04+ supported for development/testing.*

### 2. Python Runtime
* **Python 3.10, 3.11, 3.12, or 3.13** (64-bit).

### 3. System Packages & Native Libraries
The following system libraries must be installed on the Linux host (`apt`):

| Package | Purpose |
| :--- | :--- |
| `i2c-tools` | I2C bus inspection utilities (`i2cdetect`, `i2cget`) |
| `python3-smbus` | SMBus Python bindings for I2C protocol |
| `libopenblas0`, `libopenblas0-pthread`, `libopenblas-dev` | High-performance BLAS linear algebra runtime for PyTorch on ARM64 |
| `liblapack-dev` | Numerical computation routines |
| `libgl1`, `libgomp1` | OpenGL runtime and OpenMP support for OpenCV |
| `v4l-utils` | Video4Linux camera diagnostic and capture tools |
| `python3-pip`, `python3-venv`, `python3-dev` | Python virtual environment and header packages |

### 4. Python Dependencies (`requirements.txt`)
* **`torch` & `torchvision`**:
  * On Raspberry Pi: Pure **CPU-only build** (`--index-url https://download.pytorch.org/whl/cpu`) to eliminate unnecessary multi-gigabyte NVIDIA CUDA overhead.
  * On Mac: Native MPS (Metal Performance Shaders) acceleration is automatically utilized.
* **`transformers` (>= 4.30.0)**: Hugging Face runtime for loading `openai/clip-vit-base-patch32` (~350 MB cached locally for 100% offline inference).
* **`opencv-python` (>= 4.5.0)**: Real-time video frame acquisition, Gaussian background modeling, ROI segmentation, and HUD rendering.
* **`adafruit-circuitpython-servokit` (>= 1.3.0)**: Direct I2C hardware PWM control over PCA9685 registers via Linux I2C device tree (`/dev/i2c-1`).
* **`pillow`**: Image handling and pre-processing pipeline for CLIP.
* **`numpy`**: Matrix transformations and running average calculations.
* **`pyserial` (>= 3.5)**: Serial communication utilities.

---

## Physical 2x2 Grid Layout & Kinematics

The 4 solid waste bins are positioned in a **2x2 square grid** with the **2-Axis Pan-Tilt mechanism mounted directly at the center**. 

The tray utilizes **bidirectional pitch** (forward vs. reverse tilt) along two diagonal axes, allowing standard 180° servos to reach all 4 quadrants without 360° continuous rotation.

```text
                           [ FRONT ]
         +------------------------------+------------------------------+
         |   BIN 1: Paper & Cardboard   |   BIN 2: Plastics & Poly     |
         |   Color: BLUE                |   Color: ORANGE              |
         |   Position: FRONT-LEFT       |   Position: FRONT-RIGHT      |
         |   Pan: 135°                  |   Pan: 45°                   |
         |   Tilt: 35° (Forward Pitch)  |   Tilt: 35° (Forward Pitch)  |
     [L] +------------------------------+------------------------------+ [R]
         |                  \        (0,0)        /                    |
         |                   \  PAN-TILT AT CENTER/                     |
         |                    \   (Home: 90°,90°)/                      |
         +------------------------------+------------------------------+
         |   BIN 3: Organic / Food      |   BIN 4: Glass & Landfill    |
         |   Color: GREEN               |   Color: RED / BLACK         |
         |   Position: REAR-LEFT        |   Position: REAR-RIGHT       |
         |   Pan: 45°                   |   Pan: 135°                  |
         |   Tilt: 145° (Reverse Pitch) |   Tilt: 145° (Reverse Pitch) |
         +------------------------------+------------------------------+
                           [ REAR ]
```

### Colombo Municipal Council (CMC) Category Mapping:

| Bin | Waste Category | CMC Color | Quadrant | Pan Angle | Tilt Dump | Motion Description |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **—** | **Home / Standby** | — | Center | **90°** | **90°** | Flat horizontal scanning tray |
| **Bin 1** | Paper & Cardboard | Blue | Front-Left | **135°** | **35°** | Aligns to 135° diagonal, pitches forward |
| **Bin 2** | Plastics & Polymers | Orange | Front-Right | **45°** | **35°** | Aligns to 45° diagonal, pitches forward |
| **Bin 3** | Organic / Food Waste | Green | Rear-Left | **45°** | **145°** | Aligns to 45° diagonal, pitches in reverse |
| **Bin 4** | Glass, Metal & Landfill | Red | Rear-Right | **135°** | **145°** | Aligns to 135° diagonal, pitches in reverse |

*Direction-Aware Anti-Stick Vibration:* After tilting, the tray performs high-frequency micro-pulses (reaching 25° for forward dumps, or 155° for reverse dumps) to shake loose sticky waste, before smoothly returning to 90° Home.

---

## Wiring & Hardware Connections

### 1. Raspberry Pi 5 to PCA9685 (Logic Header)

Direct I2C connection via the 40-pin GPIO header:

| PCA9685 Pin | Raspberry Pi 5 Pin | Header Location | Description |
| :--- | :--- | :--- | :--- |
| **VCC** | **Pin 1** | 3.3V Power | Powers PCA9685 logic IC (3.3V logic) |
| **GND** | **Pin 9 (or 6)** | Ground | Common logic ground |
| **SDA** | **Pin 3** | GPIO 2 / SDA1 | Hardware I2C Data line |
| **SCL** | **Pin 5** | GPIO 3 / SCL1 | Hardware I2C Clock line |

### 2. External Power Supply (PCA9685 Screw Terminal)

| Power Supply Wire | PCA9685 Screw Terminal | Description |
| :--- | :--- | :--- |
| **Positive (+5V to +6V DC)** | **`V+` Terminal** | Supplies high current to servos |
| **Negative (GND)** | **`GND` Terminal** | Common power supply ground |

### 3. Servo Connections to PCA9685 Headers

| Servo Actuator | PCA9685 3-Pin Channel | Pin Orientation (Wire Colors) |
| :--- | :--- | :--- |
| **Pan Servo (Base Rotation)** | **Channel 0** | Black/Brown $\rightarrow$ GND, Red $\rightarrow$ V+, Yellow/Orange $\rightarrow$ Signal (PWM) |
| **Tilt Servo (Chute Pitch)** | **Channel 1** | Black/Brown $\rightarrow$ GND, Red $\rightarrow$ V+, Yellow/Orange $\rightarrow$ Signal (PWM) |

---

## Installation & Setup

### Option A: Automated Installation (Raspberry Pi)
Run the automated installation script to configure system libraries, user permissions, I2C, CPU PyTorch, and pre-cache the CLIP neural network weights:

```bash
cd ~/EcoSort_Smart_Bin
bash setup_raspberry_pi.sh
```

### Option B: Manual Installation
If setting up manually on Raspberry Pi or a personal computer:

```bash
# 1. Install system prerequisites (Debian/Ubuntu)
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-dev libopenblas0 libopenblas0-pthread \
                        libopenblas-dev liblapack-dev libgl1 v4l-utils i2c-tools python3-smbus

# 2. Enable hardware I2C interface & grant permissions
sudo raspi-config nonint do_i2c 0
sudo usermod -a -G dialout,i2c $USER

# 3. Create virtual environment
python3 -m venv venv --system-site-packages
source venv/bin/activate

# 4. Install CPU-only PyTorch (avoids downloading 1.7GB+ of unused CUDA drivers)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 5. Install remaining dependencies
pip install -r requirements.txt
```

---

## Hardware Diagnostics & Verification

### 1. Check I2C PCA9685 Communication
Verify that the PCA9685 is detected on I2C bus 1 at address `0x40`:
```bash
i2cdetect -y 1
```
*(You should see `40` listed in the matrix output. If empty, check the SDA/SCL and 3.3V/GND wires).*

### 2. Verify Camera Interface
Run the built-in diagnostic utility to verify CSI / USB camera status:
```bash
./venv/bin/python check_camera.py
```
*For Pi Camera Module v2.1 on Raspberry Pi 5 CAM/0, ensure `/boot/firmware/config.txt` contains `dtoverlay=imx219,cam0` and `camera_auto_detect=0`.*

---

## Usage & Operation

### 1. Test & Calibrate Pan-Tilt Servos
Before running live video classification, use the standalone servo utility to calibrate angles and test each bin dump:
```bash
./venv/bin/python servo_control.py
```
* Interactive Options:
  * `[1]` Return to HOME (Pan 90°, Tilt 90°)
  * `[4]` Test Bin 1 (Front-Left: Paper) $\rightarrow$ Pan 135°, Tilt 35°
  * `[5]` Test Bin 2 (Front-Right: Plastics) $\rightarrow$ Pan 45°, Tilt 35°
  * `[6]` Test Bin 3 (Rear-Left: Organic) $\rightarrow$ Pan 45°, Tilt 145°
  * `[7]` Test Bin 4 (Rear-Right: Landfill) $\rightarrow$ Pan 135°, Tilt 145°
  * `[8]` Run Full 4-Bin Demo (Cycles all bins sequentially)

### 2. Run Live Smart Bin in Headless Mode (Recommended for Raspberry Pi SSH)
```bash
./venv/bin/python live_smart_bin.py --headless --driver rpi-i2c --stable-frames 2
```

### 3. Run Live Smart Bin with Graphical Desktop HUD (HDMI Monitor)
```bash
./venv/bin/python live_smart_bin.py --driver rpi-i2c
```

### 4. Run in Simulation Mode (No Physical Hardware Required)
Test classification and UI on Mac, Linux, or PC without servo hardware attached:
```bash
python live_smart_bin.py --driver sim
```

---

## CLI Options & Hotkeys

### Command Line Arguments (`live_smart_bin.py`)

| Argument | Default | Description |
| :--- | :---: | :--- |
| `--driver` | `auto` | Hardware driver mode: `auto`, `rpi-i2c`, or `sim` (simulation) |
| `--pan-ch` | `0` | PCA9685 PWM channel for Pan servo |
| `--tilt-ch` | `1` | PCA9685 PWM channel for Tilt servo |
| `--camera` | `0` | Camera device index (`0` for CSI/primary, `1` for USB) |
| `--headless` | `False` | Disables OpenCV GUI window (optimal for SSH sessions) |
| `--threshold` | `0.60` | Minimum confidence score (0.0 – 1.0) to trigger physical sorting |
| `--stable-frames` | `3` | Number of consecutive identical classifications required before triggering |
| `--cooldown` | `3.8` | Seconds to pause detection after a dump to allow user to place next item |
| `--prompts-file` | `None` | Path to custom JSON file overriding zero-shot natural language prompts |

### Interactive GUI Keyboard Shortcuts (Active in Desktop Mode)

| Key | Action |
| :---: | :--- |
| **`1`** | Manually trigger **Bin 1: Paper & Cardboard** (Pan 135° $\rightarrow$ Tilt 35° Forward) |
| **`2`** | Manually trigger **Bin 2: Plastics & Polythene** (Pan 45° $\rightarrow$ Tilt 35° Forward) |
| **`3`** | Manually trigger **Bin 3: Organic Waste** (Pan 45° $\rightarrow$ Tilt 145° Reverse) |
| **`4`** | Manually trigger **Bin 4: Glass & Landfill** (Pan 135° $\rightarrow$ Tilt 145° Reverse) |
| **`C`** or **`R`** | **Recalibrate Tray**: Resets dynamic background subtraction baseline |
| **`Space`** | **Force Scan**: Triggers immediate inference on current tray contents |
| **`H`** | Toggle on-screen **Help / Diagnostics** HUD overlay |
| **`Q`** | **Clean Exit**: Centers servos to neutral 90° Home and releases camera |
