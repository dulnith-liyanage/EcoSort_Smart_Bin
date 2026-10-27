# Existing hardware assembly

The project uses four purchased baskets arranged in a 2x2 square, the existing
centre support, two MG996R servos in the metal pan/tilt kit, and the existing
tray. No 3D-printed parts or CAD files are required.

## Mounting and camera view

1. Secure the four baskets together so they cannot slide apart. The centre
   support must rest firmly on the rims without rocking or crushing them.
2. Bolt the lower pan/tilt base to the existing support. Secure the tray to the
   upper bracket with suitable fasteners; centre its weight over the mechanism.
   Measurements and a load rating have not been established remotely.
3. Keep the Pi in its ventilated case on the existing overhead support. Secure
   the Camera V2 close enough to the Pi for the short ribbon cable. Keep the
   cable slack and away from both axes and the tray's travel.
4. Point the camera down at a plain, matte tray. Use even lighting without
   strong shadows or reflections. Check focus with the camera preview.
5. Clear the full tray path and check every attachment before powering servos.
   Start unloaded. The saved commands do not prove mechanical clearance.

## Current bin labels

From the same operator viewpoint used during calibration:

| Position | Supported contents | Pan command | Tilt command |
|---|---|---:|---:|
| Front-left | Paper/cardboard | 135 | 90 |
| Front-right | Rigid plastic containers | 45 | 90 |
| Rear-left | Metal cans | 45 | 160 |
| Rear-right | Fruit/vegetable scraps | 135 | 160 |

Label the actual baskets; their physical colours do not identify these classes.
The older organic and residual labels no longer apply. Level HOME is pan 90,
tilt 125. Shake is disabled. Tilt targets are provisional 35-degree command
offsets from HOME, pending physical clearance and delivery tests.

Unknown or ambiguous items remain on the tray for manual removal; there is no
fifth physical bin. This is not a hazardous-waste identification system.

## Before physical operation

Follow [Pi setup](pi_setup.md), [HOME calibration](home_calibration.md), and [power troubleshooting](shutdown_troubleshooting.md). 

**Power Configuration (Resolved):** The initial Pi undervoltage issue has been resolved by implementing separate power supplies for the Raspberry Pi 5 and the PCA9685 motor driver. The MG996R servos now draw from a dedicated high-current supply with a shared ground to the Pi, ensuring stable voltage drops during loaded tray movements.

Opening VNC or the camera preview does not start sorting. Use simulation for recognition tests until mechanical clearance checks are complete.