"""Phase 33 (built-in engine) checks: python -m unittest discover -s tests -v. A tiny stand-in for llama-server
(written to a temporary folder) plays the engine, so no model is loaded."""
import asyncio
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import builtin_engine, config, engine, settings

FAKE_SERVER = textwrap.dedent('''
    import json, sys, time
    from http.server import BaseHTTPRequestHandler, HTTPServer
    port = int(sys.argv[sys.argv.index('--port') + 1])
    time.sleep(0.5)                                     # "loading the model"
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status": "ok"}')
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            body =json.dumps({'choices': [{'message': {'content': 'Hello from the engine'}}]}).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(body)
    print('fake engine ready', flush=True)
    HTTPServer(('127.0.0.1', port), Handler).serve_forever()
''')


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = settings.FILE
        settings.FILE = Path(self.temp.name) / 'settings.json'

    def tearDown(self):
        settings.FILE = self.saved
        self.temp.cleanup()

    def test_fresh_install_uses_the_built_in_engine(self):
        values = settings.load()
        self.assertEqual((values['ai_mode'], values['engine_threads'], values['engine_cache']), ('builtin', 12, 'f16'))

    def test_an_older_setup_keeps_its_ai_server(self):
        settings.FILE.write_text(json.dumps({'ai_server_url': 'http://127.0.0.1:10086'}), encoding='utf-8')
        self.assertEqual(settings.load()['ai_mode'], 'server')
        settings.save({'ai_mode': 'builtin'})            # switching stays switched, even with the address kept
        self.assertEqual(settings.load()['ai_mode'], 'builtin')
        self.assertEqual(settings.load()['ai_server_url'], 'http://127.0.0.1:10086')

    def test_bad_engine_settings_are_refused(self):
        for changes in ({'ai_mode': 'cloud'}, {'engine_executable': 'llama-server.sh'}, {'engine_model': 'model.bin'},
                        {'engine_threads': 0}, {'engine_context': 100}, {'engine_cache': 'q2'},
                        {'engine_thinking': 'yes'}):
            with self.subTest(changes=changes), self.assertRaises(settings.SettingsError):
                settings.validate(changes)


class CommandTests(unittest.TestCase):
    def values(self, **changes):
        return {**config.DEFAULTS, 'engine_executable': r'C:\llama\llama-server.exe',
                'engine_model': r'C:\models\Qwen3-4B.gguf', **changes}

    def test_processor_only_and_local_only(self):
        args = builtin_engine.command(self.values(), 50123)
        joined = ' '.join(args)
        for part in ('--host 127.0.0.1', '--port 50123', '--threads 12', '--ctx-size 8192', '--n-gpu-layers 0',
                     '--cache-type-k f16', '--cache-type-v f16', '--flash-attn off', '--parallel 1',
                     '--reasoning off'):
            self.assertIn(part, joined)

    def test_quantised_cache_turns_on_flash_attention(self):
        joined = ' '.join(builtin_engine.command(self.values(engine_cache='q8_0', engine_thinking=True), 1))
        self.assertIn('--flash-attn on', joined)
        self.assertIn('--reasoning-format deepseek', joined)
        self.assertNotIn('enable_thinking', joined)

    def test_free_port_avoids_other_ai_apps(self):
        port = builtin_engine.free_port()
        self.assertNotIn(port, config.RESERVED_PORTS)
        self.assertNotEqual(port, config.WEB_PORT)

    def test_missing_files_are_explained(self):
        self.assertIn('Choose llama-server.exe', builtin_engine.missing({**config.DEFAULTS}))
        self.assertIn("can't find the engine program", builtin_engine.missing(self.values()))


