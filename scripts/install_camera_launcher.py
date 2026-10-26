"""Install a launch-on-click camera shortcut for the current Pi desktop user."""
from pathlib import Path
import subprocess


def main():
    project = Path(__file__).resolve().parents[1]
    result = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True,
                            text=True, check=True)
    desktop = Path(result.stdout.strip())
    if not desktop.is_absolute() or desktop == Path.home():
        raise RuntimeError('No desktop directory configured for this user.')
    desktop.mkdir(parents=True, exist_ok=True)
    # Desktop Entry Exec has its own escaping rules, independent of the shell.
    launcher = str(project / 'scripts/start_camera_preview.sh')
    quoted = launcher.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    content = ('[Desktop Entry]\nType=Application\nName=EcoSort Camera Preview\n'
               'Comment=View the tray camera without moving motors\n'
               f'Exec=/bin/bash "{quoted}"\nIcon=camera-photo\nTerminal=false\n'
               'Categories=AudioVideo;Video;\nStartupNotify=false\n')
    shortcut = desktop / 'ecosort-camera-preview.desktop'
    shortcut.write_text(content)
    shortcut.chmod(0o755)
    applications = Path.home() / '.local/share/applications'
    applications.mkdir(parents=True, exist_ok=True)
    (applications / shortcut.name).write_text(content)
    print(f'Installed {shortcut}. Double-click it through VNC.')


if __name__ == '__main__':
    main()
