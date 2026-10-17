"""BEYOND's web server. Phase 1: a placeholder page and a health check."""
from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import config

app = FastAPI(title='BEYOND', version=config.VERSION, docs_url=None, redoc_url=None)


@app.get('/', include_in_schema=False)
def home():
    return FileResponse(config.WEB_DIR / 'index.html')


@app.get('/api/health')
def health():
    """Quick "is BEYOND running?" check, used by the page now and by the self-test later."""
    return {'status': 'ok', 'name': 'BEYOND', 'version': config.VERSION, 'phase': config.PHASE}
