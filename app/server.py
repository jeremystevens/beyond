"""BEYOND's web server: the pages, a health check, the AI status, chat, and settings."""
import asyncio
import json
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config, engine, ports, settings

app = FastAPI(title='BEYOND', version=config.VERSION, docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=config.WEB_DIR), name='static')
# Filled in by beyond.py when the server starts (port and address in use, and the server, for restarts).
app.state.running = {'host': config.LOCAL_ONLY_HOST, 'port': config.WEB_PORT, 'allow_network': False}
app.state.server = None
app.state.restart_requested = False


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=500)


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
    return [message.model_dump() for message in request.messages][-config.CHAT_HISTORY_MESSAGES:]


@app.post('/api/chat')
async def chat(request: ChatRequest):
    """The whole reply at once (handy for tests and scripts; the page uses /api/chat/stream)."""
    try:
        reply = await engine.chat(_recent(request))
    except engine.EngineError as exc:
        return JSONResponse({'error': str(exc)}, status_code=503)
    return {'reply': reply}


@app.post('/api/chat/stream')
async def chat_stream(request: ChatRequest):
    """The reply as it's written: one JSON event per line ({"type": "token" | "done" | "error", ...}).
    If the page disconnects (Stop), the stream is cancelled and the AI stops writing."""
    recent = _recent(request)

    async def events():
        try:
            async for piece in engine.chat_stream(recent):
                yield json.dumps({'type': 'token', 'text': piece}) + '\n'
            yield json.dumps({'type': 'done'}) + '\n'
        except engine.EngineError as exc:
            yield json.dumps({'type': 'error', 'message': str(exc)}) + '\n'

    return StreamingResponse(events(), media_type='application/x-ndjson',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


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
