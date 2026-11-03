"""Real ASGI stream: supported arithmetic is computed, retained in chat and never inferred."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from app import chats, config, engine, followups, learning, memory, rules, search_history, settings
from app.tools import calculator
from tests.test_word_math import TIME, BUDGET, UPDATE


class WordMathRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from app import server
        self.server = server
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patchers = [patch.object(config, 'DATA_DIR', root), patch.object(chats, 'DB_PATH', root/'chats.sqlite3'),
                         patch.object(settings, 'FILE', root/'settings.json'), patch.object(server.notify, 'show')]
        for item in self.patchers:
            item.start()
        for module in (chats, followups, learning, memory, rules, search_history):
            module.initialize()
        settings.save({'auto_lookup': True, 'auto_facts': True, 'speech_enabled': False})
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=('127.0.0.1', 5000)), base_url='http://beyond.test')

    async def asyncTearDown(self):
        await self.client.aclose()
        for item in reversed(self.patchers):
            item.stop()
        self.temp.cleanup()

    async def ask(self, text, chat_id=None, guided=False):
        response = await self.client.post('/api/chat/stream', json={'content': text, 'chat_id': chat_id, 'think_through': guided})
        self.assertEqual(response.status_code, 200, response.text)
        events = [json.loads(line) for line in response.text.splitlines() if line]
        self.assertFalse(any(e['type'] == 'error' for e in events), events)
        return events

    async def test_supported_families_use_calculator_and_skip_model_lookup_and_fact_pickup(self):
        cases = [(TIME, '20 minutes remain:'), (BUDGET, '$280.00 remains'),
                 ('I pay $10 for three items costing $2.40 each and one item costing $1.75. There is no tax or other charge. How much change do I receive?', '$1.05 in change'),
                 ('A shelf supports 1 kg. It already holds 250 g. Each box weighs 125 g. How many whole boxes can I add?', '6 whole boxes'),
                 ('I need at least 9 clips. Store A sells packs of 5 for $6. Store B sells packs of 8 for $9. Packs cannot be split. Which has the lowest total cost?', 'Store A has the lowest total: $12.00')]
        with patch.object(engine, 'chat_stream', side_effect=AssertionError('No model for supported arithmetic')), \
             patch.object(engine, 'complete', side_effect=AssertionError('No extraction/review/fact inference')), \
             patch.object(self.server.lookups, 'run', side_effect=AssertionError('No external lookup')), \
             patch.object(calculator, 'evaluate', wraps=calculator.evaluate) as calculate:
            for question, expected in cases:
                events = await self.ask(question)
                text = ''.join(e.get('text','') for e in events if e['type']=='token')
                self.assertIn(expected, text)
                self.assertTrue(any('Calculated locally' in e.get('text','') for e in events if e['type']=='status'))
                chat_id = next(e['id'] for e in events if e['type']=='chat')
                saved = chats.get(chat_id)['messages']
                self.assertEqual(saved[-1]['content'], text)
                self.assertTrue(all(m['kind']=='chat' and not m.get('lookup') for m in saved))
        self.assertGreater(calculate.call_count, 5)
        self.assertEqual(memory.all_facts(), [])

    async def test_budget_followup_uses_user_facts_preserves_day_and_normal_chat_context(self):
        with patch.object(engine, 'chat_stream', side_effect=AssertionError('No inference')):
            events = await self.ask(BUDGET)
            chat_id = next(e['id'] for e in events if e['type']=='chat')
            chats.add_message(chat_id, 'assistant', 'Incorrect earlier arithmetic: $180 left, then $20 over.')
            events = await self.ask(UPDATE, chat_id)
        text = ''.join(e.get('text','') for e in events if e['type']=='token')
        self.assertIn('$130.00 remains', text)
        self.assertIn('$70.00 over budget', text)
        self.assertEqual(text.count('Finishes on day 5.'), 2)
        history = chats.recent_messages(chat_id, 12)
        self.assertIn(BUDGET, [m['content'] for m in history])
        self.assertIn(UPDATE, [m['content'] for m in history])

    async def test_regular_number_prose_and_unsupported_math_still_reach_model(self):
        settings.save({'auto_facts': False})
        seen=[]
        async def reply(history, *args, **kwargs):
            seen.append(history[-1]['content'])
            yield 'An ordinary model response, without a verification claim.'
        with patch.object(engine, 'chat_stream', reply):
            for question in ('I have 3 cats and 2 dogs. Tell me about their care.',
                             'A repair costs about $220 and a replacement costs $420. Budget is $500. Which fits?'):
                events = await self.ask(question)
                self.assertFalse(any('Calculated locally' in e.get('text','') for e in events))
        self.assertEqual(len(seen), 2)

    async def test_guided_flag_does_not_add_inference_for_supported_arithmetic(self):
        with patch.object(engine, 'chat_stream', side_effect=AssertionError('No final model')), \
             patch.object(engine, 'complete', side_effect=AssertionError('No preparatory model')):
            events = await self.ask(TIME, guided=True)
        self.assertIn('20 minutes remain', str(events))
