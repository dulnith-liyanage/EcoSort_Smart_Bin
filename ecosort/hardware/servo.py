"""
Servo controller abstractions, PCA9685 I2C driver, and interactive calibration controller.
"""
import os
import sys
import time
from ecosort.config import CATEGORY_CONFIG, BINS, C_BOLD, C_GREEN, C_BLUE, C_YELLOW, C_RED, C_MAG, C_RESET
from ecosort.logging import log_info, log_success, log_warning, log_warn, log_error, log_sort_event
import servo_settings


class BaseServoController:
    """Base interface for Servo Actuation."""
    def trigger_sort(self, cat_key, cfg):
        raise NotImplementedError

    def reset_home(self):
        pass

    def close(self):
        pass

    @property
    def status_str(self):
        return "SIMULATION"


class DirectPca9685Controller(BaseServoController):
    """Direct Raspberry Pi I2C control of PCA9685 (2x MG996R Servos in 2x2 Grid)."""
    def __init__(self, pan_channel=0, tilt_channel=1, address=0x40):
        if not (0 <= pan_channel < 16 and 0 <= tilt_channel < 16) or pan_channel == tilt_channel:
            raise ValueError('Pan and tilt must use distinct PCA9685 channels from 0 to 15.')
        self.calibration = servo_settings.load_calibration()
        # Reject unreachable routes BEFORE initialising hardware or emitting HOME.
        self.calibration.validate_routes(CATEGORY_CONFIG.values())
        try:
            from adafruit_servokit import ServoKit
        except ImportError:
            raise RuntimeError("Missing 'adafruit-circuitpython-servokit'. Install it via: pip install adafruit-circuitpython-servokit")

        self._hardware_lock = servo_settings.acquire_device_lock(address)
        self.kit = servo_settings.prepare_servo_kit(ServoKit(channels=16, address=address))
        self.pan_ch = pan_channel
        self.tilt_ch = tilt_channel

        # Standard MG996R servo pulse width range (600us to 2400us)
        self.kit.servo[self.pan_ch].set_pulse_width_range(600, 2400)
        self.kit.servo[self.tilt_ch].set_pulse_width_range(600, 2400)

        self.current_pan = self.calibration.pan_home
        self.current_tilt = self.calibration.tilt_home
        self._home_commanded = False
        self._pan_released = False
        self.reset_home()
        log_success(f"Direct Raspberry Pi I2C PCA9685 Connected (Pan: Ch{pan_channel}, Tilt: Ch{tilt_channel})")

    def release_pan_for_dump(self):
        """Opt-in pan release at a bin; tilt must be level and stays powered."""
        if (self.calibration.release_pan_during_dump
                and self.current_tilt == self.calibration.tilt_home):
            time.sleep(0.2)
            self.kit.servo[self.pan_ch].angle = None
            self._pan_released = True

    def release_idle_pan(self):
        """Quiet the verified unloaded vertical pan axis; always retain tilt torque."""
        if (self.calibration.release_pan_at_home
                and self.current_pan == self.calibration.pan_home
                and self.current_tilt == self.calibration.tilt_home):
            # Release immediately after the final HOME command; no powered idle dwell.
            self.kit.servo[self.pan_ch].angle = None
            self._pan_released = True

    def _smooth_move(self, channel, from_ang, to_ang, step_delay=None):
        if from_ang == to_ang:
            return
        if channel == self.pan_ch and self._pan_released:
            self.kit.servo[self.pan_ch].angle = self.current_pan
            self._pan_released = False
            time.sleep(0.15)
        from_ang = int(from_ang)
        to_ang = int(to_ang)
        if from_ang == to_ang:
            return
        step_delay = max(step_delay or self.calibration.step_delay, self.calibration.step_delay)
        for angle, delay in servo_settings.motion_steps(
                from_ang, to_ang, step_delay, self.calibration.smooth_motion):
            self.kit.servo[channel].angle = angle
            time.sleep(delay)

    def trigger_sort(self, cat_key, cfg):
        target_pan, target_tilt, shake_tilt = self.calibration.route(cfg)
        bin_pos = cfg.get('bin_pos', 'Unknown')
        log_info(f"[RPi I2C PCA9685] Sorting into {cfg['label']} ({bin_pos}) | Pan: {target_pan}°, Tilt: {target_tilt}°...")

        # A previous interrupted/manual cycle may have left the tray tilted.
        self._smooth_move(self.tilt_ch, self.current_tilt, self.calibration.tilt_home)
        self.current_tilt = self.calibration.tilt_home
        # Step 1: Pan with tilt at the calibrated level position.
        self._smooth_move(self.pan_ch, self.current_pan, target_pan)
        self.current_pan = target_pan
        if not self.calibration.smooth_motion:
            time.sleep(0.20)

        self.release_pan_for_dump()

        # Step 2: Tilt downward along pan (forward 35° or backward 145°)
        log_info(f"[RPi I2C PCA9685] Tilting tray to {target_tilt}° to drop waste into {bin_pos}...")
        self._smooth_move(self.tilt_ch, self.current_tilt, target_tilt)
        self.current_tilt = target_tilt
        time.sleep(self.calibration.dump_hold_seconds)

        if shake_tilt != target_tilt:
            self._smooth_move(self.tilt_ch, target_tilt, shake_tilt)
            self.current_tilt = shake_tilt
            time.sleep(0.12)
            self._smooth_move(self.tilt_ch, shake_tilt, target_tilt)
            self.current_tilt = target_tilt
            time.sleep(0.20)

        # Step 4: Return tilt to the calibrated HOME.
        self._smooth_move(self.tilt_ch, self.current_tilt, self.calibration.tilt_home)
        self.current_tilt = self.calibration.tilt_home
        if not self.calibration.smooth_motion:
            time.sleep(0.20)

        # Step 5: Return pan to the calibrated HOME.
        self._smooth_move(self.pan_ch, self.current_pan, self.calibration.pan_home)
        self.current_pan = self.calibration.pan_home
        self.release_idle_pan()
        log_success(f"2x2 Sort cycle for {cfg['label']} ({bin_pos}) complete. Returned to HOME.")

    def reset_home(self):
        self._smooth_move(self.tilt_ch, self.current_tilt, self.calibration.tilt_home)
        self.current_tilt = self.calibration.tilt_home
        self._smooth_move(self.pan_ch, self.current_pan, self.calibration.pan_home)
        self.current_pan = self.calibration.pan_home
        # Initial cached angles are not measurements: command and settle once.
        initial_home = not self._home_commanded
        if initial_home or not self._pan_released:
            self.kit.servo[self.tilt_ch].angle = self.calibration.tilt_home
            self.kit.servo[self.pan_ch].angle = self.calibration.pan_home
            self._pan_released = False
        self._home_commanded = True
        if initial_home:
            time.sleep(0.25)
        self.release_idle_pan()

    def close(self):
        self.reset_home()

    @property
    def status_str(self):
        return "Hardware: RASPBERRY PI I2C (PCA9685 - 2x2 Grid)"


