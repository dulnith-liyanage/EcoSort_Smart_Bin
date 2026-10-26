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

    physical command = logical command + saved HOME - 90

The complete route and extra shake are checked before movement. Invalid angles
are rejected, never clipped into a different destination. A calibration error
does not silently fall back to simulation in automatic mode.

## Why four-bin sorting is blocked

With HOME 15, the old forward tilt 35 becomes -40, and its shake 25 becomes
-50. The old reverse tilt 145 becomes 70. A servo cannot accept negative
commands. Keeping the old absolute targets would also be wrong: their angles
relative to the tray's level position would no longer match the design.

Therefore, level HOME works, but the complete four-bin mechanical route is not
ready. Do not run a full sweep or force the bracket against its stops.

## Restore travel on both sides

This requires a physical adjustment; software cannot move the servo beyond its
range. Have an experienced person identify the driven tilt horn and opposite
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
   (near 90), and update its note. Do not change it to 90 before actually
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

Exit code 2 means the current saved configuration cannot reach all routes.

Only with the unloaded mechanism secured and clear, command the saved tilt
HOME without commanding pan:

```sh
./venv/bin/python servo_control.py --tilt-home
```

This command holds the saved position after exiting; it does not release PWM.
A first command after power-up can move abruptly because the program has no
position sensor. Keep the servo power switch accessible.

## I2C compatibility correction

The real Pi driver exposed a `memoryview` combined-read error with Blinka 9.2.0
and PureIO 1.1.11. `servo_settings.BufferCompatibleI2C` converts the outgoing
buffer to bytes while preserving input/output slicing and locking. It wraps
only the ServoKit PCA9685 bus; installed third-party library files are unchanged.
Reading PWM registers confirms a command, not actual angle or level.

References: [Blinka Linux transfers](https://github.com/adafruit/Adafruit_Blinka/blob/main/src/adafruit_blinka/microcontroller/generic_linux/i2c.py),
[PureIO combined reads](https://github.com/adafruit/Adafruit_Python_PureIO/blob/main/Adafruit_PureIO/smbus.py).
