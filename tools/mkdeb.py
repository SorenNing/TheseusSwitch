#!/usr/bin/env python3
"""Deterministic Debian 2.0: pure-Python ar + gzip + USTAR, never macOS ar."""
import argparse
import gzip
import hashlib
import io
import os
from pathlib import Path
import tarfile


def ar_member(name, data, epoch):
    if len(name) > 15:
        raise ValueError('ar member name too long')
    header = f'{name + "/":<16}{epoch:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n'.encode('ascii')
    if len(header) != 60:
        raise ValueError('Invalid ar header')
    return header + data + (b'\n' if len(data) % 2 else b'')


def archive(root, paths, epoch):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for p in paths:
            if p.is_symlink():
                raise ValueError('Package symlinks must be explicitly reviewed: ' + str(p))
            name = './' + p.relative_to(root).as_posix()
            ti = tar.gettarinfo(str(p), arcname=name)
            if not ti.isdir() and not ti.isfile():
                raise ValueError('Unsupported archive file: ' + name)
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = 'root'
            ti.mode = 0o755 if ti.isdir() or (p.stat().st_mode & 0o111) else 0o644
            ti.mtime = epoch
            ti.pax_headers = {}
            if ti.isfile():
                with p.open('rb') as f:
                    tar.addfile(ti, f)
            else:
                tar.addfile(ti)
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='wb', mtime=epoch, filename='') as gz:
        gz.write(data.getvalue())
    return out.getvalue()


def build(stage, output, epoch=0):
    stage, output = Path(stage).resolve(), Path(output).resolve()
    control = stage / 'DEBIAN'
    if not (control / 'control').is_file():
        raise ValueError('DEBIAN/control missing')
    allowed = {'control', 'postinst', 'md5sums', 'conffiles', 'preinst', 'prerm', 'postrm'}
    if any(p.name not in allowed or not p.is_file() for p in control.iterdir()):
        raise ValueError('Unexpected control archive content')
    payload = sorted(p for p in stage.rglob('*') if control not in p.parents and p != control)
    if not any(p.is_file() for p in payload):
        raise ValueError('Empty package payload')
    md5 = ''.join(f'{hashlib.md5(p.read_bytes()).hexdigest()}  {p.relative_to(stage).as_posix()}\n'
                  for p in payload if p.is_file())
    (control / 'md5sums').write_text(md5)
    (control / 'md5sums').chmod(0o644)
    contents = b'!<arch>\n'
    for name, data in [('debian-binary', b'2.0\n'),
                       ('control.tar.gz', archive(control, sorted(control.iterdir()), epoch)),
                       ('data.tar.gz', archive(stage, payload, epoch))]:
        contents += ar_member(name, data, epoch)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_bytes(contents)
    temporary.replace(output)
    return {'file': output.name, 'bytes': len(contents), 'sha256': hashlib.sha256(contents).hexdigest(),
            'format': 'ar/debian2.0+ustar+gzip', 'source_date_epoch': epoch}


if __name__ == '__main__':
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage'); p.add_argument('output')
    p.add_argument('--epoch', type=int, default=int(os.environ.get('SOURCE_DATE_EPOCH', '0')))
    args = p.parse_args()
    print(json.dumps(build(args.stage, args.output, args.epoch), indent=2))
