"""BEYOND's web server: the pages, a health check, the AI status, chat (saved conversations), and settings."""
import asyncio
import base64
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt

from app import (autostart, briefing, chats, checklists, commands, config, engine, expenses, learning, lookups,
                 https, memory, models, notes, notify, personas, ports, prompts, reminders, rules, search_history, settings)

from app import builtin_engine, downloads, photo_jobs, image_jobs, speech_jobs, blackjack, followups, games, hangman, study_quiz, tictactoe, trivia
from app.tools import scan, speech, speech_to_text

models.initialize()
chats.initialize()
search_history.initialize()
followups.initialize()
games.initialize()
tictactoe.initialize()
trivia.initialize()
study_quiz.initialize()
blackjack.initialize()
hangman.initialize()
rules.initialize()
memory.initialize()
learning.initialize()
notes.initialize()
checklists.initialize()
expenses.initialize()
reminders.initialize()
briefing.initialize()

REMINDERS_CHAT = '⏰ Reminders'   # where a reminder goes off if the chat it was set in was deleted


def _fire_reminders():
    """Post every reminder whose time has come in its chat, with ✅ Done and 😴 Snooze. Each one is moved on first
    (to its next time, or marked sent), so a problem can't make it go off again and again. A repeating reminder
    missed while BEYOND was off goes off once, then continues."""
    for reminder_id, chat_id, message, recur, tz, due_at in reminders.due():
        repeat = ''
        if recur:
            rule, tz = json.loads(recur), tz or reminders.local_zone()
            previous = datetime.strptime(due_at, reminders.FMT).replace(tzinfo=timezone.utc)
            upcoming = reminders.next_due(rule, tz, previous_utc=previous)
            reminders.reschedule(reminder_id, upcoming)
            described = reminders.describe_rule(rule)
            repeat = f'\n🔁 {described[:1].upper() + described[1:]} · next {reminders.when_text(upcoming, tz)}'
        else:
            reminders.mark_sent(reminder_id)
        if not chat_id or not chats.exists(chat_id):
            chat_id = next((c['id'] for c in chats.list_chats() if c['title'] == REMINDERS_CHAT), None) or \
                chats.create(REMINDERS_CHAT)
        message_id = chats.add_message(chat_id, 'assistant', f'⏰ Reminder: {message}{repeat}', kind='reminder',
                                       buttons=commands.reminder_buttons(reminder_id))
        notify.show('reminder', '⏰ Reminder', message + repeat, chat_id,
                    buttons=[('✅ Done', f'remind:done:{reminder_id}'),
                             ('😴 10 min', f'remind:snooze:{reminder_id}:10'),
                             ('😴 1 hour', f'remind:snooze:{reminder_id}:60')],
                    on_button=lambda action, mid=message_id: _press(mid, action))


async def _watch_ai():
    """A popup if the AI server stops answering (checked every minute; once per outage)."""
    was_ok = None
    while True:
        try:
            status = await engine.status()
            state = status['state']
            if state == 'unreachable' and was_ok:
                notify.show('error', 'BEYOND: the AI stopped answering',
                            "BEYOND can't reach the AI server any more. Is it still running, with a model loaded?")
            elif state == 'error' and was_ok:
                notify.show('error', "BEYOND: the AI engine stopped", status['message'].split('\n')[0])
            if state not in ('not_set', 'starting'):
                was_ok = state == 'ok'
        except Exception:
            logging.exception('Checking the AI server failed')
        await asyncio.sleep(60)


ARRIVALS = ('reminder', 'briefing', 'vision', 'vision_error', 'image', 'image_error')   # messages BEYOND posts by itself; the page asks for new ones every few seconds
BRIEFING_CHAT = '☀️ Morning briefing'


def _send_due_briefing():
    """Post the morning briefing if it's due (marked as sent first, so it can never come twice)."""
    s = briefing.get_settings()
    if not briefing.is_due(s):
        return
    briefing.mark_sent(s)
    chat_id = s['chat_id'] if s['chat_id'] and chats.exists(s['chat_id']) else None
    if chat_id is None:   # the chat it was set up in was deleted
        chat_id = next((c['id'] for c in chats.list_chats() if c['title'] == BRIEFING_CHAT), None) or \
            chats.create(BRIEFING_CHAT)
    text = briefing.build(s)
    chats.add_message(chat_id, 'assistant', text, kind='briefing')
    notify.show('briefing', '☀️ Good morning', text.split('\n\n', 2)[1] if text.count('\n\n') > 1 else text, chat_id)


async def _briefing_loop():
    """Checks every 30 seconds whether the morning briefing is due."""
    while True:
        try:
            await asyncio.to_thread(_send_due_briefing)
        except Exception:
            logging.exception('The morning briefing failed')
        await asyncio.sleep(30)


async def _reminder_loop():
    """Runs for as long as BEYOND does: checks for due reminders every few seconds."""
    await asyncio.to_thread(reminders.warm_up)   # dateparser's first use is slow; do it now, not on the first /remind
    while True:
        try:
            await asyncio.to_thread(_fire_reminders)
        except Exception:
            logging.exception('Checking reminders failed')
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_app):
    photo_jobs.recover()
    image_jobs.recover()
    speech_jobs.recover()
    downloads.recover()
    tasks = [asyncio.create_task(loop()) for loop in (_reminder_loop, _briefing_loop, _watch_ai,
                                                      builtin_engine.supervise)]
    try:
        yield
    finally:
        await asyncio.gather(photo_jobs.shutdown(), image_jobs.shutdown(), speech_jobs.shutdown(),
                             asyncio.to_thread(downloads.shutdown))   # a running download stays resumable
        for task in tasks:
            task.cancel()
        await builtin_engine.stop()   # frees the model's memory; BEYOND starts it again next time


