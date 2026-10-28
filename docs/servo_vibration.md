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

## Sorting vibration tests and current timing

The operator subsequently reported vibration both in motion and while tilted.
Two supervised front-left, empty-tray tests were completed:

1. A slow eased profile did not noticeably help. Briefly releasing pan while
   tilted also failed to stop the vibration. Tilt stayed powered throughout.
2. A faster continuous eased profile with a 0.2-second dump pause reduced the
   vibration according to the operator, but did not eliminate it.

The second timing is now configured in both controllers: `smooth_motion: true`,
`step_delay: 0.015` and `dump_hold_seconds: 0.2`. Velocity and acceleration ramp
from/to zero at endpoints, with roughly 20-ms command updates. Peak command
speed is bounded by 1 / step_delay (about 67 degrees/second). Angles are unchanged. Extra stationary alignment waits are omitted with this
continuous profile; the configured dump pause remains.
This is faster than the earlier 40-ms-per-degree setting; it is not the slower
trial profile. The shorter pause has not been validated for loaded delivery.

Pan remains powered away from HOME: releasing it at the bin did not solve the
vibration, and could permit direction drift with a load. Tilt holding is never
disabled during a dump. These changes reduce the observed problem; they are not
a verified complete repair. The servo supply voltage/current and mechanical
load were not measured. Do not claim the remaining vibration is software-fixed.

## Follow-up axis isolation — 28 October 2026

Automatic sorting was stopped and its worker exited before a separate controller
was opened. The driver responded at 0x40 with prescale 121; Pi firmware power
flags were 0x0. No competing sorter/controller process was present.

The operator confirmed an empty, clear tray and observed these tests:

- Pan 90 → 135 → 90 with tilt held level at 125: pan rotated and vibrated.
- Tilt 125 → 100 → 125 with pan released: tilt moved smoothly.
- Pan 90 → 100 → 90 using single target writes rather than software
  interpolation: vibration remained. This was only a small diagnostic excursion,
  not a proposed full-speed sorting profile.

The first pan test was not observed and provides no movement-quality evidence;
the observed repeat is listed above. Each test returned to HOME with pan
released and tilt supporting the tray. No permanent motion settings were changed.

These observations identify the pan axis as an observed source of vibration and
show that software interpolation is not required to reproduce it. They do not
identify whether the cause is servo feedback/gearing, mount flex/play, cable
forces or the separate servo supply. A smooth, smaller tilt test does not prove
all full-range loaded tilt motions are vibration-free. Electrical measurements
and physical inspection remain necessary; there is no verified software repair.


## Current update: pan release throughout tipping

A later supervised unloaded front-left route released pan after alignment,
kept tilt powered through 125 → 90 → 125, then re-engaged pan before returning
to 90. The operator reported **less vibration and no visible direction drift**.
This differs from the earlier test that released pan only during the tilted
pause. It is a partial improvement, not a complete vibration repair.

`release_pan_during_dump: true` now enables that sequence in both controllers.
The field defaults to false for older calibration files. Release occurs only
with tilt level; normal manual tilt still re-engages pan. Tilt is never released.
Pan's last commanded heading is assumed when re-engaging because no position
sensor is available. Cable forces or an off-centre load may rotate released pan;
loaded alignment and all other routes need physical checks. Set the option to
false if direction drifts. The tray must level before pan returns HOME.

A separate pan-only test doubled `step_delay` from 0.015 to 0.03. The operator
reported it remained just as jerky, so the slower speed was not kept. The
existing eased pan motion remains. No further pan-motion improvement is claimed.

Offline regressions cover all four command sequences, release before tilt,
retaining tilt support, re-engaging pan only after level return, strict Boolean
validation and legacy opt-out behaviour. They do not measure physical drift.
