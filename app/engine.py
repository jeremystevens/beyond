"""The engine connector: the only place BEYOND talks to an AI server.

It uses the standard "OpenAI-compatible" chat API that llama.cpp's llama-server, Local AI Studio, LM Studio
and Ollama all offer, so any of them can be plugged in. If an engine ever changes, this is the file to fix.
"""
import json

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


async def status(url=None):
    """Is an AI server set up and answering? Used by the page's status line, and by "Test connection" on the
    settings page (which passes an address that may not be saved yet)."""
    url = settings.load()['ai_server_url'] if url is None else url
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


def _prepare(messages, stream):
    """The server address and the request body, or a plain-words error if no AI is set up."""
    values = settings.load()
    url = values['ai_server_url']
    if not url:
        raise EngineError("No AI is set up yet. On this version, set 'ai_server_url' in data/settings.json to an AI "
                          "server's address (for example Local AI Studio's engine).")
    payload = {'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}, *messages], 'stream': stream}
    if values['ai_model']:
        payload['model'] = values['ai_model']
    return _base_url(url) + '/v1/chat/completions', url, payload


def _client():
    # Reading a long question on a processor-only PC can take minutes before the first word arrives.
    return httpx.AsyncClient(timeout=httpx.Timeout(config.AI_TIMEOUT_SECONDS, connect=5))


def _explain(exc, url):
    """Turn a connection problem into words for the page."""
    if isinstance(exc, httpx.ConnectError):
        return EngineError(f"BEYOND can't reach the AI server at {url}. Is it running, with a model loaded?")
    if isinstance(exc, httpx.TimeoutException):
        return EngineError(f'The AI took longer than {config.AI_TIMEOUT_SECONDS // 60} minutes to answer, '
                           'so BEYOND stopped waiting. Please try again.')
    return EngineError(f'Something went wrong talking to the AI server ({type(exc).__name__}).')


def _check(status_code):
    if status_code == 503:
        raise EngineError('The AI server is still loading its model. Please try again in a moment.')
    if status_code != 200:
        raise EngineError(f'The AI server answered with an error (HTTP {status_code}).')


async def chat(messages):
    """Send the conversation (list of {'role', 'content'}) and return the AI's whole reply as text."""
    endpoint, url, payload = _prepare(messages, stream=False)
    try:
        async with _client() as client:
            response = await client.post(endpoint, json=payload)
    except httpx.HTTPError as exc:
        raise _explain(exc, url) from exc
    _check(response.status_code)
    try:
        return response.json()['choices'][0]['message']['content'].strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise EngineError("The AI server's answer wasn't in the expected format.") from exc


async def chat_stream(messages):
    """Like chat(), but yields the reply piece by piece as the AI writes it.

    If the caller stops reading (the person pressed Stop), the connection to the AI server is closed, which tells
    llama.cpp to stop writing, so the AI is free again for the next question (or for the Telegram bot)."""
    endpoint, url, payload = _prepare(messages, stream=True)
    try:
        async with _client() as client:
            async with client.stream('POST', endpoint, json=payload) as response:
                _check(response.status_code)
                async for line in response.aiter_lines():
                    if not line.startswith('data:'):
                        continue
                    data = line[5:].strip()
                    if data == '[DONE]':
                        return
                    try:
                        piece = json.loads(data)['choices'][0]['delta'].get('content') or ''
                    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                        continue
                    if piece:
                        yield piece
    except httpx.HTTPError as exc:
        raise _explain(exc, url) from exc
