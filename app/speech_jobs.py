"""Saved, queued speech clips. One bounded CPU worker at a time, at most four requests."""
import asyncio
import logging
import re
import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app import chats, settings
from app.tools import speech

router = APIRouter()
_jobs = {}
_worker_lock = threading.Lock()


info = chats.speech_info

def recover():
    with chats.connect() as db:
        db.execute("UPDATE messages SET speech_state = 'error', speech_error = ?, audio = NULL "
                   "WHERE speech_state = 'pending'",
                   ('Speech was interrupted when BEYOND stopped. Press Read aloud to try again.',))


def _run(text, values, stop):
    while not _worker_lock.acquire(timeout=.1):
        if stop.is_set():
            raise speech.SpeechError('Speech was interrupted when BEYOND stopped. Press Read aloud to try again.')
    try:
        return speech.synthesize(text, values, stop)
    finally:
        _worker_lock.release()


async def _finish(message_id, text, values, stop):
    try:
        audio, engine = await asyncio.to_thread(_run, text, values, stop)
        with chats.connect() as db:
            db.execute("UPDATE messages SET audio = ?, speech_engine = ?, speech_state = 'ready', "
                       "speech_error = NULL WHERE id = ?", (audio, engine, message_id))
    except Exception as exc:
        if not isinstance(exc, speech.SpeechError):
            logging.exception('Speech failed')
        error = str(exc) if isinstance(exc, speech.SpeechError) else 'Speech could not be made. Press Read aloud to try again.'
        with chats.connect() as db:
            db.execute("UPDATE messages SET speech_state = 'error', speech_error = ?, audio = NULL WHERE id = ?",
                       (error, message_id))


async def shutdown():
    jobs = list(_jobs.values())
    for _, stop in jobs:
        stop.set()
    if jobs:
        await asyncio.gather(*(task for task, _ in jobs), return_exceptions=True)


def start(message_id, text=None):
    """Called on the server loop after a reply is saved, or by a Read aloud request."""
    message = chats.get_message(message_id)
    if not message or message['role'] != 'assistant' or message['kind'] not in ('chat', 'command', 'vision', 'scan'):
        raise speech.SpeechError('That answer is not available to read aloud.')
    existing = info(message)
    if existing and (existing['state'] == 'ready' or message_id in _jobs):
        return existing
    values = speech.configuration()
    if len(_jobs) >= 4:
        raise speech.SpeechError('The speech queue is full. Please try Read aloud again in a moment.')
    text, truncated = speech.clean(message['content'] if text is None else text)
    with chats.connect() as db:
        db.execute("UPDATE messages SET audio = NULL, speech_state = 'pending', speech_error = NULL, "
                   "speech_engine = NULL, speech_truncated = ? WHERE id = ?", (int(truncated), message_id))
    stop = threading.Event()
    task = asyncio.create_task(_finish(message_id, text, values, stop))
    _jobs[message_id] = task, stop
    task.add_done_callback(lambda done: _jobs.pop(message_id, None))
    return {'state': 'pending', 'error': '', 'engine': '', 'truncated': truncated, 'url': ''}


class SpeechRequest(BaseModel):
    message_id: int


@router.post('/api/speech')
async def request_speech(body: SpeechRequest):
    if not chats.get_message(body.message_id):
        return JSONResponse({'error': 'That answer no longer exists.'}, status_code=404)
    try:
        result = start(body.message_id)
        return JSONResponse(result, status_code=202 if result['state'] == 'pending' else 200)
    except speech.SpeechError as exc:
        return JSONResponse({'error': str(exc)}, status_code=503)


@router.get('/api/speech/status')
def status(chat_id: int):
    if not chats.exists(chat_id):
        return JSONResponse({'error': 'That chat no longer exists.'}, status_code=404)
    with chats.connect() as db:
        rows = db.execute('SELECT id, speech_state, speech_error, speech_engine, speech_truncated FROM messages '
                          'WHERE chat_id = ? AND speech_state IS NOT NULL', (chat_id,)).fetchall()
    return {'items': [{'id': row['id'], **info(row)} for row in rows],
            'auto_read': settings.load()['speech_auto']}


@router.get('/api/speech/{message_id}.wav')
def audio_file(message_id: int, request: Request):
    with chats.connect() as db:
        row = db.execute("SELECT audio FROM messages WHERE id = ? AND speech_state = 'ready'",
                         (message_id,)).fetchone()
    if not row or not row['audio']:
        return JSONResponse({'error': 'That audio is not available.'}, status_code=404)
    audio = row['audio']
    total = len(audio)
    headers = {'Content-Disposition': f'inline; filename="beyond-speech-{message_id}.wav"',
               'Cache-Control': 'no-store', 'Accept-Ranges': 'bytes'}
    span = request.headers.get('range')
    if span:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', span)
        try:
            if not match or not any(match.groups()):
                raise ValueError()
            first, last = match.groups()
            start = int(first) if first else max(0, total - int(last))
            end = min(int(last), total-1) if first and last else total-1
            if start >= total or end < start:
                raise ValueError()
        except ValueError:
            return Response(status_code=416, headers={**headers, 'Content-Range': f'bytes */{total}'})
        headers['Content-Range'] = f'bytes {start}-{end}/{total}'
        return Response(audio[start:end+1], status_code=206, media_type='audio/wav', headers=headers)
    return Response(audio, media_type='audio/wav', headers=headers)
