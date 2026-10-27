# EcoSort web dashboard

A local web interface for the existing camera, classifier and four-bin pan–tilt
assembly. There is no cloud service, frontend build, CDN or extra Python package.
The web server uses Python's standard library; a real camera session uses the
project's existing runtime dependencies. The dashboard itself never opens
hardware at startup.

## Try the design on your Mac

From the repository directory:

```sh
./venv/bin/python -m dashboard --demo
```

Open **http://127.0.0.1:8080**. Enter the access code printed in the terminal.
Choose **Start session → Start demo → Enable routing**, then **Run sample**.
Sample events are marked DEMO and never mixed with physical command counts.
The tray illustration is a placeholder, not an actual camera image. Device
health readings come from the host running the server; unavailable Pi metrics
show a dash. No pretrained model is loaded in demo mode.

## Run on the Raspberry Pi

1. Open SSH and change to your checkout:

   ```sh
   cd ~/EcoSort_Smart_Bin
   ```

2. Stop any separate sorter or camera-preview application. One process must own
   the camera. The existing I2C lock also protects against competing EcoSort
   motor controllers.

3. Start the web server for access on your trusted Wi-Fi:

   ```sh
   ./venv/bin/python -m dashboard --host 0.0.0.0
   ```

4. On your Mac or phone, open **http://ecosort.local:8080**, or use
   `http://<current-Pi-IP>:8080`. Run `hostname -I` on the Pi if you need the
   current address. `0.0.0.0` is a bind address, not the address to enter on your
   phone. Enter the access code from the Pi terminal; this is separate from your
   SSH password. All viewers with this code can access the camera and controls.

5. Choose **Start session → Observe & simulate**. Keep the tray empty while the
   first 30 frames establish its background. The camera and CLIP run on the Pi;
   the browser receives a compressed 640 × 480 preview capped at two images per
   second. It does not run the ML model on your phone. The first model load can
   take time and may download weights if they are not already cached.

6. Place an item on the tray. Observe the four relative match scores, selected
   route and decision message. **Enable routing** in an observation session
   only records simulated routes. It never enables physical motors.

### Physical sorting, when the assembly is ready

End the observation session, stop the server with Ctrl+C, and restart with the
explicit physical-control opt-in:

```sh
./venv/bin/python -m dashboard --host 0.0.0.0 --allow-hardware-controls
```

Choose **Start session → Physical hardware** and confirm the readiness check.
**Starting a physical session commands the saved HOME**, even though automatic
routing initially remains paused. Check the tray is unloaded and clear before
starting. Keep the tray empty during background calibration. Use **Enable
routing** to allow accepted predictions to command the four existing routes.
A hardware initialization failure is reported as an error, not silently
converted to simulation. The dashboard does not modify saved servo angles.

**Pause routing** prevents the next route; a cycle already in progress finishes
first. **End session** similarly waits for a cycle boundary, returns hardware
to HOME through the existing controller shutdown, and releases the camera.
Neither button is an emergency electrical cutoff. Continue supervised testing
and address the previously observed power-supply issue before extended use.

**Reset empty tray** is available after pausing and completing the current
cycle. It resets camera background detection, not mechanical calibration.
**Scan tray** retains the confidence, margin and stable-prediction checks; it
cannot force an uncertain item to move.

## Features and honest measurements

- Camera preview, scanning guide toggle, full-screen view and snapshot download.
- Four material scores, best supported category, stability and decision reason.
- Saved HOME and route commands: pan 90° / tilt 125° HOME, with the existing
  90° and 160° tilt endpoints. All values are loaded from the shared calibration.
- Today's completed command counts for the selected session mode. These are
  neither measured bin fill nor verified correct deliveries.
- Persistent history with category/mode filters and CSV export. A new record is
  created only after the controller's route method returns successfully.
- Pi temperature, memory, disk use, uptime, load and available firmware power
  flags. Historical undervoltage flags are distinguished from current flags.
- Disconnection/stale-camera states and observation-first sessions.

History is stored in `~/.local/share/ecosort-dashboard/history.sqlite3` unless
`--data-dir` is supplied. Dates follow the server's local timezone; configure
Pi OS for Asia/Colombo if needed. The activity screen shows the latest 250
records and CSV exports the latest 10,000. Frames are temporary: on Pi OS they
are written to `/dev/shm` (RAM), not continuously saved to the SD card. No video
recording is enabled. An inference or motor cycle can delay the next frame;
the interface marks a stream stale after eight seconds.

## Access and startup options

By default the server binds only to loopback. `--host 0.0.0.0` allows trusted
LAN clients. Requests require a session cookie obtained with the terminal
access code, and control requests must be same-origin. Do not port-forward
this HTTP server to the Internet. HTTP does not encrypt the access code or
camera stream. For encrypted access, retain the loopback default and use SSH
from your Mac:

```sh
ssh -L 8080:127.0.0.1:8080 en12@ecosort.local
```

Then open **http://127.0.0.1:8080** on the Mac. This does not require VNC.
For a stable code across server restarts, set `ECOSORT_DASHBOARD_CODE` to an
at-least-eight-character secret in your shell environment. Do not commit it to
Git. Without that variable, each restart prints a new random code and
invalidates previous browser sessions.

Start the server manually during initial tests. Automatic boot startup is
intentionally not installed; no camera or motor session should begin
unexpectedly. A future service can start the web server, while the operator
still starts each observation/physical session through the dashboard.

## Verification

```sh
./venv/bin/python scripts/verify.py
node --check dashboard/web/app.js
```

Offline tests cover authenticated API access, cross-origin rejection, persistent
mode-separated history, error states, hardware opt-in and the actual runtime's
pause gate. Demo browser checks do not verify Pi camera capture, physical
motion, power stability or sorting accuracy. Validate those on the assembled
Pi before relying on physical sessions.
