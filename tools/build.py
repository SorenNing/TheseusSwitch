#!/usr/bin/env python3
"""Native Xcode-only build, separate real arm64 rootless / arm64e RootHide packages."""
import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import time
from project import ROOT, CONFIG, check, discover, icon_source, rel, sha256, vendor_manifest
import mkdeb
import verify


class Build:
    def __init__(self, variant, smoke=False):
        self.variant = variant
        self.smoke = smoke
        self.sdkname = 'iphonesimulator' if smoke else 'iphoneos'
        self.arch = ('arm64' if platform.machine() == 'arm64' else 'x86_64') if smoke else variant
        self.target = f'{self.arch}-apple-ios{CONFIG["deployment"]}' + ('-simulator' if smoke else '')
        self.out = ROOT / 'build' / ('simulator' if smoke else variant)
        self.obj = self.out / 'obj'
        self.evidence = ROOT / 'evidence' / ('simulator' if smoke else variant)
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.commands = []
        self.started = time.time()
        self.log = (self.evidence / 'build.log').open('w')
        self.sdk = None

    def run(self, cmd, capture=False):
        cmd = [str(x) for x in cmd]
        self.commands.append(cmd)
        self.log.write('$ '+shlex.join(cmd)+'\n'); self.log.flush()
        print('$ '+shlex.join(cmd), flush=True)
        result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.log.write(result.stdout); self.log.flush()
        if not capture or result.returncode:
            print(result.stdout, end='', flush=True)
        if result.returncode:
            raise RuntimeError(f'Command failed ({result.returncode}): {shlex.join(cmd)}\n{result.stdout[-12000:]}')
        return result.stdout

    def tool(self, name):
        return ['xcrun', '--sdk', self.sdkname, name]

    def prepare(self):
        if platform.system() != 'Darwin':
            raise RuntimeError('Native iOS build requires macOS + Xcode; Linux does not substitute for Apple arm64e linker')
        self.run(['xcodebuild', '-version'])
        self.sdk = self.run(['xcrun', '--sdk', self.sdkname, '--show-sdk-path'], True).strip()
        self.swift = Path(self.run(['xcrun', '--find', 'swiftc'], True).strip())
        self.toolchain = self.swift.parents[2]
        self.run([self.swift, '--version'])
        self.run(self.tool('clang')+['--version'])
        if self.out.exists():
            shutil.rmtree(self.out)
        self.obj.mkdir(parents=True)
        result = check()
        (self.evidence / 'source-check.json').write_text(json.dumps(result, indent=2)+'\n')
        self.src = discover()
        self.includes = [ROOT / 'src', self.obj, ROOT / 'packaging/include']
        self.ccbase = ['-target', self.target, '-isysroot', self.sdk, '-O2', '-fblocks', '-fmodules',
                       '-fmodules-cache-path='+str(self.out/'ModuleCache'), '-fPIC']
        for path in self.includes:
            self.ccbase += ['-I', str(path)]
        self.defines = ['-DNG_TESTING=1'] if self.smoke else []
        if not self.smoke and self.variant == 'arm64e':
            self.defines += ['-DTHEOS_PACKAGE_SCHEME_ROOTHIDE=1', '-DNG_ROOTHIDE=1']
        self.frameworks = []
        for name in CONFIG['frameworks']:
            self.frameworks += ['-framework', name]
        self.swift_runtime = self.toolchain / 'usr/lib/swift' / self.sdkname
        self.swift_static = self.toolchain / 'usr/lib/swift_static' / self.sdkname
        self.linkbase = ['-target', self.target, '-isysroot', self.sdk, '-Wl,-undefined,error',
                         '-Wl,-twolevel_namespace', '-L'+str(self.swift_runtime), '-L'+str(self.swift_static),
                         '-L'+str(Path(self.sdk)/'usr/lib/swift'), '-Wl,-rpath,/usr/lib/swift', '-lc++',
                         *self.frameworks]
        if not self.smoke and self.variant == 'arm64e':
            self.linkbase += ['-L'+str(ROOT/'packaging/stubs'), '-Wl,-needed-lroothide']

    def swift_library(self):
        sources = list(self.src['swift'])
        archive = self.obj / 'libTheseusSwitchSwift.a'
        cmd = [self.swift, '-target', self.target, '-sdk', self.sdk, '-swift-version', '5', '-O',
               '-parse-as-library', '-whole-module-optimization', '-module-name', 'TheseusSwitch',
               '-import-objc-header', ROOT/'src/Bridge.h', '-emit-library', '-static',
               '-emit-module', '-emit-module-path', self.obj/'TheseusSwitch.swiftmodule',
               '-emit-objc-header', '-emit-objc-header-path', self.obj/'TheseusSwitch-Swift.h',
               '-module-cache-path', self.out/'ModuleCache', '-Xcc', '-fblocks', '-o', archive]
        for path in self.includes:
            cmd += ['-I', path, '-Xcc', '-I'+str(path)]
        for define in self.defines:
            cmd += ['-Xcc', define]
        if self.smoke:
            cmd += ['-D', 'NG_TESTING']
        cmd += sources
        self.run(cmd)
        self.archive = archive
        # Ask the Swift driver for ABI compatibility and autolink search flags, then use
        # Xcode clang++ for the real final link. Do not guess compatibility archive names.
        dry = [self.swift, '-###', '-emit-library', '-target', self.target, '-sdk', self.sdk,
               '-module-name', 'TheseusSwitch', '-o', self.obj/'swift-link-plan.dylib', archive]
        plan = self.run(dry, True)
        (self.evidence/'swift-link-plan.txt').write_text(plan)
        linker = None
        for line in plan.splitlines():
            try:
                tokens = shlex.split(line)
            except ValueError:
                continue
            if tokens and any(flag in tokens for flag in ('-dylib', '-dynamiclib')):
                name = Path(tokens[0]).name
                if name.startswith(('ld', 'clang')):
                    linker = tokens
        if linker is None:
            raise RuntimeError('Cannot obtain native Swift linker plan from swiftc -###')
        flags = []
        i = 1
        while i < len(linker):
            token = linker[i]
            if token in ('-L', '-F', '-framework', '-weak_framework', '-l') and i+1 < len(linker):
                flags += [token, linker[i+1]]; i += 2; continue
            if token.startswith(('-L', '-F', '-l')) and len(token) > 2 and token not in ('-lazy_library',):
                flags.append(token)
            elif token in ('-force_load', '-weak_library') and i+1 < len(linker):
                flags += ['-Xlinker', token, '-Xlinker', linker[i+1]]; i += 2; continue
            elif token.endswith('.a') and Path(token) != archive:
                flags.append(token)
            i += 1
        self.swift_link = flags
        (self.evidence/'swift-runtime-link-flags.json').write_text(json.dumps(flags, indent=2)+'\n')
        return archive

    def compile(self, sources):
        objects = []
        for source in sources:
            output = self.obj / (re.sub(r'[^A-Za-z0-9_]', '_', rel(source))+'.o')
            cpp = source.suffix in ('.mm', '.cpp', '.cc', '.cxx')
            cmd = self.tool('clang++' if cpp else 'clang')+self.ccbase+self.defines
            if cpp:
                cmd += ['-std=gnu++17', '-stdlib=libc++']
            if source.suffix in ('.m', '.mm'):
                cmd += ['-fobjc-arc']
            cmd += ['-c', source, '-o', output]
            self.run(cmd)
            objects.append(output)
        return objects

    def resources(self, destination):
        destination.mkdir(parents=True, exist_ok=True)
        groups = [(self.src['theseus_metal'], destination, 'com.ning.theseusswitch.resources')]
        for sources, bundle, ident in groups:
            bundle.mkdir(parents=True, exist_ok=True)
            air = []
            for index, source in enumerate(sources):
                output = self.obj / (ident+f'.{index}.air')
                metal_target = ('air64-apple-ios15.0-simulator' if self.smoke else 'air64-apple-ios15.0')
                self.run(self.tool('metal')+['-target', metal_target, '-isysroot', self.sdk, '-std=ios-metal2.4',
                         '-O2', '-I', source.parent, '-c', source, '-o', output])
                air.append(output)
            self.run(self.tool('metallib')+[*air, '-o', bundle/'default.metallib'])
            (bundle/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': ident,
                 'CFBundleName': bundle.stem, 'CFBundlePackageType': 'BNDL', 'CFBundleVersion': CONFIG['version']}))
        return destination

    def core(self):
        self.swift_library()
        objects = self.compile(self.src['core'])
        self.objects = objects
        dylib = self.out/'TheseusSwitch.dylib'
        cmd = self.tool('clang++')+self.linkbase+['-dynamiclib', '-Wl,-install_name,@rpath/TheseusSwitch.dylib',
               '-Xlinker', '-force_load', '-Xlinker', self.archive, *objects, *self.swift_link, '-o', dylib]
        self.run(cmd)
        self.run(['codesign', '--force', '--sign', '-', '--timestamp=none', dylib])
        self.run(['codesign', '--verify', '--strict', '--verbose=4', dylib])
        self.resources(self.out/'TheseusSwitchResources.bundle')
        return dylib

    def preferences(self):
        # The compile SDK stays current Xcode; private-framework link interface may
        # come from original Theos iPhoneOS16.5.sdk or checked-in minimal fallback.
        candidates = []
        if os.environ.get('THEOS'):
            candidates.append(Path(os.environ['THEOS'])/'sdks/iPhoneOS16.5.sdk/System/Library/PrivateFrameworks')
        candidates += [ROOT/'.toolchain/theos-sdks/iPhoneOS16.5.sdk/System/Library/PrivateFrameworks',
                       Path(self.sdk)/'System/Library/PrivateFrameworks', ROOT/'packaging/stubs']
        interface = next((p for p in candidates if (p/'Preferences.framework/Preferences.tbd').is_file()), None)
        if interface is None:
            raise RuntimeError('No explicit Preferences.framework link interface')
        objects = self.compile(self.src['prefs'] + [ROOT/'src/NGResources.m'])
        output = self.out/'TheseusSwitchPrefs'
        self.run(self.tool('clang++')+self.linkbase+['-bundle', '-F'+str(interface),
                 '-framework', 'Preferences', *objects, '-o', output])
        self.run(['codesign', '--force', '--sign', '-', '--timestamp=none', output])
        self.run(['codesign', '--verify', '--strict', '--verbose=4', output])
        (self.evidence/'preferences-interface.json').write_text(json.dumps({'path': str(interface),
                    'sha256': sha256(interface/'Preferences.framework/Preferences.tbd')}, indent=2)+'\n')
        return output

    def package(self, dylib, prefs):
        vendor_manifest()  # Recheck originals immediately before staging.
        stage = self.out/'stage'
        base = stage/CONFIG['variants'][self.variant]['prefix']
        lib = base/'Library/MobileSubstrate/DynamicLibraries'
        pb = base/'Library/PreferenceBundles/TheseusSwitchPrefs.bundle'
        entry = base/'Library/PreferenceLoader/Preferences'
        icons = base/'usr/share/icons'
        resources = base/'Library/Application Support/TheseusSwitch'
        docs = base/'usr/share/doc'/CONFIG['package']
        for p in (lib, pb, entry, icons, resources, docs, stage/'DEBIAN'):
            p.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dylib, lib/'TheseusSwitch.dylib')
        shutil.copy2(ROOT/'src/Filter.plist', lib/'TheseusSwitch.plist')
        shutil.copy2(prefs, pb/'TheseusSwitchPrefs')
        for src in sorted((ROOT/'prefs/Resources').rglob('*')):
            if src.is_file() and src.name != 'entry.plist':
                dest = pb/src.relative_to(ROOT/'prefs/Resources')
                dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest)
        for name in ('icon.png', 'icon@2x.png', 'icon@3x.png'):
            shutil.copy2(icon_source(name), pb/name)
        shutil.copy2(ROOT/'prefs/Resources/entry.plist', entry/'TheseusSwitch.plist')
        shutil.copy2(icon_source('pkgicon.png'), icons/(CONFIG['package']+'.png'))
        shutil.copytree(self.out/'TheseusSwitchResources.bundle', resources/'TheseusSwitchResources.bundle')
        for vendor in ('Theseus',):
            for filename in ('LICENSE', 'LICENSE.md', 'NOTICE', 'UPSTREAM.json'):
                src = ROOT/'Vendor'/vendor/filename
                if src.is_file():
                    shutil.copy2(src, docs/(vendor+'-'+filename))
        shutil.copy2(ROOT/'Vendor/manifest.json', docs/'vendor-manifest.json')
        control = {}
        template = ROOT/'control'
        if template.is_file():
            control.update(dict(line.split(': ', 1) for line in template.read_text().splitlines() if ': ' in line))
        variant = CONFIG['variants'][self.variant]
        control.update({'Package': CONFIG['package'], 'Name': CONFIG['name'], 'Version': CONFIG['version'],
                        'Architecture': variant['architecture'], 'Author': CONFIG['author'],
                        'Maintainer': CONFIG.get('maintainer', 'Ning'), 'Section': 'Tweaks', 'Depends': variant['depends'],
                        'Description': 'Standalone original Theseus switch integration.',
                        'Homepage': CONFIG['repository'], 'Icon': 'file:///'+(variant['prefix']+'/' if variant['prefix'] else '')+
                        'usr/share/icons/'+CONFIG['package']+'.png'})
        (stage/'DEBIAN/control').write_text(''.join(k+': '+v+'\n' for k, v in control.items()))
        shutil.copy2(ROOT/'packaging/postinst', stage/'DEBIAN/postinst')
        for p in stage.rglob('*'):
            p.chmod(0o755 if p.is_dir() else 0o644)
        for p in (lib/'TheseusSwitch.dylib', pb/'TheseusSwitchPrefs', stage/'DEBIAN/postinst'):
            p.chmod(0o755)
        # Seal the assembled preference bundle, including its Info.plist and resources.
        self.run(['codesign', '--force', '--sign', '-', '--timestamp=none', pb])
        self.run(['codesign', '--verify', '--strict', '--verbose=4', pb])
        name = f'{CONFIG["package"]}_{CONFIG["version"]}_{variant["architecture"]}.deb'
        result = mkdeb.build(stage, ROOT/'dist'/name, int(os.environ.get('SOURCE_DATE_EPOCH', '0')))
        output = ROOT/'dist'/name
        metadata = verify.verify(output, self.variant, native=True)
        (self.evidence/'verification.json').write_text(json.dumps(metadata, indent=2)+'\n')
        (ROOT/'dist'/(name+'.metadata.json')).write_text(json.dumps(metadata, indent=2)+'\n')
        (ROOT/'dist'/(name+'.sha256')).write_text(result['sha256']+'  '+name+'\n')
        return result

    def execute(self):
        result = {'status': 'failed', 'variant': self.variant, 'smoke': self.smoke, 'target': self.target}
        try:
            self.prepare()
            core = self.core()
            if self.smoke:
                result.update({'status': 'passed', 'output': str(core), 'NG_TESTING': True,
                               'native_runtime_executed': False})
            else:
                result.update({'status': 'passed', 'package': self.package(core, self.preferences())})
            return result
        except Exception as e:
            result['error'] = str(e)
            raise
        finally:
            result['elapsed_seconds'] = round(time.time()-self.started, 3)
            (self.evidence/'commands.json').write_text(json.dumps(self.commands, indent=2)+'\n')
            (self.evidence/'build-result.json').write_text(json.dumps(result, indent=2)+'\n')
            self.log.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arch', choices=['arm64','arm64e','all'], default='arm64e')
    p.add_argument('--smoke', action='store_true')
    args = p.parse_args()
    variants = ['simulator'] if args.smoke else (['arm64','arm64e'] if args.arch == 'all' else [args.arch])
    failed = False
    for variant in variants:
        try:
            print(json.dumps(Build(variant, args.smoke).execute(), indent=2))
        except Exception as e:
            print(str(e), file=sys.stderr); failed = True
    sys.exit(1 if failed else 0)
