"""Model downloads from Hugging Face (Phase 35): resumable, fingerprint-checked, one at a time.

A download goes into BEYOND's models folder (models/<owner>--<repo>/), first as "<file>.part". Each piece is written
and fed to a SHA-256 fingerprint as it arrives; when the file is complete the fingerprint must match the one Hugging
Face publishes for it (or, for the recommended models, the one pinned below) before the ".part" is renamed. A broken
connection is retried, then resumed later from where it stopped with an HTTP Range request. The free disk space is
checked before starting and before resuming. The finished model appears on the Models page straight away.

Only huggingface.co is contacted, only .gguf files are downloaded, and nothing outside the models folder is written.
Gated models (sign-in needed) are explained and linked rather than downloaded; models whose licence has terms the
maker asks you to accept need that acceptance first.
"""
import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

import httpx
import psutil

from app import config

HF = 'https://huggingface.co'
CHUNK = 1024 * 1024
SPACE_MARGIN = 512 * 1024 * 1024        # keep at least this much free after a download
RETRIES = 5                             # connection drops retried automatically before pausing
REPO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9_.-]{1,96}$')
SPLIT = re.compile(r'^(.*-)(\d{5})-of-(\d{5})\.gguf$', re.I)
SHA256 = re.compile(r'^[a-f0-9]{64}$')
OPEN_LICENCES = {'apache-2.0', 'mit', 'bsd-2-clause', 'bsd-3-clause', 'cc-by-4.0', 'cc0-1.0', 'unlicense'}

# Recommended models that run well on a processor. Sizes and fingerprints are pinned: a file that doesn't match is
# never kept. Licences marked accept=True ask you to agree to the maker's terms first.
RECOMMENDED = [
    {'key': 'qwen3-4b', 'name': 'Qwen3 4B', 'repo': 'Qwen/Qwen3-4B-GGUF', 'file': 'Qwen3-4B-Q4_K_M.gguf',
     'size': 2497280256, 'sha256': '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5',
     'about': 'A strong all-rounder for chat, writing and reasoning. A good first choice.',
     'licence': 'Apache 2.0', 'licence_url': 'https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/main/LICENSE',
     'accept': False},
    {'key': 'qwen3-1.7b', 'name': 'Qwen3 1.7B', 'repo': 'Qwen/Qwen3-1.7B-GGUF', 'file': 'Qwen3-1.7B-Q8_0.gguf',
     'size': 1834426016, 'sha256': '061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a',
     'about': 'Small and quick. For older or busy PCs, or when speed matters more than depth.',
     'licence': 'Apache 2.0', 'licence_url': 'https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/blob/main/LICENSE',
     'accept': False},
    {'key': 'llama-3.2-3b', 'name': 'Llama 3.2 3B Instruct', 'repo': 'bartowski/Llama-3.2-3B-Instruct-GGUF',
     'file': 'Llama-3.2-3B-Instruct-Q4_K_M.gguf', 'size': 2019377696,
     'sha256': '6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff',
     'about': "Meta's compact model: friendly, quick everyday chat.",
     'licence': 'Llama 3.2 Community License',
     'licence_url': 'https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct/blob/main/LICENSE.txt', 'accept': True},
    {'key': 'gemma-3-4b', 'name': 'Gemma 3 4B', 'repo': 'bartowski/google_gemma-3-4b-it-GGUF',
     'file': 'google_gemma-3-4b-it-Q4_K_M.gguf', 'size': 2489758112,
     'sha256': '4996030242583a40aa151ff93f49ed787ac8c25e4120c3ae4588b2e2a7d1ae94',
     'about': "Google's model: clear writing and good at many languages.",
     'licence': 'Gemma Terms of Use', 'licence_url': 'https://ai.google.dev/gemma/terms', 'accept': True},
    {'key': 'phi-4-mini', 'name': 'Phi-4 mini', 'repo': 'bartowski/microsoft_Phi-4-mini-instruct-GGUF',
     'file': 'microsoft_Phi-4-mini-instruct-Q4_K_M.gguf', 'size': 2491874688,
     'sha256': '01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2',
     'about': "Microsoft's small model, good at maths, logic and step-by-step answers.",
     'licence': 'MIT', 'licence_url': 'https://huggingface.co/microsoft/Phi-4-mini-instruct/blob/main/LICENSE',
     'accept': False},
    {'key': 'qwen2.5-7b', 'name': 'Qwen2.5 7B Instruct', 'repo': 'bartowski/Qwen2.5-7B-Instruct-GGUF',
     'file': 'Qwen2.5-7B-Instruct-Q4_K_M.gguf', 'size': 4683074240,
     'sha256': '65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423',
     'about': 'Bigger and more knowledgeable, but slower. Best with 16 GB of memory or more.',
     'licence': 'Apache 2.0', 'licence_url': 'https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/LICENSE',
     'accept': False},
]


