# EcoSort Smart Bin - 2-Axis Pan-Tilt Hardware (2x2 Grid)

This hardware setup uses a **Raspberry Pi 5 (Direct I2C)** connected to a **PCA9685 16-Channel PWM Servo Driver** to actuate two **MG996R high-torque metal gear servos** in a **2x2 waste bin grid** layout.

---

## 1. Physical 2x2 Grid Bin Layout

The 4 solid waste bins are arranged in a **2x2 square grid**, with the **2-Axis Pan-Tilt mechanism mounted directly at the center**:

```text
               [ FRONT ]
    +------------------------------+------------------------------+
    |   BIN 1: Paper & Cardboard   |   BIN 2: Plastics & Poly     |
    |   Color: BLUE                |   Color: ORANGE              |
    |   Position: FRONT-LEFT       |   Position: FRONT-RIGHT      |
    |   Pan: 135° | Tilt: 35° (Fwd)|   Pan: 45°  | Tilt: 35° (Fwd)|
[L] +------------------------------+------------------------------+ [R]
    |                  \        (0,0)        /                    |
    |                   \  PAN-TILT AT CENTER/                     |
    |                    \     (Home: 90°)  /                      |
    +------------------------------+------------------------------+
    |   BIN 3: Organic / Food      |   BIN 4: Glass & Landfill    |
    |   Color: GREEN               |   Color: RED / BLACK         |
    |   Position: REAR-LEFT        |   Position: REAR-RIGHT       |
    |   Pan: 45°  | Tilt: 145°(Rev)|   Pan: 135° | Tilt: 145°(Rev)|
    +------------------------------+------------------------------+
               [ REAR ]
```

### Motion Kinematics:
- **Pan Servo (Channel 0)**: Rotates the platform between the two diagonal axes:
  - **Diagonal 1 (45°)**: Aligns between Front-Right and Rear-Left.
  - **Diagonal 2 (135°)**: Aligns between Front-Left and Rear-Right.
  - **Center / Home (90°)**: Faces straight forward.
- **Tilt Servo (Channel 1)**: Tilts the tray along the chosen diagonal:
  - **Level / Home (90°)**: Tray is horizontal and flat (waiting for object).
  - **Forward Dump (35°)**: Tray dips downward to slide waste into the **Front** bin.
  - **Backward Dump (145°)**: Tray tilts in reverse to slide waste into the **Rear** bin.

---

## 2. Wiring Diagram: Raspberry Pi 5 to PCA9685

No Arduino is needed! The PCA9685 connects directly to the Raspberry Pi hardware I2C pins.

```text
Raspberry Pi 5 (GPIO Header)                  PCA9685 16-Ch Servo Driver
  Pin 1  (3.3V Power)   -------------------->  VCC  (Logic 3.3V)
  Pin 9  (Ground)       -------------------->  GND  (Logic Ground)
  Pin 3  (GPIO 2 / SDA) -------------------->  SDA  (I2C Data)
  Pin 5  (GPIO 3 / SCL) -------------------->  SCL  (I2C Clock)

External Power (5V - 6V, 3A DC)               PCA9685 Screw Terminal
  Positive (+)          -------------------->  V+   (Green Screw Terminal)
  Negative (-)          -------------------->  GND  (Green Screw Terminal)

MG996R Servos                                 PCA9685 3-Pin Headers
  Pan Servo (Base Horizontal Rotation) ----->  Channel 0
  Tilt Servo (Tray Vertical Pitch)     ----->  Channel 1
```

> [!IMPORTANT]
> **Servo Power**: MG996R servos draw up to 2.5A peak. Always supply external 5V-6V power to the green screw terminal. Never power the servos directly from the Raspberry Pi 5V header pin.

---

## 3. Testing & Calibrating Servos

To test the 2x2 grid movements without running any vision models:

```bash
cd ~/EcoSort_Smart_Bin
./venv/bin/python servo_control.py
```

Options in the interactive menu:
- `[1]` Return to HOME (Pan 90°, Tilt 90°)
- `[4]` Test Bin 1 (Front-Left: Paper) -> Pan 135°, Tilt 35°
- `[5]` Test Bin 2 (Front-Right: Plastics) -> Pan 45°, Tilt 35°
- `[6]` Test Bin 3 (Rear-Left: Organic) -> Pan 45°, Tilt 145°
- `[7]` Test Bin 4 (Rear-Right: Landfill) -> Pan 135°, Tilt 145°
- `[8]` Run Full 4-Bin Demo (Cycles all 4 quadrants)
