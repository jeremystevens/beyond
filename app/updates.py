"""Easy updates (Phase 45): is a newer BEYOND out, and if so, update to it with one click.

The check reads the VERSION file on GitHub and compares it with the version running here, as version numbers
(1.10.0 is newer than 1.9.0). VERSION only changes once a release is fully published, so ordinary commits never
offer an update. Checking is off by default: it runs when someone presses Check for updates, or once a day if
"Check automatically" is on. A failed check is recorded and never gets in the way of anything else.

Updating is always started by a person (this PC or an administrator). BEYOND downloads the release's
Update-Beyond.ps1, checks it against the release's SHA256SUMS.txt (and GitHub's own digest), starts it as a
separate process and then closes itself. The updater does the rest; see installer/Update-Beyond.ps1. Copies set
up with git are never updated this way: they get a message to run git pull.
"""
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from app import config, settings

REPO = 'jeremystevens/beyond'
VERSION_URL = f'https://raw.githubusercontent.com/{REPO}/main/VERSION'
RELEASE_FILE_URL = f'https://github.com/{REPO}/releases/download/v{{version}}/{{name}}'
RELEASE_API_URL = f'https://api.github.com/repos/{REPO}/releases/tags/v{{version}}'
RELEASE_PAGE_URL = f'https://github.com/{REPO}/releases/tag/v{{version}}'
UPDATER = 'Update-Beyond.ps1'
CHECK_EVERY_SECONDS = 24 * 3600
TIMEOUT = httpx.Timeout(15, connect=10)
NOTES_CHARS = 4000
_VERSION = re.compile(r'v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})')
_lock = threading.Lock()
_installing = threading.Event()

# Set by app/server.py: closes BEYOND once the updater is running, so it can replace the program files.
request_quit = None


class UpdateError(Exception):
    """Something stopped a check or an update, explained in plain words."""


def parse_version(text):
    """'1.10.0' -> (1, 10, 0). Raises ValueError for anything that isn't a plain three-part version number."""
    match = _VERSION.fullmatch(str(text).strip())
    if not match:
        raise ValueError(f'Not a version number: {str(text)[:40]!r}')
    return tuple(int(part) for part in match.groups())


def is_newer(latest, installed):
    return parse_version(latest) > parse_version(installed)


def folder():
    return config.DATA_DIR / 'updates'


def status_file():
    return folder() / 'status.json'


def is_git_checkout():
    return (config.ROOT / '.git').exists()


def _read_status():
    try:
        saved = json.loads(status_file().read_text(encoding='utf-8'))
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_status(values):
    folder().mkdir(parents=True, exist_ok=True)
    temp = status_file().with_suffix('.tmp')
    temp.write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
    temp.replace(status_file())


def status():
    """What the Updates section shows. 'available' is worked out again here, so it's right after an update too."""
    saved = _read_status()
    latest = saved.get('latest', '')
    try:
        available = bool(latest) and is_newer(latest, config.VERSION)
    except ValueError:
        available = False
    return {
        'installed': config.VERSION,
        'latest': latest,
        'available': available,
        'checked_at': saved.get('checked_at', 0),
        'error': saved.get('error', ''),
        'notes': saved.get('notes', '') if available else '',
        'notes_url': RELEASE_PAGE_URL.format(version=latest) if available else '',
        'auto': settings.load()['update_auto_check'],
        'git': is_git_checkout(),
        'installing': _installing.is_set(),
    }


def _release_notes(client, version):
    """The release's notes from GitHub, shortened; '' if they can't be fetched (the check still counts)."""
    try:
        response = client.get(RELEASE_API_URL.format(version=version), headers={'Accept': 'application/vnd.github+json'})
        response.raise_for_status()
        notes = str(response.json().get('body') or '').strip()
    except (httpx.HTTPError, ValueError):
        return ''
    return notes if len(notes) <= NOTES_CHARS else notes[:NOTES_CHARS].rsplit('\n', 1)[0] + '\n…'


def check():
    """Ask GitHub for the published version now. Returns status(); a failure is recorded in it, never raised."""
    with _lock:
        saved = _read_status()
        saved['checked_at'] = time.time()
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
                response = client.get(VERSION_URL, headers={'Cache-Control': 'no-cache'})
                response.raise_for_status()
                latest = response.text.strip()
                parse_version(latest)
                notes = ''
                if is_newer(latest, config.VERSION) and saved.get('notes_for') != latest:
                    notes = _release_notes(client, latest)
            saved.update(latest=latest, error='')
            if notes:
                saved.update(notes=notes, notes_for=latest)
        except httpx.HTTPError as exc:
            logging.info('Update check failed: %s', exc)
            saved['error'] = "Couldn't reach GitHub. Check the internet connection and try again."
        except ValueError:
            saved['error'] = "GitHub's version file couldn't be read. Try again later."
        _write_status(saved)
    return status()


