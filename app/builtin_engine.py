"""BEYOND's built-in AI engine: starts, watches and stops llama.cpp's llama-server itself.

With "Built-in engine" chosen in Settings, BEYOND runs the llama-server.exe you pick with your .gguf model, on a free
port only this PC can reach, and app/engine.py talks to it exactly like any other OpenAI-compatible server. Everything
runs on the processor (no graphics card): the tuned settings are 12 threads, an f16 cache and one conversation slot,
so the prompt cache keeps working between messages. A change to the engine settings restarts it with the new ones;
if it stops by itself, BEYOND starts it again (up to three times, then waits for a settings change).
"""
import asyncio
import logging
import os
import socket
import subprocess
import time
from pathlib import Path

import httpx
import psutil

from app import config, settings

HOST = '127.0.0.1'            # never reachable from other devices; BEYOND's own page is the only way in
START_TIMEOUT = 300           # loading a big model from a hard disk can take minutes
MAX_RETRIES = 3               # after this many crashes in a row, wait for a settings change
CHECK_SECONDS = 2
SETTING_KEYS = ('engine_executable', 'engine_model', 'engine_threads', 'engine_context', 'engine_cache',
                'engine_thinking')


class _Engine:
    process = None
    port = None
    wanted = None             # the settings the running (or starting) engine was started with
    state = 'off'             # off · not_set · starting · ready · error
    problem = ''
    failures = 0


_engine = _Engine()


def log_file():
    return config.DATA_DIR / 'engine.log'


def _pid_file():
    return config.DATA_DIR / 'engine.pid'


def wanted(values):
    """The engine settings to run with, or None when the built-in engine isn't chosen."""
    if values['ai_mode'] != 'builtin':
        return None
    return tuple(values[key] for key in SETTING_KEYS)


def missing(values):
    """What still has to be set up before the engine can start, in plain words ('' = nothing)."""
    executable, model = values['engine_executable'], values['engine_model']
    if not executable or not model:
        return ('Choose llama-server.exe and a .gguf model in Settings → AI engine, or switch to an AI server you '
                'already run.')
    if not Path(executable).is_file():
        return f"BEYOND can't find the engine program at {executable}."
    if not Path(model).is_file():
        return f"BEYOND can't find the model file at {model}."
    return ''


def free_port():
    """A free port on this PC, picked by Windows, that no other local AI app relies on."""
    for _ in range(20):
        with socket.socket() as probe:
            probe.bind((HOST, 0))
            port = probe.getsockname()[1]
        if port not in config.RESERVED_PORTS and port not in (config.WEB_PORT, config.WEB_PORT + 1):
            return port
    raise OSError('No free port found for the AI engine.')


def command(values, port):
    """The llama-server command line. Processor only: no layers on a graphics card. A quantised (q8_0 / q4_0) cache
    needs flash attention; f16, the tuned default, runs fastest here without it."""
    cache = values['engine_cache']
    args = [values['engine_executable'], '--model', values['engine_model'], '--host', HOST, '--port', str(port),
            '--threads', str(values['engine_threads']), '--ctx-size', str(values['engine_context']),
            '--n-gpu-layers', '0', '--cache-type-k', cache, '--cache-type-v', cache,
            '--flash-attn', 'off' if cache == 'f16' else 'on', '--batch-size', '512', '--ubatch-size', '512',
            '--parallel', '1', '--no-ui']
    if values['engine_thinking']:
        args += ['--reasoning-format', 'deepseek']   # the thinking goes in a separate field, never into the answer
    else:   # thinking models (Qwen3…) answer straight away; a token budget of 0 still let Qwen3 think out loud
        args += ['--reasoning', 'off', '--chat-template-kwargs', '{"enable_thinking": false}']
    return args


def model_name(values=None):
    values = values or settings.load()
    return Path(values['engine_model']).name


def url():
    """The engine's address while it's ready for questions, else None."""
    return f'http://{HOST}:{_engine.port}' if _engine.state == 'ready' else None


def status():
    """For the page's status line and Settings: {'state', 'model', 'message'}."""
    values = settings.load()
    state = _engine.state
    if state == 'off' and wanted(values):   # chosen, but the watcher hasn't run yet
        state = 'not_set' if missing(values) else 'starting'
    message = {'ready': '', 'starting': 'The AI engine is loading the model.', 'off': 'The AI engine is off.'}.get(
        state, _engine.problem or missing(values))
    return {'state': 'ok' if state == 'ready' else state, 'builtin': True, 'model': model_name(values),
            'message': message, 'port': _engine.port if state == 'ready' else None}


