#!/usr/bin/python
"""Local wallpaper-driven KDE colors; no network access or root privileges."""
import argparse
import colorsys
import configparser
import fcntl
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import unquote

from PIL import Image

HOME = Path.home()
CONFIG = HOME / '.config/wallpaper-theme/config.json'
STATE = HOME / '.local/state/wallpaper-theme'
DATA = HOME / '.local/share'


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=20).stdout.strip()


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def settings():
    result = {'paused': False, 'screen': 0, 'overrides': {}}
    if CONFIG.exists():
        result.update(json.loads(CONFIG.read_text()))
    return result


def plasma(script):
    return run('qdbus6', 'org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell.evaluateScript', script)


def current(screen):
    script = '''var ds=desktops();for(var i=0;i<ds.length;i++){var d=ds[i];
    if(d.screen==SCREEN){d.currentConfigGroup=["Wallpaper",d.wallpaperPlugin,"General"];
    print(JSON.stringify({plugin:d.wallpaperPlugin,source:d.readConfig("WallpaperSource",""),
    image:d.readConfig("Image","")}));break;}}'''.replace('SCREEN', str(int(screen)))
    value = plasma(script)
    if not value:
        raise ValueError(f'No desktop on screen {screen}')
    return json.loads(value)


def local_path(value):
    return Path(os.path.expandvars(unquote(value.removeprefix('file://').removeprefix('file:')))).expanduser()


def resolve(wallpaper):
    if wallpaper['plugin'] == 'com.github.catsout.wallpaperEngineKde':
        source = wallpaper['source'].rsplit('+', 1)[0]
        folder = local_path(source).parent
        project = json.loads((folder / 'project.json').read_text())
        preview = (folder / project['preview']).resolve()
        if not preview.is_relative_to(folder.resolve()):
            raise ValueError('Preview must be inside the wallpaper directory')
        return 'workshop:' + str(folder.name), preview
    if wallpaper['plugin'] == 'org.kde.image':
        path = local_path(wallpaper['image'])
        return 'image:' + str(path), path
    raise ValueError('Unsupported wallpaper plugin: ' + wallpaper['plugin'])


def extract(path):
    with Image.open(path) as image:
        image.seek(0)
        image = image.convert('RGB')
        image.thumbnail((128, 128))
        quantized = image.quantize(colors=12)
        palette = quantized.getpalette()
        choices = []
        for count, index in quantized.getcolors():
            rgb = palette[index * 3:index * 3 + 3]
            h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))
            if 0.15 < v < 0.97 and s > 0.18:
                choices.append((count * s ** 0.7 * v ** 0.3, h, s))
        if not choices:
            return '#8da9bd'
        _, hue, saturation = max(choices)
        return hex_rgb(colorsys.hsv_to_rgb(hue, min(0.7, max(0.4, saturation)), 0.88))


def hex_rgb(rgb):
    return '#' + ''.join(f'{round(x * 255):02x}' for x in rgb)


def rgb(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Accent must be a hex color such as #57ade6')
    return tuple(int(value[i:i+2], 16) / 255 for i in (1, 3, 5))


def csv(value):
    return ','.join(str(round(x * 255)) for x in value)


def luminance(value):
    channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in value]
    return sum(a*b for a,b in zip(channels, (0.2126, 0.7152, 0.0722)))


def selection(accent):
    color = rgb(accent)
    while 1.05 / (luminance(color) + 0.05) < 4.5:
        color = tuple(c * 0.95 for c in color)
    return color


def parser(path):
    p = configparser.ConfigParser(interpolation=None)
    p.optionxform = str
    if not p.read(path):
        raise FileNotFoundError(path)
    return p


def save_ini(p, path):
    output = io.StringIO()
    p.write(output, space_around_delimiters=False)
    atomic(path, output.getvalue())


