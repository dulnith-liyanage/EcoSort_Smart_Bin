/*
 * EcoSort Smart Bin - Dual Servo Controller (L293D Shield)
 * 
 * Target Board: Arduino Uno / Mega with L293D Motor Driver Shield
 * 
 * Pinout on standard L293D Shield:
 *   - SERVO_1 header = Arduino Digital Pin 10
 *   - SERVO_2 header = Arduino Digital Pin 9
 *
 * Mapping:
 *   - Servo 1: Activated when vision model detects GENERAL TRASH
 *   - Servo 2: Activated when vision model detects RECYCLABLES
 * 
 * Commands received over Serial (9600 baud):
 *   - 'G' or '1' -> Trigger Servo 1 (General Trash)
 *   - 'R' or '2' -> Trigger Servo 2 (Recyclables)
 *   - 'N' or '0' -> Reset both servos to Neutral
 *   - 'T'        -> Self-test sequence
 */

#include <Servo.h>

// --- Pin Definitions on L293D Motor Shield ---
const int SERVO1_PIN = 10; // SERVO_1 header on L293D shield
const int SERVO2_PIN = 9;  // SERVO_2 header on L293D shield

// --- Angle Settings (Adjust to match your mechanical design) ---
const int SERVO1_NEUTRAL = 90; // Rest position for Servo 1
const int SERVO1_DUMP    = 150; // Active/Dump position for Servo 1
const int SERVO2_NEUTRAL = 90; // Rest position for Servo 2
const int SERVO2_DUMP    = 30;  // Active/Dump position for Servo 2

const int HOLD_TIME_MS   = 1200; // How long to hold dump position (ms)

Servo servo1;
Servo servo2;

void triggerGeneralTrash() {
  Serial.println(F("ACK: Activating SERVO 1 -> GENERAL TRASH"));
  servo1.write(SERVO1_DUMP);
  delay(HOLD_TIME_MS);
  servo1.write(SERVO1_NEUTRAL);
  Serial.println(F("ACK: Servo 1 returned to Neutral"));
}

void triggerRecyclables() {
  Serial.println(F("ACK: Activating SERVO 2 -> RECYCLABLES"));
  servo2.write(SERVO2_DUMP);
  delay(HOLD_TIME_MS);
  servo2.write(SERVO2_NEUTRAL);
  Serial.println(F("ACK: Servo 2 returned to Neutral"));
}

void resetBoth() {
  servo1.write(SERVO1_NEUTRAL);
  servo2.write(SERVO2_NEUTRAL);
  Serial.println(F("ACK: Both servos at Neutral"));
}

void selfTest() {
  Serial.println(F("ACK: Running Self-Test..."));
  triggerGeneralTrash();
  delay(500);
  triggerRecyclables();
  Serial.println(F("ACK: Self-Test Complete"));
}

void setup() {
  Serial.begin(9600);
  
  // Attach servos to the dedicated L293D shield pins
  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);

  // Set initial neutral resting positions
  servo1.write(SERVO1_NEUTRAL);
  servo2.write(SERVO2_NEUTRAL);

  delay(500);
  Serial.println(F("ECOSORT_READY: L293D Dual Servo Controller Online"));
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    // Ignore whitespace / newlines
    if (cmd == '\r' || cmd == '\n' || cmd == ' ') {
      return;
    }

    switch (cmd) {
      case 'G':
      case '1':
        triggerGeneralTrash();
        break;

      case 'R':
      case '2':
        triggerRecyclables();
        break;

      case 'N':
      case '0':
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
