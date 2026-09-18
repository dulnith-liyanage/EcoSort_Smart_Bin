#!/usr/bin/env python3
"""
==============================================================================
 EcoSort Smart Bin - 2-Axis Servo Pan-Tilt Controller & Calibrator
 2x2 Grid Layout (Pan-Tilt Mechanism Mounted in the Middle)
 Direct Raspberry Pi I2C control of PCA9685 (Channels 0 & 1)
 For 2x MG996R High-Torque Servos
==============================================================================
"""

import os
import sys
import time
import argparse
import signal

# ANSI Terminal Colors
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[92m"
C_BLUE   = "\033[94m"
C_YELLOW = "\033[93m"
C_RED    = "\033[91m"
C_CYAN   = "\033[96m"
C_MAG    = "\033[95m"

def log_info(msg):
    print(f"{C_CYAN}[INFO]{C_RESET} {msg}")

def log_success(msg):
    print(f"{C_GREEN}[SUCCESS]{C_RESET} {msg}")

def log_warn(msg):
    print(f"{C_YELLOW}[WARN]{C_RESET} {msg}")

def log_error(msg):
    print(f"{C_RED}[ERROR]{C_RESET} {msg}")

# 2x2 Grid Configuration (Center-Mounted Pan-Tilt)
# Bins are arranged in 4 quadrants around the center:
# - Front-Left  (Quadrant 2): Pan 135°, Tilt 35° (Forward dump)
# - Front-Right (Quadrant 1): Pan 45°,  Tilt 35° (Forward dump)
# - Rear-Left   (Quadrant 3): Pan 45°,  Tilt 145° (Backward dump along 45° axis)
# - Rear-Right  (Quadrant 4): Pan 135°, Tilt 145° (Backward dump along 135° axis)
BINS = {
    '1': {
        'name': 'Paper & Cardboard',
        'color': 'Blue',
        'pos': 'Front-Left',
        'pan': 135,
        'tilt': 35,
        'mode': 'Forward Dump'
    },
    '2': {
        'name': 'Plastics & Poly',
        'color': 'Orange',
        'pos': 'Front-Right',
        'pan': 45,
        'tilt': 35,
        'mode': 'Forward Dump'
    },
    '3': {
        'name': 'Organic / Food',
        'color': 'Green',
        'pos': 'Rear-Left',
        'pan': 45,
        'tilt': 145,
        'mode': 'Backward Dump'
    },
    '4': {
        'name': 'Glass & Landfill',
        'color': 'Red/Black',
        'pos': 'Rear-Right',
        'pan': 135,
        'tilt': 145,
        'mode': 'Backward Dump'
    }
}

class ServoPanTilt:
    """Manages the 2-Axis MG996R Pan-Tilt mechanism via PCA9685."""

    def __init__(self, pan_ch=0, tilt_ch=1, i2c_address=0x40):
        self.pan_ch = pan_ch
        self.tilt_ch = tilt_ch
        self.i2c_address = i2c_address
        self.kit = None

        self.current_pan = 90
        self.current_tilt = 90

        self._init_hardware()

    def _init_hardware(self):
        """Initializes I2C communication and ServoKit."""
        try:
            from adafruit_servokit import ServoKit
        except ImportError:
            log_error("Missing 'adafruit-circuitpython-servokit'!")
            print("Install it with:")
            print("  ./venv/bin/pip install adafruit-circuitpython-servokit")
            sys.exit(1)

        # Check I2C device presence on Linux
        if sys.platform.startswith('linux'):
            if not os.path.exists('/dev/i2c-1'):
                log_error("I2C bus '/dev/i2c-1' not found!")
                print("Enable I2C on your Raspberry Pi:")
                print("  sudo raspi-config nonint do_i2c 0")
                print("  sudo reboot")
                sys.exit(1)

        try:
            log_info(f"Connecting to PCA9685 at I2C address 0x{self.i2c_address:02X}...")
            self.kit = ServoKit(channels=16, address=self.i2c_address)
            
            # Calibrated pulse width range for standard MG996R (600us to 2400us)
            self.kit.servo[self.pan_ch].set_pulse_width_range(600, 2400)
            self.kit.servo[self.tilt_ch].set_pulse_width_range(600, 2400)

            log_success(f"PCA9685 Connected! Pan = Channel {self.pan_ch}, Tilt = Channel {self.tilt_ch}")
        except PermissionError:
            log_error("Permission denied accessing I2C bus!")
            print("Fix permissions by adding user to i2c group:")
            print("  sudo usermod -a -G i2c $USER")
            print("  newgrp i2c")
            sys.exit(1)
        except Exception as e:
            log_error(f"Failed to connect to PCA9685: {e}")
            print("\nTroubleshooting checklist:")
            print("  1. Verify wiring: Pi Pin 1 (3.3V) -> PCA9685 VCC, Pin 9 (GND) -> GND")
            print("  2. Verify I2C pins: Pi Pin 3 (SDA) -> SDA, Pin 5 (SCL) -> SCL")
            print("  3. External 5V-6V power MUST be connected to the green terminal for MG996R servos!")
            print("  4. Check bus detection: i2cdetect -y 1 (should display 40)")
            sys.exit(1)

    def smooth_move(self, channel, from_ang, to_ang, step_delay=0.009):
        """Moves a servo gradually to prevent power spikes and mechanical gear jerking."""
        from_ang = int(max(0, min(180, from_ang)))
        to_ang = int(max(0, min(180, to_ang)))
        if from_ang == to_ang:
            return
        step = 1 if to_ang > from_ang else -1
        for a in range(from_ang, to_ang + step, step):
            self.kit.servo[channel].angle = a
            time.sleep(step_delay)

    def set_pan(self, angle, smooth=True, step_delay=0.009):
        """Sets Pan (Azimuth) angle [0 - 180 deg]."""
        target = int(max(0, min(180, angle)))
        if smooth:
            self.smooth_move(self.pan_ch, self.current_pan, target, step_delay)
        else:
            self.kit.servo[self.pan_ch].angle = target
        self.current_pan = target
        log_info(f"Pan -> {self.current_pan}°")

    def set_tilt(self, angle, smooth=True, step_delay=0.009):
        """Sets Tilt (Pitch) angle [0 - 180 deg]."""
        target = int(max(0, min(180, angle)))
        if smooth:
            self.smooth_move(self.tilt_ch, self.current_tilt, target, step_delay)
        else:
            self.kit.servo[self.tilt_ch].angle = target
        self.current_tilt = target
        log_info(f"Tilt -> {self.current_tilt}°")

    def go_home(self):
        """Returns both servos to safe level center (Pan 90°, Tilt 90°)."""
        log_info("Returning mechanism to HOME (Pan 90°, Tilt 90°)...")
        # Level tilt first to avoid collision
        self.set_tilt(90)
        time.sleep(0.1)
        self.set_pan(90)
        log_success("Mechanism at HOME (Level & Centered).")

    def dump_bin(self, bin_num):
        """Executes full sorting cycle for 2x2 grid:
        1. Pan to diagonal
        2. Tilt forward (35°) or backward (145°)
        3. Vibration shake
        4. Level tray
        5. Return Pan to center
        """
        b = BINS.get(str(bin_num))
        if not b:
            log_error(f"Unknown bin '{bin_num}'. Choose 1-4.")
            return

        print(f"\n{C_BOLD}>>> [TRIGGER 2x2 SORT] {b['color'].upper()} BIN ({b['name']}){C_RESET}")
        print(f"    Target Position: {b['pos']} | {b['mode']} | Pan: {b['pan']}° | Tilt: {b['tilt']}°")

        # Step 1: Pan to diagonal while tray remains level (90°)
        log_info(f"1. Aligning Pan to {b['pan']}° along {b['pos']} diagonal...")
        self.set_pan(b['pan'])
        time.sleep(0.2)

        # Step 2: Tilt tray to dump angle
        log_info(f"2. Tilting to {b['tilt']}° ({b['mode']}) to dump waste...")
        self.set_tilt(b['tilt'])
        time.sleep(1.0)

        # Step 3: Gentle vibration pulse to ensure sticky waste slides off
        log_info("3. Vibration pulse...")
        try:
            if b['tilt'] < 90: # Forward dump
                self.kit.servo[self.tilt_ch].angle = max(15, b['tilt'] - 10)
                time.sleep(0.12)
                self.kit.servo[self.tilt_ch].angle = b['tilt']
                time.sleep(0.20)
            else: # Backward dump
                self.kit.servo[self.tilt_ch].angle = min(175, b['tilt'] + 10)
                time.sleep(0.12)
                self.kit.servo[self.tilt_ch].angle = b['tilt']
                time.sleep(0.20)
        except Exception:
            pass

        # Step 4: Level tray back to 90°
        log_info("4. Leveling tray back to 90°...")
        self.set_tilt(90)
        time.sleep(0.2)

        # Step 5: Pan back to center 90°
        log_info("5. Returning Pan to center (90°)...")
        self.set_pan(90)
        log_success(f"Dump sequence for {b['name']} ({b['pos']}) complete!\n")

    def sweep_pan(self, min_ang=45, max_ang=135, cycles=2):
        """Sweeps pan along the two diagonal axes (45° <-> 135°)."""
        log_info(f"Sweeping Pan between {min_ang}° and {max_ang}° ({cycles} cycles)...")
        self.set_tilt(90)  # Ensure level
        for c in range(cycles):
            self.set_pan(min_ang, step_delay=0.012)
            time.sleep(0.3)
            self.set_pan(max_ang, step_delay=0.012)
            time.sleep(0.3)
        self.set_pan(90)
        log_success("Diagonal Pan sweep completed.")

    def sweep_tilt(self, min_ang=35, max_ang=145, cycles=2):
        """Sweeps tilt through full range: Forward dump (35°) <-> Level (90°) <-> Backward dump (145°)."""
        log_info(f"Sweeping Tilt between {min_ang}° (Forward) and {max_ang}° (Backward) ({cycles} cycles)...")
        for c in range(cycles):
            self.set_tilt(min_ang, step_delay=0.012)
            time.sleep(0.4)
            self.set_tilt(90, step_delay=0.012)
            time.sleep(0.3)
            self.set_tilt(max_ang, step_delay=0.012)
            time.sleep(0.4)
            self.set_tilt(90, step_delay=0.012)
            time.sleep(0.3)
        log_success("Full Tilt sweep test completed.")

    def run_all_bins(self):
        """Demonstrates sorting into all 4 bins of the 2x2 grid sequentially."""
        log_info("Running complete 2x2 grid sorting demonstration...")
        for num in ['1', '2', '3', '4']:
            self.dump_bin(num)
            time.sleep(0.8)
        log_success("2x2 Grid demonstration complete!")

    def release(self):
        """Disables PWM signal to prevent servos from buzzing and drawing idle current."""
        try:
            self.kit.servo[self.pan_ch].angle = None
            self.kit.servo[self.tilt_ch].angle = None
            log_info("PWM pulses released. Servos are free to rotate by hand.")
        except Exception as e:
            log_warn(f"Release failed: {e}")

def print_menu(controller):
    print(f"\n{C_BOLD}{C_MAG}================================================================{C_RESET}")
    print(f"{C_BOLD}{C_MAG}   EcoSort 2x2 Grid Pan-Tilt Bracket Controller (Center Mount)  {C_RESET}")
    print(f"{C_BOLD}{C_MAG}================================================================{C_RESET}")
    print(f" Current Status : {C_GREEN}Pan = {controller.current_pan}° | Tilt = {controller.current_tilt}°{C_RESET}")
    print(f" PCA9685 I2C    : Address 0x{controller.i2c_address:02X} | Pan: Ch{controller.pan_ch}, Tilt: Ch{controller.tilt_ch}")
    print("----------------------------------------------------------------")
    print(f" {C_BOLD}[1]{C_RESET} Move to HOME (Pan 90°, Tilt 90° - Flat & Level)")
    print(f" {C_BOLD}[2]{C_RESET} Set Pan Angle manually (0° - 180°)")
    print(f" {C_BOLD}[3]{C_RESET} Set Tilt Angle manually (0° - 180°)")
    print("----------------------------------------------------------------")
    print(f" {C_BOLD}[4]{C_RESET} Test Bin 1: {C_BLUE}BLUE{C_RESET}   [FRONT-LEFT]  (Paper: Pan 135°, Tilt 35° Fwd)")
    print(f" {C_BOLD}[5]{C_RESET} Test Bin 2: {C_YELLOW}ORANGE{C_RESET} [FRONT-RIGHT] (Plastic: Pan 45°, Tilt 35° Fwd)")
    print(f" {C_BOLD}[6]{C_RESET} Test Bin 3: {C_GREEN}GREEN{C_RESET}  [REAR-LEFT]   (Organic: Pan 45°, Tilt 145° Rev)")
    print(f" {C_BOLD}[7]{C_RESET} Test Bin 4: {C_RED}RED{C_RESET}    [REAR-RIGHT]  (Landfill: Pan 135°, Tilt 145° Rev)")
    print("----------------------------------------------------------------")
    print(f" {C_BOLD}[8]{C_RESET} Run Full 2x2 Grid Demo (Cycles 1 -> 2 -> 3 -> 4)")
    print(f" {C_BOLD}[9]{C_RESET} Sweep Pan Diagonals (45° <-> 135°)")
    print(f" {C_BOLD}[t]{C_RESET} Sweep Tilt Full Range (35° Forward <-> 145° Backward)")
    print(f" {C_BOLD}[r]{C_RESET} Release Servos (Stop PWM / Cool down)")
    print(f" {C_BOLD}[q]{C_RESET} Quit")
    print("----------------------------------------------------------------")

def interactive_loop(controller):
    """Runs an interactive text interface to control the servos."""
    controller.go_home()
    
    while True:
        try:
            print_menu(controller)
            choice = input(f"{C_BOLD}Select an option > {C_RESET}").strip().lower()

            if choice == '1':
                controller.go_home()
            elif choice == '2':
                val = input(f"Enter target Pan angle (0-180) [current {controller.current_pan}]: ").strip()
                if val.isdigit():
                    controller.set_pan(int(val))
            elif choice == '3':
                val = input(f"Enter target Tilt angle (0-180) [current {controller.current_tilt}]: ").strip()
                if val.isdigit():
                    controller.set_tilt(int(val))
            elif choice == '4':
                controller.dump_bin('1')
            elif choice == '5':
                controller.dump_bin('2')
            elif choice == '6':
                controller.dump_bin('3')
            elif choice == '7':
                controller.dump_bin('4')
            elif choice == '8':
                controller.run_all_bins()
            elif choice == '9':
                controller.sweep_pan()
            elif choice == 't':
                controller.sweep_tilt()
            elif choice == 'r':
                controller.release()
            elif choice in ['q', 'exit']:
                log_info("Returning to HOME before exiting...")
                controller.go_home()
                log_info("Exiting. Bye!")
                break
            else:
                log_warn("Invalid option! Please select from menu.")
        except KeyboardInterrupt:
            print("\n")
            log_info("Interrupted. Returning servos to HOME...")
            controller.go_home()
            break

def main():
    parser = argparse.ArgumentParser(description="EcoSort Smart Bin - 2x2 Grid Pan-Tilt Controller")
    parser.add_argument("--pan-ch", type=int, default=0, help="PCA9685 Channel for Pan servo (default: 0)")
    parser.add_argument("--tilt-ch", type=int, default=1, help="PCA9685 Channel for Tilt servo (default: 1)")
    parser.add_argument("--address", type=lambda x: int(x, 0), default=0x40, help="PCA9685 I2C address (default: 0x40)")

    # CLI Direct Action Flags
    parser.add_argument("--home", action="store_true", help="Send both servos to Home (90, 90) and exit")
    parser.add_argument("--pan", type=int, help="Move Pan servo to specific angle (0-180)")
    parser.add_argument("--tilt", type=int, help="Move Tilt servo to specific angle (0-180)")
    parser.add_argument("--bin", choices=['1', '2', '3', '4'], help="Test dump sequence for 2x2 bin (1=Paper/Front-Left, 2=Plastic/Front-Right, 3=Organic/Rear-Left, 4=Landfill/Rear-Right)")
    parser.add_argument("--test-bins", action="store_true", help="Run full 2x2 4-bin dump sequence and exit")
    parser.add_argument("--sweep", action="store_true", help="Run pan diagonal sweep test and exit")
    parser.add_argument("--release", action="store_true", help="Release PWM signal on both servos and exit")

    args = parser.parse_args()

    controller = ServoPanTilt(pan_ch=args.pan_ch, tilt_ch=args.tilt_ch, i2c_address=args.address)

    # Clean shutdown on SIGINT/SIGTERM
    def handle_sig(sig, frame):
        log_info("Caught termination signal. Returning to HOME...")
        try:
            controller.go_home()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    # CLI One-shot actions
    executed_cli = False

    if args.home:
        controller.go_home()
        executed_cli = True

    if args.pan is not None:
        controller.set_pan(args.pan)
        executed_cli = True

    if args.tilt is not None:
        controller.set_tilt(args.tilt)
        executed_cli = True

    if args.bin:
        controller.dump_bin(args.bin)
        executed_cli = True

    if args.test_bins:
        controller.run_all_bins()
        executed_cli = True

    if args.sweep:
        controller.sweep_pan()
        executed_cli = True

    if args.release:
        controller.release()
        executed_cli = True

    # If no one-shot flags were passed, launch interactive terminal interface
    if not executed_cli:
        interactive_loop(controller)

if __name__ == "__main__":
    main()