class DownloadError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class _Stop(Exception):
    """Pause or Cancel was pressed."""


_lock = threading.RLock()
_jobs = []
_worker = None
_wake = threading.Event()
_stop_requests = {}          # job id -> 'pause' | 'cancel'
_closing = False


def _file():
    return config.DATA_DIR / 'downloads.json'


def _client(**kwargs):
    """The HTTP client (tests replace this with one that never touches the network)."""
    return httpx.Client(follow_redirects=True, headers={'User-Agent': f'BEYOND/{config.VERSION}'},
                        timeout=httpx.Timeout(30, read=60), **kwargs)


# ---------- saved state ----------

def _save():
    config.DATA_DIR.mkdir(exist_ok=True)
    temp = _file().with_suffix('.tmp')
    temp.write_text(json.dumps(_jobs, indent=1), encoding='utf-8')
    temp.replace(_file())


def recover():
    """At start-up: a download that was running when BEYOND closed waits to be resumed."""
    global _jobs
    with _lock:
        try:
            saved = json.loads(_file().read_text(encoding='utf-8'))
            _jobs = [job for job in saved if isinstance(job, dict) and job.get('id')]
        except (OSError, ValueError):
            _jobs = []
        for job in _jobs:
            if job['state'] in ('downloading', 'verifying', 'queued'):
                job.update(state='paused', speed=0,
                           error='BEYOND was closed during this download. Press Resume to continue where it stopped.')
        _save()


def shutdown():
    """BEYOND is quitting: stop the running download; its .part file stays for Resume."""
    global _closing
    with _lock:
        _closing = True
        for job in _jobs:
            if job['state'] in ('downloading', 'verifying'):
                _stop_requests[job['id']] = 'pause'
        _wake.set()
    if _worker and _worker.is_alive():
        _worker.join(timeout=10)


# ---------- where files go ----------

def folder_for(repo):
    return config.MODELS_DIR / repo.replace('/', '--')


def _target(job, path):
    return Path(job['folder']) / Path(path).name


def _inside_models(path):
    base = config.MODELS_DIR.resolve()
    return Path(path).resolve().is_relative_to(base)


# ---------- Hugging Face ----------

def parse_repo(text):
    """'owner/name', a huggingface.co link, or a link to a file in it -> 'owner/name'."""
    text = (text or '').strip()
    match = re.match(r'^(?:https?://)?(?:www\.)?(?:huggingface\.co|hf\.co)/([^/?#]+/[^/?#]+)', text, re.I)
    repo = match[1] if match else text
    if repo.split('/')[0] in ('models', 'datasets', 'spaces'):
        raise DownloadError('Paste the link to a model, for example huggingface.co/Qwen/Qwen3-4B-GGUF.')
    if not REPO.match(repo):
        raise DownloadError('Enter a Hugging Face model as owner/name, for example Qwen/Qwen3-4B-GGUF, or paste its link.')
    return repo


def _get_json(client, url):
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        raise DownloadError("BEYOND couldn't reach Hugging Face. Check the internet connection and try again.", 502) from exc
    if response.status_code in (401, 403):
        raise DownloadError('Hugging Face needs you to sign in to see this model, which BEYOND does not support.', 403)
    if response.status_code == 404:
        raise DownloadError('Hugging Face has no public model with that name. Check the spelling.', 404)
    if response.status_code != 200:
        raise DownloadError(f'Hugging Face answered with an error (HTTP {response.status_code}). Try again later.', 502)
    try:
        return response.json()
    except ValueError as exc:
        raise DownloadError("Hugging Face's answer wasn't in the expected format.", 502) from exc


def _licence(repo, info):
    card = info.get('cardData') or {}
    name = card.get('license_name') or card.get('license') or ''
    if isinstance(name, list):
        name = ', '.join(map(str, name))
    link = card.get('license_link') or ''
    if link and not link.startswith('http'):
        link = f'{HF}/{repo}/blob/main/{link.lstrip("/")}'
    return {'licence': str(name) or 'Not stated', 'licence_url': link or f'{HF}/{repo}',
            'accept': str(name).lower() not in OPEN_LICENCES}


