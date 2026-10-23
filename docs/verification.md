# Verification — 23 October 2026

The Raspberry Pi and physical assembly were unavailable. This report separates
the completed computer checks from work that still requires your hardware.

## Completed on this Mac

- `venv/bin/python scripts/verify.py`: Python syntax checks, shell syntax checks,
  and **10 passing tests**. Nine tests exercise fake servos, fake/synthetic camera
  data, all four routes, channel validation, explicit hardware failure, startup
  centring, level-before-pan, and a manual-sort main-loop regression. The tenth
  independently reads all nine binary STLs, checks triangle counts, confirms each
  edge is shared twice and confirms positive enclosed volume.
- `venv/bin/python live_smart_bin.py --help`: successful CLI import/argument
  display with the installed runtime. No model weights downloaded or inference
  performed by this check.
- FreeCAD generated all nine printable solids. Each is valid, one connected
  solid and a closed mesh. The individual STEP parts and complete/motor-only
  inspection assemblies are included. Preview visually reviewed.
- Reopened the saved FreeCAD and STEP assemblies: **30** individual components
  in the complete layout and **16** in the separate motor layout. Group-folder
  aggregate geometry is excluded from STEP export to avoid duplicate parts.
- Printed parts do not overlap the **provisional reference bin walls** in the
  assembled CAD pose. Rounded reference walls/lips are explicitly approximated;
  this is not proof of fit on the photographed baskets.
- Conservative 65° whole-tray height envelope is 37.4 mm above reference rim
  height. This only bounds tray vs rim height; it is not dynamic collision or
  torque analysis. Detailed fasteners, cables and waste motion are not included.

The generated numeric record is
[`hardware/design/output/checks.json`](../hardware/design/output/checks.json).
Run the macro again after changing parameters, then rerun the offline checks.

## Necessary runtime fixes

- Explicit HOME commands are emitted even when cached starting angles equal 90°.
  These are commanded positions, not measured physical positions.
- Sorting levels a previously tilted tray before panning.
- Manual sorting discards its pre-movement camera frame; cooldown begins after
  the synchronous movement completes and uses a monotonic clock.
- Picamera2 respects the selected camera index and does not swap the BGR bytes
  of its RGB888 stream. Partially opened cameras are closed on fallback.
- Explicit PCA9685 mode fails clearly when hardware initialization fails;
  automatic mode retains its documented simulation fallback.
- Setup installs the native camera packages. The camera diagnostic reports real
  observations or unavailable tooling instead of asserting an unobserved I2C
  error. The unused serial dependency and legacy TLS bypass were removed.

The classifier, prompts, category routing and default servo angle targets remain
the same. No new recognition accuracy or model training result is claimed.

## Pending hardware checks

1. Measure basket opening, lip, gap, case, tray and kit mounting holes; print the
   coupon and confirm clamp/wood fit before full prints.
2. Verify four supported rim contacts, shoe clearance, rear rim stiffness and
   mast bracing. Confirm actual fasteners and tray attachment; inspect print
   layers and joints. No load rating has been established.
3. Check supply ratings/polarity, common ground, servo plug order, I2C address
   and camera enumeration. Establish the correct servo horns/home directions
   with small unloaded movements and an accessible power switch.
4. Confirm the entire movement range including shake, all four trajectories,
   cable slack and bracket/adapter clearance with light dummy items.
5. Check live image framing/focus/colour and empty-tray calibration. Evaluate
   actual samples under real lighting, hands/false positives, throughput and
   repeated cycles before using waste. A CLIP relative score does not establish
   correct waste handling or collection-rule compliance.

Without these steps, the correct status is **offline-verified prototype**, not
hardware-tested or ready for unattended deployment.