class SimulatedServoController(BaseServoController):
    """Simulation fallback."""
    def trigger_sort(self, cat_key, cfg):
        target_pan, target_tilt, _ = servo_settings.load_calibration().route(cfg)
        bin_pos = cfg.get('bin_pos', 'Unknown')
        log_info(f"[SIMULATION TRIGGER] Pan {target_pan}° -> Tilt {target_tilt}° ({bin_pos}) -> {cfg['label']}")

    @property
    def status_str(self):
        return "Hardware: SIMULATION (2x2 Grid)"


def init_hardware_controller(driver_mode='auto', pan_ch=0, tilt_ch=1):
    """Initializes the Raspberry Pi I2C PCA9685 servo controller or simulation."""
    live = sys.modules.get('live_smart_bin')
    direct_cls = getattr(live, 'DirectPca9685Controller', DirectPca9685Controller) if live else DirectPca9685Controller
    sim_cls = getattr(live, 'SimulatedServoController', SimulatedServoController) if live else SimulatedServoController

    if driver_mode == 'sim':
        log_info("Running in SIMULATION MODE as requested.")
        return sim_cls()

    # Configuration failures (including missing files/keys) are not missing
    # hardware and must not silently fall back to simulation.
    saved = servo_settings.load_calibration()
    saved.validate_routes(CATEGORY_CONFIG.values())

    try:
        if os.path.exists('/dev/i2c-1') or driver_mode in ['auto', 'rpi-i2c', 'pca9685']:
            return direct_cls(pan_channel=pan_ch, tilt_channel=tilt_ch)
    except (ValueError, servo_settings.HardwareInUseError):
        # A mechanically unreachable calibration must never masquerade as a
        # successful simulation fallback in automatic mode.
        raise
    except Exception as e:
        if driver_mode != 'auto':
            raise RuntimeError(f'Requested hardware driver failed: {e}') from e
        log_warning(f"Direct Raspberry Pi I2C PCA9685 unavailable ({e}). Falling back to simulation.")

    return sim_cls()


