# EcoSort: AI-Powered Smart Waste Bin (Zero-Shot CLIP)

EcoSort is an Edge AI computer vision system designed to automate waste segregation into **4 distinct categories**:
1. **Paper** (Cardboard boxes, packaging, sheets)
2. **Plastic / Metal** (Bottles, containers, soda cans)
3. **Organic** (Food waste, fruit peels, vegetables)
4. **General Trash** (Dirty wrappers, non-recyclable landfill waste)

Powered by **OpenAI's Zero-Shot CLIP**, EcoSort classifies waste in real time without requiring manual dataset training, and communicates via USB Serial with an **Arduino (L293D Shield or PCA9685)** to physically trigger servo motors.

---

## Hardware Setup
- **Computing Device:** Mac or Raspberry Pi (with webcam / Pi Camera Module)
- **Microcontroller:** Arduino Uno / Nano / Mega
- **Motor Driver:** PCA9685 16-Channel PWM Driver or L293D Motor Shield
- **Actuators:** 2× Servo Motors (SG90 or MG996R)

---

## Software Stack
- **Python 3**
- **OpenAI CLIP** (`transformers` / `clip-vit-base-patch32`) — Zero-shot natural language image classification
- **PyTorch** (MPS Metal acceleration on Apple Silicon / CPU on Raspberry Pi)
- **OpenCV** (Background subtraction motion detection, object cropping)
- **pySerial** (USB Serial communication to Arduino at 9600 baud)

---

## Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Upload Firmware to Arduino
* For **PCA9685 16-Channel Driver**:  
  Open and upload [`hardware/arduino_ecosort_pca9685/arduino_ecosort_pca9685.ino`](hardware/arduino_ecosort_pca9685/arduino_ecosort_pca9685.ino)
* For **L293D Shield**:  
  Open and upload [`hardware/arduino_ecosort_l293d/arduino_ecosort_l293d.ino`](hardware/arduino_ecosort_l293d/arduino_ecosort_l293d.ino)

### 3. Run the Live Smart Bin
```bash
# Standard live run (Auto-detects camera and connected Arduino):
python live_smart_bin.py

# Simulation mode (No Arduino attached):
python live_smart_bin.py --no-arduino

# Raspberry Pi SSH Headless Mode (no GUI window required):
python live_smart_bin.py --headless --stable-frames 2

# Tuned confidence threshold:
python live_smart_bin.py --threshold 0.55
```

---

## Interactive Keyboard Shortcuts (In GUI Window)

| Hotkey | Action |
| :---: | :--- |
| **`1`** | Manually trigger **Paper** servo (`'P'`) |
| **`2`** | Manually trigger **Plastic/Metal** servo (`'M'`) |
| **`3`** | Manually trigger **Organic** servo (`'O'`) |
| **`4`** | Manually trigger **General Trash** servo (`'G'`) |
| **`C`** or **`R`** | **Recalibrate Tray**: Resets background subtraction on demand |
| **`Space`** | **Force Scan**: Evaluates current tray area immediately |
| **`H`** | Toggle on-screen **Help / Cheat Sheet** overlay |
| **`Q`** | Clean exit (resets servos to neutral position and closes serial) |

---

## 4-Way Hardware Trigger Mapping

| Waste Category | Serial Command | Default Servo Action |
| :--- | :---: | :--- |
| **Paper** | `'P'` | Servo 1 tilts Left ($45^\circ$) |
| **Plastic / Metal** | `'M'` | Servo 1 tilts Right ($135^\circ$) |
| **Organic** | `'O'` | Servo 2 tilts Forward ($45^\circ$) |
| **General Trash** | `'G'` | Servo 2 tilts Backward ($135^\circ$) |
