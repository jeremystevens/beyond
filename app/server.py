"""BEYOND's web server: the pages, a health check, the AI status, chat (saved conversations), and settings."""
import asyncio
import base64
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import (autostart, briefing, chats, checklists, commands, config, engine, expenses, learning, lookups,
                 memory, notes, notify, ports, reminders, rules, settings)

from app.tools import scan

chats.initialize()
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
            state = (await engine.status())['state']
            if state == 'unreachable' and was_ok:
                notify.show('error', 'BEYOND: the AI stopped answering',
                            "BEYOND can't reach the AI server any more. Is it still running, with a model loaded?")
            if state != 'not_set':
                was_ok = state == 'ok'
        except Exception:
            logging.exception('Checking the AI server failed')
        await asyncio.sleep(60)


ARRIVALS = ('reminder', 'briefing')   # messages BEYOND posts by itself; the page asks for new ones every few seconds
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
    tasks = [asyncio.create_task(loop()) for loop in (_reminder_loop, _briefing_loop, _watch_ai)]
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title='BEYOND', version=config.VERSION, docs_url=None, redoc_url=None, lifespan=lifespan)
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
    """Settings can only be changed from the PC BEYOND runs on (until there's a login, Phase 38)."""
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


# ---------- status ----------

@app.get('/api/health')
def health():
    """Quick "is BEYOND running?" check, used by the page now and by the self-test later."""
    return {'status': 'ok', 'name': 'BEYOND', 'version': config.VERSION, 'phase': config.PHASE}


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
    return _answer(chat_id, history, _background(content, sent_ids, values), opening, undo, question=content,
                   pickup=content if values['auto_facts'] else None)


def _background(question, sent_ids, values, extra=''):
    """Notes for this reply only: related exchanges from older conversations (any chat), what the ratings taught,
    and anything else for this reply (Try again's note)."""
    parts = [memory.recall_block(question, sent_ids) if values['recall'] else '',
             learning.prompt_block(question, sent_ids), extra]
    return '\n\n'.join(part for part in parts if part)


def _answer(chat_id, history, background, opening, undo, question=None, pickup=None, retry_of=None,
            temperature=None):
    """Stream an AI answer to the end of `history` and save it with 👍 👎 🔄 under it. If the page disconnects
    (Stop), what was written so far is saved, marked as stopped; if nothing was written at all, undo() runs.
    `question`: checked for an automatic lookup (weather, news, web) first, whose results go in the notes."""
    budget = learning.max_tokens()
    wanted = lookups.detect(question) if question else None
    found = wanted if wanted and settings.load()['auto_lookup'] else None
    if wanted and not found:   # needs current information, but automatic lookups are off
        background = '\n\n'.join(part for part in (background, lookups.NOT_CHECKED) if part)

    async def events():
        global ANSWERS_IN_PROGRESS
        answer, finished, saved, lookup = [], False, False, None
        ANSWERS_IN_PROGRESS += 1
        writing = True
        try:
            yield json.dumps(opening) + '\n'
            notes = background
            if found:
                yield json.dumps({'type': 'status', 'text': lookups.status(*found)}) + '\n'
                result = await asyncio.to_thread(lookups.run, question, *found)
                lookup = lookups.saved(result)
                notes = '\n\n'.join(part for part in (background, lookups.notes(result)) if part)
                # Written by BEYOND, so "Looked up" only ever appears when a lookup really ran.
                yield json.dumps({'type': 'lookup', **lookup}) + '\n'
            try:
                async for piece in engine.chat_stream(history, notes, max_tokens=budget, temperature=temperature):
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
                answer_id = chats.add_message(chat_id, 'assistant', text, retry_of=retry_of, lookup=lookup)
                previous = chats.previous_answer(chat_id, answer_id)
                buttons = learning.rating_buttons(answer_id)
                chats.set_buttons(answer_id, buttons)
                saved = True
                if previous and learning.has_retry(previous['buttons']):   # 🔄 is only for the newest answer
                    chats.set_buttons(previous['id'], learning.without_retry(previous['buttons']))
                yield json.dumps({'type': 'message', 'id': answer_id, 'buttons': buttons}) + '\n'
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
                    chats.add_message(chat_id, 'assistant', text, stopped=True, retry_of=retry_of, lookup=lookup)
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

    background = _background(history[-1]['content'], sent_ids, settings.load(), learning.retry_note(old['content']))
    return _answer(chat_id, history, background, {'type': 'retry', 'id': message_id}, undo,
                   question=history[-1]['content'], retry_of=message_id,
                   temperature=min(1.1, config.TEMPERATURE + 0.3))

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


def _command_reply(chat_id, content):
    """A /command: BEYOND answers it itself. Both are saved in the chat (so they're there when you come back) but
    marked as commands, so they're never sent to the AI. Same event stream as an AI answer, so the page needs no
    special handling. A new chat is created after the command runs, so it's named from the safe version of the
    command (a /qr wifi password never ends up in the chat list)."""
    async def events():
        try:
            reply = await asyncio.to_thread(commands.run, content)   # some commands look things up online
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
        message_id = chats.add_message(current, 'assistant', reply.text, kind='command', buttons=reply.buttons,
                                       image=reply.image)
        if reply.on_saved:   # e.g. /remind: the reminder goes off in this chat
            reply.on_saved(current)
        yield json.dumps({'type': 'token', 'text': reply.text, 'kind': 'command'}) + '\n'
        # The saved message's id, buttons and picture, so the page can show them and send presses back.
        yield json.dumps({'type': 'message', 'id': message_id, 'buttons': reply.buttons,
                          'image': reply.image}) + '\n'
        yield json.dumps({'type': 'done'}) + '\n'

    return StreamingResponse(events(), media_type='application/x-ndjson')


@app.get('/api/reminders/fired')
def fired_reminders(after: int = -1):
    """Reminders that went off since message `after`, for the page (which asks every few seconds). after=-1 only
    returns where to start, so opening the page doesn't replay old reminders."""
    latest = chats.latest_message_id(ARRIVALS)
    if after < 0:
        return {'latest': latest, 'items': []}
    return {'latest': latest, 'items': chats.messages_after(ARRIVALS, after)}


def _press(message_id, action):
    """A button pressed on a popup (e.g. a reminder's Snooze): same rules as on the page."""
    message = chats.get_message(message_id)
    if message is None or action not in {b.get('action') for row in message['buttons'] for b in row}:
        return
    reply = commands.press(action, message)
    if reply is not None:
        chats.update_message(message_id, reply.text, reply.buttons)


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
    chats.update_message(message_id, reply.text, reply.buttons)
    return {'id': message_id, 'text': reply.text, 'buttons': reply.buttons, 'toast': reply.toast}


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
    return {'ok': True} if chats.delete(chat_id) else JSONResponse({'error': 'That chat no longer exists.'},
                                                                   status_code=404)



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
        'running': running,
        'restart_needed': [key for key in config.RESTART_SETTINGS if values[key] != running[key.replace('web_', '')]],
        'network_addresses': [{'adapter': a, 'address': ip} for a, ip in ports.network_addresses()],
        'can_change': is_this_pc(request),
    }


@app.get('/api/settings')
def get_settings(request: Request):
    return _settings_view(request)


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
