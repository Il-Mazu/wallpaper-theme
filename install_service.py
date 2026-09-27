#!/usr/bin/env python3
"""Install the user service using this checkout and Python interpreter."""
from pathlib import Path
import subprocess
import sys


def quoted(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def main():
    root = Path(__file__).resolve().parent
    template = (root / 'wallpaper-theme.service').read_text()
    command = quoted(sys.executable) + ' ' + quoted(root / 'wallpaper_theme.py') + ' watch'
    unit = template.replace('@EXEC_START@', command)
    target = Path.home() / '.config/systemd/user/wallpaper-theme.service'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(unit)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', 'wallpaper-theme.service'], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'wallpaper-theme.service'], check=True)
    print('Installed', target)


if __name__ == '__main__':
    main()
