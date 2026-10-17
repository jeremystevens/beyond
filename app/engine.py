"""The engine connector: the only place BEYOND talks to an AI server.

It uses the standard "OpenAI-compatible" chat API that llama.cpp's llama-server, Local AI Studio, LM Studio
and Ollama all offer, so any of them can be plugged in. If an engine ever changes, this is the file to fix.
"""
import httpx

from app import config, settings

SYSTEM_PROMPT = ("You are BEYOND, a friendly and helpful assistant that runs entirely on the user's own computer. "
                 "Answer clearly and get to the point.")   # replaced by the full personality in Phase 6


class EngineError(Exception):
    """A problem explained in plain words, ready to show on the page."""


def _base_url(url):
    """Accept 'http://host:port', '.../v1' or '.../v1/chat/completions' and return 'http://host:port'."""
    url = url.strip().rstrip('/')
    for suffix in ('/chat/completions', '/v1'):
        if url.endswith(suffix):
            url = url[:-len(suffix)]
    return url


async def status():
    """Is an AI server set up and answering? Used by the page's status line."""
    url = settings.load()['ai_server_url']
    if not url:
        return {'state': 'not_set'}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(_base_url(url) + '/v1/models')
            response.raise_for_status()
            models = [m.get('id', '') for m in response.json().get('data', [])]
    except (httpx.HTTPError, ValueError):
        return {'state': 'unreachable', 'url': url}
    model = settings.load()['ai_model'] or (models[0] if models else '')
    return {'state': 'ok', 'url': url, 'model': model}


async def chat(messages):
    """Send the conversation (list of {'role', 'content'}) and return the AI's reply as text."""
    values = settings.load()
    url = values['ai_server_url']
    if not url:
        raise EngineError("No AI is set up yet. On this version, set 'ai_server_url' in data/settings.json to an AI "
                          "server's address (for example Local AI Studio's engine).")
    payload = {'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}, *messages], 'stream': False}
    if values['ai_model']:
        payload['model'] = values['ai_model']
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(config.AI_TIMEOUT_SECONDS, connect=5)) as client:
            response = await client.post(_base_url(url) + '/v1/chat/completions', json=payload)
    except httpx.ConnectError as exc:
        raise EngineError(f"BEYOND can't reach the AI server at {url}. Is it running, with a model loaded?") from exc
    except httpx.TimeoutException as exc:
        raise EngineError(f'The AI took longer than {config.AI_TIMEOUT_SECONDS // 60} minutes to answer, '
                          'so BEYOND stopped waiting. Please try again.') from exc
    except httpx.HTTPError as exc:
        raise EngineError(f'Something went wrong talking to the AI server ({type(exc).__name__}).') from exc
    if response.status_code == 503:
        raise EngineError('The AI server is still loading its model. Please try again in a moment.')
    if response.status_code != 200:
        raise EngineError(f'The AI server answered with an error (HTTP {response.status_code}).')
    try:
        return response.json()['choices'][0]['message']['content'].strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise EngineError("The AI server's answer wasn't in the expected format.") from exc