app = FastAPI(title='BEYOND', version=config.VERSION, docs_url=None, redoc_url=None, lifespan=lifespan)
app.include_router(photo_jobs.router)
app.include_router(image_jobs.router)
app.include_router(speech_jobs.router)
app.include_router(tictactoe.router)
app.include_router(trivia.router)
app.include_router(blackjack.router)
app.include_router(hangman.router)
app.mount('/static', StaticFiles(directory=config.WEB_DIR), name='static')


@app.middleware('http')
async def always_check_for_updates(request: Request, call_next):
    """Tell browsers (and phones) to check for a newer page or style before using a saved copy, so an updated BEYOND
    shows up straight away. Unchanged files are answered with "not modified", so this stays fast."""
    response = await call_next(request)
    response.headers.setdefault('Cache-Control', 'no-cache')
    return response
# Filled in by beyond.py when the server starts (port and address in use, and the server, for restarts).
app.state.running = {'host': config.LOCAL_ONLY_HOST, 'port': config.WEB_PORT, 'allow_network': False}
app.state.server = None
app.state.restart_requested = False


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=500)


class SendRequest(BaseModel):
    chat_id: int | None = None      # None = start a new chat
    content: str = Field(min_length=1, max_length=20000)


class Rename(BaseModel):
    title: str = Field(max_length=200)


class NewRule(BaseModel):
    text: str = Field(max_length=1000)


class ButtonPress(BaseModel):
    action: str = Field(max_length=300)


class SettingsChanges(BaseModel):
    changes: dict[str, Any]


class ConnectionTest(BaseModel):
    ai_server_url: str = Field(max_length=500)


def is_this_pc(request: Request):
    """General settings and host paths are local-PC-only; persona and house rules have narrow endpoints."""
    return bool(request.client) and request.client.host in ('127.0.0.1', '::1', 'localhost')


def only_this_pc():
    return JSONResponse({'error': 'Settings can only be changed on the PC BEYOND runs on, at '
                                  'http://127.0.0.1 (not from another device).'}, status_code=403)


# ---------- pages ----------

@app.get('/', include_in_schema=False)
def home():
    return FileResponse(config.WEB_DIR / 'index.html')


@app.get('/settings', include_in_schema=False)
def settings_page():
    return FileResponse(config.WEB_DIR / 'settings.html')


@app.get('/models', include_in_schema=False)
def models_page():
    return FileResponse(config.WEB_DIR / 'models.html')


class ModelChoice(BaseModel):
    model_config = {'extra': 'forbid'}
    id: str = Field(min_length=24, max_length=24, pattern=r'^[a-f0-9]+$')


class ModelProfile(ModelChoice):
    changes: dict[str, Any]


class ModelPath(BaseModel):
    model_config = {'extra': 'forbid'}
    path: str = Field(min_length=1, max_length=1024)


def _model_action(function, *args):
    try:
        return function(*args)
    except models.ModelError as exc:
        return JSONResponse({'error': str(exc)}, status_code=exc.status)
    except settings.SettingsError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    except OSError:
        logging.exception('Could not read or save the model list')
        return JSONResponse({'error': 'The model list could not be read or saved. Check the file permissions on this PC.'},
                            status_code=503)


@app.get('/api/models')
def get_models(request: Request):
    result = _model_action(models.view)
    if isinstance(result, dict):
        result['can_add'] = is_this_pc(request)
    return result


# Known models can be loaded and tuned from the home-network page. Host paths and the engine program can only
# be configured on this PC, following the existing Settings rule.
@app.post('/api/models/load')
def load_model(body: ModelChoice):
    return _model_action(models.load, body.id)


@app.post('/api/models/unload')
def unload_model():
    return _model_action(models.unload)


@app.post('/api/models/profile')
def save_model_profile(body: ModelProfile):
    return _model_action(models.save_profile, body.id, body.changes)


@app.post('/api/models/register')
def register_model(body: ModelPath, request: Request):
    if not is_this_pc(request):
        return only_this_pc()
    return _model_action(models.register, body.path)


# ---------- model downloads (Phase 35) ----------
# Anyone at home can watch progress; starting, pausing and cancelling downloads (gigabytes on this PC's disk) is
# for this PC only, like adding model files.

class RecommendedDownload(BaseModel):
    model_config = {'extra': 'forbid'}
    key: str = Field(min_length=1, max_length=40)
    accept: bool = False


class CustomDownload(BaseModel):
    model_config = {'extra': 'forbid'}
    repo: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=300)
    accept: bool = False


class DownloadJob(BaseModel):
    model_config = {'extra': 'forbid'}
    id: str = Field(min_length=12, max_length=12, pattern=r'^[a-f0-9]+$')


def _download_action(request, function, *args):
    if not is_this_pc(request):
        return JSONResponse({'error': 'Downloads can only be started or changed on the PC BEYOND runs on.'},
                            status_code=403)
    try:
        function(*args)
        return {**downloads.view(), 'can_download': True}
    except downloads.DownloadError as exc:
        return JSONResponse({'error': str(exc)}, status_code=exc.status)
    except OSError:
        logging.exception('A model download could not be saved')
        return JSONResponse({'error': "The download couldn't be saved. Check the models folder's permissions and free "
                                      'space.'}, status_code=503)


@app.get('/api/downloads')
def get_downloads(request: Request):
    return {**downloads.view(), 'can_download': is_this_pc(request)}


@app.get('/api/downloads/browse')
def browse_downloads(request: Request, repo: str = Query(min_length=1, max_length=300)):
    if not is_this_pc(request):
        return only_this_pc()
    try:
        return downloads.browse(repo)
    except downloads.DownloadError as exc:
        return JSONResponse({'error': str(exc)}, status_code=exc.status)


@app.post('/api/downloads/recommended')
def download_recommended(body: RecommendedDownload, request: Request):
    return _download_action(request, downloads.start_recommended, body.key, body.accept)


