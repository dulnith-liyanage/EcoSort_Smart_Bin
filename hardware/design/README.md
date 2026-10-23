# Current mechanical design

Open `output/complete_assembly.FCStd` or `output/complete_assembly.step` to inspect
the bins, existing two-servo kit and tray, and shared Pi/camera support.
Use only `output/stl/` files for printing. Each editable part is also in
`output/step/`. Start with the small `09_rim_and_timber_fit_coupon`.

See [assembly and print quantities](../../docs/assembly.md). All dimensions in
`parameters.json` are provisional. `build.py` contains the remaining detail
dimensions, solid validation, reference-bin interference check and conservative
tray height envelope. Run `Build.FCMacro` in FreeCAD to regenerate everything,
including the coloured document and preview. Output units are millimetres.

The build uses only FreeCAD's bundled libraries; the application runtime and
ML packages are not needed for CAD. Reference hardware is original simplified
geometry, not downloaded CAD. Full fasteners, cables, motor horns, fan details
and real waste trajectories are not modelled. The bin reference deliberately
uses continuous shells and a provisional lip instead of copying the photographed
vent slots and unknown rim geometry.
