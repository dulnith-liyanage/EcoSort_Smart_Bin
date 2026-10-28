# Simple dashboard and headless startup

The main screen contains the camera, current item, four bin counters and a
pause/resume button. Recent activity and read-only device details are collapsed
by default. Desktop places the camera and result side by side; mobile puts the current
classification and pause button first, followed by the camera.
No framework build, cloud account, VNC, terminal code or browser login is needed.

## Daily use after the one-time Pi installation

1. Keep the tray empty and the mechanism clear. Connect the existing separate
   servo supply and power the Pi.
2. The systemd service starts the website immediately, then loads the cached
   CLIP model and opens the single shared camera process. Classification does
   not depend on someone opening the website or on Wi-Fi becoming available.
3. Hardware initialization commands the saved HOME. The first 30 camera frames
   learn the empty tray. Only then is automatic routing enabled. Model loading
   still takes time: there is no promise of instant inference at power-on.
4. Join the same Wi-Fi and open **http://ecosort.local:8080**, assuming the Pi's
   hostname remains `ecosort`. Bookmark it or add it to your phone's home screen.
   If the hostname differs, use `http://<hostname>.local:8080`. Where mDNS does
   not work, use the Pi's IP address from your router's device list. A router
   DHCP reservation can keep that address stable.
5. Place one supported item on the tray. Recognition, score/margin/stability
   checks and the existing calibrated routes run automatically. Closing the
   browser does not stop sorting. No manual SSH command is needed each boot.

The existing HOME remains pan 90° / tilt 125°, with tilt endpoints 90° / 160°.
No servo calibration or classification threshold was changed for this work.
**Pause sorting** blocks the next cycle, leaving classification and the camera
running. An in-flight route finishes first. It is not an emergency power cutoff.
After pausing, **Reset empty tray** relearns only the camera background; remove
items and hands first. It does not change mechanical calibration.

## One-time installation (to do when the Pi is powered)

Installed and reboot-tested on the Pi on 28 October 2026. These commands are
retained for reinstalling; the installer defaults to a preview and refuses to
install on a Mac.

First copy/update the dashboard branch on the Pi, close competing sorter and
camera applications, verify the established motor routes and inspect the power
supply issue before enabling physical startup. Confirm Wi-Fi is saved in Pi OS.

Run as the normal Pi user, from the repository:

```sh
# Read the proposed service without installing it:
./venv/bin/python scripts/install_dashboard_service.py

# Install for the NEXT boot (does not start the camera/motors now):
./venv/bin/python scripts/install_dashboard_service.py --install
```

The installer checks the local model cache in offline mode and validates the
saved servo routes before making system changes. If the model is missing,
cache it using the existing setup workflow with an Internet connection first.
It installs Avahi for local hostname discovery, writes the service, and enables
it for the next boot. It never enables the sorter with `--now`.

After clearing the tray/assembly, the first supervised reboot will test startup,
local hostname access, camera capture, model inference, I2C and delivery. Future
power-ons will not need SSH, VNC or a manually started command. That first Pi
verification passed for boot, model loading, I2C and camera streaming; this
does not establish correct physical item delivery.

Files installed on the Pi:

- `/etc/systemd/system/ecosort-dashboard.service`
- `/etc/avahi/services/ecosort.service`

The service runs as the normal user with I2C/video access and the existing venv
and model cache. It uses one inference thread, caps previews at two JPEGs per
second, and stores temporary frames in RAM under `/dev/shm`. It does not depend
on a desktop session or `network-online.target`. History persists under
`~/.local/share/ecosort-dashboard/history.sqlite3`.

## Startup and failure handling

The website stays available while the camera/model loads. At most three initial
startup attempts are made, 15 seconds apart. Once camera operation is reached,
a later error stops sorting and is shown in the browser; there is no blind
motor restart after an operational error. **Start sorting** can retry after the
operator checks the assembly. A pause during startup cancels automatic routing.

Systemd restarts the web supervisor on failure with a delay and a rate limit.
Normal shutdown requests a worker stop and allows an active route to finish.
A software crash, forced shutdown or power loss cannot guarantee a level tray:
the prototype has no angle or delivery feedback sensors.

For maintenance only (not daily operation):

```sh
sudo systemctl status ecosort-dashboard.service
journalctl -u ecosort-dashboard.service -n 80 --no-pager
# Stop it now and disable automatic startup:
sudo systemctl disable --now ecosort-dashboard.service
```

Stopping the service normally returns the motor controller to HOME. Clear the
assembly before issuing maintenance commands.

## Local access without a code

Anyone on the trusted LAN can view the camera and use the basic controls.
This is the deliberate replacement for the previous terminal-code login.
HTTP is unencrypted. Keep the service on a trusted home/project network and do
not expose/port-forward it to the Internet. Unexpected hostnames, public source
addresses and cross-origin control requests are rejected. These checks are not
a substitute for network isolation and cannot protect against a router proxy
that disguises public traffic as local traffic.

Pi OS advertises the hostname through Avahi/mDNS; the installer also advertises
an HTTP service. Actual name resolution depends on the client and Wi-Fi network.
An IP address, bookmark or later printed URL/QR label provides a fallback.

## Preview on the Mac

```sh
./venv/bin/python -m dashboard --demo --autostart
```

Open **http://127.0.0.1:8080**. It opens directly without a code. **Try a sample
item** changes the category and updates labelled simulated history. Demo mode
never loads a model, opens the camera or initializes motors.

For an explicit live observation session on the Pi without physical motor output:

```sh
./venv/bin/python -m dashboard --host 0.0.0.0 --autostart
```

Physical boot operation additionally uses `--allow-hardware-controls` in the
installed service. Do not run a second server/classifier alongside that service.

## Verification and measurements

```sh
./venv/bin/python scripts/verify.py
node --check dashboard/web/app.js
```

Counts are completed route commands, not bin fullness or verified deliveries.
Match scores are not measured accuracy. CSV export retains modes/outcomes and
up to the latest 10,000 records; the collapsed history shows the latest five.
Missing Pi metrics are unavailable, never invented. Stale or disconnected
camera views are labelled. Boot, camera streaming and hardware-mode startup
were checked on the Pi on 28 October 2026. Item accuracy and correct-bin
delivery still need separate supervised tests.

References: [Pi remote access and mDNS](https://www.raspberrypi.com/documentation/computers/remote-access.html),
[systemd service configuration](https://www.freedesktop.org/software/systemd/man/systemd.service.html).

## Quiet HOME operation

`release_pan_at_home: true` in the shared calibration releases only the pan
holding signal once both axes reach HOME. Tilt remains powered to support the
tray. Pan re-engages before a route or a manual tilt away from level. The
operator confirmed tilt holding with pan released was quiet. Do not rotate the
released pan axis by hand: the software has no physical angle feedback. See
[the vibration diagnosis](servo_vibration.md).
