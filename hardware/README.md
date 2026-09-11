# EcoSort Smart Bin - Arduino & L293D Dual Servo Setup

This folder contains the Arduino firmware to control **two servo motors** using an **L293D Motor Driver Shield** connected to your computer via USB Serial.

---

## 1. Pin Mapping on L293D Shield

Standard L293D motor shields (Adafruit v1 clone) have two dedicated 3-pin headers in the top corner for servo motors:

| L293D Shield Header | Arduino Digital Pin | Waste Category | Target Action |
| :--- | :--- | :--- | :--- |
| **`SERVO_1`** | **Pin 10** | **General Trash** (`organic`, `general`) | Triggers Servo 1 dump cycle |
| **`SERVO_2`** | **Pin 9** | **Recyclables** (`paper`, `plastic_metal`) | Triggers Servo 2 dump cycle |

Each 3-pin header is arranged as:
* **`-` or `GND`**: Connect to Servo **Brown / Black** wire
* **`+` or `5V`**: Connect to Servo **Red** wire
* **`S` or `Signal`**: Connect to Servo **Orange / Yellow** wire

---

## 2. Arduino Setup Instructions

1. Open the [Arduino IDE](https://www.arduino.cc/en/software).
2. Open the sketch file:  
   [`hardware/arduino_ecosort_l293d/arduino_ecosort_l293d.ino`](arduino_ecosort_l293d/arduino_ecosort_l293d.ino)
3. Select your Board (**Tools > Board > Arduino Uno**) and Port (**Tools > Port**).
4. Click **Upload** (Arrow icon).
5. (Optional) Open **Serial Monitor** at **9600 baud**:
   * Type `G` and press Enter $\rightarrow$ Servo 1 should move (General Trash).
   * Type `R` and press Enter $\rightarrow$ Servo 2 should move (Recyclables).
   * Type `T` and press Enter $\rightarrow$ Runs a full self-test of both servos.

---

## 3. Running with Python Vision Model

Once the Arduino code is uploaded and connected via USB to your computer:

```bash
# 1. Install serial communication library
pip install pyserial

# 2. Run the live vision script (automatically detects Arduino port)
python live_smart_bin.py

# Or specify your port explicitly if needed:
# macOS example:
python live_smart_bin.py --port /dev/cu.usbmodem1101
# Windows example:
python live_smart_bin.py --port COM3
```

### How the Logic Works:
1. The camera scans the center tray.
2. Background subtraction detects when an object is placed.
3. The Keras model (`ecosort_model.keras`) predicts the item:
   - If classified as `paper` or `plastic_metal` $\rightarrow$ Sends `'R'` over USB $\rightarrow$ **Servo 2 moves**.
   - If classified as `organic` or `general` $\rightarrow$ Sends `'G'` over USB $\rightarrow$ **Servo 1 moves**.
4. The system pauses for a 2.5-second cooldown while the physical sorting completes before scanning for the next item.
