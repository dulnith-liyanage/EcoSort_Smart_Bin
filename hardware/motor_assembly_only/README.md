# Motor assembly only

**EcoSort_motor_assembly.FCStd** contains the motor support from the electronics design, its four rim shoes, two simplified MG996R reference servos, the two RB0051 pan/tilt bracket pieces, and the tray. The bins, Pi, camera, driver and electronics supports are excluded. The support, shoes, bracket and tray retain their previous geometry and positions. Coplanar faces on the support are merged to improve its CAD display; the tray is partly transparent to reveal the mechanism.

**EcoSort_motor_assembly.step** contains the same ten separate component solids/compounds for other CAD software. This is a static assembly, with no motion joints or collision validation.

For printing, use only **motor_mount_PRINT.stl** (one) and **rim_shoe_PRINT_FOUR.stl** (four, if required). These are exact copies of the original intersection support used in the electronics design, rather than the subsequent simplified v4 alternative. Do not print the complete assembly: the servos and metal mechanism are reference hardware, and the tray is a placeholder for your existing tray.

Run **Build_motor.FCMacro** in FreeCAD to regenerate the assembly from the two
included print STLs. The macro uses its own directory and requires no earlier
design folders or downloaded component models.

For publication, the servos use original simplified envelope geometry rather
than the earlier community STEP with unconfirmed redistribution permission.
Their shape, shaft and mounting ears are approximate. The printed support and
shoe files remain byte-for-byte unchanged. Bracket and tray geometry also retain
the previous layout; this is not a dimensionally verified or motion-constrained
model.

Hardware identification references:

- [TowerPro MG996R](https://towerpro.com.tw/product/mg996R/) — nominal body dimensions.
- [Tronic RB0051](https://tronic.lk/product/2-dof-pan-and-tilt-servo-mount-kit-mg995-mg996) — user-identified pan/tilt kit.

These links identify the physical components. No third-party CAD geometry is
embedded in the published assembly.