@app.post('/api/downloads/custom')
def download_custom(body: CustomDownload, request: Request):
    return _download_action(request, downloads.start_custom, body.repo, body.name, body.accept)


@app.post('/api/downloads/pause')
def pause_download(body: DownloadJob, request: Request):
    return _download_action(request, downloads.pause, body.id)


@app.post('/api/downloads/resume')
def resume_download(body: DownloadJob, request: Request):
    return _download_action(request, downloads.resume, body.id)


@app.post('/api/downloads/cancel')
def cancel_download(body: DownloadJob, request: Request):
    return _download_action(request, downloads.cancel, body.id)


@app.post('/api/downloads/clear')
def clear_downloads(request: Request):
    return _download_action(request, downloads.clear_finished)


@app.get('/search-history', include_in_schema=False)
def search_history_page():
    return FileResponse(config.WEB_DIR / 'search-history.html')


@app.get('/api/search-history')
def list_search_history(query: str = Query('', max_length=200), tool: str = Query('', max_length=16),
                        start: str = Query('', max_length=10), end: str = Query('', max_length=10),
                        origin: str = Query('', max_length=16), offset: int = Query(0, ge=0, le=1000000),
                        limit: int = Query(25, ge=1, le=50)):
    try:
        return search_history.browse(query,tool,start,end,origin,offset,limit)
    except (ValueError, OverflowError):
        return JSONResponse({'error':'Use valid dates (YYYY-MM-DD), with the end on or after the start, and a listed tool.'},
                            status_code=400)


class DeleteSearches(BaseModel):
    model_config = {'extra':'forbid'}
    ids: list[StrictInt] = Field(min_length=1,max_length=100)


@app.post('/api/search-history/delete')
def delete_searches(body: DeleteSearches):
    try:
        return {'deleted':search_history.delete(body.ids)}
    except ValueError as exc:
        return JSONResponse({'error':str(exc)},status_code=400)


@app.post('/api/search-history/{identifier}/repeat')
async def repeat_search(identifier: int):
    entry = await asyncio.to_thread(search_history.get,identifier)
    if entry is None:
        return JSONResponse({'error':'That search was deleted or no longer exists.'},status_code=404)
    reply = await asyncio.to_thread(commands.run,entry['command'])
    chat_id = chats.create('Search again: '+entry['query'])
    chats.add_message(chat_id,'user',entry['command'],kind='command')
    message_id = chats.add_message(chat_id,'assistant',reply.text,kind='command',buttons=reply.buttons)
    followups.save(chat_id,message_id,reply.lookup_context)
    followups.save_pending(chat_id,message_id,reply.pending_lookup)
    return {'chat_id':chat_id}


# ---------- status ----------

@app.get('/api/health')
def health():
    """Quick "is BEYOND running?" check, used by the page now and by the self-test later."""
    return {'status': 'ok', 'name': 'BEYOND', 'version': config.VERSION, 'phase': config.PHASE,
            'https_port': app.state.running.get('https_port')}   # the secure address for other devices, if on


@app.get('/api/https/certificate')
def download_certificate():
    """Settings → Download certificate: BEYOND's certificate authority (public; no secrets in it), for installing
    on other devices so their browsers trust BEYOND's secure address without a warning (app/https.py). Only
    while the secure address is on."""
    if not app.state.running.get('https_port'):
        return JSONResponse({'error': 'The secure address is off. Turn on "Allow other devices on my network" '
                                      'and restart BEYOND.'}, status_code=404)
    try:
        path = https.authority_file()
    except (ImportError, OSError, ValueError):
        logging.exception('Could not prepare the certificate for download')
        return JSONResponse({'error': 'The certificate could not be prepared.'}, status_code=503)
    return Response(path.read_bytes(), media_type='application/x-x509-ca-cert',
                    headers={'Content-Disposition': 'attachment; filename="BEYOND-certificate.crt"',
                             'Cache-Control': 'no-store'})


@app.get('/api/ai-status')
async def ai_status():
    return await engine.status()


# ---------- chat ----------

def _recent(request):
    return [message.model_dump() for message in request.messages][-config.HISTORY_LIMIT:]


@app.post('/api/chat')
async def chat(request: ChatRequest):
    """The whole reply at once (handy for tests and scripts; the page uses /api/chat/stream)."""
    try:
        reply = await engine.chat(_recent(request))
    except engine.EngineError as exc:
        return JSONResponse({'error': str(exc)}, status_code=503)
    return {'reply': reply}


