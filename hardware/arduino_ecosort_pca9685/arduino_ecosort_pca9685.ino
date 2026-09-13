/*
 * EcoSort Smart Bin - 4-Way Waste Segregator (PCA9685 16-Channel PWM Driver)
 * 
 * Hardware:
 *   - Arduino Uno / Nano / Mega
 *   - PCA9685 16-Channel 12-bit PWM Servo Driver
 *   - 2x Servo Motors (e.g., SG90 or MG996R)
 *   - External 5V-6V Power Supply (connected to PCA9685 green screw terminal)
 * 
 * Required Library:
 *   - "Adafruit PWM Servo Driver Library" (Install via Arduino Library Manager)
 * 
 * PCA9685 to Arduino Wiring (I2C):
 *   - GND -> Arduino GND
 *   - VCC -> Arduino 5V (Powers the PCA9685 logic chip)
 *   - SDA -> Arduino A4 (or dedicated SDA pin)
 *   - SCL -> Arduino A5 (or dedicated SCL pin)
 *   - OE  -> Leave unconnected
 * 
 * Servo Connections on PCA9685:
 *   - Channel 0: Servo 1 (Paper vs Plastic/Metal Axis)
 *   - Channel 1: Servo 2 (Organic vs General Trash Axis)
 *   Matching row colors:
 *     - Black  (bottom) = GND (Brown / Black wire)
 *     - Red    (middle) = V+  (Red wire)
 *     - Yellow (top)    = PWM (Orange / Yellow wire)
 * 
 * Serial Commands (9600 baud):
 *   - 'P' or '1' -> Paper
 *   - 'M' or '2' -> Plastic / Metal
 *   - 'O' or '3' -> Organic
 *   - 'G' or '4' -> General Trash
 *   - '0'        -> Reset both servos to Neutral (90 deg)
 *   - 'T'        -> Self-Test sequence
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Default I2C address for PCA9685 is 0x40
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// --- Servo Channels on PCA9685 ---
const uint8_t SERVO1_CHANNEL = 0; // Channel 0 on PCA9685
const uint8_t SERVO2_CHANNEL = 1; // Channel 1 on PCA9685

// --- Pulse Lengths (50 Hz / 20ms period, 12-bit = 4096 ticks) ---
// Standard hobby servos: ~1000us (0 deg) to ~2000us (180 deg)
// Tweak SERVOMIN and SERVOMAX slightly if your servos hit mechanical stops
const int SERVOMIN = 125; // Pulse length count for 0 degrees (~600us)
const int SERVOMAX = 575; // Pulse length count for 180 degrees (~2400us)

// --- Angle Settings (Adjust to match your physical bin/tray mechanism) ---
const int S1_NEUTRAL       = 90;
const int S1_PAPER         = 45;  // Tilt Left
const int S1_PLASTIC_METAL = 135; // Tilt Right

const int S2_NEUTRAL       = 90;
const int S2_ORGANIC       = 45;  // Tilt Forward
const int S2_GENERAL       = 135; // Tilt Backward

const int HOLD_TIME_MS     = 1200; // Hold position for 1.2 seconds

// Helper function to convert angle (0-180) to 12-bit PWM pulse (0-4095)
void setServoAngle(uint8_t channel, int angle) {
  angle = constrain(angle, 0, 180);
  int pulse = map(angle, 0, 180, SERVOMIN, SERVOMAX);
  pwm.setPWM(channel, 0, pulse);
}

void triggerPaper() {
  Serial.println(F("ACK: [1/4] PAPER -> Servo 1 (Channel 0) to 45 deg"));
  setServoAngle(SERVO1_CHANNEL, S1_PAPER);
  delay(HOLD_TIME_MS);
  setServoAngle(SERVO1_CHANNEL, S1_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void triggerPlasticMetal() {
  Serial.println(F("ACK: [2/4] PLASTIC/METAL -> Servo 1 (Channel 0) to 135 deg"));
  setServoAngle(SERVO1_CHANNEL, S1_PLASTIC_METAL);
  delay(HOLD_TIME_MS);
  setServoAngle(SERVO1_CHANNEL, S1_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void triggerOrganic() {
  Serial.println(F("ACK: [3/4] ORGANIC -> Servo 2 (Channel 1) to 45 deg"));
  setServoAngle(SERVO2_CHANNEL, S2_ORGANIC);
  delay(HOLD_TIME_MS);
  setServoAngle(SERVO2_CHANNEL, S2_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void triggerGeneral() {
  Serial.println(F("ACK: [4/4] GENERAL TRASH -> Servo 2 (Channel 1) to 135 deg"));
  setServoAngle(SERVO2_CHANNEL, S2_GENERAL);
  delay(HOLD_TIME_MS);
  setServoAngle(SERVO2_CHANNEL, S2_NEUTRAL);
  Serial.println(F("ACK: Returned to Neutral"));
}

void resetBoth() {
  setServoAngle(SERVO1_CHANNEL, S1_NEUTRAL);
  setServoAngle(SERVO2_CHANNEL, S2_NEUTRAL);
  Serial.println(F("ACK: Both servos set to Neutral (90 deg)"));
}

void selfTest() {
  Serial.println(F("ACK: Running PCA9685 4-Way Self-Test..."));
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
  Wire.begin();

  // Initialize PCA9685
  pwm.begin();
  pwm.setOscillatorFrequency(27000000); // Standard PCA9685 internal oscillator frequency
  pwm.setPWMFreq(50);                   // 50Hz standard analog servo frequency

  delay(200);

  // Set initial neutral positions
  resetBoth();

  Serial.println(F("ECOSORT_READY: PCA9685 16-Channel Driver Online (4-Way Segregation)"));
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
