# Simple motor mount and purchased electronics supports

Use **motor_mount.stl** to print just the centre support. Nothing else is included in that file. **motor_mount.step** is the same design with clean CAD faces for editing; it avoids the triangle-edge display caused by importing an STL into CAD. All STL files necessarily contain triangles, even when their surfaces are flat.

To regenerate the STLs, install `requirements-cad.txt` in a separate Python
environment and run `python build.py` from this folder. To regenerate the STEP
files, use FreeCAD's Python interpreter with `build.py --step`. The CAD packages
are separate from the Raspberry Pi runtime requirements.

The mount is a flat 160 × 160 × 8 mm base, a hollow 60 mm square upright, and a 94 × 80 mm top plate. Total height is 116 mm. All slots and openings are straight-sided. The 100 mm upright height retains the earlier provisional clearance; lowering it without testing may make the tipping tray hit the bin rims. Hardware dimensions remain unmeasured. Top mounting slots are 60 mm apart with 24 mm length and 4 mm width; confirm these suit the actual RB0051 base before printing. Washers bridge the slots.

## Attach it to the four bins

1. Arrange four bins in a square, with their inner corners beneath the mount. All four rims must support the base at the same height. Add thin rubber strips between the base and rims.
2. Put one M5 bolt down each base slot, through the existing gaps beside the rims. Do not drill the bins for this method.
3. Under each rim, add a small metal repair plate, washer and wing nut. The plate acts like a finger hooking under that bin's inward lip. Choose plates around 28 × 35 mm with an M5 clearance hole, then check their actual reach and hole position. They must grip the underside of the lip without intersecting the bin wall.
4. If suitable metal plates are unavailable, print **optional_rim_shoe.stl four times**. Point each shoe's longer toe inward under its bin's lip. Use a broad washer under its square clearance hole. The prototype assumes an accessible inward lip; rolled/sealed/outward rims need a different clamp.
5. Tighten the four wing nuts evenly by hand. Bolt the existing metal pan/tilt kit onto the top, using M3 bolts and washers if they fit the real kit. Access the nuts through the front window. Verify the full tray movement with light dummy objects before loading.

Bolt length must cover the base, rim depth, backing plate, washers and nut; approximately 40–60 mm is a starting range, not a confirmed shopping size. Strap the bin group together if they slide apart. Do not empty or move a bin while the assembly is running.

This keeps the printed count to **one main part** when metal backing plates are used. It avoids a frame connecting the outside edges of all four bins. STL validity checks establish a closed printable surface, not a physical load rating. Check fit before committing to the full print; use supports beneath the top overhang as needed in the slicer.

## Keep the Pi and camera together

Use the Pi's existing ventilated case. Strap it to a small piece of plywood or a perforated mounting plate. Attach Camera V2 beside it using an adjustable camera board bracket or two small angle brackets and M2 insulating spacers. Keep the camera connector close to the Pi's camera connector so the actual ribbon reaches with a gentle loop. Do not use the ribbon to carry the camera's weight. There is no new printed electronics enclosure in this recommendation.

Support this **whole Pi-and-camera plate** above the rear bin using a rigid shelf bracket or a vertical slotted metal strip with two angle brackets. Bolt the support to the bin wall with large backing plates, if drilling is acceptable. For removable attachment, use two padded screw clamps around a reinforced rim or a separate stable support beside the bin. A thin flexible bin rim may not support the leverage of the elevated plate. Keep the fan unobstructed and the plate out of the falling waste path.

Place the lens roughly **300–350 mm above the detection surface** as a starting point, facing down toward it. This is camera-to-waste distance; the Pi can still sit directly beside the camera. For the nominal 300 × 220 mm tray, Camera V2's documented 62.2° horizontal and 48.8° vertical view imply a minimum height of roughly 249 mm and 243 mm respectively for an uncropped, straight-down image. Extra distance gives framing margin. Angled mounting, tall objects and software cropping change that result: use the actual live preview, mark a detection area fully within view, and keep objects within it. Capture while the tray is level and stationary, before moving the servos.

The earlier v3 long arm with the Pi down on the bin is superseded by this shared elevated plate. No retraining is automatically required by a mounting change; test recognition at the new position and lighting before deciding whether the model needs changes.

## Purchased options

- **Lowest-cost approach:** hardware-store slotted shelf/angle brackets, a small plywood board, reusable straps, M2 spacers, and M5 backing plates/wing nuts. These are shopping specifications; a particular shop's availability and fit have not been verified.
- **Camera-specific adjustable mount:** [The Pi Hut Adjustable Raspberry Pi Camera Mount & Protector](https://thepihut.com/collections/all/products/adjustable-raspberry-pi-camera-mount-and-protector). Its listing explicitly supports Camera V2 and provides angle adjustment and a tripod mounting point. Bolt its base to the same board as the Pi. Check included screws and international shipping before ordering.
- **Removable adjustable support:** [SmallRig 2164 clamp and ballhead arm](https://www.smallrig.com/smallrig-multi-functional-crab-shaped-clamp-with-ballhead-magic-arm-2164.html). This is a photography clamp/arm reference, not a bin-specific part. A board needs a compatible threaded adapter; confirm thread, jaw opening, reach and total load. The short arm alone may not provide the required height, and it should grip a rigid upright or reinforced rim. This is likely a convenience upgrade rather than the cheapest solution.
- **Local motor bracket:** [Tronic Optimus MG995 Servo Mount Bracket OP0109](https://tronic.lk/product/optimus-mg995-servo-mount-bracket) is acrylic and the listing also names MG996 compatibility. It holds a servo, but does not replace the four-bin base and may overlap the hardware already in your RB0051 kit. Check hole alignment before buying.
- **Your existing mechanism:** [Tronic RB0051 two-axis kit](https://tronic.lk/product/2-dof-pan-and-tilt-servo-mount-kit-mg995-mg996). Reuse it. I did not find a confirmed ready-made support specifically joining this kit to the four bin rims. A small plywood base plus a timber spacer or hardware-store brackets can replace the printed centre support if you prefer basic fabrication.

Manufacturer camera specifications: [Raspberry Pi camera documentation](https://www.raspberrypi.com/documentation/accessories/camera.html). Product listings were checked on 7 October 2026; local stock, delivered cost, and fit are not guaranteed.