def browse(text):
    """The downloadable .gguf models in a Hugging Face repository (split models grouped as one)."""
    repo = parse_repo(text)
    with _client() as client:
        info = _get_json(client, f'{HF}/api/models/{repo}')
        if info.get('gated'):
            return {'repo': repo, 'gated': True, 'files': [], 'page': f'{HF}/{repo}', **_licence(repo, info)}
        tree = _get_json(client, f'{HF}/api/models/{repo}/tree/main?recursive=true')
    files, splits = [], {}
    for item in tree if isinstance(tree, list) else []:
        path = item.get('path', '')
        lfs = item.get('lfs') or {}
        sha, size = lfs.get('oid', ''), lfs.get('size') or item.get('size') or 0
        name = Path(path).name
        if item.get('type') != 'file' or not name.lower().endswith('.gguf') or not SHA256.match(sha) or not size:
            continue
        if any(word in name.lower() for word in ('mmproj', 'projector')):
            continue
        part = {'path': path, 'size': int(size), 'sha256': sha}
        split = SPLIT.match(name)
        if split:
            splits.setdefault((str(Path(path).parent), split[1], split[3]), []).append(part)
        else:
            files.append({'name': name, 'files': [part], 'size': part['size']})
    for (_, prefix, count), parts in splits.items():
        if len(parts) == int(count):
            parts.sort(key=lambda p: p['path'])
            files.append({'name': Path(parts[0]['path']).name, 'files': parts,
                          'size': sum(p['size'] for p in parts), 'parts': len(parts)})
    files.sort(key=lambda f: f['size'])
    return {'repo': repo, 'gated': False, 'files': files, 'page': f'{HF}/{repo}', **_licence(repo, info)}


# ---------- starting and controlling downloads ----------

def _free_space(folder):
    folder = Path(folder)
    while not folder.exists():
        folder = folder.parent
    return shutil.disk_usage(folder).free


def _bytes(size):
    return f'{size / 1024 ** 3:.1f} GB' if size >= 1024 ** 3 else f'{size / 1024 ** 2:.0f} MB'


def _check_space(job):
    needed = sum(f['size'] for f in job['files']) - _present(job) + SPACE_MARGIN
    free = _free_space(job['folder'])
    if free < needed:
        raise DownloadError(f"Not enough free disk space: this needs about {_bytes(needed)} and the drive has "
                            f"{_bytes(free)} free. Free up some space, then try again.", 507)


def _present(job):
    """Bytes already on disk for this job (finished parts and the current .part)."""
    total = 0
    for item in job['files']:
        target = _target(job, item['path'])
        partial = target.with_name(target.name + '.part')
        if target.is_file() and target.stat().st_size == item['size']:
            total += item['size']
        elif partial.is_file():
            total += min(partial.stat().st_size, item['size'])
    return total


def _new_job(name, repo, files, licence, accept, key=''):
    folder = folder_for(repo)
    job = {'id': uuid.uuid4().hex[:12], 'key': key, 'name': name, 'repo': repo, 'files': files,
           'folder': str(folder), 'total': sum(f['size'] for f in files), 'received': 0, 'speed': 0,
           'state': 'queued', 'error': '', 'created': time.time(), 'finished': None, **licence}
    if not _inside_models(folder):
        raise DownloadError('That model name would save outside the models folder.')
    if licence['accept'] and not accept:
        raise DownloadError(f"Accept the {licence['licence']} first: read it, then tick the box.", 409)
    for item in files:
        name = Path(item['path']).name
        if not name.lower().endswith('.gguf') or not SHA256.match(item['sha256']) or item['size'] <= 0:
            raise DownloadError('Only .gguf model files with a published fingerprint can be downloaded.')
    with _lock:
        for other in _jobs:
            if (other['repo'] == repo and [f['path'] for f in other['files']] == [f['path'] for f in files]
                    and other['state'] in ('queued', 'downloading', 'verifying', 'paused')):
                raise DownloadError('That model is already in your downloads.', 409)
        target = _target(job, files[0]['path'])
        if target.is_file() and target.stat().st_size == files[0]['size'] and len(files) == 1:
            raise DownloadError('That model is already downloaded. Find it in Your models.', 409)
        job['received'] = _present(job)
        _check_space(job)
        _jobs.insert(0, job)
        _save()
        _start_worker()
    logging.info('Downloads: queued %s from %s', job['name'], repo)
    return job


def start_recommended(key, accept=False):
    item = next((m for m in RECOMMENDED if m['key'] == key), None)
    if not item:
        raise DownloadError('That recommended model is not in the list.', 404)
    files = [{'path': item['file'], 'size': item['size'], 'sha256': item['sha256']}]
    licence = {k: item[k] for k in ('licence', 'licence_url', 'accept')}
    return _new_job(item['name'], item['repo'], files, licence, accept, key=item['key'])