@app.post('/api/chat/stream')
async def chat_stream(body: SendRequest):
    """Send one message in a saved chat (or start a new one) and get the reply as it's written: one JSON event per
    line ({"type": "chat" | "token" | "done" | "error", ...}). The question is saved straight away and the answer
    when it's finished; if the page disconnects (Stop), what was written so far is saved, marked as stopped, and the
    AI stops writing. If nothing was answered at all, the question is taken back out, as if it was never sent."""
    content = body.content.strip()
    if not content:
        return JSONResponse({'error': 'The message is empty.'}, status_code=400)
    new_chat = body.chat_id is None
    if not new_chat and not chats.exists(body.chat_id):
        return JSONResponse({'error': 'That chat no longer exists. Start a new one.'}, status_code=404)
    if content.startswith('/'):
        return _command_reply(body.chat_id, content)
    recalled = search_history.recall_request(content)
    if recalled is not None:
        return _command_reply(body.chat_id, content, run_as='/searchhistory ' + recalled)
    web_request = await asyncio.to_thread(followups.web_request, body.chat_id, content)
    if web_request:
        if web_request['kind'] == 'command':
            return _command_reply(body.chat_id, content, run_as=web_request['command'], follow_action=web_request)
        return _command_reply(body.chat_id, content, prepared=commands.Reply(web_request['text']))
    weather_request = (await asyncio.to_thread(followups.weather_request, body.chat_id, content)
                       if settings.load()['auto_lookup'] else None)
    if weather_request:
        if weather_request['kind']=='command':
            return _command_reply(body.chat_id, content, run_as=weather_request['command'], follow_action=weather_request)
        reply=(commands.weather_confirmation_reply(weather_request) if weather_request['kind']=='weather_confirm'
               else commands.Reply(weather_request['text'],pending_lookup=weather_request.get('pending')))
        return _command_reply(body.chat_id, content, prepared=reply)
    followup = await asyncio.to_thread(followups.resolve, body.chat_id, content)
    if followup and followup['kind'] in ('command','weather_day'):
        return _command_reply(body.chat_id, content, run_as=followup['command'], follow_action=followup)
    if followup and followup['kind'] in ('fact','clarify','clarify_search'):
        reply = await asyncio.to_thread(followups.answer,followup)
        return _command_reply(body.chat_id, content, prepared=reply)
    chat_id = chats.create(content) if new_chat else body.chat_id
    question_id = chats.add_message(chat_id, 'user', content)
    values = settings.load()
    history, sent_ids = chats.recent_messages(chat_id, engine.history_window(chats.message_count(chat_id)),
                                              with_ids=True)

    def undo():   # nothing was answered: take the question back out, as if it was never sent
        chats.remove_message(question_id)
        if new_chat and chats.message_count(chat_id, kind=None) == 0:
            chats.delete(chat_id)

    opening = {'type': 'chat', 'id': chat_id, 'new': new_chat, 'title': chats.title_from(content)}
    extra = followup.get('notes','') if followup else ''
    return _answer(chat_id, history, _background(content, sent_ids, values,extra), opening, undo, question=content,
                   pickup=content if values['auto_facts'] else None,
                   prior_context=followup['state'] if followup else None, suppress_auto=bool(followup))


def _background(question, sent_ids, values, extra=''):
    """Notes for this reply only: related exchanges from older conversations (any chat), what the ratings taught,
    and anything else for this reply (Try again's note)."""
    parts = [memory.recall_block(question, sent_ids) if values['recall'] else '',
             learning.prompt_block(question, sent_ids), extra]
    return '\n\n'.join(part for part in parts if part)


