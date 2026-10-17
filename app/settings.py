"""Your settings: the defaults in app/config.py plus any changes saved in data/settings.json.

data/ is git-ignored, so your changes (like pointing BEYOND at Local AI Studio) stay on your PC and a fresh
download always starts from the defaults. Read on every use, so editing the file takes effect at once.
The settings page that writes this file arrives in Phase 4.
"""
import json
import logging

from app import config

FILE = config.DATA_DIR / 'settings.json'


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
        values.update({key: value for key, value in saved.items() if key in config.DEFAULTS})
    return values