def start_custom(repo_text, name, accept=False):
    """Download one model (all its parts) chosen from browse(); fingerprints come from Hugging Face itself."""
    found = browse(repo_text)
    if found['gated']:
        raise DownloadError('This model needs you to sign in to Hugging Face and accept its terms there, which BEYOND '
                            'does not support. Look for a community GGUF copy instead.', 403)
    choice = next((f for f in found['files'] if f['name'] == name), None)
    if not choice:
        raise DownloadError('That file is not in this model any more. Look it up again.', 404)
    licence = {k: found[k] for k in ('licence', 'licence_url', 'accept')}
    label = Path(choice['name']).stem
    return _new_job(re.sub(r'-00001-of-\d{5}$', '', label), found['repo'], choice['files'], licence, accept)


def _find(job_id):
    job = next((j for j in _jobs if j['id'] == job_id), None)
    if not job:
        raise DownloadError('That download is no longer in the list.', 404)
    return job


def pause(job_id):
    with _lock:
        job = _find(job_id)
        if job['state'] == 'queued':
            job.update(state='paused', error='')
        elif job['state'] == 'downloading':
            _stop_requests[job_id] = 'pause'
        _save()
    return view()


def resume(job_id):
    with _lock:
        job = _find(job_id)
        if job['state'] not in ('paused', 'failed'):
            raise DownloadError('Only a paused or failed download can be resumed.', 409)
        job['received'] = _present(job)
        _check_space(job)
        job.update(state='queued', error='', speed=0)
        _save()
        _start_worker()
    return view()


def cancel(job_id):
    """Stop a download and delete its unfinished .part files (finished models are never deleted here)."""
    with _lock:
        job = _find(job_id)
        if job['state'] in ('downloading', 'verifying'):
            _stop_requests[job_id] = 'cancel'
        else:
            _remove_parts(job)
            if job['state'] != 'done':
                job.update(state='cancelled', error='', speed=0)
            _jobs.remove(job)
        _save()
    return view()


def _remove_parts(job):
    for item in job['files']:
        partial = _target(job, item['path'])
        partial = partial.with_name(partial.name + '.part')
        if _inside_models(partial):
            partial.unlink(missing_ok=True)


def clear_finished():
    with _lock:
        _jobs[:] = [j for j in _jobs if j['state'] not in ('done', 'cancelled')]
        _save()
    return view()


# ---------- the worker ----------

def _start_worker():
    global _worker, _closing
    _closing = False
    _wake.set()
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_work, name='model-downloads', daemon=True)
        _worker.start()


def _work():
    while True:
        with _lock:
            job = next((j for j in reversed(_jobs) if j['state'] == 'queued'), None) if not _closing else None
            if job is None:
                _wake.clear()
                return
            job.update(state='downloading', error='', speed=0)
            _save()
        try:
            _download(job)
        except _Stop:
            with _lock:
                if _stop_requests.pop(job['id'], 'pause') == 'cancel':
                    _remove_parts(job)
                    if job in _jobs:
                        _jobs.remove(job)
                    logging.info('Downloads: cancelled %s', job['name'])
                else:
                    job.update(state='paused', speed=0)
                _save()
        except DownloadError as exc:
            with _lock:
                job.update(state='failed', error=str(exc), speed=0)
                _save()
            logging.warning('Downloads: %s failed: %s', job['name'], exc)
        except Exception:
            logging.exception('Downloads: %s failed', job['name'])
            with _lock:
                job.update(state='failed', speed=0, error='Something went wrong saving the download. Press Resume to try again.')
                _save()


def _check_stop(job):
    if job['id'] in _stop_requests:
        raise _Stop()


def _download(job):
    Path(job['folder']).mkdir(parents=True, exist_ok=True)
    _check_space(job)
    done_before = 0
    for item in job['files']:
        target = _target(job, item['path'])
        if not _inside_models(target):
            raise DownloadError('That file would save outside the models folder.')
        if target.is_file() and target.stat().st_size == item['size']:
            done_before += item['size']   # an earlier part of a split model, already verified and renamed
            continue
        _download_file(job, item, target, done_before)
        done_before += item['size']
    with _lock:
        job.update(state='done', received=job['total'], speed=0, finished=time.time(), error='')
        _save()
    logging.info('Downloads: %s is ready', job['name'])


