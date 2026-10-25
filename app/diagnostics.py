"""Read-only health checks and bounded history. Explicit Diagnose requests may ask the loaded AI to explain."""
import asyncio
import json
import logging
import math
import socket
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
import psutil
from fastapi import APIRouter, Path as PathParam, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app import chats, config, settings

router = APIRouter()
_started = time.monotonic()
_running = {}
_handler = None
_test_lock = threading.Lock()
MAX_ERRORS = 200
LOW_MEMORY_BYTES = 1024**3


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def error_file():
    return config.DATA_DIR / 'diagnostics.sqlite3'


def initialize():
    config.DATA_DIR.mkdir(exist_ok=True)
    with closing(sqlite3.connect(error_file(), timeout=2)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS errors (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, '
                   'source TEXT NOT NULL, summary TEXT NOT NULL)')


def record_error(source, summary):
    """Only pass fixed app descriptions here, never prompts, exception messages, URLs or credentials."""
    try:
        initialize()
        with closing(sqlite3.connect(error_file(), timeout=2)) as db, db:
            db.execute('INSERT INTO errors(created_at,source,summary) VALUES (?,?,?)',
                       (now(), source[:60], summary[:250]))
            db.execute('DELETE FROM errors WHERE id NOT IN (SELECT id FROM errors ORDER BY id DESC LIMIT ?)',
                       (MAX_ERRORS,))
    except (OSError, sqlite3.Error):
        pass  # Diagnostics must never cause a second error or recursively log its own failure.


class ErrorHistory(logging.Handler):
    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        try:
            path = Path(record.pathname).resolve()
            root = config.ROOT.resolve()
            if not path.is_relative_to(root):
                return
        except (OSError, ValueError):
            return
        labels = {'server': 'A request or background task failed. Check app and engine status.',
                  'builtin_engine': 'The built-in engine reported an error. Check model files and engine status.',
                  'photo_jobs': 'Photo understanding failed. Check its model and program in Settings.',
                  'image_jobs': 'Picture generation failed. Check its model and program in Settings.',
                  'speech_jobs': 'Speech generation failed. Check its model and voice in Settings.',
                  'beyond': 'BEYOND reported an application error. Check the local app log.'}
        record_error(path.stem, labels.get(path.stem, 'An app operation failed. Check the local app log.'))


def configure(running):
    """Called during this app's lifespan; the dict follows the real bound ports."""
    global _running, _started, _handler
    _running = running
    _started = time.monotonic()
    initialize()
    psutil.cpu_percent(interval=None)
    if _handler is None:
        _handler = ErrorHistory()
        _handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(_handler)


def shutdown():
    global _handler
    if _handler is not None:
        logging.getLogger().removeHandler(_handler)
        _handler = None


def errors(limit=30):
    if not error_file().exists():
        return []
    try:
        with closing(sqlite3.connect(error_file().resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(
                'SELECT id,created_at,source,summary FROM errors ORDER BY id DESC LIMIT ?',
                (max(1, min(int(limit), MAX_ERRORS)),))]
    except (OSError, sqlite3.Error):
        return []


def speed_history(limit=30):
    """Read existing answer stats without exposing chat text, IDs or titles."""
    if not chats.DB_PATH.exists():
        return {'items': [], 'models': []}
    try:
        with closing(sqlite3.connect(chats.DB_PATH.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT created_at, stats FROM messages WHERE role='assistant' AND stats IS NOT NULL "
                              "AND kind IN ('chat','retried') ORDER BY id DESC LIMIT 250").fetchall()
    except (OSError, sqlite3.Error):
        return {'items': [], 'models': []}
    items = []
    for row in rows:
        try:
            value = json.loads(row['stats'])
            if not isinstance(value, dict):
                continue
            numbers = [float(value[k]) for k in ('tokens', 'seconds', 'speed')]
            if not all(math.isfinite(x) and x >= 0 for x in numbers):
                continue
            items.append({'at': row['created_at'], 'model': str(value.get('model') or 'Unknown model')[:160],
                          'tokens': int(numbers[0]), 'seconds': round(numbers[1], 1), 'speed': round(numbers[2], 2)})
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
        if len(items) >= max(1, min(int(limit), 50)):
            break
    groups = {}
    for item in items:
        groups.setdefault(item['model'], []).append(item['speed'])
    return {'items': items, 'models': [
        {'model': model, 'replies': len(speeds), 'average_speed': round(sum(speeds)/len(speeds), 2)}
        for model, speeds in groups.items()]}


def system_status():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(config.ROOT))
    return {'cpu_percent': psutil.cpu_percent(interval=0.1), 'logical_cpus': psutil.cpu_count(),
            'memory_total': memory.total, 'memory_available': memory.available, 'memory_percent': memory.percent,
            'memory_warning': memory.available < LOW_MEMORY_BYTES,
            'disk_total': disk.total, 'disk_free': disk.free, 'disk_percent': disk.percent,
            'app_uptime_seconds': int(time.monotonic()-_started)}


def memory_check(system):
    available = system['memory_available']
    low = available < LOW_MEMORY_BYTES
    return {'name': 'Available memory', 'state': 'warning' if low else 'ok',
            'detail': (f"Low memory: {available/1024**3:.1f} GiB available (below 1 GiB). "
                       "This can slow replies; close unused apps or choose a smaller model."
                       if low else f"{available/1024**3:.1f} GiB available.")}


def service_targets(running, values, ai):
    """Only configured BEYOND services, never a scan of other programs' ports."""
    targets = [{'name': 'BEYOND web', 'host': '127.0.0.1', 'port': int(running.get('port', config.WEB_PORT)),
                'url': 'http://127.0.0.1:' + str(running.get('port', config.WEB_PORT)) + '/api/health',
                'expected': 'beyond'}]
    secure = running.get('https_port')
    if secure:
        targets.append({'name': 'BEYOND secure web', 'host': '127.0.0.1', 'port': int(secure),
                        'url': f'https://127.0.0.1:{int(secure)}/api/health', 'expected': 'beyond'})
    else:
        targets.append({'name': 'BEYOND secure web', 'host': '127.0.0.1', 'port': None,
                        'state': 'disabled', 'detail': 'HTTPS is not enabled for this app session.'})
    if values['ai_mode'] == 'builtin':
        port = ai.get('port')
        targets.append({'name': 'Built-in AI', 'host': '127.0.0.1', 'port': port,
                        **({'url': f'http://127.0.0.1:{int(port)}/health', 'expected': 'engine'} if port else
                           {'state': ai['state'], 'detail': {
                               'starting': 'The model is loading or preparing its prompt.',
                               'off': 'No model is loaded.', 'not_set': 'Choose the engine and model in Settings.',
                               'error': 'The model could not start. Check Settings and the engine log.',
                               'stopping': 'The model is unloading.'}.get(ai['state'], 'The engine is not ready.')})})
    else:
        from app import engine
        raw = values.get('ai_server_url', '')
        try:
            parsed = urlsplit(engine._base_url(raw)) if raw else None
        except ValueError:
            parsed = None
        if parsed and parsed.scheme in ('http', 'https') and parsed.hostname:
            try:
                port = parsed.port or (443 if parsed.scheme == 'https' else 80)
                targets.append({'name': 'Configured AI server', 'host': parsed.hostname, 'port': port,
                                'url': urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/')+'/v1/models', '', '')),
                                'expected': 'models'})
            except ValueError:
                targets.append({'name': 'Configured AI server', 'host': '', 'port': None,
                                'state': 'not_set', 'detail': 'Check the AI server address in Settings.'})
        else:
            targets.append({'name': 'Configured AI server', 'host': '', 'port': None,
                            'state': 'not_set', 'detail': 'No AI server address is configured.'})
    return targets


async def probe(target):
    if 'url' not in target:
        return target
    public = {key: target[key] for key in ('name', 'host', 'port')}
    started = time.monotonic()
    # Only BEYOND's own loopback HTTPS endpoint uses its private certificate authority.
    verify = not (target['expected']=='beyond' and target['url'].startswith('https://127.0.0.1:'))
    try:
        async with httpx.AsyncClient(timeout=2, verify=verify, trust_env=False, follow_redirects=False) as client:
            response = await client.get(target['url'])
            response.raise_for_status()
            body = response.json()
            if target['expected']=='beyond':
                valid = isinstance(body, dict) and body.get('name')=='BEYOND' and body.get('status')=='ok'
            elif target['expected']=='models':
                valid = isinstance(body, dict) and isinstance(body.get('data'), list)
            else:
                valid = isinstance(body, dict) and body.get('status')=='ok'
            state, detail = ('ok', 'Responding.') if valid else ('error', 'The port answered with an unexpected service response.')
    except (httpx.HTTPError, ValueError, TypeError):
        state, detail = 'error', 'Not responding as expected. Check the service and its configured address.'
    return {**public, 'state': state, 'detail': detail, 'latency_ms': round((time.monotonic()-started)*1000)}


async def snapshot(running=None):
    from app import builtin_engine
    values = settings.load()
    # Reading the built-in state does not start a model; external reachability is checked below.
    ai = builtin_engine.status() if values['ai_mode']=='builtin' else {'state': 'external', 'model': values.get('ai_model','')}
    services = await asyncio.gather(*(probe(t) for t in service_targets(running or _running, values, ai)))
    return {'at': now(), 'version': config.VERSION, 'phase': config.PHASE,
            'system': await asyncio.to_thread(system_status),
            'ai': {'state': services[-1]['state'] if values['ai_mode']=='server' else ai['state'],
                   'model': ai.get('model',''), 'busy': builtin_engine.busy()},
            'services': services}


def storage_checks():
    checks = []
    path = settings.FILE
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                raise ValueError('not an object')
        checks.append({'name': 'Settings file', 'state': 'ok', 'detail': 'Readable JSON, or fresh-install defaults.'})
    except (OSError, ValueError):
        checks.append({'name': 'Settings file', 'state': 'error', 'detail': 'Settings could not be read as a JSON object.'})
    if not chats.DB_PATH.exists():
        checks.append({'name': 'Chat database', 'state': 'skipped', 'detail': 'No chat database has been created yet.'})
    else:
        try:
            with closing(sqlite3.connect(chats.DB_PATH.resolve().as_uri()+'?mode=ro', uri=True, timeout=2)) as db:
                result = db.execute('PRAGMA quick_check(1)').fetchone()[0]
            good = result == 'ok'
            checks.append({'name': 'Chat database', 'state': 'ok' if good else 'error',
                           'detail': 'SQLite quick check passed.' if good else 'SQLite reported an integrity problem.'})
        except (OSError, sqlite3.Error):
            checks.append({'name': 'Chat database', 'state': 'error', 'detail': 'The chat database could not be checked.'})
    values = settings.load()
    for name, enabled, keys in (
        ('Photo understanding', 'vision_enabled', ('vision_executable','vision_model','vision_mmproj')),
        ('Picture generation', 'image_enabled', ('image_executable','image_model')),
        ('Speech', 'speech_enabled', ('speech_kokoro_model','speech_kokoro_voices') if values.get('speech_engine')=='kokoro'
         else ('speech_piper_model',)),
    ):
        if not values.get(enabled):
            checks.append({'name': name, 'state': 'skipped', 'detail': 'Optional feature is off.'})
        else:
            found = all(values.get(key) and Path(values[key]).is_file() for key in keys)
            checks.append({'name': name, 'state': 'ok' if found else 'warning',
                           'detail': 'Configured files exist; no media job was run.' if found else 'Some configured files are missing. Review Settings.'})
    return checks


async def self_test(running=None):
    if not _test_lock.acquire(blocking=False):
        return {'busy': True, 'checks': [], 'at': now(), 'summary': 'A self-test is already running.'}
    try:
        data = await snapshot(running)
        checks = [{'name': t['name'], 'state': ('skipped' if t['state'] in ('disabled','off') else
                  'warning' if t['state'] in ('starting','stopping','not_set') else t['state']),
                   'detail': t['detail']} for t in data['services']]
        checks.extend(await asyncio.to_thread(storage_checks))
        checks.append(memory_check(data['system']))
        checks.append({'name': 'Free disk space', 'state': 'ok' if data['system']['disk_free']>=1024**3 else 'warning',
                       'detail': f"{data['system']['disk_free']/1024**3:.1f} GiB available on BEYOND's drive."})
        counts = {state: sum(c['state']==state for c in checks) for state in ('ok','warning','error','skipped')}
        return {'at': now(), 'busy': False, 'checks': checks, 'counts': counts,
                'summary': 'Some checks failed.' if counts['error'] else 'Review the warnings.' if counts['warning'] else 'All available checks passed.'}
    finally:
        _test_lock.release()


@router.get('/status', include_in_schema=False)
def status_page():
    return FileResponse(config.WEB_DIR / 'status.html')


@router.get('/api/status')
async def get_status(request: Request):
    return await snapshot(request.app.state.running)


@router.get('/api/status/speed')
def get_speed(limit: int = Query(30, ge=1, le=50)):
    return speed_history(limit)


@router.get('/api/status/errors')
def get_errors(limit: int = Query(30, ge=1, le=200)):
    return {'items': errors(limit)}


def clear_errors():
    """Clear retained summaries only; future errors can still be recorded normally."""
    initialize()
    with closing(sqlite3.connect(error_file(), timeout=2)) as db, db:
        removed = db.execute('DELETE FROM errors').rowcount
    return removed


@router.delete('/api/status/errors')
def delete_errors(request: Request):
    from app.server import can_manage, only_this_pc
    if not can_manage(request):
        return only_this_pc()
    try:
        return {'cleared': clear_errors(), 'items': errors()}
    except (OSError, sqlite3.Error):
        return JSONResponse({'error': 'Error history could not be cleared. Please try again.'}, status_code=503)


@router.post('/api/status/selftest')
async def run_self_test(request: Request):
    result = await self_test(request.app.state.running)
    return JSONResponse(result, status_code=409 if result['busy'] else 200)


@router.post('/api/status/errors/test')
async def add_test_error():
    from app.error_diagnosis import test_error
    return await asyncio.to_thread(test_error)


@router.delete('/api/status/errors/test')
async def clear_test_errors():
    from app.error_diagnosis import test_error
    return await asyncio.to_thread(test_error, clear=True)


@router.post('/api/status/errors/{error_id}/diagnose')
async def diagnose_error(request: Request, error_id: int = PathParam(gt=0)):
    from app.error_diagnosis import diagnose
    return await diagnose(error_id, request.app.state.running)


# Reports use a separate allowlist and local readings; no health probes or model requests.
from app.error_reports import ReportNotes


@router.post('/api/status/errors/{error_id}/report')
async def preview_error_report(body: ReportNotes, error_id: int = PathParam(gt=0)):
    from app.error_reports import build
    return await asyncio.to_thread(build, error_id, body)


from app.github_reports import ReviewedReport


@router.post('/api/status/errors/{error_id}/github/check')
async def check_github_report(body: ReviewedReport, error_id: int = PathParam(gt=0)):
    from app.github_reports import check
    return await check(error_id, body)
