# Assembly guide — four rounded baskets

## 1. Understand the design

The cross-shaped centre base rests on the four inner rims. Its four slots are
80 mm away from the corner intersection, where the photographed baskets have
straighter sides. Each bolt goes down **inside the opening, beside the lip** and
pulls a shoe upward beneath that lip. Do not drill a bolt through the plastic rim.
The four diagonal openings in the cross leave space below the dumping tray.

A separate rear clip holds the driver and an inexpensive timber upright. A second
timber strip reaches toward the tray. The Pi in its existing case and the camera
share one open carrier on the arm. They stay near each other, with a slack ribbon
between them. This carrier is a mounting plate, not a new Pi enclosure.

All pictured electronics and metal bracket models are simplified references.
The baskets are rounded solid-wall reference shells, not measured replicas of
the photographed slotted baskets. The photo provides no trustworthy scale.

## 2. Measure before a full print

Edit `hardware/design/parameters.json` and rebuild if these assumptions differ:

| Item | Provisional value | What to check |
|---|---|---|
| Each basket opening/body envelope | 300 mm square, 300 mm high | Opening width/length, taper, height, corner radius |
| Gap between baskets | 10 mm | All four can touch/support the base evenly |
| Inner rim | 18 mm deep, 16 mm inward reach in reference | Accessible underside and inner wall location |
| Cross base | 200 × 200 × 8 mm, arms 80 mm wide | Four supported contact patches; no corner rocking |
| Rim bolts | x = ±30, y = ±80 mm | Bolts clear the lip; shoes reach under it without crossing wall |
| Pedestal | 100 mm plus 8 mm top | Actual mechanism pivot height and tray sweep |
| Existing tray | 300 × 220 mm | Actual dimensions, mass, underside and fastener positions |
| Rear clamp opening | 32 mm | Actual rear rim width/depth; reinforced surface available |
| Existing Pi case | 100 × 75 × 30 mm | Case fits strap positions and leaves fan/ports accessible |
| Timber | 20 mm square, 20.8 mm sockets | Actual timber and printer tolerance |

The rear clamp gap, tray bolt locations and mechanism mounting slots are explicit
dimensions in `build.py`; change those there if your measurements differ. Not
every mechanical detail is exposed in the JSON file.

First print **09_rim_and_timber_fit_coupon.stl**: it tests a 32 mm clamp opening,
5.6 mm M5 clearance and a 20.8 mm timber socket. It is only a fit coupon, not a
load-bearing clamp. Make cardboard outlines of the base and carrier as well.
If the rim has no accessible inward lip, stop using the shoe attachment concept:
use measured padded rim clamps or a rigid board under/behind the basket group.
Do not squeeze thin slotted walls to compensate for an incompatible rim.

## 3. Print list

| STL in `hardware/design/output/stl/` | Quantity | Purpose |
|---|---:|---|
| 01_cross_base | 1 | Centre support, four clamp and four pedestal bolt positions |
| 02_motor_pedestal | 1 | Raises the pan/tilt mechanism above the rims |
| 03_rim_shoe | 4 | Hooks beneath the four inner lips |
| 04_tray_adapter | 1 | Slotted interface between the metal kit and your tray |
| 05_rear_clip_and_driver_shelf | 1 | Rear rim clamp, mast socket, open driver shelf |
| 06_pressure_pad | 2 | Rubber-faced pads for rear clamp screws |
| 07_timber_elbow | 1 | Joins upright and angled overhead timber |
| 08_shared_pi_camera_carrier | 1 | Existing cased Pi beside camera, lens down |
| 09_rim_and_timber_fit_coupon | 1 first | Disposable fit test; not part of the assembly |

There are 12 functional printed pieces plus the coupon. Largest flat footprint
is 200 × 200 mm; allow for a brim/supports. Print STLs individually at 100% scale,
millimetres. Do not scale the whole set to fit a printer: fastener clearances change.

PETG, approximately 4–5 walls and 35–40% infill are prototype starting points.
The pedestal top, elbow and carrier socket need support or a suitable side
orientation. Inspect layer orientation at clamp jaws and timber joints in the
slicer; remove support material from sockets before fitting. Geometry validity
does not establish printed strength or a load rating.

## 4. Other parts

- Existing four baskets, tray, two MG996R servos and RB0051 kit; retain servo horns
  and bracket screws. No new metal pan/tilt kit is required.
- Four M5 rim bolts, broad washers and wing nuts. About 40–60 mm bolt length is a
  starting range; measure base + lip depth + shoe + washers + nut engagement.
- Four M4 bolts/nuts/washers to join base to pedestal, approximately 20–25 mm.
- M3 bolts/washers for the kit's actual base. If the pan servo itself is the base,
  the top also has four slots at x ±5/y ±24 mm for its mounting tabs. Use measured
  M3 spacers: **31 mm** is only the reference tab-to-deck height. Check the actual
  kit and shaft alignment before buying spacers or drilling anything. Do not
  attach the mechanism by gluing its servo case.
- Four M4 tray bolts, broad washers and locking nuts through the adapter's
  provisional 72 × 52 mm outer pattern. Inner M3 slots are 40 mm apart. Confirm
  the actual metal tilt plate and tray before drilling. Keep heads flush/smooth
  on the waste side; do not fasten a heavy tray only to a servo horn.
