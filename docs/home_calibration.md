# HOME calibration and the tilt horn

## Current observed position

On 26 October 2026 the operator confirmed that tilt command 15 degrees makes
the unloaded tray-mounting plate flat. This is an operator observation, not an
inclinometer reading. The Pi was moved slowly to that command while the operator
watched. Pan was not commanded during this adjustment.

`servo_calibration.json` is loaded relative to the program location, not the
terminal working directory. Both controllers share it. Manual `--pan` and
`--tilt` remain absolute servo commands. HOME uses the saved physical commands.
Sorting routes are nominal logical angles relative to logical HOME 90 degrees:

    Without endpoint overrides: physical command = logical command + HOME - 90

The software-only trial instead uses two explicit endpoints. Logical tilt 35
maps to physical 5, logical 90 maps to HOME 15, and logical 145 maps to physical
70. Intermediate logical angles are linearly interpolated on each side of HOME.
Pan still uses the offset formula. `shake_degrees` is a physical extra excursion
and is currently zero; no shake is sent. `step_delay` is 0.04 seconds, and both
controllers move one degree at a time without exceeding this configured speed.

The complete route and extra shake are checked before movement. Invalid angles
are rejected, never clipped into a different destination. A calibration error
does not silently fall back to simulation in automatic mode.

## Why an offset alone did not work

With HOME 15, the old forward tilt 35 becomes -40, and its shake 25 becomes
-50. The old reverse tilt 145 becomes 70. A servo cannot accept negative
commands. Keeping the old absolute targets would also be wrong: their angles
relative to the tray's level position would no longer match the design.

The asymmetric override avoids negative commands, so all four configured routes
now pass the numeric range check. It does not restore the original symmetric
motion: the shallow pair has only 10 degrees of slope, while the other pair has
55 degrees. Waste may stick on the shallow side. Confirm actual tray attachment,
bin directions and delivery with clean light dummy items before relying on it.
Do not increase travel into a hard stop to compensate for insufficient slope.

## Optional mechanical improvement for symmetric travel

The software-only trial does not require this change. To restore the original
55-degree slope on both sides, a physical adjustment is needed; software cannot
create travel beyond the servo's range. Have an experienced person identify the driven tilt horn and opposite
support pivot. Do not confuse their screws or force a powered servo shaft.

1. Stop all control programs. Disconnect Pi and servo power before loosening
   hardware. Remove the tray and support the moving bracket.
2. Detach the driven tilt horn/linkage from the moving bracket so the servo can
   be centred without driving the bracket through an unknown arc.
3. With hands clear and the detached servo supported, centre the unloaded tilt
   servo at command 90. Do not run HOME from the old calibration (it is 15).
4. Disconnect power again. Refit the horn/linkage with the tray mounting surface
   horizontal. Account for spline spacing; do not force parts into alignment.
5. Restore power only after securing everything. Check centre with a spirit
   level. Small corrections to the HOME command may be necessary.
6. Set `tilt_home` in `servo_calibration.json` to the newly observed level command
   (near 90), remove the forward/backward endpoint overrides, restore shake only
   after verifying its clearance, and update the note. Do not change HOME to 90 before actually
   correcting the horn and checking the resulting physical level.
7. Run the read-only range check below, then test small unloaded movements in
   both directions while watching. Check bracket stops, cables and actual bin
   directions before any full dump. Numeric range checks are not collision or
   torque checks. The nominal full 65-degree shake envelope fits the command
   range only when tilt HOME is between 65 and 115 degrees.

## Commands

No movement or hardware access:

```sh
./venv/bin/python servo_control.py --check-calibration
```

The current asymmetric trial should pass. Exit code 2 means the selected
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
