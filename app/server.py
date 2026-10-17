"""BEYOND's web server: the page, a health check, the AI status, and chat."""
import json
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import config, engine

app = FastAPI(title='BEYOND', version=config.VERSION, docs_url=None, redoc_url=None)


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=500)


@app.get('/', include_in_schema=False)
def home():
    return FileResponse(config.WEB_DIR / 'index.html')


@app.get('/api/health')
def health():
    """Quick "is BEYOND running?" check, used by the page now and by the self-test later."""
    return {'status': 'ok', 'name': 'BEYOND', 'version': config.VERSION, 'phase': config.PHASE}


@app.get('/api/ai-status')
async def ai_status():
    return await engine.status()


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
