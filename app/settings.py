"""Your settings: the defaults in app/config.py plus any changes saved in data/settings.json.

data/ is git-ignored, so your changes (like pointing BEYOND at Local AI Studio) stay on your PC and a fresh
download always starts from the defaults. The file only stores what differs from the defaults, so deleting it
(or "Reset to defaults" on the settings page) brings every default back. Read on every use, so a change to the
AI server takes effect at once; the port and network switch take effect after a restart.
"""
import json
import logging
from urllib.parse import urlparse

from app import config

FILE = config.DATA_DIR / 'settings.json'


class SettingsError(ValueError):
    """A setting that can't be saved, explained in plain words."""


def load():
    values = dict(config.DEFAULTS)
    try:
        saved = json.loads(FILE.read_text(encoding='utf-8-sig'))   # -sig: also accept files saved by Notepad
    except FileNotFoundError:
        return values
    except (OSError, ValueError):
        logging.warning('Could not read %s; using the default settings', FILE)
        return values
    if isinstance(saved, dict):
        try:
            values.update(validate({key: value for key, value in saved.items() if key in config.DEFAULTS}))
        except SettingsError as exc:
            logging.warning('Ignoring %s: %s', FILE, exc)
    return values


def validate(changes):
    """Check and tidy the given settings. Returns the cleaned values; raises SettingsError if one is wrong."""
    clean = {}
    for key, value in changes.items():
        if key not in config.DEFAULTS:
            raise SettingsError(f'Unknown setting: {key}')
        if key == 'ai_server_url':
            value = str(value or '').strip().rstrip('/')
            if value:
                if '://' not in value:
                    value = 'http://' + value
                parsed = urlparse(value)
                if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                    raise SettingsError('The AI server address should look like http://127.0.0.1:10086')
        elif key == 'ai_model':
            value = str(value or '').strip()
            if len(value) > 200:
                raise SettingsError('The model name is too long.')
        elif key == 'web_port':
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise SettingsError('The port must be a whole number.') from exc
            if not config.MIN_PORT <= value <= config.MAX_PORT:
                raise SettingsError(f'The port must be between {config.MIN_PORT} and {config.MAX_PORT}.')
            if value in config.RESERVED_PORTS:
                raise SettingsError(f'Port {value} is used by {config.RESERVED_PORTS[value]}. Please pick another.')
        elif key in config.BOOLEAN_SETTINGS:
            if not isinstance(value, bool):
                raise SettingsError(f'{key} must be on or off.')
        clean[key] = value
    return clean


def save(changes):
    """Apply changes and save only what differs from the defaults. Returns all the settings now in effect."""
    values = {**load(), **validate(changes)}
    different = {key: value for key, value in values.items() if value != config.DEFAULTS[key]}
    if different:
        config.DATA_DIR.mkdir(exist_ok=True)
        temp = FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(different, indent=2) + '\n', encoding='utf-8')
        temp.replace(FILE)
    else:
        FILE.unlink(missing_ok=True)
    return values


def reset():
    """Back to the fresh-install defaults."""
    FILE.unlink(missing_ok=True)
    return dict(config.DEFAULTS)
