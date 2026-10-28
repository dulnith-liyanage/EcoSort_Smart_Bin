# HOME calibration and the tilt horn

## Current reported HOME: 125 degrees

On 26 October 2026 the operator reported that tilt command **125 degrees** is
horizontal after the previous calibration. Pan HOME remains **90 degrees**.
The Pi is disconnected: this update is verified in software only. Earlier
observations at HOME 15 and endpoints 5/70 describe the previous setup and
must not be reused with the new mounting position.

`servo_calibration.json` is loaded relative to the program location. Both
controllers share it. Manual `--pan` and `--tilt` use absolute servo commands.
The sorting configurations retain nominal logical targets; explicit endpoints
map them to the current physical commands:

| Route | Pan command | Tilt command | Offset from level |
|---|---:|---:|---:|
| HOME | 90 | 125 | 0 |
| Front-left / paper | 135 | 90 | -35 |
| Front-right / plastic | 45 | 90 | -35 |
| Rear-left / metal | 45 | 160 | +35 |
| Rear-right / food scraps | 135 | 160 | +35 |

Logical tilt 35 maps to command 90, logical 90 to HOME 125, and logical 145
to command 160. Intermediate values interpolate on each side of HOME.
These equal 35-degree command offsets are provisional, not measured tray
inclinations. The original 55-degree slope would require command 180 on one
side, leaving no command margin. Do not restore the old shake excursion.
Shake remains zero. The 28 October timing update uses eased motion with a
peak command limit of about 67 degrees/second and a 1.5-second dump pause.
The operator observed less vibration in an unloaded trial; loaded release
with this shorter timing still needs checking.
Both controllers level before panning, tilt to the route, level again, then
return pan to centre. The complete route is checked before movement. Invalid
angles are rejected rather than clipped or silently simulated.

## Reconnect and verify

1. With servo power off, secure the unloaded assembly and clear cables. Keep
   the servo power switch accessible. Close competing control programs.
2. Update the Pi checkout before starting any controller:

   ```sh
   cd /home/en12/EcoSort_Smart_Bin
   git pull --ff-only
   ./venv/bin/python servo_control.py --check-calibration
   ```

3. Check that the range report shows HOME pan 90 / tilt 125 and the targets
   above. It must not show the old HOME 15. Do not start automatic sorting yet.
4. With hands clear, power the servos and command tilt HOME only:

   ```sh
   ./venv/bin/python servo_control.py --tilt-home
   ```

   Verify level. The first command can move abruptly: there is no position
   feedback. Cached angles are not measured shaft positions.
5. Test small unloaded tilt commands, for example 123, then 125, then 127,
   then 125, using `./venv/bin/python servo_control.py --tilt ANGLE` separately.
   Stop on binding, strong buzzing or cable tension. Increase travel gradually
   towards 90 and 160 only after observing clearance.
6. Verify pan directions while level, then each unloaded route. The previous
   setup's successful route tests do not validate the new horn position.
7. Test one small clean light item per bin before automatic sorting. Adjust
   endpoints only from physical observations. If direction is reversed or an
   item does not slide, recalibrate before using waste.

The Pi has not received this update while disconnected. Numeric range checks
prove neither mechanical clearance nor correct delivery.

## Commands

No movement or hardware access:

```sh
./venv/bin/python servo_control.py --check-calibration
```

The current 125-degree HOME configuration should pass. Exit code 2 means the selected
configuration cannot reach all routes; no motors are commanded by this check.

Only with the unloaded mechanism secured and clear, command the saved tilt
HOME without commanding pan:

```sh
./venv/bin/python servo_control.py --tilt-home
```

This command holds the saved position after exiting; it does not release PWM.
A first command after power-up can move abruptly because the program has no
position sensor. Keep the servo power switch accessible.

## I2C compatibility correction

Only one controller may own the PCA9685 at a time. Both programs acquire the
same operating-system file lock before initialising ServoKit. A second sorter
or calibrator exits without commanding motors; it must not silently simulate.
Close old terminals/programs before restarting. Direct third-party I2C tools
do not respect this lock and must not be used concurrently. A lock file may
remain after exit; ownership is released by the OS, not by deleting the file.

The real Pi driver exposed a `memoryview` combined-read error with Blinka 9.2.0
and PureIO 1.1.11. `servo_settings.BufferCompatibleI2C` converts the outgoing
buffer to bytes while preserving input/output slicing and locking. It wraps
only the ServoKit PCA9685 bus; installed third-party library files are unchanged.
Reading PWM registers confirms a command, not actual angle or level.

References: [Blinka Linux transfers](https://github.com/adafruit/Adafruit_Blinka/blob/main/src/adafruit_blinka/microcontroller/generic_linux/i2c.py),
[PureIO combined reads](https://github.com/adafruit/Adafruit_Python_PureIO/blob/main/Adafruit_PureIO/smbus.py).
