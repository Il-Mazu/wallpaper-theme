# Wallpaper Theme

A Python script that changes KDE Plasma's colors when you switch wallpapers. It reads the wallpaper's preview image, picks an accent, and creates a matching dark color scheme.

Works with Wallpaper Engine for KDE (`com.github.catsout.wallpaperEngineKde`) and ordinary KDE image wallpapers. It updates KDE colors, accent-aware folders, Compact Pager, Andromeda Launcher, and a Konsole profile. Fonts, icon theme, layout, and animations stay as configured.

Everything runs locally. Live wallpapers are sampled from the first frame of their preview image. SDDM isn't changed.

## Install

Requires Linux with KDE Plasma 6, Python 3.10+, Pillow, and systemd user services. These commands must be available: `qdbus6`, `plasma-apply-colorscheme`, `kwriteconfig6`, and `kreadconfig6`. The script uses the installed `/usr/share/color-schemes/BreezeDark.colors` as its base.

```sh
git clone https://github.com/Il-Mazu/wallpaper-theme.git
cd wallpaper-theme
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python wallpaper_theme.py preview
```

`preview` shows the selected wallpaper and accent without changing anything. To start automatic updates:

```sh
.venv/bin/python install_service.py
```

Run this inside your Plasma session, without sudo. The installer registers the checkout's location and Python interpreter, then starts the service. It starts again with your graphical session. Keep the checkout and virtual environment in place; rerun the installer if you move them.

## Use

The watcher checks every four seconds and waits for two matching readings before applying a change. A wallpaper switch normally takes 4–8 seconds to update the theme.

```sh
.venv/bin/python wallpaper_theme.py status
.venv/bin/python wallpaper_theme.py pause
.venv/bin/python wallpaper_theme.py resume
```

`pause` keeps the current theme. To save an accent for the current wallpaper:

```sh
.venv/bin/python wallpaper_theme.py override '#57ade6'
```

To go back to automatic color selection for that wallpaper:

```sh
.venv/bin/python wallpaper_theme.py auto
```

Overrides take effect on the next watcher cycle unless paused. Settings are saved in `~/.config/wallpaper-theme/config.json`. Change `screen` there to use a different Plasma screen number; the default is `0`. One palette is shared by all monitors.

## Service

```sh
systemctl --user status wallpaper-theme.service
journalctl --user -u wallpaper-theme.service -n 30
systemctl --user stop wallpaper-theme.service
systemctl --user start wallpaper-theme.service
```

For a single update, stop the service and run `.venv/bin/python wallpaper_theme.py apply`. The watcher and manual updates cannot run at the same time.

## Restore

The first run saves the previous palette, terminal profile name, and supported widget colors in `~/.local/state/wallpaper-theme/`. To restore them:

```sh
systemctl --user disable --now wallpaper-theme.service
.venv/bin/python wallpaper_theme.py restore
```

Restoring also pauses automation. To enable it again, run `resume` and rerun the installer. Generated color schemes remain available in KDE's settings.

## Limitations

Tested on a CachyOS Plasma 6 desktop with Wallpaper Engine for KDE. Other distributions have not been verified.

Konsole integration currently requires an existing local default profile in `~/.local/share/konsole/`, with an explicit `ColorScheme` pointing to a `.colorscheme` file in the same directory. Built-in or inherited profiles are not supported yet. A failure during application can leave part of a theme applied; check the service log and use `restore` if needed.

Missing previews and unsupported wallpaper plugins are retried without selecting a new palette. Changing an image's contents without changing its wallpaper path is not detected. Some applications and existing terminal sessions need reopening to refresh their colors. Folder recoloring depends on the icon theme supporting KDE's accent colors.

White selection text has a target contrast ratio of at least 4.5:1. Error, warning, and success colors retain their meanings. Grayscale previews use a muted blue-gray accent. A preview can differ from the actual animated scene; use an override if its selected color doesn't fit.

## Tests

```sh
.venv/bin/python -m unittest -v
```

The palette test requires the installed Breeze Dark color scheme. Tests cover color extraction, grayscale fallback, selection contrast, invalid accents, preview path validation, and preservation of semantic colors. Live checks on the development desktop also covered repeated application, restoration, and service startup.
