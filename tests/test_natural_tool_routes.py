import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import httpx
from app import chats, config, engine, followups, learning, memory, rules, search_history, settings
from app.tools import little_lookups


class NaturalToolRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from app import server
        self.server = server
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(config, 'DATA_DIR', root), patch.object(chats, 'DB_PATH', root/'chats.sqlite3'),
                        patch.object(settings, 'FILE', root/'settings.json'), patch.object(server.notify, 'show')]
        for item in self.patches:
            item.start()
        for module in (chats, followups, learning, memory, rules, search_history):
            module.initialize()
        settings.save({'auto_lookup': False, 'auto_facts': False, 'speech_enabled': False})
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=('127.0.0.1', 5000)), base_url='http://beyond.test')

    async def asyncTearDown(self):
        await self.client.aclose()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    async def ask(self, text, chat_id=None):
        response = await self.client.post('/api/chat/stream', json={'content': text, 'chat_id': chat_id})
        self.assertEqual(response.status_code, 200, response.text)
        return [json.loads(line) for line in response.text.splitlines() if line]

    async def test_cat_fact_runs_real_command_handler_without_ai_even_with_auto_lookup_off(self):
        result = Mock(); result.json.return_value = {'fact': 'Synthetic cat fact for routing verification.'}
        with patch.object(little_lookups, 'get', return_value=result) as fetch, patch.object(engine, 'chat_stream', side_effect=AssertionError('Must not ask the model')):
            events = await self.ask('Tell me a fact about cats')
        fetch.assert_called_once_with('https://catfact.ninja/fact', timeout=6)
        text = ''.join(e.get('text', '') for e in events if e['type'] == 'token')
        self.assertIn('Synthetic cat fact', text)
        chat = chats.get(next(e['id'] for e in events if e['type'] == 'chat'))
        self.assertEqual(chat['messages'][0]['content'], 'Tell me a fact about cats')
        self.assertTrue(all(m['kind'] == 'command' for m in chat['messages']))
        self.assertEqual(events[-1]['type'], 'done')

    async def test_calculation_conversion_and_help_do_not_infer(self):
        with patch.object(engine, 'chat_stream', side_effect=AssertionError('Must not infer')):
            for text, expected in [('Calculate 25 times 48', '1,200'), ('Convert 72 f to c', '22.22'), ('What modules do you have?', '/cat')]:
                events = await self.ask(text)
                answer = ''.join(e.get('text', '') for e in events if e['type'] == 'token')
                self.assertIn(expected, answer)

    async def test_ordinary_cat_question_stays_in_normal_chat(self):
        async def reply(*args, **kwargs):
            yield 'An ordinary explanation of purring.'
        with patch.object(engine, 'chat_stream', reply), patch.object(little_lookups, 'get') as fetch:
            events = await self.ask('Explain why cats purr')
        fetch.assert_not_called()
        self.assertIn('ordinary explanation', str(events))

    async def test_pending_file_contents_are_not_intercepted_as_a_tool_request(self):
        chat_id = chats.create('Pending file')
        with patch.object(self.server.file_requests, 'plan', return_value=None), patch.object(self.server.files, 'waiting', return_value='example.txt'), patch.object(self.server.files, 'take'), patch.object(self.server.commands, 'write_pending', return_value=self.server.commands.Reply('Saved test contents')) as write, patch.object(little_lookups, 'get') as fetch:
            await self.ask('Tell me a fact about cats', chat_id)
        write.assert_called_once_with('example.txt', 'Tell me a fact about cats')
        fetch.assert_not_called()

    async def test_tokyo_question_uses_live_clock_not_model_timezone_knowledge(self):
        import importlib
        from datetime import datetime, timezone
        clock_module = importlib.import_module('app.tools.world_time')
        with patch.object(clock_module, 'datetime', wraps=datetime) as clock, patch.object(engine, 'chat_stream', side_effect=AssertionError('Must not infer')):
            clock.now.return_value = datetime(2026, 1, 2, 0, 5, tzinfo=timezone.utc)
            events = await self.ask('What is the time in Tokyo')
        answer = ''.join(e.get('text', '') for e in events if e['type'] == 'token')
        self.assertIn('Tokyo', answer)
        self.assertIn('9:05 AM', answer)
        clock.now.assert_called_once_with(timezone.utc)
