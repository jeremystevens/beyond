"""/writefile: create a new text or code file from chat, ported from PromptetheusBot's file_writer.py.

Files go into BEYOND's own files/ folder (git-ignored), never anywhere else: a plain filename with an extension,
no folders or paths, no Windows device names. An existing file is never overwritten, nothing written is ever run,
and a file is at most 64 KB. Each file can be downloaded from the chat. Only this PC, or a device signed in as
administrator, can write, list or download files.
"""
import re
import threading
import time
from pathlib import Path

from app import config

MAX_BYTES = 64 * 1024
WAIT_SECONDS = 600            # how long /writefile <name> waits for the contents in the next message
RESERVED = re.compile(r'^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])$', re.I)
NAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9 _.-]{0,119}')

_pending = {}                 # chat id -> (filename, waiting until)
_lock = threading.Lock()


class FileWriteError(ValueError):
    pass


def folder():
    return config.ROOT / 'files'


def target_path(filename):
    if (not isinstance(filename, str) or not NAME.fullmatch(filename) or filename.endswith((' ', '.'))
            or RESERVED.fullmatch(filename.split('.')[0].rstrip(' .'))):
        raise FileWriteError('Use a plain filename with an extension, such as hello.py. Folders and paths are not allowed.')
    if not re.fullmatch(r'\.[A-Za-z0-9]{1,16}', Path(filename).suffix):
        raise FileWriteError('Include a file extension, such as .py, .txt, .md, .json or .html.')
    root = folder().resolve()
    target = root / filename
    if target.parent != root:
        raise FileWriteError('Files must stay directly in the files folder.')
    return target


def check_filename(filename):
    target = target_path(filename)
    if target.exists() or target.is_symlink():
        raise FileWriteError(f'{filename} already exists. Choose a new filename; existing files are never overwritten.')
    return target


def create_file(filename, content):
    target = target_path(filename)
    if not isinstance(content, str) or not content.strip():
        raise FileWriteError('Send the text or code to put in the file.')
    if not content.endswith('\n'):
        content += '\n'
    data = content.encode('utf-8')
    if len(data) > MAX_BYTES:
        raise FileWriteError('The file is too large for this command (64 KB maximum).')
    folder().mkdir(exist_ok=True)
    try:
        # Exclusive creation also blocks symlinks and files created after the filename check.
        with target.open('xb') as stream:
            try:
                stream.write(data)
            except OSError:
                stream.close()
                target.unlink(missing_ok=True)
                raise
    except FileExistsError:
        raise FileWriteError(f'{filename} already exists. Choose a new filename; existing files are never overwritten.') from None
    return target, len(data)


def parse(args):
    """'/writefile name.ext' then, optionally, the contents on the following lines -> (filename, contents or '')."""
    header, _, body = args.partition('\n')
    filename = header.strip().strip('"\'')
    if not filename:
        raise FileWriteError('Use /writefile filename.py, then the file contents on the next lines (or in your next message).')
    return filename, body


# ---------- waiting for the contents in the next message ----------

def wait_for(chat_id, filename):
    with _lock:
        _pending[chat_id] = (filename, time.monotonic() + WAIT_SECONDS)


def waiting(chat_id):
    """The filename this chat is waiting to write, or None."""
    with _lock:
        item = _pending.get(chat_id)
        if item and item[1] < time.monotonic():
            del _pending[chat_id]
            item = None
        return item[0] if item else None


def cancel(chat_id):
    with _lock:
        return _pending.pop(chat_id, (None,))[0]


def take(chat_id):
    with _lock:
        return _pending.pop(chat_id, (None,))[0]


# ---------- editing an existing file (with a backup for Undo) ----------

def versions_folder():
    return folder() / '.versions'


def read(filename):
    """An existing file's text, for editing."""
    target = target_path(filename)
    if not target.is_file() or target.is_symlink():
        raise FileWriteError(f"There's no {filename} in the files folder. /files lists what's there.")
    data = target.read_bytes()
    if len(data) > MAX_BYTES:
        raise FileWriteError(f'{filename} is too large to edit here (64 KB maximum).')
    try:
        # Windows line endings (from Notepad, say) are read as plain ones, so they don't all look changed.
        return data.decode('utf-8').replace('\r\n', '\n')
    except UnicodeDecodeError:
        raise FileWriteError(f"{filename} isn't a text file, so it can't be edited here.") from None


def save_edit(filename, content, original):
    """Replace an existing file with its edited version, keeping the old one for Undo. Refuses if the file changed
    since the edit started."""
    target = target_path(filename)
    if read(filename) != original:
        raise FileWriteError(f'{filename} was changed by something else since this edit started. Ask for the edit again.')
    if not content.endswith('\n'):
        content += '\n'
    content = content.replace('\r\n', '\n')
    if b'\r\n' in target.read_bytes():   # keep the file's own (Windows) line endings
        content = content.replace('\n', '\r\n')
    data = content.encode('utf-8')
    if len(data) > MAX_BYTES:
        raise FileWriteError('The edited file is too large (64 KB maximum).')
    versions_folder().mkdir(parents=True, exist_ok=True)
    backup = versions_folder() / f'{filename}.{time.time_ns():020d}'   # sorts in the order they were saved
    backup.write_bytes(target.read_bytes())
    temp = target.with_name(target.name + '.saving')
    temp.write_bytes(data)
    temp.replace(target)
    return target, len(data)


def undo(filename):
    """Put back the version from before the last edit (and forget that backup). Returns the file."""
    target = target_path(filename)
    own = re.compile(re.escape(filename) + r'\.\d{20}')   # only this file's backups, oldest first
    backups = sorted(p for p in versions_folder().iterdir() if own.fullmatch(p.name)) if versions_folder().is_dir() else []
    if not backups:
        raise FileWriteError(f'There is no earlier version of {filename} to go back to.')
    latest = backups[-1]
    temp = target.with_name(target.name + '.saving')
    temp.write_bytes(latest.read_bytes())
    temp.replace(target)
    latest.unlink()
    return target


# ---------- listing ----------

def listing():
    """The files written so far, newest first: [{'name', 'bytes', 'modified'}]."""
    if not folder().is_dir():
        return []
    items = [p for p in folder().iterdir() if p.is_file() and not p.is_symlink()]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{'name': p.name, 'bytes': p.stat().st_size, 'modified': p.stat().st_mtime} for p in items]


def download_path(filename):
    """The file to send for a download, or None (only plain names directly in the files folder)."""
    try:
        target = target_path(filename)
    except FileWriteError:
        return None
    return target if target.is_file() and not target.is_symlink() else None
