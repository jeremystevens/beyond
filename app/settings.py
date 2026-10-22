"""Your settings: the defaults in app/config.py plus any changes saved in data/settings.json.

data/ is git-ignored, so your changes (like pointing BEYOND at Local AI Studio) stay on your PC and a fresh
download always starts from the defaults. The file only stores what differs from the defaults, so deleting it
(or "Reset to defaults" on the settings page) brings every default back. Read on every use, so a change to the
AI server takes effect at once; the port and network switch take effect after a restart.
"""
import json
import logging
import math
import re
import threading
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from app import config, personas, prompts

FILE = config.DATA_DIR / 'settings.json'
PROFILE_KEYS = ('engine_threads', 'engine_context', 'engine_cache', 'engine_thinking')
_lock = threading.RLock()


def _locked(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with _lock:
            return function(*args, **kwargs)
    return wrapped


def model_path(path):
    return str(Path(path).resolve())



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
        if 'ai_mode' not in saved and saved.get('ai_server_url'):
            saved['ai_mode'] = 'server'   # set up before the built-in engine existed: keep using that AI server
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
        if key == 'persona':
            if not isinstance(value, str) or value not in personas.PERSONAS:
                raise SettingsError('Choose Normal, Professional, Sarcastic, Evil or Funny.')
        elif key == 'custom_prompt':
            if not isinstance(value,str) or len(value)>prompts.MAX_CUSTOM_CHARS:
                raise SettingsError(f'The custom prompt must be text under {prompts.MAX_CUSTOM_CHARS:,} characters.')
            value=value.strip()
        elif key == 'ai_server_url':
            value = str(value or '').strip().rstrip('/')
            if value:
                if '://' not in value:
                    value = 'http://' + value
                parsed = urlparse(value)
                if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                    raise SettingsError('The AI server address should look like http://127.0.0.1:10086')
        elif key == 'model_profiles':
            if not isinstance(value, dict) or len(value) > 1000:
                raise SettingsError('The saved model list is invalid.')
            profiles = {}
            for path, profile in value.items():
                if not isinstance(path, str) or not path.lower().endswith('.gguf') or len(path) > 1024:
                    raise SettingsError('Saved models must be .gguf file paths.')
                if not isinstance(profile, dict) or set(profile) - set(PROFILE_KEYS):
                    raise SettingsError('The saved model settings are invalid.')
                profiles[model_path(path)] = validate(profile)
            value = profiles
        elif key == 'ai_mode':
            if value not in ('builtin', 'server'):
                raise SettingsError('Choose the built-in engine or an AI server.')
        elif key in ('whisper_model_dir', 'ocr_model_dir'):
            if not isinstance(value, str) or len(value) > 1024:
                raise SettingsError('Optional model folders must be file-system paths.')
            value = value.strip().strip('"')
        elif key == 'whisper_threads':
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 16:
                raise SettingsError('Whisper threads must be a whole number between 1 and 16.')
        elif key in ('engine_executable', 'engine_model'):
            if not isinstance(value, str):
                raise SettingsError('AI engine file paths must be text.')
            value = value.strip().strip('"')
            suffix = '.exe' if key == 'engine_executable' else '.gguf'
            if value and (len(value) > 1024 or not value.lower().endswith(suffix)):
                raise SettingsError('Choose llama-server.exe for the engine program.' if suffix == '.exe'
                                    else 'The AI model must be a .gguf file.')
        elif key in ('engine_threads', 'engine_context'):
            low, high = (1, 64) if key == 'engine_threads' else (1024, 131072)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise SettingsError(f'{key} must be a whole number between {low} and {high}.')
        elif key == 'engine_cache':
            if value not in ('f16', 'q8_0', 'q4_0'):
                raise SettingsError('The engine cache must be f16, q8_0 or q4_0.')
        elif key == 'ai_model':
            value = str(value or '').strip()
            if len(value) > 200:
                raise SettingsError('The model name is too long.')
        elif key in ('vision_executable', 'vision_model', 'vision_mmproj'):
            if not isinstance(value, str):
                raise SettingsError('Vision file paths must be text.')
            value = value.strip().strip('"')
            suffix = '.exe' if key == 'vision_executable' else '.gguf'
            if value and (len(value) > 1024 or not value.lower().endswith(suffix)):
                raise SettingsError(f'{key} must be a {suffix} file path.')
        elif key in ('image_executable', 'image_model'):
            if not isinstance(value, str):
                raise SettingsError('Picture file paths must be text.')
            value = value.strip().strip('"')
            suffix = '.exe' if key == 'image_executable' else '.safetensors'
            if value and (len(value) > 1024 or not value.lower().endswith(suffix)):
                raise SettingsError(f'{key} must be a {suffix} file path.')
        elif key in ('image_threads', 'image_timeout'):
            low, high = (1, 64) if key == 'image_threads' else (60, 3600)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise SettingsError(f'{key} must be a whole number between {low} and {high}.')
        elif key in ('vision_threads', 'vision_timeout'):
            low, high = (1, 64) if key == 'vision_threads' else (30, 3600)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise SettingsError(f'{key} must be a whole number between {low} and {high}.')
        elif key in ('speech_kokoro_model', 'speech_piper_model', 'speech_kokoro_voices'):
            if not isinstance(value, str):
                raise SettingsError('Speech file paths must be text.')
            value = value.strip().strip('"')
            suffixes = ('.bin', '.npz') if key == 'speech_kokoro_voices' else ('.onnx',)
            if value and (len(value) > 1024 or not value.lower().endswith(suffixes)):
                raise SettingsError('Choose the matching speech model or voice-pack file.')
        elif key == 'speech_engine':
            if value not in ('kokoro', 'piper'):
                raise SettingsError('Choose Kokoro or Piper for spoken replies.')
        elif key == 'speech_voice':
            if not isinstance(value, str) or not re.fullmatch(r'[a-z]{2}_[a-z]{2,20}', value):
                raise SettingsError('The Kokoro voice should look like af_heart.')
        elif key == 'speech_speed':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not .5 <= value <= 2:
                raise SettingsError('Speech speed must be a number between 0.5 and 2.0.')
            value = round(value, 2)
        elif key in ('speech_threads', 'speech_timeout'):
            low, high = (1, 16) if key == 'speech_threads' else (15, 600)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise SettingsError(f'{key} must be a whole number between {low} and {high}.')
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
        elif key in config.TIME_SETTINGS:
            value = str(value or '').strip()
            if value:
                match = re.fullmatch(r'(\d{1,2}):(\d{2})', value)
                if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
                    raise SettingsError('Quiet hours are times like 22:00 and 07:30 (24-hour clock).')
                value = f'{int(match.group(1)):02d}:{match.group(2)}'
        clean[key] = value
    return clean


@_locked
def save(changes):
    """Apply changes and save only what differs from the defaults. Returns all the settings now in effect."""
    values = {**load(), **validate(changes)}
    if values['custom_prompt_enabled'] and not values['custom_prompt'].strip():
        raise SettingsError('Enter a custom prompt, or turn off Use my own prompt.')
    # Settings and the Models page share one atomic file. Editing either saves the active model's profile.
    if values['engine_model']:
        profiles = dict(values['model_profiles'])
        profiles[model_path(values['engine_model'])] = {key: values[key] for key in PROFILE_KEYS}
        values['model_profiles'] = profiles
    different = {key: value for key, value in values.items() if value != config.DEFAULTS[key]}
    if values['ai_server_url']:   # always saved with an address, so load() can't mistake it for an older setup
        different['ai_mode'] = values['ai_mode']
    if different:
        config.DATA_DIR.mkdir(exist_ok=True)
        temp = FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(different, indent=2) + '\n', encoding='utf-8')
        temp.replace(FILE)
    else:
        FILE.unlink(missing_ok=True)
    return values


@_locked
def reset():
    """Back to the fresh-install defaults."""
    FILE.unlink(missing_ok=True)
    return dict(config.DEFAULTS)
