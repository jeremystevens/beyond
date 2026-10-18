"""Background /look jobs. The HTTP request returns before the CPU vision process starts.

Photo, progress and answer messages use separate kinds, so none are sent to the
text model. Finished answers arrive through the same polling path as reminders.
"""
import asyncio
import base64
import logging
import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import chats, notify
from app.tools import scan, vision

router = APIRouter()
_jobs = {}


def recover():
    """A previous process could have stopped mid-photo. Never leave a forever-thinking message."""
    with chats.connect() as db:
        pending = db.execute("SELECT id, chat_id FROM messages WHERE kind = 'vision_pending'").fetchall()
    for row in pending:
        chats.remove_message(row['id'])
        chats.add_message(row['chat_id'], 'assistant',
                          'Photo analysis was interrupted when BEYOND stopped. Attach the photo and try /look again.',
                          kind='vision_error', replaces=row['id'])


async def shutdown():
    """Stop the child process before exiting/restarting the server."""
    jobs = list(_jobs.items())
    for _, stop in jobs:
        stop.set()
    if jobs:
        await asyncio.gather(*(task for task, _ in jobs), return_exceptions=True)


async def _finish(chat_id, pending_id, png, question, values, stop):
    try:
        try:
            answer = await asyncio.to_thread(vision.ask, png, question, values, stop)
            kind, popup_kind, title = 'vision', 'reply', 'BEYOND finished looking at your photo'
        except vision.VisionError as exc:
            answer, kind, popup_kind, title = str(exc), 'vision_error', 'error', 'BEYOND: photo analysis stopped'
        except Exception:
            logging.exception('Photo analysis failed')
            answer, kind, popup_kind, title = ('The photo could not be analyzed. Please try again.',
                                               'vision_error', 'error', 'BEYOND: photo analysis failed')
        # If the chat was deleted meanwhile, discard the result and don't recreate anything.
        if chats.exists(chat_id) and chats.get_message(pending_id):
            with chats.connect() as db:
                db.execute('DELETE FROM messages WHERE id = ?', (pending_id,))
            chats.add_message(chat_id, 'assistant', answer, kind=kind, replaces=pending_id)
            if not stop.is_set():
                notify.show(popup_kind, title, answer, chat_id)
    except Exception:
        logging.exception('Could not save a photo answer')
    finally:
        vision.release()


@router.get('/api/look/status')
def status():
    try:
        vision.configuration()
        ready, problem = True, ''
    except vision.VisionError as exc:
        ready, problem = False, str(exc)
    return {'ready': ready, 'problem': problem, 'busy': vision._lock.locked()}


@router.post('/api/look')
async def start(request: Request, chat_id: int | None = None, action: str = 'describe', question: str = ''):
    """Accept a raw photo and return its saved progress message; computation outlives the browser request."""
    if action not in ('describe', 'receipt', 'ask'):
        return JSONResponse({'error': 'Choose Describe it, Receipt / totals, or Ask a question.'}, status_code=400)
    question = question.strip()
    if len(question) > 500 or (action == 'ask' and not question):
        return JSONResponse({'error': 'Type a question of 1–500 characters about the photo.'}, status_code=400)
    prompt = question if action == 'ask' else vision.ACTIONS[action]
    if chat_id is not None and not chats.exists(chat_id):
        return JSONResponse({'error': 'That chat no longer exists. Start a new one.'}, status_code=404)
    try:
        values = vision.configuration()
    except vision.VisionError as exc:
        return JSONResponse({'error': str(exc)}, status_code=503)
    if not vision.reserve():
        return JSONResponse({'error': 'BEYOND is already looking at a photo. You can keep chatting while it works.'},
                            status_code=409)
    started = False
    try:
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > scan.MAX_PHOTO_BYTES:
                return JSONResponse({'error': 'Photos must be 10 MB or smaller.'}, status_code=413)
            body.extend(chunk)
        try:
            png = await asyncio.to_thread(scan.prepare, bytes(body))
        except scan.ScanError as exc:
            return JSONResponse({'error': str(exc)}, status_code=400)
        if chat_id is not None and not chats.exists(chat_id):
            return JSONResponse({'error': 'That chat was deleted while the photo was uploading.'}, status_code=404)
        current = chats.create('Look at a photo') if chat_id is None else chat_id
        image = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
        label = '/look ' + (question if action == 'ask' else ('Receipt / totals' if action == 'receipt' else 'Describe it'))
        photo_id = chats.add_message(current, 'user', label, kind='photo', image=image)
        progress = 'Looking at your photo on this PC… Usually about 1–2 minutes. You can keep chatting while I work.'
        pending_id = chats.add_message(current, 'assistant', progress, kind='vision_pending')
        stop = threading.Event()
        task = asyncio.create_task(_finish(current, pending_id, png, prompt, values, stop))
        _jobs[task] = stop
        task.add_done_callback(lambda done: _jobs.pop(done, None))
        started = True
        return JSONResponse({'chat_id': current, 'photo_id': photo_id, 'id': pending_id, 'text': progress,
                             'label': label, 'image': image}, status_code=202)
    finally:
        if not started:
            vision.release()
