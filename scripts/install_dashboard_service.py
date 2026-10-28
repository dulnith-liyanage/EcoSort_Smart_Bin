#!/usr/bin/env python3
"""Prepare or install EcoSort's headless boot service. Preview is the default."""
import argparse
import grp
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SERVICE = 'ecosort-dashboard.service'


def unit_text(root, python, username, home, groups):
    """Use the existing venv/cache, even when the checkout contains spaces."""
    for value in [str(root), str(python), username, str(home)]:
        if any(char in value for char in ['\n', '\r', '"', '\\', '%', '$']):
            raise ValueError('Service paths/user contain unsupported characters.')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*\$?', username):
        raise ValueError('Invalid service user.')
    return f'''[Unit]
Description=EcoSort local dashboard and automatic waste sorter
After=local-fs.target avahi-daemon.service
Wants=avahi-daemon.service
StartLimitIntervalSec=120
StartLimitBurst=3

[Service]
Type=simple
User={username}
SupplementaryGroups={' '.join(groups)}
WorkingDirectory={root}
Environment="HOME={home}"
Environment=PYTHONUNBUFFERED=1
Environment=HF_HUB_OFFLINE=1
Environment=TRANSFORMERS_OFFLINE=1
Environment=OMP_NUM_THREADS=1
Environment=OPENBLAS_NUM_THREADS=1
Environment=MKL_NUM_THREADS=1
ExecStart="{python}" -m dashboard --host 0.0.0.0 --port 8080 --autostart --allow-hardware-controls
Restart=on-failure
RestartSec=10
KillSignal=SIGINT
KillMode=mixed
TimeoutStopSec=120
NoNewPrivileges=true
UMask=0077
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
'''


def avahi_text():
    return '''<?xml version="1.0" standalone="no"?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">EcoSort on %h</name>
  <service><type>_http._tcp</type><port>8080</port><txt-record>path=/</txt-record></service>
</service-group>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Pi only: install and enable for the NEXT boot; does not start motors now.')
    args = parser.parse_args()
    username = os.environ.get('SUDO_USER') or pwd.getpwuid(os.getuid()).pw_name
    account = pwd.getpwnam(username)
    python = ROOT / 'venv/bin/python'
    groups = [name for name in ['i2c', 'video', 'render'] if name in {entry.gr_name for entry in grp.getgrall()}]
    unit = unit_text(ROOT, python, username, Path(account.pw_dir), groups)
    if not args.install:
        print(unit)
        print('# Preview only. Nothing was installed or enabled.')
        return 0
    try:
        model = Path('/proc/device-tree/model').read_text().rstrip('\0')
    except OSError:
        model = ''
    if sys.platform != 'linux' or 'Raspberry Pi' not in model:
        parser.error('--install is only supported on a Raspberry Pi. Nothing changed.')
    if os.geteuid() == 0 or account.pw_uid == 0:
        parser.error('Run as the normal Pi user. This installer uses sudo only for system changes.')
    if 'i2c' not in groups or 'video' not in groups:
        parser.error('Run the existing Pi setup first: i2c and video groups are required.')
    if not python.exists():
        parser.error('The project venv is missing. Run setup_raspberry_pi.sh first.')
    # This imports the model only. It never initializes the camera or motors.
    # Ensures the service will work without Internet and uses this user's cache.
    environment = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    subprocess.run([str(python), '-c', 'from live_smart_bin import ClipClassifier; ClipClassifier(cpu_threads=1)'],
                   cwd=ROOT, env=environment, check=True)
    subprocess.run([str(python), 'servo_control.py', '--check-calibration'], cwd=ROOT, check=True)
    subprocess.run(['sudo', 'apt-get', 'install', '-y', 'avahi-daemon'], check=True)
    with tempfile.TemporaryDirectory(prefix='ecosort-service-') as directory:
        unit_path = Path(directory) / SERVICE
        unit_path.write_text(unit)
        avahi_path = Path(directory) / 'ecosort.service'
        avahi_path.write_text(avahi_text())
        subprocess.run(['systemd-analyze', 'verify', str(unit_path)], check=True)
        subprocess.run(['sudo', 'install', '-m', '644', str(unit_path), '/etc/systemd/system/' + SERVICE], check=True)
        subprocess.run(['sudo', 'install', '-m', '644', str(avahi_path), '/etc/avahi/services/ecosort.service'], check=True)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    subprocess.run(['sudo', 'systemctl', 'enable', SERVICE], check=True)
    subprocess.run(['sudo', 'systemctl', 'enable', '--now', 'avahi-daemon.service'], check=True)
    print('Installed for NEXT boot. Camera and motors have NOT been started by this installer.')
    print('Keep the tray empty and mechanism clear before booting with the servo supply connected.')
    print('Open http://<Pi-hostname>.local:8080 on the same trusted network. No login code.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