def _answer(chat_id, history, background, opening, undo, question=None, pickup=None, retry_of=None,
            temperature=None, prior_context=None, suppress_auto=False):
    """Stream an AI answer to the end of `history` and save it with 👍 👎 🔄 under it. If the page disconnects
    (Stop), what was written so far is saved, marked as stopped; if nothing was written at all, undo() runs.
    `question`: checked for an automatic lookup (weather, news, web) first, whose results go in the notes."""
    budget = learning.max_tokens()
    wanted = lookups.detect(question) if question and not suppress_auto else None
    found = wanted if wanted and settings.load()['auto_lookup'] else None
    if wanted and not found:   # needs current information, but automatic lookups are off
        background = '\n\n'.join(part for part in (background, lookups.NOT_CHECKED) if part)

    async def events():
        global ANSWERS_IN_PROGRESS
        answer, finished, saved, lookup = [], False, False, None
        active_context = prior_context
        ANSWERS_IN_PROGRESS += 1
        writing = True
        try:
            yield json.dumps(opening) + '\n'
            notes = background
            if not found:
                notes='\n\n'.join(part for part in (background,
                    'No new lookup was performed for this reply. Never promise to check/search later: your reply '
                    'cannot trigger a tool after it ends. BEYOND has built-in web search through /web <query>; '
                    'do not claim it lacks web access. Suggest /web for unknown facts, /weather for forecasts, '
                    'or /news for headlines. Use any supplied previous result only as past data.') if part)
            if found:
                yield json.dumps({'type': 'status', 'text': lookups.status(*found)}) + '\n'
                result = await asyncio.to_thread(lookups.run, question, *found)
                lookup = lookups.saved(result)
                active_context = followups.snapshot(result['kind'],result['argument'],result['raw']) if result['ok'] else None
                notes = '\n\n'.join(part for part in (background, lookups.notes(result)) if part)
                # Written by BEYOND, so "Looked up" only ever appears when a lookup really ran.
                yield json.dumps({'type': 'lookup', **lookup}) + '\n'
            try:
                thinking, stats = False, None
                async for piece in engine.chat_stream(history, notes, max_tokens=budget, temperature=temperature):
                    if isinstance(piece, engine.Stats):
                        stats = dict(piece)
                        continue
                    if piece is engine.THINKING:
                        if not thinking and not answer:   # once: the page shows "Thinking…" with a timer
                            thinking = True
                            yield json.dumps({'type': 'status', 'text': '💭 Thinking…', 'thinking': True}) + '\n'
                        continue
                    answer.append(piece)
                    yield json.dumps({'type': 'token', 'text': piece}) + '\n'
                finished = True
            except engine.EngineError as exc:
                yield json.dumps({'type': 'error', 'message': str(exc)}) + '\n'
                notify.show('error', 'BEYOND: the AI had a problem', str(exc), chat_id)
            text = ''.join(answer).strip()
            cleaned = lookups.without_fake_mark(text)
            if cleaned != text and cleaned:
                text = cleaned
                yield json.dumps({'type': 'replace', 'text': text}) + '\n'
            if finished and text:
                answer_id = chats.add_message(chat_id, 'assistant', text, retry_of=retry_of, lookup=lookup,
                                              stats=stats)
                if found or prior_context:
                    followups.save(chat_id,answer_id,active_context,for_retry=True)
                previous = chats.previous_answer(chat_id, answer_id)
                buttons = learning.rating_buttons(answer_id)
                offer = '' if found else lookups.offer_search(question or '', text)
                if offer:   # the answer sounds unsure and nothing was looked up: one tap searches the web
                    buttons = buttons + [[{'label': '🔎 Search the web for this', 'send': '/web ' + offer}]]
                chats.set_buttons(answer_id, buttons)
                saved = True
                if previous and learning.has_retry(previous['buttons']):   # 🔄 is only for the newest answer
                    chats.set_buttons(previous['id'], learning.without_retry(previous['buttons']))
                voice = settings.load()
                spoken = _start_speech(answer_id) if voice['speech_enabled'] and voice['speech_auto'] else None
                yield json.dumps({'type': 'message', 'id': answer_id, 'buttons': buttons,
                                  'speech': spoken, 'speakable': True, 'stats': stats}) + '\n'
                # "done": the answer is complete and saved, so the page can let you type again. Anything after this
                # (the automatic fact pickup) is extra and arrives a little later on the same connection.
                yield json.dumps({'type': 'done'}) + '\n'
                ANSWERS_IN_PROGRESS -= 1
                writing = False
                notify.show('reply', 'BEYOND replied', text, chat_id)   # only if you're not looking at the page
                if pickup and memory.wants_pickup(pickup):
                    note = await _pick_up_facts(pickup)
                    if note:
                        note_id = chats.add_message(chat_id, 'assistant', note, kind='note')
                        yield json.dumps({'type': 'note', 'id': note_id, 'text': note}) + '\n'
        finally:   # also runs when Stop cancels the stream
            if writing:
                ANSWERS_IN_PROGRESS -= 1
            if not saved:
                text = lookups.without_fake_mark(''.join(answer))
                if text:
                    partial_id = chats.add_message(chat_id, 'assistant', text, stopped=True, retry_of=retry_of, lookup=lookup)
                    if found or prior_context:
                        followups.save(chat_id,partial_id,active_context)
                else:
                    undo()

    return StreamingResponse(events(), media_type='application/x-ndjson',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.post('/api/messages/{message_id}/retry')
async def try_again(message_id: int):
    """🔄 Try again: a different answer to the same question. The old answer stays in the chat (marked as
    replaced, and no longer sent to the AI); the new one streams like any answer. Only for the newest answer."""
    old = chats.get_message(message_id)
    if old is None:
        return JSONResponse({'error': 'That answer no longer exists.'}, status_code=404)
    if old['kind'] != 'chat' or not learning.has_retry(old['buttons']):
        return JSONResponse({'error': 'That answer can\'t be tried again any more.'}, status_code=409)
    chat_id = old['chat_id']
    latest = chats.latest_answer(chat_id)
    if latest is None or latest['id'] != message_id:
        return JSONResponse({'error': 'Only the newest answer can be tried again. Ask again below instead.'},
                            status_code=409)
    # The same window the first answer used (the old answer isn't counted), so the AI can reuse what it read.
    window = engine.history_window(chats.message_count(chat_id) - 1)
    chats.set_buttons(message_id, [], kind='retried')
    history, sent_ids = chats.recent_messages(chat_id, window, with_ids=True)
    if not history or history[-1]['role'] != 'user':
        chats.set_buttons(message_id, old['buttons'], kind='chat')
        return JSONResponse({'error': 'There\'s no question to answer again.'}, status_code=409)
    learning.rate(message_id, -1, 'retry')

    def undo():   # no new answer: put the old one back as it was
        chats.set_buttons(message_id, old['buttons'], kind='chat')
        learning.set_rating(message_id, old['rating'], old['reason'])

    context = followups.for_message(message_id)
    grounded = followups.context_notes(context,history[-1]['content']) if context and followups.REFERENCE.search(history[-1]['content']) else ''
    extra = '\n\n'.join(part for part in (learning.retry_note(old['content']),grounded) if part)
    background = _background(history[-1]['content'], sent_ids, settings.load(), extra)
    return _answer(chat_id, history, background, {'type': 'retry', 'id': message_id}, undo,
                   question=history[-1]['content'], retry_of=message_id,
                   temperature=min(1.1, config.TEMPERATURE + 0.3),
                   prior_context=context if grounded else None, suppress_auto=bool(grounded))

ANSWERS_IN_PROGRESS = 0     # chat answers being written right now
PICKUP_LOCK = asyncio.Lock()


async def _pick_up_facts(message):
    """After an answer: ask the AI for lasting facts the person said about themselves, and save them.
    Skipped (not queued) while another answer is being written or another pickup is running, so it never makes
    anyone wait. Returns the "Noted for next time" note, or '' if nothing was saved."""
    if ANSWERS_IN_PROGRESS or PICKUP_LOCK.locked():
        return ''
    async with PICKUP_LOCK:
        try:
            raw = await engine.complete(memory.pickup_messages(message), max_tokens=120, temperature=0.1)
        except engine.EngineError:
            logging.warning('Automatic fact pickup skipped: the AI could not be reached')
            return ''
        saved = []
        for fact in memory.parse_facts(raw)[:3]:
            status, text = await asyncio.to_thread(memory.add, fact, 'auto')
            if status == 'added':
                saved.append(text)
    if not saved:
        return ''
    return '🧠 Noted for next time: ' + '; '.join(saved) + '\n(/memories to review, /forget to remove)'


def _start_speech(message_id, text=None):
    try:
        return speech_jobs.start(message_id, text)
    except speech.SpeechError as exc:
        with chats.connect() as db:
            db.execute("UPDATE messages SET speech_state = 'error', speech_error = ? WHERE id = ?",
                       (str(exc), message_id))
        return {'state': 'error', 'error': str(exc), 'engine': '', 'truncated': False, 'url': ''}


def _command_reply(chat_id, content, run_as=None, prepared=None, follow_action=None):
    """A /command: BEYOND answers it itself. Both are saved in the chat (so they're there when you come back) but
    marked as commands, so they're never sent to the AI. Same event stream as an AI answer, so the page needs no
    special handling. A new chat is created after the command runs, so it's named from the safe version of the
    command (a /qr wifi password never ends up in the chat list)."""
    async def events():
        if follow_action:
            tool, _, argument = follow_action['command'].lstrip('/').partition(' ')
            label = search_history.TOOLS.get(tool,tool)
            yield json.dumps({'type':'status','text':f'Checking {label}: {argument}…'}) + '\n'
        if content.split()[0].lower() == '/trivia':
            yield json.dumps({'type': 'status', 'text': 'Getting trivia ready…'}) + '\n'
        try:
            reply = prepared if prepared is not None else await asyncio.to_thread(commands.run, run_as or content)
            if follow_action and follow_action['kind']=='weather_day':
                reply = followups.weather_answer(reply,follow_action['day'])
        except Exception:   # a bug in one command shouldn't break the chat
            logging.exception('Command failed: %s', content.split()[0])
            reply = commands.Reply(f'Sorry, {content.split()[0]} ran into a problem. Please try again.')
        shown = reply.saved_command or content
        new_chat = chat_id is None
        current = chats.create(shown) if new_chat else chat_id
        yield json.dumps({'type': 'chat', 'id': current, 'new': new_chat, 'title': chats.title_from(shown)}) + '\n'
        chats.add_message(current, 'user', shown, kind='command')
        if reply.saved_command:   # e.g. a Wi-Fi password: hidden on the page too, not only in the saved chat
            yield json.dumps({'type': 'question', 'text': reply.saved_command}) + '\n'
        if reply.speech_text == '':
            last = chats.latest_answer(current)
            if last:
                reply.speech_text = reply.text = last['content']
            else:
                reply.text = 'There is no AI answer to read in this chat yet.\n\n' + speech.HELP
                reply.speech_text = None
        message_id = (reply.save_message(current) if reply.save_message else
                      chats.add_message(current, 'assistant', reply.text, kind='command', buttons=reply.buttons,
                                        image=reply.image, game=reply.game))
        followups.save(current,message_id,reply.lookup_context)
        followups.save_pending(current,message_id,reply.pending_lookup)
        if reply.on_saved:   # e.g. /remind: the reminder goes off in this chat
            reply.on_saved(current)
        spoken = _start_speech(message_id, reply.speech_text) if reply.speech_text is not None else None
        yield json.dumps({'type': 'token', 'text': reply.text, 'kind': 'command'}) + '\n'
        # The saved message's id, buttons and picture, so the page can show them and send presses back.
        yield json.dumps({'type': 'message', 'id': message_id, 'buttons': reply.buttons,
                          'image': reply.image, 'game': reply.game, 'speech': spoken,
                          'speakable': reply.speech_text is not None, 'speak_requested': spoken is not None}) + '\n'
        yield json.dumps({'type': 'done'}) + '\n'

    return StreamingResponse(events(), media_type='application/x-ndjson')


@app.get('/api/reminders/fired')
def fired_reminders(after: int = -1):
    """Reminders that went off since message `after`, for the page (which asks every few seconds). after=-1 only
    returns where to start, so opening the page doesn't replay old reminders."""
    latest = chats.latest_message_id(ARRIVALS)
    if after < 0:
        return {'latest': latest, 'items': []}
    items = chats.messages_after(ARRIVALS, after)
    return {'latest': items[-1]['id'] if items else after, 'items': items}


def _press(message_id, action):
    """A button pressed on a popup (e.g. a reminder's Snooze): same rules as on the page."""
    message = chats.get_message(message_id)
    if message is None or action not in {b.get('action') for row in message['buttons'] for b in row}:
        return
    reply = commands.press(action, message)
    if reply is not None:
        chats.update_message(message_id, reply.text, reply.buttons, game=reply.game)


class Presence(BaseModel):
    visible: bool


@app.post('/api/presence')
def presence(body: Presence):
    """The page says whether it's on screen, so popups only come when you're not looking at BEYOND."""
    notify.page_seen(body.visible)
    return {'ok': True}


class PopupTest(BaseModel):
    kind: Literal['reply', 'reminder', 'error'] = 'error'


@app.post('/api/notify/test')
def test_popup(body: PopupTest, request: Request):
    """"Send a test popup" on the Settings page. Shown even while you're looking, so you can see it."""
    if not is_this_pc(request):
        return only_this_pc()
    examples = {'reply': ('BEYOND replied', 'This is what a popup looks like when an answer is ready.'),
                'reminder': ('⏰ Reminder', 'This is what a reminder popup looks like.'),
                'error': ('BEYOND: test problem', 'This is what a popup looks like when something goes wrong.')}
    title, text = examples[body.kind]
    problem = notify.show(body.kind, title, text, force=True)
    if problem:
        return JSONResponse({'error': f'No popup: {problem}.'}, status_code=400)
    return {'ok': True, 'would_show_normally': notify.why_not(body.kind) or 'yes'}


@app.post('/api/messages/{message_id}/press')
async def press_button(message_id: int, body: ButtonPress):
    """Someone pressed a button under a message: run its action and change the message in place.
    Only actions that are actually on this message's buttons are accepted."""
    message = chats.get_message(message_id)
    if message is None:
        return JSONResponse({'error': 'That message no longer exists.'}, status_code=404)
    allowed = {b.get('action') for row in message['buttons'] for b in row}
    if body.action not in allowed:
        return JSONResponse({'error': 'That button is no longer available.'}, status_code=409)
    try:
        reply = await asyncio.to_thread(commands.press, body.action, message)
    except Exception:
        logging.exception('Button failed: %s', body.action.split(':')[0])
        return JSONResponse({'error': 'That button ran into a problem. Please try again.'}, status_code=500)
    if reply is None:
        return JSONResponse({'error': 'That button is no longer available.'}, status_code=409)
    chats.update_message(message_id, reply.text, reply.buttons, game=reply.game)
    return {'id': message_id, 'text': reply.text, 'buttons': reply.buttons, 'toast': reply.toast, 'game': reply.game}


@app.get('/api/expenses.csv')
def expenses_csv(period: str = 'all'):
    """📄 Download CSV under a /spent report: that period's expenses, UTF-8 with a BOM so Excel opens it."""
    if not re.fullmatch(r'all|y\d{4}|m\d{4}(0[1-9]|1[0-2])', period):
        return JSONResponse({'error': 'Unknown period.'}, status_code=400)
    data, name = expenses.csv_file(expenses.period_from_token(period))
    return Response(data, media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{name}"', 'Cache-Control': 'no-store'})


@app.get('/api/commands')
def list_commands():
    """The commands, for the list the page shows when you type "/"."""
    return commands.menu()


# ---------- house rules ----------

@app.get('/api/rules')
def list_rules():
    return rules.all_rules()


@app.post('/api/rules')
def add_rule(body: NewRule):
    try:
        rule_id = rules.add(body.text)
    except ValueError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    if rule_id is None:
        return JSONResponse({'error': 'That rule is already there.'}, status_code=400)
    return {'id': rule_id, 'rules': rules.all_rules()}


@app.delete('/api/rules/{rule_id}')
def delete_rule(rule_id: int):
    if not rules.remove(rule_id):
        return JSONResponse({'error': 'That rule no longer exists.'}, status_code=404)
    return {'rules': rules.all_rules()}


# ---------- saved conversations ----------

@app.get('/api/chats')
def list_chats():
    return chats.list_chats()


@app.get('/api/chats/{chat_id}')
def get_chat(chat_id: int):
    chat = chats.get(chat_id)
    return chat if chat else JSONResponse({'error': 'That chat no longer exists.'}, status_code=404)


@app.patch('/api/chats/{chat_id}')
def rename_chat(chat_id: int, body: Rename):
    try:
        found = chats.rename(chat_id, body.title)
    except ValueError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    return {'ok': True} if found else JSONResponse({'error': 'That chat no longer exists.'}, status_code=404)


@app.delete('/api/chats/{chat_id}')
def delete_chat(chat_id: int):
    image_jobs.remove_previews(chat_id)
    return {'ok': True} if chats.delete(chat_id) else JSONResponse({'error': 'That chat no longer exists.'},
                                                                   status_code=404)



# ---------- voice input ----------

@app.post('/api/transcribe')
async def transcribe_recording(request: Request):
    """The 🎤 button: a recording from the browser (raw body, at most 10 MB) -> its words, offline. Nothing is
    saved; the page puts the words in the message box and sends them like typed text."""
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > speech_to_text.MAX_RECORDING_BYTES:
            return JSONResponse({'error': 'That recording is too long. Keep it under two minutes.'}, status_code=413)
        body.extend(chunk)
    kind = request.headers.get('content-type', '')
    suffix = '.mp4' if 'mp4' in kind or 'aac' in kind else '.ogg' if 'ogg' in kind else '.wav' if 'wav' in kind \
        else '.webm'
    try:
        text, seconds = await asyncio.to_thread(speech_to_text.transcribe, bytes(body), suffix)
    except speech_to_text.SpeechBusy as exc:
        return JSONResponse({'error': str(exc)}, status_code=409)
    except speech_to_text.SpeechError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    except ImportError:
        return JSONResponse({'error': 'Voice input is not installed. Install requirements-lock.txt and restart '
                                      'BEYOND.'}, status_code=503)
    except Exception:
        logging.exception('Turning a recording into text failed')
        return JSONResponse({'error': "Voice input isn't working right now. Please type your message instead."},
                            status_code=503)
    if not text:
        return JSONResponse({'error': "I didn't catch any words. Try again a little closer to the microphone."},
                            status_code=400)
    return {'text': text, 'seconds': round(seconds, 1)}


# ---------- photos and offline text recognition ----------

@app.post('/api/scan')
async def scan_photo(request: Request, chat_id: int | None = None):
    """Read a bounded raw image body in a worker; save the photo and result only after success."""
    if chat_id is not None and not chats.exists(chat_id):
        return JSONResponse({'error': 'That chat no longer exists. Start a new one.'}, status_code=404)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > scan.MAX_PHOTO_BYTES:
            return JSONResponse({'error': 'Photos must be 10 MB or smaller.'}, status_code=413)
        body.extend(chunk)
    try:
        png, text, seconds = await asyncio.to_thread(scan.read_photo, bytes(body))
    except scan.ScanBusy as exc:
        return JSONResponse({'error': str(exc)}, status_code=409)
    except scan.ScanError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    except ImportError:
        return JSONResponse({'error': 'The text reader is not installed. Install requirements-lock.txt and restart BEYOND.'},
                            status_code=503)
    except Exception:
        logging.exception('Reading text from a photo failed')
        return JSONResponse({'error': "The text reader could not read that photo. Please try another picture."},
                            status_code=503)
    # A chat could have been deleted while the OCR worker was running.
    if chat_id is not None and not chats.exists(chat_id):
        return JSONResponse({'error': 'That chat was deleted while the photo was being read.'}, status_code=404)
    new_chat = chat_id is None
    current = chats.create('Scan text from a photo') if new_chat else chat_id
    image = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
    photo_id = chats.add_message(current, 'user', 'Photo for /scan', kind='photo', image=image)
    content = text or "I couldn't find readable text. Try a sharper, well-lit photo with printed text."
    answer_id = chats.add_message(current, 'assistant', content, kind='scan')
    return {'chat_id': current, 'new': new_chat, 'photo_id': photo_id, 'id': answer_id,
            'text': content, 'has_text': bool(text), 'image': image, 'seconds': round(seconds, 2)}


# ---------- settings ----------

def _settings_view(request, values=None):
    values = values or settings.load()
    running = app.state.running
    return {
        'values': values,
        'defaults': config.DEFAULTS,
        'personas': personas.options(),
        'default_prompt': prompts.default_prompt(),
        'custom_prompt_max_chars': prompts.MAX_CUSTOM_CHARS,
        'running': running,
        'restart_needed': [key for key in config.RESTART_SETTINGS if values[key] != running[key.replace('web_', '')]],
        'network_addresses': [{'adapter': a, 'address': ip} for a, ip in ports.network_addresses()],
        'can_change': is_this_pc(request),
    }


@app.get('/api/settings')
def get_settings(request: Request):
    return _settings_view(request)



class PromptChoice(BaseModel):
    model_config = {'extra': 'forbid'}
    custom_prompt: str = Field(max_length=16000)
    custom_prompt_enabled: bool = False


@app.post('/api/prompt')
def save_prompt(body: PromptChoice):
    # A narrow text preference like house rules; no engine, file path or network changes.
    try:
        values=settings.save(body.model_dump())
    except settings.SettingsError as exc:
        return JSONResponse({'error':str(exc)},status_code=400)
    return {key:values[key] for key in ('custom_prompt','custom_prompt_enabled')}



class PromptDraft(BaseModel):
    model_config = {'extra': 'forbid'}
    prompt: str = Field(min_length=1,max_length=16000)


PROMPT_IMPROVE_LOCK = asyncio.Lock()


@app.post('/api/prompt/improve')
async def improve_prompt(body: PromptDraft):
    draft=body.prompt.strip()
    if not draft:
        return JSONResponse({'error':'Enter a prompt to improve.'},status_code=400)
    if PROMPT_IMPROVE_LOCK.locked() or builtin_engine.busy():
        return JSONResponse({'error':'The AI is busy. Try improving the prompt after its current reply finishes.'},status_code=409)
    async with PROMPT_IMPROVE_LOCK:
        try:
            improved=await engine.complete(prompts.improvement_messages(draft),max_tokens=600,temperature=0.2)
        except engine.EngineError as exc:
            return JSONResponse({'error':str(exc)},status_code=503)
    improved=improved.strip()
    lines=improved.splitlines()
    fence=chr(96)*3
    if len(lines)>2 and lines[0].startswith(fence) and lines[-1].strip()==fence:
        improved='\n'.join(lines[1:-1]).strip()
    if not improved or len(improved)>prompts.MAX_CUSTOM_CHARS:
        return JSONResponse({'error':'The AI did not return a usable prompt. Your draft is unchanged.'},status_code=502)
    # Return a draft only. Applying it still requires the explicit Save prompt action.
    return {'prompt':improved,'words':len(improved.split())}


class PersonaChoice(BaseModel):
    model_config = {'extra': 'forbid'}
    persona: str = Field(min_length=1, max_length=30)
    persona_enabled: bool = False


@app.post('/api/persona')
def save_persona(body: PersonaChoice):
    """A speaking-style preference, editable from other devices like the existing house rules.
    Only the preset and its on/off switch can be changed here, never engine paths or general settings."""
    try:
        values = settings.save({'persona': body.persona, 'persona_enabled': body.persona_enabled})
    except settings.SettingsError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    logging.info('Persona changed to %s', values['persona'])
    return {'persona': values['persona'], 'persona_enabled': values['persona_enabled']}


@app.post('/api/settings')
def save_settings(body: SettingsChanges, request: Request):
    if not is_this_pc(request):
        return only_this_pc()
    try:
        cleaned = settings.validate(body.changes)
    except settings.SettingsError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    running = app.state.running
    new_port = cleaned.get('web_port', running['port'])
    new_host = (config.NETWORK_HOST if cleaned.get('allow_network', running['allow_network'])
                else config.LOCAL_ONLY_HOST)
    if new_port != running['port']:   # check the new port before saving, so a restart can't fail on it
        problem = ports.problem(new_host, new_port)
        if problem:
            first_line = problem.split('\n')[0].replace("BEYOND can't start: port", 'Port')
            return JSONResponse({'error': first_line + ' Please pick another.'}, status_code=400)
    if 'start_with_windows' in cleaned and cleaned['start_with_windows'] != autostart.is_on():
        problem = autostart.apply(cleaned['start_with_windows'])   # the Windows startup entry, only when it changes
        if problem:
            return JSONResponse({'error': problem}, status_code=400)
    return _settings_view(request, settings.save(cleaned))


@app.post('/api/settings/reset')
def reset_settings(request: Request):
    if not is_this_pc(request):
        return only_this_pc()
    if autostart.is_on():
        autostart.apply(False)
    return _settings_view(request, settings.reset())


@app.post('/api/settings/test')
async def test_connection(body: ConnectionTest, request: Request):
    if not is_this_pc(request):
        return only_this_pc()
    try:
        url = settings.validate({'ai_server_url': body.ai_server_url})['ai_server_url']
    except settings.SettingsError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    return await engine.status(url)


@app.post('/api/engine/restart')
def restart_engine(request: Request):
    """Settings → Restart engine: start the built-in engine again (also after it gave up following crashes)."""
    if not is_this_pc(request):
        return only_this_pc()
    if settings.load()['ai_mode'] != 'builtin':
        return JSONResponse({'error': 'The built-in engine is not chosen.'}, status_code=409)
    settings.save({'engine_enabled': True})
    builtin_engine.request_restart()
    return {'ok': True}


@app.post('/api/restart')
async def restart(request: Request):
    """Restart BEYOND so a new port or network setting takes effect (beyond.py starts it again)."""
    if not is_this_pc(request):
        return only_this_pc()
    if app.state.server is None:
        return JSONResponse({'error': 'BEYOND was not started with beyond.py, so it can\'t restart itself.'},
                            status_code=409)
    values = settings.load()
    app.state.restart_requested = True
    asyncio.get_running_loop().call_later(0.5, setattr, app.state.server, 'should_exit', True)   # after replying
    return {'url': f"http://127.0.0.1:{values['web_port']}/settings"}
