"""BEYOND's web server: the pages, a health check, the AI status, chat (saved conversations), and settings."""
import asyncio
import json
import logging
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import chats, commands, config, engine, memory, ports, rules, settings

chats.initialize()
rules.initialize()
memory.initialize()
app = FastAPI(title='BEYOND', version=config.VERSION, docs_url=None, redoc_url=None)
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
    chat_id = chats.create(content) if new_chat else body.chat_id
    if content.startswith('/'):
        return _command_reply(chat_id, new_chat, content)
    question_id = chats.add_message(chat_id, 'user', content)
    history = chats.recent_messages(chat_id, engine.history_window(chats.message_count(chat_id)))

    async def events():
        answer, finished = [], False
        yield json.dumps({'type': 'chat', 'id': chat_id, 'new': new_chat, 'title': chats.title_from(content)}) + '\n'
        try:
            async for piece in engine.chat_stream(history):
                answer.append(piece)
                yield json.dumps({'type': 'token', 'text': piece}) + '\n'
            finished = True
            yield json.dumps({'type': 'done'}) + '\n'
        except engine.EngineError as exc:
            yield json.dumps({'type': 'error', 'message': str(exc)}) + '\n'
        finally:   # also runs when Stop cancels the stream
            text = ''.join(answer).strip()
            if text:
                chats.add_message(chat_id, 'assistant', text, stopped=not finished)
            else:
                chats.remove_message(question_id)
                if new_chat and chats.message_count(chat_id, kind=None) == 0:
                    chats.delete(chat_id)

    return StreamingResponse(events(), media_type='application/x-ndjson',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def _command_reply(chat_id, new_chat, content):
    """A /command: BEYOND answers it itself. Both are saved in the chat (so they're there when you come back) but
    marked as commands, so they're never sent to the AI. Same event stream as an AI answer, so the page needs no
    special handling."""
    async def events():
        yield json.dumps({'type': 'chat', 'id': chat_id, 'new': new_chat, 'title': chats.title_from(content)}) + '\n'
        try:
            reply = await asyncio.to_thread(commands.run, content)   # some commands look things up online
        except Exception:   # a bug in one command shouldn't break the chat
            logging.exception('Command failed: %s', content.split()[0])
            reply = commands.Reply(f'Sorry, {content.split()[0]} ran into a problem. Please try again.')
        chats.add_message(chat_id, 'user', content, kind='command')
        message_id = chats.add_message(chat_id, 'assistant', reply.text, kind='command', buttons=reply.buttons)
        yield json.dumps({'type': 'token', 'text': reply.text, 'kind': 'command'}) + '\n'
        # The saved message's id and buttons, so the page can show the buttons and send presses back.
        yield json.dumps({'type': 'message', 'id': message_id, 'buttons': reply.buttons}) + '\n'
        yield json.dumps({'type': 'done'}) + '\n'

    return StreamingResponse(events(), media_type='application/x-ndjson')


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
        reply = await asyncio.to_thread(commands.press, body.action)
    except Exception:
        logging.exception('Button failed: %s', body.action.split(':')[0])
        return JSONResponse({'error': 'That button ran into a problem. Please try again.'}, status_code=500)
    if reply is None:
        return JSONResponse({'error': 'That button is no longer available.'}, status_code=409)
    chats.update_message(message_id, reply.text, reply.buttons)
    return {'id': message_id, 'text': reply.text, 'buttons': reply.buttons, 'toast': reply.toast}


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
    return _settings_view(request, settings.save(cleaned))


@app.post('/api/settings/reset')
def reset_settings(request: Request):
    if not is_this_pc(request):
        return only_this_pc()
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
