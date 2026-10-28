# Pan holding vibration - 28 October 2026

## Diagnosis on the assembled Pi

The operator supplied a short video of an empty, lined tray vibrating near HOME.
Automatic sorting was paused, and vibration continued. No competing controller
was running. The PCA9685 prescale register was 121: about 50.03 Hz using the
nominal 25 MHz oscillator. Eight register samples were identical; this checks
saved PWM settings, not electrical noise or actual shaft position.

With the tray supported and the sorter worker stopped, both channel holding
signals were disabled. The operator confirmed the vibration stopped and the
tray stayed level without torque. Tilt alone was then restored at its unchanged
125-degree HOME, leaving pan released. The operator confirmed this was quiet.

This isolates the observed vibration to active pan holding in this assembly.
It does not distinguish an internal servo issue from mechanical resonance or
servo-supply noise. Pi firmware flags remained `0x0`; those flags do not measure
the separate servo power rail. No supply voltage or current was measured.

## Implemented control change

The shared calibration now opts into `release_pan_at_home: true`:

- Tilt remains driven at the calibrated 125-degree level position.
- Pan moves to its calibrated 90-degree HOME, settles briefly, then its PWM
  signal is disabled with `angle = None`.
- Before the next route, pan is re-engaged, then follows the existing slow path.
- Both axes stay driven during the route. Pan releases only after BOTH axes
  have returned to HOME.
- Manual controls follow the same rule and re-engage pan before tilting away
  from level. Controller shutdown returns HOME with quiet pan behaviour.

HOME, route angles, pulse-width limits, speed and shake settings are unchanged.
The option defaults to false for configurations that do not explicitly enable
it. Tilt is never released by this idle policy.

Pan is free to rotate while released. Keep cables slack and do not manually
rotate or push the tray. There is no encoder, so reacquisition assumes the pan
has not been displaced. The prototype still needs supervised load/delivery
checks. If vibration happens during powered movement as well, inspect the
bracket, mounting and servo supply; releasing at HOME is not a repair for a
faulty servo or inadequate wiring.

## Empty-tray startup

The dashboard now allows 60 camera frames to settle exposure before recording
its 30-frame empty-tray reference. This avoids learning the initial camera
exposure transient as the background. It does not change CLIP labels or weaken
confidence/margin/stability checks. The tray must remain empty during startup.

## Software verification

Fake-device tests cover pan-only release at HOME, re-engagement before routes,
all four return sequences, retaining tilt torque, refusing release away from
HOME, strict Boolean configuration and camera warmup preceding calibration.
They do not measure vibration, torque or classification accuracy.

Power wiring reference: [Adafruit PCA9685 servo power guidance](https://learn.adafruit.com/16-channel-pwm-servo-driver/hooking-it-up).

## Smoother movement during sorting

The operator subsequently reported vibration both in motion and while tilted.
`smooth_motion: true` now uses the same eased position profile in both motor
controllers. The command velocity and acceleration ramp from/to zero at each
endpoint. Updates are about 20 ms apart, and profile duration is lengthened so
the peak speed does not exceed the previous one-degree-per-40-ms limit. Sorting
therefore takes longer, with the same angles, no additional shake and the same
HOME behaviour.

This is a command-motion improvement, not proof that a loaded servo will stop
hunting at a stationary position. Pan release at a tilted bin remains disabled
pending a supervised empty-tray test for both vibration and directional drift.
Tilt holding is never disabled during a dump.
