# EcoSort Smart Bin - 4-Way Waste Segregation Hardware

This folder contains Arduino firmware for two different motor driver options to segregate waste into **4 distinct categories**:
1. **Paper**
2. **Plastic or Metal**
3. **Organic**
4. **General Trash**

---

## Option A: PCA9685 16-Channel 12-bit PWM Driver (Recommended!)

The **PCA9685** module uses I2C communication (only 2 data wires to Arduino) and has a dedicated external power terminal to safely power high-torque servos without resetting the Arduino.

### 1. Arduino to PCA9685 Wiring (I2C):
| PCA9685 Pin | Arduino Uno / Nano | Arduino Mega | Note |
| :--- | :--- | :--- | :--- |
| **`GND`** | **`GND`** | **`GND`** | Logic Ground |
| **`VCC`** | **`5V`** | **`5V`** | Powers the PCA9685 chip only |
| **`SDA`** | **`A4`** (or SDA) | **Pin 20** (SDA) | I2C Data line |
| **`SCL`** | **`A5`** (or SCL) | **Pin 21** (SCL) | I2C Clock line |
| **`OE`** | *Unconnected* | *Unconnected* | Output Enable (pulled low internally) |

### 2. Servo Power (Green Screw Terminal):
* **`POWER +`**: Connect external **5V to 6V** power supply (positive)
* **`POWER -`**: Connect external power supply **GND** (negative)

### 3. Servo Connections:
Plug your servos into the 3-pin headers:
* **Channel 0**: Servo 1 (Paper / Plastic & Metal Axis)
* **Channel 1**: Servo 2 (Organic / General Trash Axis)

Follow the board's color rows:
* **Yellow Row (top)** = `PWM` (Signal wire: Orange/Yellow)
* **Red Row (middle)** = `V+` (Power wire: Red)
* **Black Row (bottom)** = `GND` (Ground wire: Brown/Black)

### 4. Software Setup:
1. In Arduino IDE, go to **Tools > Manage Libraries...**
2. Search for **"Adafruit PWM Servo Driver"** and click **Install**.
3. Open [`hardware/arduino_ecosort_pca9685/arduino_ecosort_pca9685.ino`](arduino_ecosort_pca9685/arduino_ecosort_pca9685.ino) and upload it to your Arduino!

---

## Option B: L293D Motor Driver Shield

If you are using the older stacking L293D shield instead:
* Use sketch: [`hardware/arduino_ecosort_l293d/arduino_ecosort_l293d.ino`](arduino_ecosort_l293d/arduino_ecosort_l293d.ino)
* `SERVO_1` header = Arduino Pin 10
* `SERVO_2` header = Arduino Pin 9

---

## 4-Way Category & Serial Command Table

Both Arduino sketches use the exact same serial commands from Python at **9600 baud**:

| Category | Model Prediction | Serial Cmd | Active Servo / Channel | Default Motion (Adjustable) |
| :--- | :--- | :---: | :--- | :--- |
| **Paper** | `paper` | **`'P'`** | Servo 1 (Channel 0 / Pin 10) | Tilts **Left** ($45^\circ$) |
| **Plastic / Metal** | `plastic_metal` | **`'M'`** | Servo 1 (Channel 0 / Pin 10) | Tilts **Right** ($135^\circ$) |
| **Organic** | `organic` | **`'O'`** | Servo 2 (Channel 1 / Pin 9) | Tilts **Forward** ($45^\circ$) |
| **General Trash** | `general` | **`'G'`** | Servo 2 (Channel 1 / Pin 9) | Tilts **Backward** ($135^\circ$) |

---

## Running with the Python Vision System

```bash
# Run the live vision script (auto-detects Arduino port)
python live_smart_bin.py --camera 1
```
