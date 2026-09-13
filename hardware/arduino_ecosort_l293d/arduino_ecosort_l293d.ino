/*
 * EcoSort Smart Bin - 4-Way Waste Segregator (L293D Shield)
 * 
 * Target Board: Arduino Uno / Mega with L293D Motor Driver Shield
 * 
 * Pinout on standard L293D Shield:
 *   - SERVO_1 header = Arduino Digital Pin 10
 *   - SERVO_2 header = Arduino Digital Pin 9
 *
 * 4 Categories Supported:
 *   1. PAPER            -> Trigger Paper action (e.g. Servo 1 Tilt Left)
 *   2. PLASTIC / METAL  -> Trigger Plastic/Metal action (e.g. Servo 1 Tilt Right)
 *   3. ORGANIC          -> Trigger Organic action (e.g. Servo 2 Tilt Forward)
 *   4. GENERAL TRASH    -> Trigger General action (e.g. Servo 2 Tilt Backward)
 * 
 * Commands received over Serial (9600 baud):
 *   - 'P' or '1' -> Paper
 *   - 'M' or '2' -> Plastic or Metal
 *   - 'O' or '3' -> Organic
 *   - 'G' or '4' -> General Trash
 *   - '0'        -> Reset both servos to Neutral
 *   - 'T'        -> Full 4-category Self-Test sequence
 */

#include <Servo.h>

// --- Pin Definitions on L293D Motor Shield ---
const int SERVO1_PIN = 10; // SERVO_1 header on L293D shield
const int SERVO2_PIN = 9;  // SERVO_2 header on L293D shield

// --- Angle Settings (Adjust to match your physical bin/tray mechanism) ---
const int S1_NEUTRAL = 90;
const int S2_NEUTRAL = 90;

// Category 1: Paper (Servo 1 dumps Left)
const int S1_PAPER = 45;

// Category 2: Plastic / Metal (Servo 1 dumps Right)
const int S1_PLASTIC_METAL = 135;

// Category 3: Organic (Servo 2 dumps Forward)
const int S2_ORGANIC = 45;

// Category 4: General Trash (Servo 2 dumps Backward)
const int S2_GENERAL = 135;

const int HOLD_TIME_MS = 1200; // Time in ms to hold dump position

Servo servo1;
Servo servo2;

void triggerPaper() {
  Serial.println(F("ACK: Activating -> [1/4] PAPER (Servo 1 -> 45 deg)"));
  servo1.write(S1_PAPER);
  delay(HOLD_TIME_MS);
  servo1.write(S1_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void triggerPlasticMetal() {
  Serial.println(F("ACK: Activating -> [2/4] PLASTIC/METAL (Servo 1 -> 135 deg)"));
  servo1.write(S1_PLASTIC_METAL);
  delay(HOLD_TIME_MS);
  servo1.write(S1_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void triggerOrganic() {
  Serial.println(F("ACK: Activating -> [3/4] ORGANIC (Servo 2 -> 45 deg)"));
  servo2.write(S2_ORGANIC);
  delay(HOLD_TIME_MS);
  servo2.write(S2_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void triggerGeneral() {
  Serial.println(F("ACK: Activating -> [4/4] GENERAL TRASH (Servo 2 -> 135 deg)"));
  servo2.write(S2_GENERAL);
  delay(HOLD_TIME_MS);
  servo2.write(S2_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void resetBoth() {
  servo1.write(S1_NEUTRAL);
  servo2.write(S2_NEUTRAL);
  Serial.println(F("ACK: Both servos at Neutral (90 deg)"));
}

void selfTest() {
  Serial.println(F("ACK: Running 4-Way Self-Test..."));
  triggerPaper();
  delay(400);
  triggerPlasticMetal();
  delay(400);
  triggerOrganic();
  delay(400);
  triggerGeneral();
  Serial.println(F("ACK: 4-Way Self-Test Complete"));
}

void setup() {
  Serial.begin(9600);
  
  // Attach servos to L293D shield pins
  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);

  // Initialize neutral positions
  servo1.write(S1_NEUTRAL);
  servo2.write(S2_NEUTRAL);

  delay(500);
  Serial.println(F("ECOSORT_READY: 4-Way Waste Segregator Online (Paper, Plastic/Metal, Organic, General)"));
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    // Ignore whitespace / newlines
    if (cmd == '\r' || cmd == '\n' || cmd == ' ') {
      return;
    }

    switch (cmd) {
      case 'P':
      case '1':
        triggerPaper();
        break;

      case 'M':
      case '2':
        triggerPlasticMetal();
        break;

      case 'O':
      case '3':
        triggerOrganic();
        break;

      case 'G':
      case '4':
        triggerGeneral();
        break;

      case '0':
      case 'N':
        resetBoth();
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