- Two M5 rear clamp screws (roughly 45–60 mm), washers and pairs of nuts. These
  are clearance holes, not printed threads: lock a nut on each side of the outer
  jaw, then turn the screw against its pressure pad. Confirm nut/tool access.
- Six M4 timber through-bolts with washers and locking nuts (roughly 40–45 mm):
  two mast base, two upright/elbow, one boom/elbow, one carrier/boom.
- Two straight 20 × 20 mm timber lengths: **586 mm upright** and **406 mm boom**
  for the provisional geometry. Cut only after measuring. Brace the upright or
  use a stable external stand if the basket rim flexes. The boom extends 20 mm
  beyond the carrier's centre so its retaining bolt passes through timber.
- Four M2 camera screws with insulating spacers around 6 mm; M2 nuts and suitable
  screw lengths after checking the board. Board hole pattern is 21 × 12.5 mm.
- Reusable straps for the existing Pi case and driver, rubber rim pads, insulating
  driver spacers, cable ties, and a strap holding the four baskets together.
- Suitable separate servo supply, Pi USB-C supply, and longer I²C/ground wires to
  reach the elevated Pi. The existing Pi-to-camera ribbon can stay short if its
  actual connector route fits. Wire lengths, shielding/routing and I²C reliability
  need testing; keep the driver cable short and separate from servo power leads.

## 5. Assemble with power disconnected

1. Arrange and strap the baskets together. Put rubber under the cross's contact
   patches. Support all four arms evenly; the centre must not balance on a gap.
2. Insert M5 bolts at x ±30/y ±80. Turn each shoe toe toward its own lip: right
   shoes point left, left shoes point right. Tighten shoes upward beneath the
   lips gently. The reference shoe starts 20 mm toward the lip from its bolt.
3. Join the pedestal to the base with four M4 bolts. Reach the internal nuts
   through the tower. Check that no bolt protrudes into a moving servo.
4. Fit the existing pan servo/kit with appropriate measured hardware/spacers.
   Centre servos electrically only when the assembly is clear and supported;
   then install horns so 90° gives a level tray and the intended pan direction.
   Software has no encoder and cannot know the physical position at startup.
5. Bolt the tray adapter to the tilt bracket, then bolt the lightweight tray to
   the adapter. The STL is an adapter, not a full tray. Keep both dumping ends
   open so an item can slide off. Test one light, dry item near the centre.
6. Clamp the separate rear clip to a reinforced rear rim with rubber-faced pads.
   Tighten only enough to prevent slipping. A flexible/slotted basket is not a
   certified cantilever support: use a rigid backer/brace or stable external
   tripod if the rim bends. Keep electronics clear of the falling waste path.
7. Insert/through-bolt the upright timber, elbow, then overhead timber. Support
   the arm while fitting. The elbow angle is generated for mast (200,330 mm)
   relative to the centre; moving the mast requires rebuilding the elbow.
8. Slide the carrier onto the arm and through-bolt it. Strap the existing Pi case
   onto its flat area, with fan and ports clear. Mount Camera V2 below the small
   lens opening on insulating M2 spacers. Lens points down; do not tighten screws
   against PCB components. Camera board/lens placement is approximate: compare
   your actual PCB before the final print.
9. Support the ribbon gently between Pi and camera. Strap the PCA9685 onto
   insulating spacers on the rear shelf; solder joints must not touch fasteners.
   Route wires beside the upright, with strain relief and slack away from moving
   parts. No full cable harness or fastener set is modelled in the assembly.

## 6. Alignment and operation

The reference lens is about **321 mm above the tray**. Camera V2's nominal
62.2° × 48.8° view covers roughly 387 × 291 mm at this distance before cropping.
That is a geometric estimate, not a verified preview. The software scans a
central 400 × 400 pixel square within its 640 × 480 image: centre the tray in
that square, mark a small central placement target, and keep the entire item in
view. Tall objects, focus and selected sensor mode can change the usable area.

The conservative whole-tray height envelope stays **37.4 mm above reference rim
height** even at 65° tilt, but this only checks tray vs rim height. It does not
validate bracket self-collisions, torque, item trajectories, camera cables or
real basket dimensions. Some off-centre items may hit the cross or tower during
their fall. Check all four paths with small light dummy items and an accessible
power switch before using waste. No automatic mechanism clearing is provided.

Map labels onto the baskets; pink/cream basket colours do not identify classes:

| Route from the operator's front | Category | Pan / tilt |
|---|---|---|
| Front-left | Paper/cardboard | 135° / 35° |
| Front-right | Plastic/polythene | 45° / 35° |
| Rear-left | Organic | 45° / 145° |
| Rear-right | Glass/metal/residual | 135° / 145° |

The shake extends tilt to 25°/155° (65° from level). Start with an unloaded tray,
small manual angle changes and confirm direction. The listed angles and 600–2400 µs
pulse range are inherited starting values, not physical calibration of your servos.
Keep hands clear; stop power on binding rather than forcing a stalled servo.

References: [Camera specifications](https://www.raspberrypi.com/documentation/accessories/camera.html),
[Camera V2 drawing](https://datasheets.raspberrypi.com/camera/camera-module-2-mechanical-drawing.pdf),
[user-identified RB0051 kit](https://tronic.lk/product/2-dof-pan-and-tilt-servo-mount-kit-mg995-mg996).
