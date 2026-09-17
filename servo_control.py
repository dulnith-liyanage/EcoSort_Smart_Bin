#!/usr/bin/env python3
"""
==============================================================================
 EcoSort Smart Bin - 2-Axis Servo Pan-Tilt Controller & Calibrator
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

# Colombo Municipal Council (CMC) 4-Bin Layout
BINS = {
    '1': {'name': 'Paper & Cardboard', 'color': 'Blue',     'pan': 30,  'tilt': 30},
    '2': {'name': 'Plastics & Poly',   'color': 'Orange',   'pan': 70,  'tilt': 30},
    '3': {'name': 'Organic / Food',    'color': 'Green',    'pan': 110, 'tilt': 30},
    '4': {'name': 'Glass & Landfill',  'color': 'Red/Black','pan': 150, 'tilt': 30}
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
        log_success("Mechanism at HOME.")

    def dump_bin(self, bin_num):
        """Simulates full sorting cycle: Pan to bin -> Tilt dump -> Vibrate -> Reset."""
        b = BINS.get(str(bin_num))
        if not b:
            log_error(f"Unknown bin '{bin_num}'. Choose 1-4.")
            return

        print(f"\n{C_BOLD}>>> [TRIGGER SORT] {b['color'].upper()} BIN ({b['name']}){C_RESET}")
        
        # Step 1: Pan to bin angle while tray stays level (90°)
        log_info(f"1. Panning to {b['pan']}°...")
        self.set_pan(b['pan'])
        time.sleep(0.2)

        # Step 2: Tilt tray down to 30°
        log_info(f"2. Tilting down to {b['tilt']}° to dump waste...")
        self.set_tilt(b['tilt'])
        time.sleep(1.0)

        # Step 3: Gentle vibration pulse to ensure sticky waste slides off
        log_info("3. Vibration pulse...")
        try:
            self.kit.servo[self.tilt_ch].angle = 22
            time.sleep(0.12)
            self.kit.servo[self.tilt_ch].angle = 30
            time.sleep(0.20)
        except Exception:
            pass

        # Step 4: Tilt back to level (90°)
        log_info("4. Raising tray back to level (90°)...")
        self.set_tilt(90)
        time.sleep(0.2)

        # Step 5: Pan back to center (90°)
        log_info("5. Returning pan to center (90°)...")
        self.set_pan(90)
        log_success(f"Dump sequence for {b['name']} complete!\n")

    def sweep_pan(self, min_ang=30, max_ang=150, cycles=1):
        """Sweeps pan back and forth to inspect mechanical clearance."""
        log_info(f"Sweeping Pan between {min_ang}° and {max_ang}° ({cycles} cycles)...")
        self.set_tilt(90)  # Ensure level
        for c in range(cycles):
            self.set_pan(min_ang, step_delay=0.012)
            time.sleep(0.3)
            self.set_pan(max_ang, step_delay=0.012)
            time.sleep(0.3)
        self.set_pan(90)
        log_success("Pan sweep test completed.")

    def sweep_tilt(self, min_ang=30, max_ang=90, cycles=2):
        """Sweeps tilt between dumping slope and level."""
        log_info(f"Sweeping Tilt between {min_ang}° and {max_ang}° ({cycles} cycles)...")
        for c in range(cycles):
            self.set_tilt(min_ang, step_delay=0.012)
            time.sleep(0.4)
            self.set_tilt(max_ang, step_delay=0.012)
            time.sleep(0.4)
        log_success("Tilt sweep test completed.")

    def run_all_bins(self):
        """Demonstrates sorting into all 4 bins sequentially."""
        log_info("Running complete 4-bin sorting sequence...")
        for num in ['1', '2', '3', '4']:
            self.dump_bin(num)
            time.sleep(0.8)
        log_success("4-Bin demonstration complete!")

    def release(self):
        """Disables PWM signal to prevent servos from buzzing and drawing idle current."""
        try:
            self.kit.servo[self.pan_ch].angle = None
            self.kit.servo[self.tilt_ch].angle = None
            log_info("PWM pulses released. Servos are free to rotate by hand.")
        except Exception as e:
            log_warn(f"Release failed: {e}")

def print_menu(controller):
    print(f"\n{C_BOLD}{C_MAG}========================================================{C_RESET}")
    print(f"{C_BOLD}{C_MAG}   EcoSort Servo Bracket Controller (MG996R x 2)        {C_RESET}")
    print(f"{C_BOLD}{C_MAG}========================================================{C_RESET}")
    print(f" Current Status : {C_GREEN}Pan = {controller.current_pan}° | Tilt = {controller.current_tilt}°{C_RESET}")
    print(f" PCA9685 I2C    : Address 0x{controller.i2c_address:02X} | Pan: Ch{controller.pan_ch}, Tilt: Ch{controller.tilt_ch}")
    print("--------------------------------------------------------")
    print(f" {C_BOLD}[1]{C_RESET} Move to HOME (Pan 90°, Tilt 90°)")
    print(f" {C_BOLD}[2]{C_RESET} Set Pan Angle manually (0° - 180°)")
    print(f" {C_BOLD}[3]{C_RESET} Set Tilt Angle manually (0° - 180°)")
    print("--------------------------------------------------------")
    print(f" {C_BOLD}[4]{C_RESET} Test Bin 1: {C_BLUE}BLUE{C_RESET} (Paper & Cardboard - 30°)")
    print(f" {C_BOLD}[5]{C_RESET} Test Bin 2: {C_YELLOW}ORANGE{C_RESET} (Plastics & Poly - 70°)")
    print(f" {C_BOLD}[6]{C_RESET} Test Bin 3: {C_GREEN}GREEN{C_RESET} (Organic Waste - 110°)")
    print(f" {C_BOLD}[7]{C_RESET} Test Bin 4: {C_RED}RED{C_RESET} (Glass & Landfill - 150°)")
    print("--------------------------------------------------------")
    print(f" {C_BOLD}[8]{C_RESET} Run Full 4-Bin Demo (Cycles 1 -> 4)")
    print(f" {C_BOLD}[9]{C_RESET} Run Smooth Pan Sweep (30° <-> 150°)")
    print(f" {C_BOLD}[t]{C_RESET} Run Tilt Dump Sweep (30° <-> 90°)")
    print(f" {C_BOLD}[r]{C_RESET} Release Servos (Stop PWM / Cool down)")
    print(f" {C_BOLD}[q]{C_RESET} Quit")
    print("--------------------------------------------------------")

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
    parser = argparse.ArgumentParser(description="EcoSort Smart Bin - 2-Axis Servo Bracket Controller")
    parser.add_argument("--pan-ch", type=int, default=0, help="PCA9685 Channel for Pan servo (default: 0)")
    parser.add_argument("--tilt-ch", type=int, default=1, help="PCA9685 Channel for Tilt servo (default: 1)")
    parser.add_argument("--address", type=lambda x: int(x, 0), default=0x40, help="PCA9685 I2C address (default: 0x40)")

    # CLI Direct Action Flags
    parser.add_argument("--home", action="store_true", help="Send both servos to Home (90, 90) and exit")
    parser.add_argument("--pan", type=int, help="Move Pan servo to specific angle (0-180)")
    parser.add_argument("--tilt", type=int, help="Move Tilt servo to specific angle (0-180)")
    parser.add_argument("--bin", choices=['1', '2', '3', '4'], help="Test dump sequence for specific bin (1=Paper, 2=Plastic, 3=Organic, 4=Landfill)")
    parser.add_argument("--test-bins", action="store_true", help="Run full 4-bin dump sequence and exit")
    parser.add_argument("--sweep", action="store_true", help="Run pan sweep test and exit")
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