class ThinkingTests(unittest.IsolatedAsyncioTestCase):
    """With thinking on, the page is told the model is thinking, but never what it thinks."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = settings.FILE
        settings.FILE = Path(self.temp.name) / 'settings.json'
        settings.save({'ai_mode': 'builtin', 'engine_thinking': True})
        self.sent = []

    def tearDown(self):
        settings.FILE = self.saved
        self.temp.cleanup()

    def reply(self, request):
        self.sent.append(json.loads(request.content))
        if not self.sent[-1]['stream']:
            return httpx.Response(200, json={'choices': [{'message': {'content': '["The user has a dog"]'}}]})
        lines = [{'reasoning_content': 'The user said hi, so'}, {'reasoning_content': ' I should greet them.'},
                 {'content': 'Hi'}, {'content': ' there!'}]
        chunks = [{'choices': [{'delta': d}]} for d in lines]
        chunks.append({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'model': r'C:\models\Qwen3-4B.gguf',
                       'timings': {'predicted_n': 77, 'predicted_ms': 36000.0, 'predicted_per_second': 2.1388}})
        body = ''.join(f'data: {json.dumps(c)}\n\n' for c in chunks) + 'data: [DONE]\n\n'
        return httpx.Response(200, text=body)

    def client(self, *args, **kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(self.reply))

    async def test_thinking_is_signalled_not_shown(self):
        with patch.object(builtin_engine, 'url', return_value='http://127.0.0.1:1'), \
                patch.object(engine, '_client', self.client):
            pieces = [p async for p in engine.chat_stream([{'role': 'user', 'content': 'Hi'}])]
            await engine.complete([{'role': 'user', 'content': 'Facts?'}], max_tokens=120, temperature=0.1)
        *pieces, stats = pieces
        self.assertEqual(pieces, [engine.THINKING, engine.THINKING, 'Hi', ' there!'])
        self.assertIsInstance(stats, engine.Stats)   # the line under the answer: the engine's own numbers
        self.assertEqual((stats['model'], stats['tokens'], stats['speed']), ('Qwen3-4B.gguf', 77, 2.14))
        self.assertGreaterEqual(stats['thought'], 0)
        self.assertEqual(self.sent[0]['stream_options'], {'include_usage': True})
        chat, one_off = self.sent
        self.assertEqual(chat['max_tokens'], config.ANSWER_MAX_TOKENS + engine.THINKING_EXTRA_TOKENS)
        self.assertNotIn('chat_template_kwargs', chat)
        self.assertEqual(one_off['chat_template_kwargs'], {'enable_thinking': False})   # small jobs never think
        self.assertEqual(one_off['max_tokens'], 120)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)   # Windows may hold engine.log a moment longer
        folder = Path(self.temp.name)
        self.saved = config.DATA_DIR, settings.FILE
        config.DATA_DIR, settings.FILE = folder, folder / 'settings.json'
        script = folder / 'fake_llama_server.py'
        script.write_text(FAKE_SERVER, encoding='utf-8')
        exe, model = folder / 'llama-server.exe', folder / 'model.gguf'
        exe.write_bytes(b'')
        model.write_bytes(b'')
        settings.save({'ai_mode': 'builtin', 'engine_executable': str(exe), 'engine_model': str(model)})
        self.command = patch.object(builtin_engine, 'command',
                                    lambda values, port: [sys.executable, '-I', str(script), '--port', str(port)])
        self.command.start()

    async def asyncTearDown(self):
        await builtin_engine.stop()
        builtin_engine._engine.wanted, builtin_engine._engine.state = None, 'off'
        self.command.stop()
        config.DATA_DIR, settings.FILE = self.saved
        self.temp.cleanup()

    async def test_start_chat_and_stop(self):
        with self.assertRaises(engine.EngineError):       # not started yet: a plain-words message, no crash
            await engine.chat([{'role': 'user', 'content': 'Hi'}])
        await builtin_engine.start(settings.load())
        status = await engine.status()
        self.assertEqual((status['state'], status['model'], status['builtin']), ('ok', 'model.gguf', True))
        self.assertTrue((config.DATA_DIR / 'engine.pid').exists())
        self.assertEqual(await engine.chat([{'role': 'user', 'content': 'Hi'}]), 'Hello from the engine')
        process = builtin_engine._engine.process
        await builtin_engine.stop()
        self.assertIsNotNone(process.poll())
        self.assertFalse((config.DATA_DIR / 'engine.pid').exists())
        self.assertIsNone(builtin_engine.url())

    async def test_watcher_restarts_a_crashed_engine(self):
        watcher = asyncio.create_task(builtin_engine.supervise())
        try:
            await self.wait_for('ok')
            first = builtin_engine._engine.process
            first.kill()
            await self.wait_for('error')
            await self.wait_for('ok')
            self.assertIsNot(builtin_engine._engine.process, first)
            settings.save({'ai_mode': 'server'})           # switching away stops it
            await self.wait_for('off')
            self.assertIsNone(builtin_engine._engine.process)
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)

    async def wait_for(self, state, seconds=30):
        for _ in range(seconds * 10):
            if builtin_engine._engine.state == {'ok': 'ready'}.get(state, state):
                return
            await asyncio.sleep(0.1)
        self.fail(f'The engine never reached {state!r} (it is {builtin_engine._engine.state!r}).')


if __name__ == '__main__':
    unittest.main()