def write_scheme(accent, name='WallpaperAdaptive'):
    p = parser('/usr/share/color-schemes/BreezeDark.colors')
    hue, _, _ = colorsys.rgb_to_hsv(*rgb(accent))
    tint = lambda v, s=0.32: csv(colorsys.hsv_to_rgb(hue, s, v))
    for section in p.sections():
        if section.startswith('Colors:'):
            p[section].update({'BackgroundNormal': tint(0.15), 'BackgroundAlternate': tint(0.19),
                'ForegroundNormal': '234,240,246', 'ForegroundInactive': '156,172,187',
                'DecorationFocus': csv(rgb(accent)), 'DecorationHover': tint(0.95, 0.45),
                'ForegroundActive': csv(rgb(accent)), 'ForegroundLink': tint(1, 0.4),
                'ForegroundVisited': tint(0.85, 0.25)})
    p['Colors:View'].update({'BackgroundNormal':tint(0.105), 'BackgroundAlternate':tint(0.14)})
    p['Colors:Button']['BackgroundNormal'] = tint(0.22)
    p['Colors:Selection'].update({'BackgroundNormal':csv(selection(accent)),
        'BackgroundAlternate':csv(selection(accent)), 'ForegroundNormal':'255,255,255',
        'ForegroundInactive':'240,240,240', 'ForegroundActive':'255,255,255', 'ForegroundLink':'255,255,255'})
    p['General'].clear()
    p['General'].update({'Name':name, 'ColorScheme':name})
    p['WM'].update({'activeBackground':tint(0.15),'activeBlend':tint(0.15),
        'inactiveBackground':tint(0.15),'inactiveBlend':tint(0.15),
        'activeForeground':'234,240,246','inactiveForeground':'156,172,187'})
    save_ini(p, DATA / ('color-schemes/' + name + '.colors'))
    return tint(0.105)


def widget_colors(accent):
    return plasma('''var out=[];var ps=panels();for(var i=0;i<ps.length;i++){
    var ws=ps[i].widgets();for(var j=0;j<ws.length;j++){var w=ws[j];var key="";
    if(w.type=="com.github.tilorenz.compact_pager"){w.currentConfigGroup=["Appearance"];key="borderColor";}
    if(w.type=="AndromedaLauncher"){w.currentConfigGroup=["General"];key="indicatorColor";}
    if(key){out.push({id:w.id,group:w.currentConfigGroup,key:key,value:w.readConfig(key,"")});
    SETTING}}}print(JSON.stringify(out));'''.replace('SETTING', '' if accent is None else
        'w.writeConfig(key,' + json.dumps(csv(rgb(accent))) + ');'))


def backup():
    path = STATE / 'original.json'
    if path.exists():
        return
    global_config = parser(HOME / '.config/kdeglobals')
    original = {'scheme':global_config.get('General','ColorScheme'),
        'profile':run('kreadconfig6','--file','konsolerc','--group','Desktop Entry','--key','DefaultProfile'),
        'widgets':json.loads(widget_colors(None))}
    atomic(path, json.dumps(original, indent=2))
    # Freeze original palette even if another tool later regenerates it.
    saved = configparser.ConfigParser(interpolation=None)
    saved.optionxform = str
    for section in global_config.sections():
        if section.startswith(('Colors:', 'ColorEffects:')) or section == 'WM':
            saved[section] = dict(global_config[section])
    saved['General'] = {'Name':'Wallpaper Theme Original','ColorScheme':'WallpaperThemeOriginal'}
    save_ini(saved, DATA / 'color-schemes/WallpaperThemeOriginal.colors')