def request_restart():
    """Start the engine again on the watcher's next check, with a fresh set of retries."""
    _engine.wanted, _engine.failures = ('restart',), 0


def not_ready_message():
    s = status()
    if s['state'] == 'starting':
        return "BEYOND's AI engine is still loading the model. Please try again in a moment."
    return s['message'] or "BEYOND's AI engine isn't running."


def _stop_leftover():
    """If BEYOND was closed without stopping its engine (a crash, or the PC being shut down), that llama-server may
    still be running and holding gigabytes of memory. Stop it before starting a new one."""
    try:
        pid = int(_pid_file().read_text(encoding='utf-8'))
        process = psutil.Process(pid)
        if 'llama-server' in process.name().lower():
            process.kill()
            logging.info('Stopped a leftover AI engine (process %s)', pid)
    except (OSError, ValueError, psutil.Error):
        pass
    _pid_file().unlink(missing_ok=True)


def _log_tail(lines=6):
    try:
        text = log_file().read_text(encoding='utf-8', errors='replace').strip().splitlines()
    except OSError:
        return ''
    useful = [line for line in text if line.strip()][-lines:]
    return '\n'.join(useful)


async def _healthy(client, port):
    try:
        return (await client.get(f'http://{HOST}:{port}/health', timeout=3)).status_code == 200
    except httpx.HTTPError:
        return False


async def start(values):
    """Start llama-server with these settings and wait until the model is loaded."""
    await stop()
    _engine.wanted = wanted(values)
    problem = missing(values)
    if problem:
        _engine.state, _engine.problem = 'not_set', problem
        return
    _engine.state, _engine.problem = 'starting', ''
    config.DATA_DIR.mkdir(exist_ok=True)
    port = free_port()
    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '-1'}   # processor only, even with a GPU-enabled build
    with open(log_file(), 'w', encoding='utf-8') as log:
        process = subprocess.Popen(command(values, port), stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, env=env, cwd=str(Path(values['engine_executable']).parent),
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    _engine.process, _engine.port = process, port
    _pid_file().write_text(str(process.pid), encoding='utf-8')
    logging.info('Starting the AI engine on port %s with %s', port, model_name(values))
    deadline = time.monotonic() + START_TIMEOUT
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                _failed('The AI engine stopped while loading the model.')
                return
            if await _healthy(client, port):
                _engine.state, _engine.failures = 'ready', 0
                logging.info('The AI engine is ready')
                return
            await asyncio.sleep(0.5)
    await stop()
    _failed(f"The AI engine didn't finish loading the model within {START_TIMEOUT // 60} minutes.")


def _failed(problem):
    tail = _log_tail()
    _engine.state, _engine.problem = 'error', problem + (f'\n{tail}' if tail else '')
    _engine.failures += 1
    logging.warning('%s\n%s', problem, tail)


async def stop():
    """Stop the engine (gently first) and free its memory."""
    process, _engine.process = _engine.process, None
    _engine.port = None
    if _engine.state in ('ready', 'starting'):
        _engine.state = 'off'
    if process is None or process.poll() is not None:
        _pid_file().unlink(missing_ok=True)
        return
    process.terminate()
    try:
        await asyncio.to_thread(process.wait, 10)
    except subprocess.TimeoutExpired:
        process.kill()
        await asyncio.to_thread(process.wait, 10)
    _pid_file().unlink(missing_ok=True)
    logging.info('Stopped the AI engine')


async def supervise():
    """Runs for as long as BEYOND does: keeps the engine in step with the settings and restarts it if it stops."""
    await asyncio.to_thread(_stop_leftover)
    try:
        while True:
            try:
                values = settings.load()
                want = wanted(values)
                if want != _engine.wanted:                       # chosen, switched off or settings changed
                    _engine.failures = 0
                    if want is None:
                        await stop()
                        _engine.wanted, _engine.state = None, 'off'
                    else:
                        await start(values)
                elif want and _engine.state == 'ready' and _engine.process.poll() is not None:
                    await stop()
                    _failed('The AI engine stopped unexpectedly.')
                elif want and _engine.state == 'error' and _engine.failures < MAX_RETRIES:
                    await asyncio.sleep(5 * _engine.failures)
                    await start(values)
                elif want and _engine.state == 'not_set' and not missing(values):   # the files appeared
                    await start(values)
            except Exception:
                logging.exception('The AI engine watcher failed')
            await asyncio.sleep(CHECK_SECONDS)
    finally:
        await stop()