class ServoPanTilt:
    """Manages the 2-Axis MG996R Pan-Tilt mechanism via PCA9685 for calibration & testing."""

    def __init__(self, pan_ch=0, tilt_ch=1, i2c_address=0x40):
        if not (0 <= pan_ch < 16 and 0 <= tilt_ch < 16) or pan_ch == tilt_ch:
            raise ValueError('Pan and tilt must use distinct PCA9685 channels from 0 to 15.')
        self.pan_ch = pan_ch
        self.tilt_ch = tilt_ch
        self.i2c_address = i2c_address
        self.kit = None
        self.calibration = servo_settings.load_calibration()
        self.current_pan = self.calibration.pan_home
        self.current_tilt = self.calibration.tilt_home
        self._pan_released = False
        self._home_commanded = False

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
            self._hardware_lock = servo_settings.acquire_device_lock(self.i2c_address)
            self.kit = servo_settings.prepare_servo_kit(ServoKit(channels=16, address=self.i2c_address))

            # Pulse range for MG996R
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

    def smooth_move(self, channel, from_ang, to_ang, step_delay=None):
        """Moves a servo gradually to prevent power spikes and mechanical gear jerking."""
        from_ang = int(max(0, min(180, from_ang)))
        to_ang = int(max(0, min(180, to_ang)))
        if from_ang == to_ang:
            return
        step_delay = max(step_delay or self.calibration.step_delay, self.calibration.step_delay)
        for angle, delay in servo_settings.motion_steps(
                from_ang, to_ang, step_delay, self.calibration.smooth_motion):
            self.kit.servo[channel].angle = angle
            time.sleep(delay)

    def set_pan(self, angle, smooth=True, step_delay=None):
        """Sets Pan (Azimuth) angle [0 - 180 deg]."""
        target = int(max(0, min(180, angle)))
        if self._pan_released and target == self.current_pan:
            return
        if self._pan_released:
            self.kit.servo[self.pan_ch].angle = self.current_pan
            self._pan_released = False
            time.sleep(0.15)
        if smooth:
            self.smooth_move(self.pan_ch, self.current_pan, target, step_delay)
        else:
            self.kit.servo[self.pan_ch].angle = target
        self.current_pan = target
        log_info(f"Pan -> {self.current_pan}°")

    def set_tilt(self, angle, smooth=True, step_delay=None):
        """Sets Tilt (Pitch) angle [0 - 180 deg]."""
        target = int(max(0, min(180, angle)))
        if self._pan_released and target != self.calibration.tilt_home:
            self.kit.servo[self.pan_ch].angle = self.current_pan
            self._pan_released = False
            time.sleep(0.15)
        if smooth:
            self.smooth_move(self.tilt_ch, self.current_tilt, target, step_delay)
        else:
            self.kit.servo[self.tilt_ch].angle = target
        self.current_tilt = target
        log_info(f"Tilt -> {self.current_tilt}°")

    def release_pan_for_dump(self):
        """Opt-in pan release at a bin; tilt must be level and stays powered."""
        if (self.calibration.release_pan_during_dump
                and self.current_tilt == self.calibration.tilt_home):
            time.sleep(0.2)
            self.kit.servo[self.pan_ch].angle = None
            self._pan_released = True

    def release_idle_pan(self):
        """Release only pan when both axes have returned to calibrated HOME."""
        if (self.calibration.release_pan_at_home
                and self.current_pan == self.calibration.pan_home
                and self.current_tilt == self.calibration.tilt_home):
            # Release immediately after the final HOME command; no powered idle dwell.
            self.kit.servo[self.pan_ch].angle = None
            self._pan_released = True

    def go_home(self):
        """Command saved HOME angles; physical level must be checked by the operator."""
        pan, tilt = self.calibration.pan_home, self.calibration.tilt_home
        log_info(f"Returning to calibrated HOME (Pan {pan}°, Tilt {tilt}°)...")
        # Level tilt first to avoid collision
        self.set_tilt(tilt)
        time.sleep(0.1)
        self.set_pan(pan)
        self.kit.servo[self.tilt_ch].angle = tilt
        if not self._pan_released:
            self.kit.servo[self.pan_ch].angle = pan
        if not self._home_commanded:
            time.sleep(0.25)
        self._home_commanded = True
        self.release_idle_pan()
        log_success("Saved HOME commanded; verify level on the mounting plate.")

    def _set_dump_tilt(self, angle):
        # A route may leave pan released; ordinary manual tilt still re-engages it.
        if self.calibration.release_pan_during_dump and self._pan_released:
            self.smooth_move(self.tilt_ch, self.current_tilt, angle)
            self.current_tilt = angle
        else:
            self.set_tilt(angle)

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

        # Check the entire route, including shake, before moving either motor.
        pan, tilt, shake = self.calibration.route(b)

        print(f"\n{C_BOLD}>>> [TRIGGER 2x2 SORT] {b['color'].upper()} BIN ({b['name']}){C_RESET}")
        print(f"    Target Position: {b['pos']} | {b['mode']} | Calibrated Pan: {pan}° | Tilt: {tilt}°")

        self.set_tilt(self.calibration.tilt_home)
        # Step 1: Pan to diagonal with tilt at the saved level position.
        log_info(f"1. Aligning Pan to {pan}° along {b['pos']} diagonal...")
        self.set_pan(pan)
        if not self.calibration.smooth_motion:
            time.sleep(0.2)

        self.release_pan_for_dump()

        # Step 2: Tilt tray to dump angle
        log_info(f"2. Tilting to {tilt}° ({b['mode']}) to dump waste...")
        self._set_dump_tilt(tilt)
        time.sleep(self.calibration.dump_hold_seconds)

        if shake != tilt:
            log_info("3. Calibrated shake...")
            self._set_dump_tilt(shake)
            time.sleep(0.12)
            self._set_dump_tilt(tilt)
            time.sleep(0.20)

        # Step 4: Return to calibrated level position.
        log_info(f"4. Returning tilt to calibrated HOME {self.calibration.tilt_home}°...")
        self._set_dump_tilt(self.calibration.tilt_home)
        if not self.calibration.smooth_motion:
            time.sleep(0.2)

        # Step 5: Return pan to calibrated centre.
        log_info(f"5. Returning pan to calibrated HOME {self.calibration.pan_home}°...")
        self.set_pan(self.calibration.pan_home)
        self.release_idle_pan()
        log_success(f"Dump sequence for {b['name']} ({b['pos']}) complete!\n")

    def sweep_pan(self, min_ang=45, max_ang=135, cycles=2):
        """Sweeps pan along the two diagonal axes (45° <-> 135°)."""
        log_info(f"Sweeping Pan between {min_ang}° and {max_ang}° ({cycles} cycles)...")
        min_ang, max_ang = self.calibration.pan(min_ang), self.calibration.pan(max_ang)
        self.set_tilt(self.calibration.tilt_home)
        for c in range(cycles):
            self.set_pan(min_ang, step_delay=0.012)
            time.sleep(0.3)
            self.set_pan(max_ang, step_delay=0.012)
            time.sleep(0.3)
        self.set_pan(self.calibration.pan_home)
        self.release_idle_pan()
        log_success("Diagonal Pan sweep completed.")

    def sweep_tilt(self, min_ang=35, max_ang=145, cycles=2):
        """Sweeps tilt through full range: Forward dump (35°) <-> Level (90°) <-> Backward dump (145°)."""
        min_ang, max_ang = self.calibration.tilt(min_ang), self.calibration.tilt(max_ang)
        log_info(f"Sweeping tilt between calibrated {min_ang}° and {max_ang}°...")
        for c in range(cycles):
            self.set_tilt(min_ang, step_delay=0.012)
            time.sleep(0.4)
            self.set_tilt(self.calibration.tilt_home, step_delay=0.012)
            time.sleep(0.3)
            self.set_tilt(max_ang, step_delay=0.012)
            time.sleep(0.4)
            self.set_tilt(self.calibration.tilt_home, step_delay=0.012)
            time.sleep(0.3)
        log_success("Full Tilt sweep test completed.")

    def run_all_bins(self):
        """Demonstrates sorting into all 4 bins of the 2x2 grid sequentially."""
        log_info("Running complete 2x2 grid sorting demonstration...")
        self.calibration.validate_routes(BINS.values())
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