def apply(accent, identity):
    rgb(accent)
    backup()
    # Alternate two files because KDE skips applying the currently selected scheme.
    selected = run('kreadconfig6','--file','kdeglobals','--group','General','--key','ColorScheme')
    name = 'WallpaperAdaptiveB' if selected == 'WallpaperAdaptiveA' else 'WallpaperAdaptiveA'
    background = write_scheme(accent, name)
    run('plasma-apply-colorscheme',name)
    active = run('kreadconfig6','--file','kdeglobals','--group','Colors:Window','--key','BackgroundNormal')
    expected = parser(DATA / ('color-schemes/' + name + '.colors'))['Colors:Window']['BackgroundNormal']
    if active != expected:
        raise RuntimeError('KDE did not reload the generated palette')
    template = STATE / 'terminal-template.colorscheme'
    if not template.exists():
        profile = run('kreadconfig6','--file','konsolerc','--group','Desktop Entry','--key','DefaultProfile')
        profile_path = DATA / 'konsole' / profile
        terminal = parser(profile_path)
        base = DATA / 'konsole' / (terminal['Appearance']['ColorScheme'] + '.colorscheme')
        atomic(template, base.read_text())
    terminal = parser(template)
    terminal['General']['Description'] = 'Wallpaper Adaptive'
    for section in ('Background','BackgroundIntense','BackgroundFaint'):
        terminal[section]['Color'] = background
    save_ini(terminal, DATA / 'konsole/WallpaperAdaptive.colorscheme')
    original = json.loads((STATE / 'original.json').read_text())
    profile = parser(DATA / 'konsole' / original['profile'])
    profile['Appearance']['ColorScheme'] = 'WallpaperAdaptive'
    profile['General']['Name'] = 'Wallpaper Adaptive'
    save_ini(profile, DATA / 'konsole/WallpaperAdaptive.profile')
    run('kwriteconfig6','--file','konsolerc','--group','Desktop Entry','--key','DefaultProfile','WallpaperAdaptive.profile')
    widget_colors(accent)
    atomic(STATE / 'last.json', json.dumps({'wallpaper':identity,'accent':accent,'applied':time.time()}, indent=2))
    logging.info('Applied %s for %s', accent, identity)


def choose(config):
    identity, preview = resolve(current(config['screen']))
    accent = config['overrides'].get(identity) or extract(preview)
    rgb(accent)
    return identity, preview, accent


def watch():
    previous = None
    pending = None
    while True:
        try:
            config = settings()
            if config['paused']:
                previous = pending = None
            else:
                wall = current(config['screen'])
                key = json.dumps([wall, config], sort_keys=True)
                if key == pending and key != previous:
                    identity, preview = resolve(wall)
                    accent = config['overrides'].get(identity) or extract(preview)
                    apply(accent, identity)
                    previous = key
                pending = key
        except Exception as error:
            logging.warning('%s; preserving current theme and retrying', error)
        time.sleep(4)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('command', choices=['watch','preview','apply','pause','resume','status','override','auto','restore'])
    cli.add_argument('accent', nargs='?')
    args = cli.parse_args()
    config = settings()
    if args.command in ('pause','resume'):
        config['paused'] = args.command == 'pause'
        atomic(CONFIG, json.dumps(config, indent=2))
        print(args.command + 'd')
        return
    if args.command == 'status':
        print(json.dumps(config, indent=2))
        if (STATE / 'last.json').exists():
            print((STATE / 'last.json').read_text())
        return
    if args.command in ('override','auto'):
        identity, _ = resolve(current(config['screen']))
        if args.command == 'override':
            rgb(args.accent or '')
            config['overrides'][identity] = args.accent
        else:
            config['overrides'].pop(identity, None)
        atomic(CONFIG, json.dumps(config, indent=2))
        print('Saved preference for', identity)
        return
    if args.command == 'preview':
        identity, preview, accent = choose(config)
        print(json.dumps({'wallpaper':identity,'preview':str(preview),'accent':accent}, indent=2))
        return
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'watch.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Watcher is running; stop wallpaper-theme.service before apply or restore.')
        if args.command == 'watch':
            watch()
        elif args.command == 'apply':
            identity, _, accent = choose(config)
            apply(accent, identity)
        elif args.command == 'restore':
            config['paused'] = True
            atomic(CONFIG, json.dumps(config, indent=2))
            original = json.loads((STATE / 'original.json').read_text())
            run('plasma-apply-colorscheme','WallpaperThemeOriginal')
            run('kwriteconfig6','--file','konsolerc','--group','Desktop Entry','--key','DefaultProfile',original['profile'])
            for w in original['widgets']:
                plasma('var ps=panels();for(var i=0;i<ps.length;i++){var w=ps[i].widgetById(' + str(w['id']) + ');if(w){w.currentConfigGroup=' + json.dumps(w['group']) + ';w.writeConfig(' + json.dumps(w['key']) + ',' + json.dumps(w['value']) + ');}}')
            print('Original palette restored; automatic updates paused.')


if __name__ == '__main__':
    main()
