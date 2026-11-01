#!/usr/bin/env python3
"""
EcoSort Smart Bin - 2-Axis Servo Pan-Tilt Controller & Calibrator CLI.

Provides manual terminal controls, diagonal sweep tests, single-bin test dumps,
and calibration verification for the 2x2 grid sorting mechanism.
"""
import argparse
import signal
import sys

from ecosort.config import (
    BINS,
    C_RESET,
    C_BOLD,
    C_GREEN,
    C_BLUE,
    C_YELLOW,
    C_RED,
    C_MAG,
)
from ecosort.logging import (
    log_info,
    log_success,
    log_warn,
    log_error,
)
from ecosort.hardware.servo import ServoPanTilt
import servo_settings


def print_menu(controller):
    print(f"\n{C_BOLD}{C_MAG}================================================================{C_RESET}")
    print(f"{C_BOLD}{C_MAG}   EcoSort 2x2 Grid Pan-Tilt Bracket Controller (Center Mount)  {C_RESET}")
    print(f"{C_BOLD}{C_MAG}================================================================{C_RESET}")
    print(f" Current Status : {C_GREEN}Pan = {controller.current_pan}° | Tilt = {controller.current_tilt}°{C_RESET}")
    print(f" PCA9685 I2C    : Address 0x{controller.i2c_address:02X} | Pan: Ch{controller.pan_ch}, Tilt: Ch{controller.tilt_ch}")
    print("----------------------------------------------------------------")
    print(f" {C_BOLD}[1]{C_RESET} Saved HOME (Pan {controller.calibration.pan_home}°, Tilt {controller.calibration.tilt_home}°)")
    print(" Bin angles below are logical targets relative to HOME; unreachable routes are rejected.")
    print(f" {C_BOLD}[2]{C_RESET} Set Pan Angle manually (0° - 180°)")
    print(f" {C_BOLD}[3]{C_RESET} Set Tilt Angle manually (0° - 180°)")
    print("----------------------------------------------------------------")
    print(f" {C_BOLD}[4]{C_RESET} Test Bin 1: {C_BLUE}BLUE{C_RESET}   [FRONT-LEFT]  (Paper: Pan 135°, Tilt 35° Fwd)")
    print(f" {C_BOLD}[5]{C_RESET} Test Bin 2: {C_YELLOW}ORANGE{C_RESET} [FRONT-RIGHT] (Plastic: Pan 45°, Tilt 35° Fwd)")
    print(f" {C_BOLD}[6]{C_RESET} Test Bin 3: {C_GREEN}GREEN{C_RESET}  [REAR-LEFT]   (Metal cans: Pan 45°, Tilt 145° Rev)")
    print(f" {C_BOLD}[7]{C_RESET} Test Bin 4: {C_RED}RED{C_RESET}    [REAR-RIGHT]  (Food scraps: Pan 135°, Tilt 145° Rev)")
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
    parser.add_argument("--home", action="store_true", help="Send both servos to the saved calibrated HOME and exit")
    parser.add_argument("--tilt-home", action="store_true", help="Command only the saved tilt HOME; do not command pan")
    parser.add_argument("--check-calibration", action="store_true", help="Check saved HOME and route range without accessing hardware")
    parser.add_argument("--pan", type=int, help="Move Pan servo to specific angle (0-180)")
    parser.add_argument("--tilt", type=int, help="Move Tilt servo to specific angle (0-180)")
    parser.add_argument("--bin", choices=['1', '2', '3', '4'], help="Test dump sequence for 2x2 bin (1=Paper/Front-Left, 2=Plastic/Front-Right, 3=Metal/Rear-Left, 4=Food/Rear-Right)")
    parser.add_argument("--test-bins", action="store_true", help="Run full 2x2 4-bin dump sequence and exit")
    parser.add_argument("--sweep", action="store_true", help="Run pan diagonal sweep test and exit")
    parser.add_argument("--release", action="store_true", help="Release PWM signal on both servos and exit")

    args = parser.parse_args()

    if args.check_calibration:
        saved = servo_settings.load_calibration()
        print(f'Saved HOME: pan={saved.pan_home}°, tilt={saved.tilt_home}°')
        try:
            saved.validate_routes(BINS.values())
        except ValueError as error:
            print(f'SORTING BLOCKED: {error}')
            raise SystemExit(2) from error
        print('All configured targets and shake fit 0..180; physical clearance remains unverified.')
        return

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

    if args.tilt_home:
        controller.set_tilt(controller.calibration.tilt_home, smooth=False)
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
