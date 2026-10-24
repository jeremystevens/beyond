"""Build the files a BEYOND release publishes (Phase 45), the same way every time.

    .venv\\Scripts\\python.exe tools\\make_release.py            # the version in app/config.py, from HEAD
    .venv\\Scripts\\python.exe tools\\make_release.py --out D:\\x  # somewhere else (default: dist\\release-<version>)

Writes, from the committed files at HEAD (never uncommitted changes, data, models or the .venv):
  BEYOND-<version>-source.zip   every tracked file in one BEYOND-<version>/ folder, plus app-files.txt (the list of
                                program files, which the updater uses to remove files a version no longer has).
                                Its VERSION file says <version>.
  Update-Beyond.ps1             the updater (from installer/)
  Update-Beyond.cmd             the double-click launcher for people on 1.0.0
  SHA256SUMS.txt                checksums of the three files above
  artifact.json                 version, commit, size and checksum of the ZIP

Then publish them on GitHub as release v<version>, check every download, and only after that change the VERSION file
on main to <version>: that's the moment BEYOND offers the update to everyone.
"""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = {'Update-Beyond.ps1': 'installer/Update-Beyond.ps1', 'Update-Beyond.cmd': 'Update-Beyond.cmd'}


def git(*args, binary=False):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True)
    return result.stdout if binary else result.stdout.decode('utf-8').strip()


def committed_version():
    text = git('show', 'HEAD:app/config.py')
    match = re.search(r"^VERSION = '([^']+)'", text, re.M)
    if not match:
        sys.exit("Couldn't find VERSION in app/config.py at HEAD.")
    return match.group(1)


def build(version, out):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        sys.exit(f'{version!r} is not a version number like 1.1.0.')
    if version != committed_version():
        sys.exit(f'app/config.py at HEAD says {committed_version()}, not {version}. Commit the version change first.')
    if git('status', '--porcelain', '--untracked-files=no'):
        print('Note: there are uncommitted changes. They are NOT included; the release uses HEAD only.')
    out.mkdir(parents=True, exist_ok=True)
    commit = git('rev-parse', 'HEAD')
    prefix = f'BEYOND-{version}/'
    with tarfile.open(fileobj=io.BytesIO(git('archive', '--format=tar', 'HEAD', binary=True))) as tar:
        contents = {member.name: tar.extractfile(member).read() for member in tar.getmembers() if member.isfile()}
    files = sorted(contents)
    files_list = sorted(set(files) | {'app-files.txt'})

    zip_name = f'BEYOND-{version}-source.zip'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            data = version.encode() + b'\n' if name == 'VERSION' else contents[name]
            archive.writestr(prefix + name, data)
        archive.writestr(prefix + 'app-files.txt', '\n'.join(files_list) + '\n')
    (out / zip_name).write_bytes(buffer.getvalue())

    for asset, source in ASSETS.items():
        if source not in contents:
            sys.exit(f'{source} is not committed, so it cannot be published. Commit it first.')
        (out / asset).write_bytes(contents[source])

    sums = {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in (zip_name, *ASSETS)}
    (out / 'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name, digest in sums.items()),
                                        encoding='ascii', newline='\n')
    artifact = {'version': version, 'commit': commit, 'artifact': zip_name, 'sha256': sums[zip_name],
                'bytes': (out / zip_name).stat().st_size, 'entries': len(files_list),
                'scope': 'source only; dependencies and weights download separately',
                'updater': {'file': 'Update-Beyond.ps1', 'sha256': sums['Update-Beyond.ps1']}}
    (out / 'artifact.json').write_text(json.dumps(artifact, indent=2) + '\n', encoding='utf-8')
    return artifact


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--version', help='defaults to the version in app/config.py at HEAD')
    parser.add_argument('--out', type=Path, help='defaults to dist/release-<version>')
    args = parser.parse_args(argv)
    version = args.version or committed_version()
    out = args.out or ROOT / 'dist' / f'release-{version}'
    artifact = build(version, out)
    print(f"Built BEYOND {version} from {artifact['commit'][:7]} in {out}:")
    for path in sorted(out.iterdir()):
        print(f'  {path.name}  ({path.stat().st_size:,} bytes)')
    print(f'\nNext: publish these as release v{version}, check every download link and checksum, and only then '
          f'set VERSION on main to {version}.')


if __name__ == '__main__':
    main()
