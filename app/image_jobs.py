"""Background /imagine jobs, saved pictures, downloads and notification previews."""
import asyncio
import base64
import io
import json
import logging
import threading

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from PIL import Image
from pydantic import BaseModel, Field
from typing import Literal

from app import chats, config, notify
from app.tools import imagine, image_prompts

router = APIRouter()
_jobs = {}


def preview_path(message_id):
    return config.DATA_DIR / 'image-previews' / f'{message_id}.png'


def remove_previews(chat_id):
    with chats.connect() as db:
        ids = [r[0] for r in db.execute("SELECT id FROM messages WHERE chat_id = ? AND kind = 'image'", (chat_id,))]
    for message_id in ids:
        preview_path(message_id).unlink(missing_ok=True)


def recover():
    with chats.connect() as db:
        pending = db.execute("SELECT id, chat_id FROM messages WHERE kind = 'image_pending'").fetchall()
        images = {str(r[0]) for r in db.execute("SELECT id FROM messages WHERE kind = 'image'")}
    for row in pending:
        chats.remove_message(row['id'])
        chats.add_message(row['chat_id'], 'assistant',
                          'Picture generation was interrupted when BEYOND stopped. Try /imagine again.',
                          kind='image_error', replaces=row['id'])
    for path in (config.DATA_DIR / 'image-previews').glob('*.png'):
        if path.stem not in images:
            path.unlink(missing_ok=True)


async def shutdown():
    jobs = list(_jobs.items())
    for _, stop in jobs:
        stop.set()
    if jobs:
        await asyncio.gather(*(task for task, _ in jobs), return_exceptions=True)


async def _finish(chat_id, pending_id, prompt, preset, values, stop, seed=-1):
    try:
        try:
            options = {'seed': seed} if seed != -1 else {}
            png = await asyncio.to_thread(imagine.generate, prompt, preset, values, stop, **options)
            answer = f"Your picture is ready · {imagine.PRESETS[preset]['label']}\n{prompt}"
            kind = 'image'
        except imagine.ImagineError as exc:
            answer, kind, png = str(exc), 'image_error', None
        except Exception:
            logging.exception('Picture generation failed')
            answer, kind, png = 'The picture could not be made. Try /imagine again.', 'image_error', None
        if chats.exists(chat_id) and chats.get_message(pending_id):
            image = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii') if png else None
            # Replace progress and save its result atomically.
            with chats.connect() as db:
                now = chats._now()
                db.execute('DELETE FROM messages WHERE id = ?', (pending_id,))
                message_id = db.execute(
                    'INSERT INTO messages (chat_id, role, content, created_at, kind, image, replaces) '
                    "VALUES (?, 'assistant', ?, ?, ?, ?, ?)",
                    (chat_id, answer, now, kind, image, pending_id)).lastrowid
                if png:
                    buttons = [[{'label': 'Download PNG', 'url': f'/api/images/{message_id}.png'}]]
                    db.execute('UPDATE messages SET buttons = ? WHERE id = ?', (json.dumps(buttons), message_id))
                db.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (now, chat_id))
            preview = None
            if png and not stop.is_set():
                try:
                    preview = preview_path(message_id)
                    preview.parent.mkdir(exist_ok=True)
                    with Image.open(io.BytesIO(png)) as picture:
                        picture.thumbnail((256, 256))
                        picture.save(preview, format='PNG')
                except Exception:
                    logging.exception('Could not prepare a picture popup preview')
                    preview = None
            if not stop.is_set():
                notify.show('reply' if png else 'error',
                            'BEYOND finished your picture' if png else 'BEYOND: picture generation stopped',
                            answer, chat_id, image_path=preview)
    except Exception:
        logging.exception('Could not save a generated picture')
    finally:
        imagine.release()


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1200)


@router.post('/api/imagine/prompt')
async def improve_prompt(body: PromptRequest):
    if not body.prompt.strip():
        return JSONResponse({'error': 'Type a picture idea first.'}, status_code=400)
    try:
        prompt = await image_prompts.improve(body.prompt)
        return {'prompt': prompt, 'negative_prompt': image_prompts.negative_prompt(prompt)}
    except image_prompts.PromptError as exc:
        return JSONResponse({'error': str(exc)}, status_code=503)


class PictureRequest(BaseModel):
    chat_id: int | None = None
    prompt: str = Field(min_length=1, max_length=1200)
    preset: Literal['quick', 'good', 'best'] = 'good'
    # Optional API seed for reproducible comparisons; browser users still choose presets only.
    seed: int = Field(default=-1, ge=-1, le=2147483647, strict=True)


@router.get('/api/imagine/status')
def status():
    try:
        imagine.configuration()
        ready, problem = True, ''
    except imagine.ImagineError as exc:
        ready, problem = False, str(exc)
    return {'ready': ready, 'problem': problem, 'busy': imagine._lock.locked(), 'presets': imagine.PRESETS}


@router.post('/api/imagine')
async def start(body: PictureRequest):
    prompt = body.prompt.strip()
    if not prompt:
        return JSONResponse({'error': 'Type a picture idea first.'}, status_code=400)
    if body.chat_id is not None and not chats.exists(body.chat_id):
        return JSONResponse({'error': 'That chat no longer exists. Start a new one.'}, status_code=404)
    try:
        values = imagine.configuration()
    except imagine.ImagineError as exc:
        return JSONResponse({'error': str(exc)}, status_code=503)
    if not imagine.reserve():
        return JSONResponse({'error': 'BEYOND is already making a picture. You can keep chatting while it works.'},
                            status_code=409)
    started = False
    try:
        current = chats.create('/imagine ' + prompt) if body.chat_id is None else body.chat_id
        spec = imagine.PRESETS[body.preset]
        avoid = image_prompts.negative_prompt(prompt)
        chats.add_message(current, 'user', f"/imagine {prompt}\nPreset: {spec['label']}\nAvoid: {avoid}",
                          kind='image_request')
        progress = f"Making your picture · {spec['label']} · {spec['estimate']}. You can keep chatting while I work."
        pending_id = chats.add_message(current, 'assistant', progress, kind='image_pending')
        stop = threading.Event()
        task = asyncio.create_task(_finish(current, pending_id, prompt, body.preset, values, stop, body.seed))
        _jobs[task] = stop
        task.add_done_callback(lambda done: _jobs.pop(done, None))
        started = True
        return JSONResponse({'chat_id': current, 'id': pending_id, 'text': progress}, status_code=202)
    finally:
        if not started:
            imagine.release()


@router.get('/api/images/{message_id}.png')
def download(message_id: int):
    with chats.connect() as db:
        row = db.execute("SELECT image FROM messages WHERE id = ? AND kind = 'image'", (message_id,)).fetchone()
    if not row or not row['image']:
        return JSONResponse({'error': 'That picture no longer exists.'}, status_code=404)
    png = base64.b64decode(row['image'].split(',', 1)[1])
    return Response(png, media_type='image/png',
                    headers={'Content-Disposition': f'attachment; filename="beyond-picture-{message_id}.png"',
                             'Cache-Control': 'no-store'})