def _download_file(job, item, target, done_before):
    partial = target.with_name(target.name + '.part')
    fingerprint = hashlib.sha256()
    offset = partial.stat().st_size if partial.is_file() else 0
    if offset > item['size']:
        partial.unlink()
        offset = 0
    if offset:   # resuming: the fingerprint must include what is already on disk
        with _lock:
            job['error'] = 'Checking the part that was already downloaded…'
        with open(partial, 'rb') as existing:
            while block := existing.read(CHUNK * 4):
                _check_stop(job)
                fingerprint.update(block)
        with _lock:
            job['error'] = ''
    url = f"{HF}/{job['repo']}/resolve/main/{item['path']}"
    attempts = 0
    # Shared with _fetch, so what a dropped connection already wrote is counted (and never written twice).
    progress = {'offset': offset, 'fingerprint': fingerprint}
    while progress['offset'] < item['size']:
        _check_stop(job)
        try:
            _fetch(job, item, url, partial, progress, done_before)
            attempts = 0
        except httpx.HTTPError as exc:
            attempts += 1
            if attempts > RETRIES:
                raise DownloadError('The connection to Hugging Face keeps dropping. Press Resume to continue '
                                    'from where it stopped.') from exc
            logging.info('Downloads: connection dropped (%s), retrying', type(exc).__name__)
            for _ in range(min(30, 2 ** attempts) * 10):
                time.sleep(0.1)
                _check_stop(job)
    with _lock:
        job.update(state='verifying', speed=0)
        _save()
    if progress['fingerprint'].hexdigest() != item['sha256']:
        partial.unlink(missing_ok=True)
        raise DownloadError("The downloaded file's fingerprint didn't match the one Hugging Face publishes, so it was "
                            'deleted (it may have been damaged on the way). Press Resume to download it again.')
    os.replace(partial, target)
    with _lock:
        job['state'] = 'downloading'


def _fetch(job, item, url, partial, progress, done_before):
    """One HTTP request from progress['offset'] to the end (or until the connection drops). Every piece written is
    added to progress straight away, so a drop part-way loses nothing."""
    offset = progress['offset']
    headers = {'Range': f'bytes={offset}-'} if offset else {}
    with _client() as client, client.stream('GET', url, headers=headers) as response:
        if response.status_code == 416 and offset == item['size']:
            return
        if response.status_code in (401, 403):
            raise DownloadError('Hugging Face needs you to sign in and accept the terms for this model, which BEYOND '
                                f"does not support. See {HF}/{job['repo']}.")
        if response.status_code == 404:
            raise DownloadError('Hugging Face no longer has this file. Look the model up again.')
        if response.status_code not in (200, 206):
            raise httpx.HTTPStatusError(f'HTTP {response.status_code}', request=response.request, response=response)
        if offset and response.status_code == 200:   # the server ignored the resume request: start this file again
            progress.update(offset=0, fingerprint=hashlib.sha256())
            offset = 0
        mode = 'ab' if offset else 'wb'
        window_start, window_bytes = time.monotonic(), 0
        with open(partial, mode) as out:
            for block in response.iter_bytes():   # pieces as they arrive, so Pause answers within a moment
                if job['id'] in _stop_requests:
                    out.flush()
                    raise _Stop()
                block = block[:item['size'] - offset]
                if not block:
                    break
                out.write(block)
                progress['fingerprint'].update(block)
                offset += len(block)
                progress['offset'] = offset
                window_bytes += len(block)
                now = time.monotonic()
                if now - window_start >= 1:
                    with _lock:
                        job.update(received=done_before + offset, speed=window_bytes / (now - window_start))
                    window_start, window_bytes = now, 0
        with _lock:
            job['received'] = done_before + offset


# ---------- the page ----------

def _have(item, models):
    return any(m['name'].casefold() == item['file'].casefold() and m['bytes'] == item['size'] for m in models)


def view(models=None):
    """Everything the Models page shows about downloads."""
    from app import models as model_list
    entries = models if models is not None else model_list.catalogue()
    memory = psutil.virtual_memory().total
    with _lock:
        jobs = [dict(job) for job in _jobs]
    for job in jobs:
        first = _target(job, job['files'][0]['path'])
        job['model_id'] = model_list.model_id(first) if job['state'] == 'done' else None
        job['remaining'] = (job['total'] - job['received']) / job['speed'] if job['speed'] else None
        job.pop('folder', None)
    by_key = {job['key']: job for job in jobs if job.get('key')}
    recommended = []
    for item in RECOMMENDED:
        entry = {k: item[k] for k in ('key', 'name', 'repo', 'file', 'size', 'about', 'licence', 'licence_url',
                                      'accept')}
        entry.update(have=_have(item, entries), job=by_key.get(item['key'], {}).get('id'),
                     tight=item['size'] + 1024 ** 3 > memory * 0.7)
        recommended.append(entry)
    return {'jobs': jobs, 'recommended': recommended, 'free': _free_space(config.MODELS_DIR),
            'memory': memory}