def due():
    """True when "Check automatically" is on and the last check was a day or more ago."""
    if not settings.load()['update_auto_check']:
        return False
    return time.time() - float(_read_status().get('checked_at') or 0) >= CHECK_EVERY_SECONDS


def mark_announced(version):
    """The tray popup for this version was shown (Yes or No), so it isn't shown again."""
    with _lock:
        saved = _read_status()
        saved['announced'] = version
        _write_status(saved)


def needs_announcing():
    """The version to announce with a tray popup, or '' (none available, or already announced)."""
    current = status()
    if current['available'] and not current['git'] and _read_status().get('announced') != current['latest']:
        return current['latest']
    return ''


def _download(client, version, name, target, limit):
    response = client.get(RELEASE_FILE_URL.format(version=version, name=name))
    response.raise_for_status()
    if len(response.content) > limit:
        raise UpdateError(f'{name} is larger than expected, so it was not used.')
    target.write_bytes(response.content)
    return response.content


def _published_digest(client, version, name):
    """The SHA-256 GitHub reports for a release file, or '' if GitHub doesn't say (older releases)."""
    try:
        response = client.get(RELEASE_API_URL.format(version=version), headers={'Accept': 'application/vnd.github+json'})
        response.raise_for_status()
        for asset in response.json().get('assets', []):
            if asset.get('name') == name and str(asset.get('digest', '')).startswith('sha256:'):
                return asset['digest'].split(':', 1)[1].lower()
    except (httpx.HTTPError, ValueError, AttributeError):
        pass
    return ''


def fetch_updater(version):
    """Download Update-Beyond.ps1 for this release and check it. Returns its path; raises UpdateError."""
    target_folder = folder() / f'updater-{version}'
    target_folder.mkdir(parents=True, exist_ok=True)
    script = target_folder / UPDATER
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            sums = _download(client, version, 'SHA256SUMS.txt', target_folder / 'SHA256SUMS.txt', 64 * 1024)
            content = _download(client, version, UPDATER, script, 2 * 1024 * 1024)
            published = _published_digest(client, version, UPDATER)
    except httpx.HTTPError as exc:
        raise UpdateError(f"Couldn't download the updater for {version}. Check the internet connection and "
                          'try again.') from exc
    expected = ''
    for line in sums.decode('utf-8', 'replace').splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == UPDATER:
            expected = parts[0].lower()
    actual = hashlib.sha256(content).hexdigest()
    if not expected or actual != expected or (published and actual != published):
        script.unlink(missing_ok=True)
        raise UpdateError("The downloaded updater didn't match the release's checksum, so it was not run.")
    return script


def start(version, port):
    """Download and check the updater, start it, then close BEYOND. Raises UpdateError if it can't start."""
    if is_git_checkout():
        raise UpdateError('This copy of BEYOND was set up with git. Run "git pull", then restart BEYOND.')
    current = status()
    if not current['available'] or version != current['latest']:
        raise UpdateError('That update is no longer available. Check for updates again.')
    if sys.platform != 'win32':
        raise UpdateError('Updating needs Windows.')
    if _installing.is_set():
        raise UpdateError('An update is already starting.')
    _installing.set()
    try:
        script = fetch_updater(version)
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                   '-InstallDir', str(config.ROOT), '-Version', version, '-WaitPid', str(os.getpid()),
                   '-Port', str(port)]
        subprocess.Popen(command, cwd=str(script.parent), close_fds=True,
                         creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))   # its own progress window
    except (OSError, UpdateError) as exc:
        _installing.clear()
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError("The updater couldn't be started.") from exc
    logging.info('Updating BEYOND from %s to %s: the updater is running; closing BEYOND', config.VERSION, version)
    if request_quit:
        request_quit()


def recent_result():
    """What the updater wrote after the last update ({'from', 'to', 'ok', 'message', 'at'}), or {}."""
    try:
        result = json.loads((folder() / 'last-update.json').read_text(encoding='utf-8-sig'))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}
