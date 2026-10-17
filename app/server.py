"""BEYOND's web server: the page, a health check, the AI status, and chat."""
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
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


@app.post('/api/chat')
async def chat(request: ChatRequest):
    recent = [message.model_dump() for message in request.messages][-config.CHAT_HISTORY_MESSAGES:]
    try:
        reply = await engine.chat(recent)
    except engine.EngineError as exc:
        return JSONResponse({'error': str(exc)}, status_code=503)
    return {'reply': reply}
