"""Local chat-model catalogue and profiles. Model weights are never copied, downloaded or deleted here."""
import hashlib
import logging
import os
import re
from pathlib import Path

from app import builtin_engine, config, settings

SPLIT = re.compile(r'^(.*-)(\d{5})-of-(\d{5})(\.gguf)$', re.I)


class ModelError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def initialize():
    config.MODELS_DIR.mkdir(exist_ok=True)
    # Remember an existing Phase 33 model without copying gigabytes into a second folder.
    if settings.load()['engine_model']:
        settings.save({})


def _key(path):
    return os.path.normcase(settings.model_path(path))


def model_id(path):
    return hashlib.sha256(_key(path).encode('utf-8')).hexdigest()[:24]


def profile(path, values):
    defaults = {key: config.DEFAULTS[key] for key in settings.PROFILE_KEYS}
    if values['engine_model'] and _key(path) == _key(values['engine_model']):
        return {key: values[key] for key in settings.PROFILE_KEYS}
    return {**defaults, **values['model_profiles'].get(settings.model_path(path), {})}


def _entry(path, values):
    path = Path(settings.model_path(path))
    parts, problem = [path], ''
    split = SPLIT.match(path.name)
    if split:
        if int(split[2]) != 1:
            return None
        count = int(split[3])
        if not 1 <= count <= 999:
            return None
        parts = [path.with_name(f'{split[1]}{i:05d}-of-{count:05d}{split[4]}') for i in range(1, count + 1)]
    size = 0
    for part in parts:
        try:
            size += part.stat().st_size
        except OSError:
            problem = 'File not found.' if len(parts) == 1 else 'One or more split-model parts are missing.'
    try:
        location = str(path.relative_to(config.MODELS_DIR.resolve()))
        origin = 'Models folder'
    except ValueError:
        location, origin = str(path), 'Added from this PC'
    return {'id': model_id(path), 'name': path.name, 'location': location, 'origin': origin,
            'bytes': size, 'parts': len(parts), 'available': not problem, 'problem': problem,
            'settings': profile(path, values), '_path': str(path)}


def catalogue(values=None):
    values = values or settings.load()
    paths = dict.fromkeys(values['model_profiles'])
    if values['engine_model']:
        paths[values['engine_model']] = None
    # No symlink traversal: a folder shortcut must not turn this into a scan of another drive.
    if config.MODELS_DIR.is_dir():
        base = config.MODELS_DIR.resolve()
        for folder, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if not Path(folder, d).is_symlink()]
            for name in files:
                p = Path(folder, name)
                if p.suffix.lower() == '.gguf' and p.resolve().is_relative_to(base):
                    paths[str(p)] = None
    entries = {}
    for path in paths:
        if any(word in Path(path).name.lower() for word in ('mmproj', 'projector')):
            continue
        entry = _entry(path, values)
        if entry:
            entries[entry['id']] = entry
    return sorted(entries.values(), key=lambda e: (e['name'].casefold(), e['location'].casefold()))


def _find(identifier, values):
    for entry in catalogue(values):
        if entry['id'] == identifier:
            return entry
    raise ModelError('That model is no longer in the list. Refresh and choose it again.', 404)


def view():
    values = settings.load()
    state = builtin_engine.status()
    selected = model_id(values['engine_model']) if values['engine_model'] else None
    active = None
    running = builtin_engine._engine
    if running.state == 'ready' and running.wanted and len(running.wanted) == len(builtin_engine.SETTING_KEYS):
        active = model_id(running.wanted[1])
    entries = catalogue(values)
    for entry in entries:
        entry.pop('_path', None)
    return {'models': entries, 'folder': str(config.MODELS_DIR), 'mode': values['ai_mode'],
            'enabled': values['engine_enabled'], 'selected': selected, 'active': active,
            'engine': state, 'busy': builtin_engine.busy(),
            'engine_configured': Path(values['engine_executable']).is_file() if values['engine_executable'] else False}


def _idle():
    if builtin_engine.busy():
        raise ModelError('The AI is answering. Wait for it to finish, or press Stop in chat, then try again.', 409)


def load(identifier):
    with builtin_engine.control_lock:
        _idle()
        values = settings.load()
        entry = _find(identifier, values)
        if not entry['available']:
            raise ModelError(entry['problem'], 404)
        changes = {'ai_mode': 'builtin', 'engine_enabled': True, 'engine_model': entry['_path'],
                   **entry['settings']}
        problem = builtin_engine.missing({**values, **changes})
        if problem:
            raise ModelError(problem)
        same = (values['ai_mode'] == 'builtin' and values['engine_enabled']
                and values['engine_model'] and _key(values['engine_model']) == _key(entry['_path']))
        settings.save(changes)
        if same and builtin_engine._engine.state in ('error', 'not_set', 'off'):
            builtin_engine.request_restart()
        logging.info('Models: selected %s', entry['name'])
    return view()


def unload():
    with builtin_engine.control_lock:
        _idle()
        settings.save({'engine_enabled': False})
        logging.info('Models: unloaded the built-in model')
    return view()


def save_profile(identifier, changes):
    if set(changes) - set(settings.PROFILE_KEYS):
        raise ModelError('Only this model’s threads, context, cache and thinking settings can be changed here.')
    try:
        cleaned = settings.validate(changes)
    except settings.SettingsError as exc:
        raise ModelError(str(exc)) from exc
    with builtin_engine.control_lock:
        values = settings.load()
        entry = _find(identifier, values)
        current = bool(values['engine_model'] and _key(entry['_path']) == _key(values['engine_model']))
        new = {**entry['settings'], **cleaned}
        changed = new != entry['settings']
        if current and values['ai_mode'] == 'builtin' and values['engine_enabled'] and changed:
            _idle()
        profiles = dict(values['model_profiles'])
        profiles[entry['_path']] = new
        settings.save({'model_profiles': profiles, **(new if current else {})})
        logging.info('Models: saved settings for %s', entry['name'])
    return view()


def register(path):
    # Only the existing local-PC settings permission allows registering arbitrary host file paths.
    with builtin_engine.control_lock:
        path = settings.validate({'engine_model': path})['engine_model']
        if not path or not Path(path).is_file():
            raise ModelError('Choose an existing .gguf model on this PC.')
        if any(word in Path(path).name.lower() for word in ('mmproj', 'projector')):
            raise ModelError('Choose a chat model, rather than a vision projector.')
        if SPLIT.match(Path(path).name) and SPLIT.match(Path(path).name)[2] != '00001':
            raise ModelError('For a split model, choose its first part (00001).')
        values = settings.load()
        profiles = dict(values['model_profiles'])
        profiles.setdefault(settings.model_path(path), profile(path, values))
        settings.save({'model_profiles': profiles})
    return view()
