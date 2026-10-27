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

    async def test_missing_email_asks_without_model_and_followup_keeps_intent(self):
        with patch.object(engine, 'chat_stream', side_effect=AssertionError('Missing email must not reach AI')), \
             patch.object(engine, 'complete', side_effect=AssertionError('No classification call')):
            events = await self.ask('Reply to this email')
        answer = ''.join(e.get('text', '') for e in events if e['type'] == 'token')
        self.assertEqual(answer, 'Could you paste the email or message you want me to reply to?')
        chat_id = next(e['id'] for e in events if e['type'] == 'chat')
        saved = chats.get(chat_id)['messages']
        self.assertEqual([m['kind'] for m in saved], ['chat', 'chat'])
        self.assertEqual(saved[-1]['content'], answer)
        self.assertIsNone(saved[-1]['stats'])
        async def reply(history, *args, **kwargs):
            self.assertEqual(history[0]['content'], 'Reply to this email')
            self.assertEqual(history[1]['content'], answer)
            self.assertIn('Can you attend Friday?', history[-1]['content'])
            yield 'Thanks for inviting me. I can attend Friday.'
        with patch.object(engine, 'chat_stream', reply):
            followup_events = await self.ask('Hi, Can you attend Friday?', chat_id)
        self.assertIn('I can attend Friday', str(followup_events))

    async def test_attachment_or_working_notes_preserves_normal_inference(self):
        async def reply(*args, **kwargs):
            yield 'Answer from supplied context.'
        for source in ('attachment', 'working_notes'):
            with self.subTest(source=source), \
                 patch.object(self.server.attachments, 'listing', return_value=[{'id': 1}] if source == 'attachment' else []), \
                 patch('app.working_notes.prompt_block', return_value='Reviewed source' if source == 'working_notes' else ''), \
                 patch.object(engine, 'chat_stream', reply):
                events = await self.ask('Reply to this email')
            self.assertIn('Answer from supplied context.', str(events))

    async def test_bare_request_with_guided_mode_still_asks_without_preparatory_calls(self):
        with patch.object(engine, 'complete', side_effect=AssertionError('No preparatory calls')), \
             patch.object(engine, 'chat_stream', side_effect=AssertionError('No model needed')):
            response = await self.client.post('/api/chat/stream', json={'content': 'Write a letter', 'think_through': True})
        self.assertEqual(response.status_code, 200)
        self.assertIn('What should the letter say?', response.text)

    async def test_photo_context_does_not_trigger_bare_error_question(self):
        chat_id = chats.create('Photo context')
        chats.add_message(chat_id, 'user', 'An attached screenshot', kind='photo')
        async def reply(*args, **kwargs):
            yield 'Use screenshot evidence through the normal workflow.'
        with patch.object(engine, 'chat_stream', reply):
            events = await self.ask('Help me fix this error', chat_id)
        self.assertIn('normal workflow', str(events))
