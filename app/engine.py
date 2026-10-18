"""The engine connector: the only place BEYOND talks to an AI server.

It uses the standard "OpenAI-compatible" chat API that llama.cpp's llama-server, Local AI Studio, LM Studio
and Ollama all offer, so any of them can be plugged in. If an engine ever changes, this is the file to fix.
"""
import json
import re

import httpx

from app import builtin_engine, config, memory, rules, settings

FALLBACK_PROMPT = ("You are BEYOND, a friendly and helpful assistant that runs entirely on the user's own computer. "
                   "Answer clearly and get to the point.")


class EngineError(Exception):
    """A problem explained in plain words, ready to show on the page."""


def system_prompt():
    """BEYOND's personality (app/personality.md), then the house rules, then the saved facts. Read on every message,
    so changes to any of them apply straight away. All three rarely change, so the AI server can keep reusing them."""
    try:
        personality = config.PERSONALITY_FILE.read_text(encoding='utf-8').strip() or FALLBACK_PROMPT
    except OSError:
        personality = FALLBACK_PROMPT
    return personality + rules.prompt_block() + memory.prompt_block()


def history_window(total):
    """How many recent messages to send with a question (including the question itself).

    The AI server reuses ("caches") the start of the prompt when it matches the previous one exactly, and only reads
    the rest. So the window grows from half the limit to the limit and is then cut back in one step (6 → 11, then
    6 again with the default 12), instead of sliding by one message every turn, which would change the start each
    time and make the AI re-read the whole conversation. Ported from PromptetheusBot."""
    step = max(2, config.HISTORY_LIMIT // 2)
    return min(config.HISTORY_LIMIT, step + total % step)


def trim(messages):
    """Keep the prompt small: a very long earlier message would otherwise slow down every later reply.
    The newest message (the question) is never shortened."""
    limit = config.HISTORY_MESSAGE_CHARS
    return [m if len(m['content']) <= limit or i == len(messages) - 1
            else {**m, 'content': m['content'][:limit] + ' …(shortened)'} for i, m in enumerate(messages)]


def with_reply_notes(messages, background=''):
    """Attach short notes for this reply to the newest message (not saved in the chat).

    Things that change with every message (related old conversations found for this question) go here rather than in
    the personality, so the start of the prompt stays the same and the AI server can reuse it. The house rules are
    repeated here too: small models pay most attention to the end of the prompt, and a rule only at the end of the
    long personality was ignored (tested: "Always answer in French"). Rules come last, closest to the question.
    Same approach as PromptetheusBot's notes block."""
    if not messages or messages[-1]['role'] != 'user':
        return messages
    parts = [background.strip()] if background.strip() else []
    current = rules.all_rules()
    if current:
        parts.append('Follow the house rules: ' + ' '.join(rule['text'].rstrip('.') + '.' for rule in current))
    if not parts:
        return messages
    notes = ('[Notes for this reply from BEYOND (not written by the person; do not mention them):\n' +
             '\n\n'.join(parts) + "]\n\n## The person's message\n")
    return [*messages[:-1], {**messages[-1], 'content': notes + messages[-1]['content']}]


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
    if url is None and settings.load()['ai_mode'] == 'builtin':
        return builtin_engine.status()
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


def _server():
    values = settings.load()
    if values['ai_mode'] == 'builtin':
        url = builtin_engine.url()
        if not url:
            raise EngineError(builtin_engine.not_ready_message())
        return url, ''
    url = values['ai_server_url']
    if not url:
        raise EngineError('No AI is set up yet. Open Settings and enter the address of an AI server you run '
                          '(for example Local AI Studio\'s engine).')
    return url, values['ai_model']


def _prepare(messages, stream, background='', max_tokens=None, temperature=None):
    """The server address and the request body for a chat reply, or a plain-words error if no AI is set up."""
    url, model = _server()
    # The personality comes first and never changes between messages, so the AI server can reuse it (see
    # history_window); the conversation follows, newest message last, with any notes for this reply attached to it.
    messages = with_reply_notes(trim(messages), background)
    payload = {'messages': [{'role': 'system', 'content': system_prompt()}, *messages], 'stream': stream,
               'max_tokens': max_tokens or config.ANSWER_MAX_TOKENS,
               'temperature': config.TEMPERATURE if temperature is None else temperature, 'cache_prompt': True}
    if model:
        payload['model'] = model
    return _base_url(url) + '/v1/chat/completions', url, payload


async def complete(messages, max_tokens, temperature):
    """A one-off request with its own instructions (not BEYOND's personality), e.g. picking facts out of a message.
    Returns the AI's text."""
    url, model = _server()
    payload = {'messages': messages, 'stream': False, 'max_tokens': max_tokens, 'temperature': temperature}
    if model:
        payload['model'] = model
    try:
        async with _client() as client:
            response = await client.post(_base_url(url) + '/v1/chat/completions', json=payload)
    except httpx.HTTPError as exc:
        raise _explain(exc, url) from exc
    return _text(response)


def complete_blocking(messages, max_tokens, temperature):
    """complete() for code that runs in a worker thread (commands such as /rewrite and /joke)."""
    url, model = _server()
    payload = {'messages': messages, 'stream': False, 'max_tokens': max_tokens, 'temperature': temperature}
    if model:
        payload['model'] = model
    try:
        with httpx.Client(timeout=httpx.Timeout(config.AI_TIMEOUT_SECONDS, connect=5)) as client:
            response = client.post(_base_url(url) + '/v1/chat/completions', json=payload)
    except httpx.HTTPError as exc:
        raise _explain(exc, url) from exc
    return _text(response)


def _text(response):
    """The AI's text from a one-off reply, with any <think>…</think> reasoning removed."""
    _check(response.status_code)
    try:
        text = response.json()['choices'][0]['message']['content'] or ''
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise EngineError("The AI server's answer wasn't in the expected format.") from exc
    return re.sub(r'<think>.*?</think>', '', text, flags=re.S | re.I).strip()


def _client():
    # Reading a long question on a processor-only PC can take minutes before the first word arrives.
    return httpx.AsyncClient(timeout=httpx.Timeout(config.AI_TIMEOUT_SECONDS, connect=5))


def _explain(exc, url):
    """Turn a connection problem into words for the page."""
    if isinstance(exc, httpx.ConnectError):
        if settings.load()['ai_mode'] == 'builtin':
            return EngineError("BEYOND's AI engine isn't answering. It restarts by itself; please try again shortly.")
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


async def chat_stream(messages, background='', max_tokens=None, temperature=None):
    """Like chat(), but yields the reply piece by piece as the AI writes it. `background`: notes for this reply
    only (for example related old conversations). `max_tokens` / `temperature`: None = the defaults.

    If the caller stops reading (the person pressed Stop), the connection to the AI server is closed, which tells
    llama.cpp to stop writing, so the AI is free again for the next question (or for the Telegram bot)."""
    endpoint, url, payload = _prepare(messages, stream=True, background=background, max_tokens=max_tokens,
                                     temperature=temperature)
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
