/*
 * EcoSort Smart Bin - 4-Way Waste Segregator
 * 2-Axis Pan-Tilt Servo Controller (PCA9685 16-Channel PWM Driver)
 * Tailored for Colombo Municipal Council (CMC) / Sri Lanka Solid Waste Guidelines
 * 
 * Hardware:
 *   - Arduino Uno / Nano / Mega
 *   - PCA9685 16-Channel 12-bit PWM Driver (I2C: SDA=A4, SCL=A5 on Uno)
 *   - 2-Axis Pan-Tilt Bracket with 2x SG90 / MG90S / MG996R Servos:
 *       * Servo 1 (PAN  - Channel 0): Base horizontal rotation (Yaw 0 to 180 deg)
 *       * Servo 2 (TILT - Channel 1): Pitch elevation arm (Tray up/down)
 *   - External 5V-6V Power Supply connected to PCA9685 green screw terminal
 * 
 * Colombo Municipal Council (CMC) 4-Bin Arc Layout:
 *   - Bin 1 (Far Left   - Pan 30 deg)  : BLUE   -> Paper & Cardboard ('P' / '1')
 *   - Bin 2 (Mid-Left   - Pan 70 deg)  : ORANGE -> Plastics & Polythene ('M' / '2')
 *   - Bin 3 (Mid-Right  - Pan 110 deg) : GREEN  -> Organic / Biodegradable Food Waste ('O' / '3')
 *   - Bin 4 (Far Right  - Pan 150 deg) : RED    -> Glass, Metal & Residual Landfill Trash ('G' / '4')
 * 
 * Operation Sequence:
 *   1. Resting state: Pan = 90 deg (Center), Tilt = 90 deg (Tray horizontal / flat).
 *   2. Command received from AI vision:
 *        a) Pan servo rotates smoothly to target bin angle while Tilt stays 90 deg (flat).
 *        b) Once over the designated bin, Tilt servo pitches down to 30 deg to slide waste off.
 *        c) Holds for 1000ms (gravity slide + gentle dislodge vibration).
 *        d) Tilt servo returns to 90 deg (level).
 *        e) Pan servo returns to 90 deg (center home).
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Default I2C address for PCA9685 is 0x40
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// --- PCA9685 Channel Assignments ---
const uint8_t PAN_CHANNEL  = 0; // Bottom Base Servo (Horizontal Pan)
const uint8_t TILT_CHANNEL = 1; // Upper Arm Servo (Vertical Tilt / Dump)

// --- Pulse Lengths (50 Hz / 20ms period, 12-bit = 4096 ticks) ---
const int SERVOMIN = 125; // Pulse length count for 0 degrees (~600us)
const int SERVOMAX = 575; // Pulse length count for 180 degrees (~2400us)

// --- Pan-Tilt Home & Dump Positions ---
const int PAN_HOME       = 90;  // Straight ahead / center
const int TILT_HOME      = 90;  // Level / Flat tray (holds waste while scanning & panning)
const int TILT_DUMP      = 30;  // Pitched down forward to dump (invert to 150 if horn is reversed)

const int DUMP_HOLD_MS   = 1100; // Time in ms to pause at dump angle for gravity slide
const int STEP_DELAY_MS  = 9;    // Speed control: ms per 1-degree step (prevents jerking)

// --- Colombo Municipal Council (CMC) 4-Bin Pan Angles ---
const int PAN_BIN_PAPER    = 30;  // [1] Blue Bin: Paper & Cardboard (Far Left)
const int PAN_BIN_PLASTIC  = 70;  // [2] Orange Bin: Plastics & Polythene (Mid-Left)
const int PAN_BIN_ORGANIC  = 110; // [3] Green Bin: Organic / Food Waste (Mid-Right)
const int PAN_BIN_RESIDUAL = 150; // [4] Red/Black Bin: Glass/Metal/Residual Trash (Far Right)

// Track live positions
int currentPanAngle  = PAN_HOME;
int currentTiltAngle = TILT_HOME;

// Helper: Convert degree angle (0-180) to PCA9685 12-bit PWM pulse count
void setServoAngle(uint8_t channel, int angle) {
  angle = constrain(angle, 0, 180);
  int pulse = map(angle, 0, 180, SERVOMIN, SERVOMAX);
  pwm.setPWM(channel, 0, pulse);
}

// Helper: Smooth interpolated motion between two angles to prevent sudden fling
void smoothMove(uint8_t channel, int fromAngle, int toAngle, int stepDelay) {
  fromAngle = constrain(fromAngle, 0, 180);
  toAngle   = constrain(toAngle, 0, 180);
  
  if (fromAngle == toAngle) return;

  int step = (toAngle > fromAngle) ? 1 : -1;
  for (int a = fromAngle; a != toAngle; a += step) {
    setServoAngle(channel, a);
    delay(stepDelay);
  }
  setServoAngle(channel, toAngle);
  delay(20);
}

// Coordinated Pan-Tilt Dumping Sequence
void dumpIntoBin(int targetPanAngle, const char* categoryName, const char* binColor) {
  Serial.print(F(">>> ACTION: Segregating to ["));
  Serial.print(categoryName);
  Serial.print(F("] -> "));
  Serial.print(binColor);
  Serial.print(F(" Bin @ Pan "));
  Serial.print(targetPanAngle);
  Serial.println(F(" deg"));

  // Step 1: Smoothly PAN to target bin while TILT remains securely level
  smoothMove(PAN_CHANNEL, currentPanAngle, targetPanAngle, STEP_DELAY_MS);
  currentPanAngle = targetPanAngle;
  delay(180);

  // Step 2: Smoothly TILT downward to slide the waste into the bin
  smoothMove(TILT_CHANNEL, currentTiltAngle, TILT_DUMP, STEP_DELAY_MS);
  currentTiltAngle = TILT_DUMP;

  // Step 3: Hold dump position + gentle vibration pulse to dislodge any sticky polythene/food
  delay(DUMP_HOLD_MS);
  setServoAngle(TILT_CHANNEL, TILT_DUMP - 8);
  delay(120);
  setServoAngle(TILT_CHANNEL, TILT_DUMP);
  delay(200);

  // Step 4: Smoothly return TILT back to flat level (HOME)
  smoothMove(TILT_CHANNEL, currentTiltAngle, TILT_HOME, STEP_DELAY_MS);
  currentTiltAngle = TILT_HOME;
  delay(180);

  // Step 5: Smoothly return PAN back to center (HOME)
  smoothMove(PAN_CHANNEL, currentPanAngle, PAN_HOME, STEP_DELAY_MS);
  currentPanAngle = PAN_HOME;

  Serial.println(F("ACK: Waste dumped successfully. Tray returned to HOME position."));
}

void resetToHome() {
  smoothMove(TILT_CHANNEL, currentTiltAngle, TILT_HOME, STEP_DELAY_MS);
  currentTiltAngle = TILT_HOME;
  smoothMove(PAN_CHANNEL, currentPanAngle, PAN_HOME, STEP_DELAY_MS);
  currentPanAngle = PAN_HOME;
  Serial.println(F("ACK: Pan-Tilt returned to HOME (Pan: 90 deg, Tilt: 90 deg)"));
}

void selfTest() {
  Serial.println(F("=== ECOSORT 2-AXIS PAN-TILT 4-BIN SELF-TEST ==="));
  delay(500);
  dumpIntoBin(PAN_BIN_PAPER,    "PAPER & CARDBOARD",      "BLUE");
  delay(600);
  dumpIntoBin(PAN_BIN_PLASTIC,  "PLASTICS & POLYTHENE",   "ORANGE");
  delay(600);
  dumpIntoBin(PAN_BIN_ORGANIC,  "ORGANIC / FOOD WASTE",   "GREEN");
  delay(600);
  dumpIntoBin(PAN_BIN_RESIDUAL, "GLASS/METAL/RESIDUAL",   "RED");
  Serial.println(F("=== SELF-TEST SEQUENCE COMPLETED ==="));
}

void setup() {
  Serial.begin(9600);
  Wire.begin();

  // Initialize PCA9685 I2C PWM controller
  pwm.begin();
  pwm.setOscillatorFrequency(27000000);
  pwm.setPWMFreq(50); // 50Hz standard servo frequency

  delay(250);

  // Bring Pan-Tilt gently to Home position
  setServoAngle(PAN_CHANNEL, PAN_HOME);
  setServoAngle(TILT_CHANNEL, TILT_HOME);
  currentPanAngle  = PAN_HOME;
  currentTiltAngle = TILT_HOME;

  Serial.println(F("ECOSORT_ONLINE: 2-Axis Pan-Tilt Waste Segregator Ready (Colombo CMC System)"));
  Serial.println(F("Layout: [P]=Blue(30 deg) | [M]=Orange(70 deg) | [O]=Green(110 deg) | [G]=Red(150 deg)"));
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    // Ignore whitespace / carriage returns
    if (cmd == '\r' || cmd == '\n' || cmd == ' ') {
      return;
    }

    switch (cmd) {
      // 1. Paper & Cardboard -> Blue Bin (Far Left)
      case 'P':
      case 'p':
      case '1':
        dumpIntoBin(PAN_BIN_PAPER, "PAPER & CARDBOARD", "BLUE");
        break;

      // 2. Plastics & Polythene -> Orange Bin (Mid-Left)
      case 'M':
      case 'm':
      case '2':
        dumpIntoBin(PAN_BIN_PLASTIC, "PLASTICS & POLYTHENE", "ORANGE");
        break;

      // 3. Organic / Biodegradable Waste -> Green Bin (Mid-Right)
      case 'O':
      case 'o':
      case '3':
        dumpIntoBin(PAN_BIN_ORGANIC, "ORGANIC / FOOD WASTE", "GREEN");
        break;

      // 4. Glass / Metal & Residual Trash -> Red/Black Bin (Far Right)
      case 'G':
      case 'g':
      case '4':
        dumpIntoBin(PAN_BIN_RESIDUAL, "GLASS, METAL & RESIDUAL TRASH", "RED");
        break;

      // Reset / Home
      case '0':
      case 'H':
      case 'h':
      case 'N':
        resetToHome();
        break;

      // Self-Test
      case 'T':
      case 't':
        selfTest();
        break;

      default:
        Serial.print(F("WARN: Unknown command: "));
        Serial.println(cmd);
        break;
    }
  }
}
