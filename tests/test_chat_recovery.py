"""Failure recovery uses the same saved question without rating or duplicating it."""
import asyncio
import gc
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, engine, server, settings
from support import closing_connections, local_request


class ChatRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patchers = [
            patch.object(config, 'DATA_DIR', Path(self.temp.name)),
            patch.object(chats, 'DB_PATH', Path(self.temp.name) / 'chat.sqlite3'),
            patch.object(chats, 'connect', closing_connections()),
            patch.object(settings, 'FILE', Path(self.temp.name) / 'settings.json'),
            patch.object(server, '_background', return_value=''),
            patch.object(server.lookups, 'detect', return_value=None),
            patch.object(server.file_reading, 'for_message', return_value=('', '', False)),
            patch.object(server.followups, 'for_message', return_value=None),
            patch.object(server.memory, 'wants_pickup', return_value=False),
            patch.object(server.notify, 'show'),
            patch.object(server.diagnostics, 'record_error'),
        ]
        for p in self.patchers:
            p.start()
        chats.initialize()
        server.learning.initialize()
        server.ACTIVE_CHAT_ANSWERS.clear()
        self.chat = chats.create('A code example')

    def tearDown(self):
        server.ACTIVE_CHAT_ANSWERS.clear()
        for p in reversed(self.patchers):
            p.stop()
        gc.collect()
        self.temp.cleanup()

    def consume(self, response):
        async def read():
            return [json.loads(line) async for line in response.body_iterator]
        return asyncio.run(read())

    def recover(self, question_id):
        return asyncio.run(server.retry_question(question_id, local_request()))

    def test_timeout_keeps_question_and_retry_does_not_duplicate_it(self):
        async def fail(*args, **kwargs):
            if False:
                yield ''
            raise engine.EngineError('The AI timed out.')
        with patch.object(engine, 'chat_stream', fail):
            events = self.consume(server._ai_answer(server.SendRequest(chat_id=self.chat, content='Show a class'),
                                                   'Show a class', local_request()))
        question_id = events[0]['question_id']
        self.assertEqual(events[-1]['type'], 'error')
        self.assertIsNotNone(chats.get_message(question_id))
        self.assertNotIn(self.chat, server.ACTIVE_CHAT_ANSWERS)

        async def succeed(history, *args, **kwargs):
            self.assertEqual(history[-1], {'role': 'user', 'content': 'Show a class'})
            yield '```python\nclass Cat: pass\n```'
        with patch.object(engine, 'chat_stream', succeed), patch.object(server.learning, 'rate') as rate:
            self.assertEqual(self.consume(self.recover(question_id))[-1]['type'], 'done')
            rate.assert_not_called()
        messages = chats.get(self.chat)['messages']
        self.assertEqual(sum(m['role'] == 'user' for m in messages), 1)
        self.assertEqual(sum(m['role'] == 'assistant' for m in messages), 1)

    def test_partial_answer_stays_visible_but_is_excluded_from_retry_history(self):
        question_id = chats.add_message(self.chat, 'user', 'Show a class')
        partial_id = chats.add_message(self.chat, 'assistant', 'unfinished code', stopped=True)
        async def succeed(history, *args, **kwargs):
            self.assertNotIn('unfinished code', str(history))
            self.assertEqual(history[-1]['content'], 'Show a class')
            yield 'complete code'
        with patch.object(engine, 'chat_stream', succeed), patch.object(server.learning, 'rate') as rate:
            self.consume(self.recover(question_id))
            rate.assert_not_called()
        old = chats.get_message(partial_id)
        self.assertEqual(old['content'], 'unfinished code')
        self.assertEqual(old['kind'], 'retried')
        self.assertIsNone(old['rating'])
        self.assertEqual(chats.message_count(self.chat), 2)

    def test_failed_recovery_restores_old_partial_and_remains_retryable(self):
        question_id = chats.add_message(self.chat, 'user', 'Show a class')
        partial_id = chats.add_message(self.chat, 'assistant', 'unfinished', stopped=True)
        async def fail(*args, **kwargs):
            if False:
                yield ''
            raise engine.EngineError('Offline')
        with patch.object(engine, 'chat_stream', fail):
            self.consume(self.recover(question_id))
            self.consume(self.recover(question_id))
        self.assertEqual(chats.get_message(partial_id)['kind'], 'chat')
        self.assertEqual(chats.message_count(self.chat), 2)

    def test_recovery_rejects_newer_prompts_commands_and_active_streams(self):
        question_id = chats.add_message(self.chat, 'user', 'Old prompt')
        server.ACTIVE_CHAT_ANSWERS[self.chat] = 1
        self.assertEqual(self.recover(question_id).status_code, 409)
        server.ACTIVE_CHAT_ANSWERS.clear()
        chats.add_message(self.chat, 'user', 'New prompt')
        self.assertEqual(self.recover(question_id).status_code, 409)
        command_id = chats.add_message(self.chat, 'user', '/writefile example.py', kind='command')
        self.assertEqual(self.recover(command_id).status_code, 409)
        self.assertEqual(self.recover(99999).status_code, 404)

    def test_engine_eof_without_completion_is_an_error_but_normal_completion_works(self):
        async def run(suffix):
            def handler(request):
                return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n' + suffix)
            with patch.object(engine, '_prepare', return_value=('http://test/v1/chat/completions', 'http://test', {})), \
                 patch.object(engine, '_client', side_effect=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))), \
                 patch.object(engine.builtin_engine, 'using_model', return_value=nullcontext()), \
                 patch.object(engine.settings, 'load', return_value={'ai_mode':'external', 'ai_model':'test'}):
                return [part async for part in engine.chat_stream([{'role':'user','content':'Hello'}])]
        with self.assertRaisesRegex(engine.EngineError, 'ended before'):
            asyncio.run(run(''))
        self.assertEqual(asyncio.run(run('data: [DONE]\n\n'))[0], 'partial')
        self.assertEqual(asyncio.run(run('data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'))[0], 'partial')
