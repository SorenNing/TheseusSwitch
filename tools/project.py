#!/usr/bin/env python3
"""Portable standalone source contracts; never compiles or invokes network tools."""
import hashlib
import json
import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'packaging/config.json').read_text())
KEYS = {'enabledSwitch'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def discover():
    # Preserve the complete pinned upstream archive unchanged. The two unrelated
    # UI components are archived but explicitly excluded from this tweak build.
    vendor = sorted((ROOT/'Vendor/Theseus/Sources/Theseus').rglob('*.swift'))
    swift = [p for p in vendor if p.name not in ('TheseusSlider.swift', 'TheseusTabBar.swift')]
    return {'vendor_swift': vendor, 'switch_swift': swift,
            'swift': swift+[ROOT/'src/TheseusBridge.swift', ROOT/'src/TheseusBundle.swift'],
            'core': sorted((ROOT/'src').glob('*.m')),
            'prefs': sorted((ROOT/'prefs').glob('*.m')),
            'theseus_metal': sorted((ROOT/'Vendor/Theseus/Sources/Theseus').rglob('*.metal'))}


def vendor_manifest():
    path = ROOT/'Vendor/manifest.json'
    manifest = json.loads(path.read_text())
    actual = {rel(p) for p in (ROOT/'Vendor/Theseus').rglob('*') if p.is_file() and p.name != 'UPSTREAM.json'}
    if set(manifest) != actual or len(actual) != 37:
        raise ValueError('Pinned upstream file coverage mismatch')
    for name, digest in manifest.items():
        if sha256(ROOT/name) != digest:
            raise ValueError('Immutable upstream hash mismatch: '+name)
    upstream = json.loads((ROOT/'Vendor/Theseus/UPSTREAM.json').read_text())
    if upstream['revision'] != '71ca1c127a4e7fe3387361f160c4890dbd427f66':
        raise ValueError('Unexpected upstream revision')
    return {'files': len(actual), 'verified': True, 'manifest_sha256': sha256(path), 'upstream': upstream}


def icon_source(name):
    return ROOT/('assets/pkgicon.png' if name == 'pkgicon.png' else 'prefs/Resources/'+name)


def specifiers(path):
    data = plistlib.loads(Path(path).read_bytes())
    items = data.get('items', [])
    if len(items) != 1 or {p.get('key') for p in items} != KEYS:
        raise ValueError('Exactly one standalone setting is required')
    if items[0].get('defaults') != CONFIG['package'] or items[0].get('default') is not True:
        raise ValueError('Wrong preference domain/default')
    return items


def check():
    sources = discover()
    counts = {k: len(v) for k, v in sources.items()}
    expected = {'vendor_swift': 33, 'switch_swift': 31, 'swift': 33, 'core': 4, 'prefs': 1, 'theseus_metal': 1}
    if counts != expected:
        raise ValueError('Missing or unexpected source: '+str(counts))
    for p in ROOT.rglob('*.plist'):
        plistlib.loads(p.read_bytes())
    specifiers(ROOT/'prefs/Resources/Root.plist')
    info = plistlib.loads((ROOT/'prefs/Resources/Info.plist').read_bytes())
    entry = plistlib.loads((ROOT/'prefs/Resources/entry.plist').read_bytes())['entry']
    assert info['CFBundleExecutable'] == 'TheseusSwitchPrefs'
    assert entry['bundle'] == 'TheseusSwitchPrefs'
    assert plistlib.loads((ROOT/'src/Filter.plist').read_bytes())['Filter']['Bundles'] == ['com.apple.UIKit']
    forbidden = re.compile(r'Glassify|NGDock|NGClearDockView|NGWallpaper|enabledDock|dockStyle|NGRefreshDock|NGGlassComponent')
    for p in [*(ROOT/'src').glob('*'), *(ROOT/'prefs').glob('*.m'), ROOT/'prefs/Resources/Root.plist', ROOT/'tools/build.py']:
        if forbidden.search(p.read_text()):
            raise ValueError('Unwanted integration reference: '+rel(p))
    for name in ('icon.png','icon@2x.png','icon@3x.png','pkgicon.png'):
        assert icon_source(name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    bridge = (ROOT/'src/TheseusBridge.swift').read_text()
    assert 'private let toggle = TheseusSwitch()' in bridge
    assert not re.search(r'toggle\.(configuration|layout|onTintColor|tintColor)\s*=', bridge)
    native = (ROOT/'src/NGSwitch.m').read_text()
    assert 'binding.overlay.bounds = source.bounds' in native
    assert 'source.alpha = 0.0' in native
    assert 'convertRect:' not in native
    hooks = (ROOT/'src/Tweak.m').read_text()
    for selector in ('layoutSubviews','didMoveToWindow','didMoveToSuperview','setOn:','setOn:animated:','setEnabled:','setHidden:','setAlpha:','setUserInteractionEnabled:'):
        assert '@selector('+selector+')' in hooks,selector
    assert 'dlsym' in hooks and 'MSHookMessageEx' in hooks
    assert not (ROOT/'Vendor/Glassify').exists()
    workflows = ROOT/'.github/workflows'
    if workflows.exists():
        for workflow in workflows.glob('*.y*ml'):
            text = workflow.read_text()
            if re.search(r'(?m)^\s*push\s*:', text) or re.search(r'(?m)^\s*pull_request\s*:', text):
                raise ValueError('Automatic workflow triggers are forbidden: '+rel(workflow))
    return {'status':'passed','counts':counts,'vendor':vendor_manifest(),'preference_keys':sorted(KEYS),
            'sources':{k:[rel(p) for p in v] for k,v in sources.items()},
            'native_build_executed':False,'device_validation_executed':False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = check()
    text = json.dumps(result,indent=2)+'\n'
    if args.output:
        output = Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); output.write_text(text)
    print(text)
