/*
 * EcoSort Smart Bin - 4-Way Waste Segregator
 * 2-Axis Pan-Tilt Servo Controller (Direct Arduino Pins / L293D Shield)
 * Tailored for Colombo Municipal Council (CMC) / Sri Lanka Solid Waste Guidelines
 * 
 * Target Board: Arduino Uno / Mega
 * Pinout:
 *   - PAN Servo  (Horizontal base)  -> Digital Pin 10 (or SERVO_1 on L293D)
 *   - TILT Servo (Vertical dumping)  -> Digital Pin 9  (or SERVO_2 on L293D)
 * 
 * Colombo Municipal Council (CMC) 4-Bin Arc Layout:
 *   - Bin 1 (Far Left   - Pan 30 deg)  : BLUE   -> Paper & Cardboard ('P' / '1')
 *   - Bin 2 (Mid-Left   - Pan 70 deg)  : ORANGE -> Plastics & Polythene ('M' / '2')
 *   - Bin 3 (Mid-Right  - Pan 110 deg) : GREEN  -> Organic / Biodegradable Food Waste ('O' / '3')
 *   - Bin 4 (Far Right  - Pan 150 deg) : RED    -> Glass, Metal & Residual Landfill Trash ('G' / '4')
 */

#include <Servo.h>

// --- Pin Definitions ---
const int PAN_PIN  = 10; // Pan Servo (Horizontal Base)
const int TILT_PIN = 9;  // Tilt Servo (Pitch / Dumping)

Servo panServo;
Servo tiltServo;

// --- Pan-Tilt Home & Dump Positions ---
const int PAN_HOME       = 90;  // Straight ahead / center
const int TILT_HOME      = 90;  // Level / Flat tray (holds waste flat while scanning & panning)
const int TILT_DUMP      = 30;  // Pitched down forward to dump (invert to 150 if horn is reversed)

const int DUMP_HOLD_MS   = 1100; // Time in ms to pause at dump angle
const int STEP_DELAY_MS  = 9;    // Speed control: ms per 1-degree step

// --- Colombo Municipal Council (CMC) 4-Bin Pan Angles ---
const int PAN_BIN_PAPER    = 30;  // [1] Blue Bin: Paper & Cardboard (Far Left)
const int PAN_BIN_PLASTIC  = 70;  // [2] Orange Bin: Plastics & Polythene (Mid-Left)
const int PAN_BIN_ORGANIC  = 110; // [3] Green Bin: Organic / Food Waste (Mid-Right)
const int PAN_BIN_RESIDUAL = 150; // [4] Red/Black Bin: Glass/Metal/Residual Trash (Far Right)

int currentPanAngle  = PAN_HOME;
int currentTiltAngle = TILT_HOME;

// Helper: Smooth interpolated motion
void smoothMove(Servo &servo, int &currentAngle, int targetAngle, int stepDelay) {
  targetAngle = constrain(targetAngle, 0, 180);
  if (currentAngle == targetAngle) return;

  int step = (targetAngle > currentAngle) ? 1 : -1;
  for (int a = currentAngle; a != targetAngle; a += step) {
    servo.write(a);
    delay(stepDelay);
  }
  servo.write(targetAngle);
  currentAngle = targetAngle;
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

  // Step 1: Pan to target bin while Tilt remains level
  smoothMove(panServo, currentPanAngle, targetPanAngle, STEP_DELAY_MS);
  delay(180);

  // Step 2: Tilt downward to slide waste into bin
  smoothMove(tiltServo, currentTiltAngle, TILT_DUMP, STEP_DELAY_MS);

  // Step 3: Hold dump position + gentle shake to dislodge items
  delay(DUMP_HOLD_MS);
  tiltServo.write(TILT_DUMP - 8);
  delay(120);
  tiltServo.write(TILT_DUMP);
  delay(200);

  // Step 4: Tilt back to level HOME
  smoothMove(tiltServo, currentTiltAngle, TILT_HOME, STEP_DELAY_MS);
  delay(180);

  // Step 5: Pan back to center HOME
  smoothMove(panServo, currentPanAngle, PAN_HOME, STEP_DELAY_MS);

  Serial.println(F("ACK: Waste dumped successfully. Tray returned to HOME."));
}

void resetToHome() {
  smoothMove(tiltServo, currentTiltAngle, TILT_HOME, STEP_DELAY_MS);
  smoothMove(panServo, currentPanAngle, PAN_HOME, STEP_DELAY_MS);
  Serial.println(F("ACK: Returned to HOME position (Pan: 90 deg, Tilt: 90 deg)"));
}

void selfTest() {
  Serial.println(F("=== ECOSORT PAN-TILT 4-BIN SELF-TEST ==="));
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

  panServo.attach(PAN_PIN);
  tiltServo.attach(TILT_PIN);

  panServo.write(PAN_HOME);
  tiltServo.write(TILT_HOME);
  currentPanAngle  = PAN_HOME;
  currentTiltAngle = TILT_HOME;

  delay(300);

  Serial.println(F("ECOSORT_ONLINE: Direct Servo Pan-Tilt Waste Segregator (Colombo CMC)"));
  Serial.println(F("Layout: [P]=Blue(30 deg) | [M]=Orange(70 deg) | [O]=Green(110 deg) | [G]=Red(150 deg)"));
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    if (cmd == '\r' || cmd == '\n' || cmd == ' ') {
      return;
    }

    switch (cmd) {
      case 'P':
      case 'p':
      case '1':
        dumpIntoBin(PAN_BIN_PAPER, "PAPER & CARDBOARD", "BLUE");
        break;

      case 'M':
      case 'm':
      case '2':
        dumpIntoBin(PAN_BIN_PLASTIC, "PLASTICS & POLYTHENE", "ORANGE");
        break;

      case 'O':
      case 'o':
      case '3':
        dumpIntoBin(PAN_BIN_ORGANIC, "ORGANIC / FOOD WASTE", "GREEN");
        break;

      case 'G':
      case 'g':
      case '4':
        dumpIntoBin(PAN_BIN_RESIDUAL, "GLASS, METAL & RESIDUAL TRASH", "RED");
        break;

      case '0':
      case 'H':
      case 'h':
      case 'N':
        resetToHome();
        break;

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
