# Pi powers off when an item is detected

## Observations on 26 October 2026

The operator reports that both Pi and motor-driver lights go off when an item
is presented, and that the driver has a separate supply. The Pi was reachable
after a recent reboot. At idle it reported `get_throttled=0x0`, supply voltage
about 5.14 V, temperature 48 C, 3.5 GiB available RAM and no swap use.
These readings describe the new boot and do not exclude a power dip in the
previous boot. Previous-boot journals were not available. No cause is proven.

A Python exception usually terminates the application, rather than removing
board power. Possible causes include a weak Pi supply/cable, servo supply
overload, incorrect power interconnections, loose wiring or a short. A driver's
logic LED may go out simply because its VCC is supplied by the Pi; that does
not prove that its separate servo supply also went off.

## Isolate recognition from motor power

Close the camera preview and any sorter first. Run this on the Pi:

```sh
cd /home/en12/EcoSort_Smart_Bin
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ./venv/bin/python scripts/pi_health_check.py --inference --frames 20
```

This tests live camera capture and CLIP without constructing a motor controller
or changing PWM outputs. An existing servo holding command is not removed by
this test. It records health before loading the model and after every prediction
in `~/.local/state/ecosort/diagnostics.jsonl`, flushing each record to disk.
It does not save camera images. A sudden power cut can still lose the final
record. Instantaneous voltage readings cannot capture every short transient.

For supervised item recognition without servo commands, run:

```sh
./venv/bin/python -u live_smart_bin.py --driver sim
```

Do not use `--driver auto` or `--driver rpi-i2c` until the power wiring and
supplies have been checked. A successful recognition-only test isolates one
part of the system; it does not prove that full sorting will work under load.

## Check power with everything disconnected

1. Shut down the Pi and unplug both power supplies before changing wires.
2. Power the Pi through a suitable USB-C supply. Raspberry Pi recommends a
   5 V / 5 A supply for Pi 5; the official 27 W USB-C supply is a suitable option.
3. Connect PCA9685 **VCC to Pi 3.3 V** (physical pin 1), SDA to pin 3 and SCL to
   pin 5. Join Pi GND to driver GND.
4. Connect the regulated servo supply to driver **V+ and GND** with the correct
   polarity. Verify the actual servos' permitted voltage and current demand.
   Do not connect this positive rail to Pi 5 V pins 2/4 or Pi 3.3 V. Separate
   positive supplies stay separate; grounds must be shared.
5. Check for pinched cables, loose USB-C connections, incorrect servo plug
   orientation and binding under the tray's weight. Use suitable power wires
   and terminals for servo current rather than breadboard/jumper power paths.
6. Confirm supply ratings and wiring before powered motor tests. Do not repeat
   shutdowns as a test or force a stalled servo. Software cannot repair a short
   or increase a supply's current capacity.

References: [Raspberry Pi power supply documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply),
[PCA9685 logic and servo power](https://learn.adafruit.com/16-channel-pwm-servo-driver/hooking-it-up).

## Retained logs

The deployed Pi now has bounded persistent journaling configured at
`/etc/systemd/journald.conf.d/60-ecosort-diagnostics.conf` (50 MB maximum system
journal). After a future reboot, inspect:

```sh
journalctl --list-boots
sudo journalctl -b -1 -k --no-pager
tail -20 ~/.local/state/ecosort/diagnostics.jsonl
```

Persistent logs help with errors, memory exhaustion and orderly shutdowns.
An abrupt loss of electricity may leave no final error. This configuration
does not prevent or cure a power interruption.
