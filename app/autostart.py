"""Start BEYOND when you sign in to Windows (the "Start with Windows" setting).

It adds (or removes) one entry under your Windows user's startup programs:
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run, value "BEYOND", which runs BEYOND with pythonw.exe (no
console window), so it starts in the tray. Only changed when you switch the setting on the Settings page.
"""
import sys

from app import config

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME = 'BEYOND'


def command():
    """pythonw.exe next to the running python.exe (the project's .venv), and beyond.py."""
    python = config.ROOT / '.venv' / 'Scripts' / 'pythonw.exe'
    if not python.exists():
        python = sys.executable.replace('python.exe', 'pythonw.exe')
    return f'"{python}" "{config.ROOT / "beyond.py"}"'


def is_on():
    if sys.platform != 'win32':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, NAME)[0])
    except OSError:
        return False


def apply(on):
    """Add or remove the startup entry. Returns '' or a problem in plain words."""
    if sys.platform != 'win32':
        return 'Starting with Windows only works on Windows.'
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(key, NAME)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        return f'Windows did not allow changing the startup programs ({exc.strerror or exc}).'
    return ''
