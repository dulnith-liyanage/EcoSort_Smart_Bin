# View the Pi desktop and tray camera

## Connect from the Mac

The Pi at `192.168.8.159` uses Raspberry Pi OS Trixie's Wayland desktop and
WayVNC. VNC is enabled at boot and uses Pi-account authentication. The existing
desktop session already starts automatically and has a 1920x1080 headless
display, so no monitor or OS reinstall is needed.

1. Keep the Mac and Pi on the same local network.
2. Install [TigerVNC Viewer](https://tigervnc.org/) for macOS. Raspberry Pi's
   [official instructions](https://www.raspberrypi.com/documentation/computers/remote-access.html#vnc)
   recommend this client for the current server.
3. Open TigerVNC Viewer and connect to `192.168.8.159` (default port 5900).
4. Log in as `en12` with the existing Pi password. If a certificate warning
   appears on the first connection, verify that the address is your Pi before
   trusting it. No password is stored in this repository.
5. Double-click **EcoSort Camera Preview** on the Pi desktop. If asked whether
   to execute the trusted local launcher, choose Execute. The preview can also
   be found in the desktop application menu.
6. Centre the tray below the green crosshair. Press **Q**, **Esc**, the close
   button, or close the window to release the camera.

`camera_preview.py` displays 640x480 frames through Tk/Pillow, which VNC can
capture. It does not import servo code, run classification, or command motors.
VNC shares the desktop; the camera program supplies the visible camera window.
Only one application can use Camera V2 at a time. Close the preview before
starting the classifier/sorter. Disconnecting the VNC viewer does not close
applications running on the Pi.

## Start and stop the server

VNC should already start automatically. These commands run **on the Pi**, over
SSH or in a Pi terminal:

```sh
sudo systemctl start wayvnc
systemctl is-active wayvnc
```

To stop it: `sudo systemctl stop wayvnc`. To enable it on another Raspberry Pi
OS desktop installation: `sudo raspi-config nonint do_vnc 0`. This requires a
running desktop; a Lite installation needs a desktop installed separately.

Keep this setup on the local network; no router port forwarding is needed.
If the IP changes after a reboot, find it with `hostname -I` on the Pi. The
hostname `ecosort.local` may also work where the network supports mDNS.

## Reinstall or run the preview manually

Use the project's system-site-packages virtual environment so it can import
the OS-provided Picamera2, Tk and Pillow packages:

```sh
sudo apt-get install python3-picamera2 python3-tk python3-pil.imagetk
cd /home/en12/EcoSort_Smart_Bin
./venv/bin/python scripts/install_camera_launcher.py
```

From a terminal **inside the VNC desktop**:

```sh
bash /home/en12/EcoSort_Smart_Bin/scripts/start_camera_preview.sh
```

For a ten-second display check, add `--seconds 10`. Plain SSH has no graphical
display by default, so the preview explains that it should be opened from the
desktop. Errors are written to standard error. If another camera application
is open, close it before retrying.

During remote setup the preview may be started as a temporary user service:

```sh
systemctl --user status ecosort-camera-preview
journalctl --user -u ecosort-camera-preview -n 20 --no-pager
systemctl --user stop ecosort-camera-preview
```

This temporary service does not automatically start after reboot. Use the
desktop shortcut to reopen the preview. Sorting remains a separate deliberate
action: opening VNC or the camera shortcut never starts the motors.
