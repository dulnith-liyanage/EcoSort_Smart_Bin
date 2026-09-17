# EcoSort: AI-Powered Smart Waste Bin (Zero-Shot CLIP)

EcoSort is an Edge AI computer vision and robotic sorting system designed to automate municipal waste segregation into **4 distinct bins** following the **Colombo Municipal Council (CMC) / Sri Lanka Solid Waste Guidelines**:
1. **Paper & Cardboard (Blue Bin)**: Cardboard packaging, newspapers, textbooks, cartons, clean paper sheets.
2. **Plastics & Polythene (Orange Bin)**: PET drink bottles, food containers, polythene grocery bags, lunch sheets, milk packets.
3. **Organic / Biodegradable Waste (Green Bin)**: Cooked food scraps, fruit peels, vegetable waste, coconut shells, tea leaves.
4. **Glass, Metal & Residual Landfill Trash (Red/Black Bin)**: Aluminum soda cans, tin cans, glass bottles, foil snack wrappers, non-recyclables.

Powered by **OpenAI's Zero-Shot CLIP**, EcoSort classifies waste in real time and commands an **Arduino-driven 2-Axis Pan-Tilt Servo Controller** to rotate horizontally to the designated bin and dump the waste with a downward pitch.

---

## Hardware Setup
- **Computing Device:** Mac or Raspberry Pi (with webcam / Pi Camera Module)
## Hardware Options

### Option A: Direct Raspberry Pi I2C (No Arduino Needed - Recommended!)
Connect the PCA9685 driver directly to the Raspberry Pi's 40-pin GPIO header:

| PCA9685 Pin | Raspberry Pi 40-Pin Header | Purpose |
| :--- | :--- | :--- |
| **VCC** | **Pin 1 (3.3V Power)** | Powers PCA9685 logic chip with 3.3V |
| **GND** | **Pin 6 (or Pin 9 GND)** | Common Ground |
| **SDA** | **Pin 3 (GPIO 2 / I2C1 SDA)** | I2C Data |
| **SCL** | **Pin 5 (GPIO 3 / I2C1 SCL)** | I2C Clock |
| **V+ (Screw Terminal)** | **External 5V–6V 3A Power Supply** | Powers the high-torque MG996R motors |

- **MG996R Pan Servo**: Plugs into **Channel 0** on PCA9685.
- **MG996R Tilt Servo**: Plugs into **Channel 1** on PCA9685.

### Option B: Arduino over USB Serial
If using an Arduino Uno / Nano as a USB bridge, connect Arduino to PCA9685 (SDA $\rightarrow$ A4, SCL $\rightarrow$ A5) and plug the Arduino into the Pi or Mac via USB.

---

## Quickstart

### 1. Automated Setup on Raspberry Pi
```bash
bash setup_raspberry_pi.sh
```

### 2. Run the Live Smart Bin
```bash
# Auto-detects Direct Raspberry Pi I2C or connected Arduino:
python live_smart_bin.py

# Explicit Direct Raspberry Pi I2C mode (SSH Headless):
python live_smart_bin.py --driver rpi-i2c --headless --stable-frames 2

# Simulation Mode (No hardware attached):
python live_smart_bin.py --driver sim
```

---

## Interactive Keyboard Shortcuts (In GUI Window)

| Hotkey | Action |
| :---: | :--- |
| **`1`** | Manually trigger **Paper (Blue Bin)** (`'P'` -> Pan 30° -> Dump) |
| **`2`** | Manually trigger **Plastic & Polythene (Orange Bin)** (`'M'` -> Pan 70° -> Dump) |
| **`3`** | Manually trigger **Organic Waste (Green Bin)** (`'O'` -> Pan 110° -> Dump) |
| **`4`** | Manually trigger **Glass/Metal/Residual (Red Bin)** (`'G'` -> Pan 150° -> Dump) |
| **`C`** or **`R`** | **Recalibrate Tray**: Resets background subtraction on demand |
| **`Space`** | **Force Scan**: Evaluates current tray area immediately |
| **`H`** | Toggle on-screen **Help / Cheat Sheet** overlay |
| **`Q`** | Clean exit (resets servos to neutral position and closes serial) |

---

## Colombo Municipal Council (CMC) 4-Bin Pan-Tilt Layout

```
         [Front Arc of 4 Bins]
   
   (Blue Bin)     (Orange Bin)     (Green Bin)     (Red Bin)
    Paper           Plastic          Organic        Residual
     30°              70°             110°            150°
       \               |               /               /
        \              |              /               /
         ───────> [2-Axis Pan-Tilt] <───────
                     (Home: 90°)
```

| Waste Category (CMC System) | Bin Color | Serial Cmd | Pan Angle | Tilt Action |
| :--- | :---: | :---: | :---: | :--- |
| **Paper & Cardboard** | **Blue** | `'P'` | **30° (Far Left)** | Pan 30° $\rightarrow$ Tilt down 30° $\rightarrow$ Return Home |
| **Plastics & Polythene** | **Orange** | `'M'` | **70° (Mid-Left)** | Pan 70° $\rightarrow$ Tilt down 30° $\rightarrow$ Return Home |
| **Organic / Food Waste** | **Green** | `'O'` | **110° (Mid-Right)** | Pan 110° $\rightarrow$ Tilt down 30° $\rightarrow$ Return Home |
| **Glass, Metal & Residual** | **Red / Black** | `'G'` | **150° (Far Right)** | Pan 150° $\rightarrow$ Tilt down 30° $\rightarrow$ Return Home |
