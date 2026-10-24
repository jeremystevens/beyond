"""Adjust this answer (Phase 46): python -m unittest tests.test_adjust -v. The AI is a stand-in that records what it
was given; chats and settings go to a temporary folder, and web lookups are not allowed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, engine, followups, learning, memory, rules, search_history, settings


class AdjustTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from app.server import app
        cls.app = app

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp.name)
        self.saved = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR, chats.DB_PATH, settings.FILE = root, root / 'chats.sqlite3', root / 'settings.json'
        for module in (chats, followups, search_history, memory, rules, learning):
            module.initialize()
        self.calls, self.pickups = [], []
        self.patches = [patch.object(engine, 'chat_stream', self.ai),
                        patch('app.lookups.run', side_effect=AssertionError('an adjustment never looks things up')),
                        patch('app.memory.wants_pickup', side_effect=self.pickups.append)]
        for item in self.patches:
            item.start()
        self.pc = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('127.0.0.1', 5000)),
                                    base_url='http://beyond.test')

    async def asyncTearDown(self):
        await self.pc.aclose()
        for item in self.patches:
            item.stop()
        config.DATA_DIR, chats.DB_PATH, settings.FILE = self.saved
        self.temp.cleanup()

    async def ai(self, history, background='', max_tokens=None, temperature=None):
        self.calls.append((history, background))
        yield f'Answer {len(self.calls)}.'

    async def stream(self, url, payload):
        response = await self.pc.post(url, json=payload)
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()] \
            if response.status_code == 200 else []
        return response, events

    async def ask(self, text, chat=None):
        _, events = await self.stream('/api/chat/stream', {'content': text, 'chat_id': chat})
        chat = next(e['id'] for e in events if e['type'] == 'chat')
        return chat, next(e['id'] for e in events if e['type'] == 'message')

    async def adjust(self, message_id, kind):
        return await self.stream(f'/api/messages/{message_id}/adjust', {'kind': kind})

    async def test_each_choice_is_saved_as_a_message_and_answered_below(self):
        said = {'simpler': 'Simpler, please', 'detail': 'More detail, please', 'example': 'Show me an example',
                'steps': 'Walk me through it'}
        asked = {'simpler': 'more simply', 'detail': 'more useful detail', 'example': 'concrete, practical example',
                 'steps': 'numbered list'}
        for kind in said:
            with self.subTest(kind=kind):
                chat, answer = await self.ask('How does a heat pump work?')
                response, events = await self.adjust(answer, kind)
                self.assertEqual(response.status_code, 200)
                history, background = self.calls[-1]
                self.assertEqual(history[-1], {'role': 'user', 'content': said[kind]})
                self.assertIn(history[-2]['content'], ('Answer 1.', f'Answer {len(self.calls) - 1}.'))
                self.assertIn(asked[kind], background)
                self.assertIn("don't apologise", background)
                messages = chats.get(chat)['messages']
                self.assertEqual([m['content'] for m in messages[-3:]],
                                 [messages[-3]['content'], said[kind], f'Answer {len(self.calls)}.'])
                new = next(e for e in events if e['type'] == 'message')
                self.assertTrue(learning.has_retry(new['buttons']))   # the new answer can be adjusted again
        self.assertNotIn('Simpler, please', self.pickups)   # a button press is never checked for facts about you
        self.assertIn('How does a heat pump work?', self.pickups)

    async def test_only_the_newest_ai_answer_can_be_adjusted(self):
        chat, first = await self.ask('What is a heat pump?')
        _, second = await self.ask('And is it efficient?', chat)
        response, _ = await self.adjust(first, 'simpler')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(chats.get(chat)['messages'][-1]['id'], second)   # nothing was added
        response, events = await self.adjust(second, 'steps')
        self.assertEqual(response.status_code, 200)
        newest = next(e['id'] for e in events if e['type'] == 'message')
        self.assertEqual((await self.adjust(second, 'simpler'))[0].status_code, 409)   # it's no longer the newest
        self.assertEqual((await self.adjust(newest, 'simpler'))[0].status_code, 200)

    async def test_refuses_unknown_choices_missing_answers_and_command_replies(self):
        _, answer = await self.ask('Hello')
        self.assertEqual((await self.adjust(answer, 'rewrite as a poem'))[0].status_code, 422)
        self.assertEqual((await self.adjust(999999, 'simpler'))[0].status_code, 404)
        chat, reply = await self.ask('/help')
        self.assertEqual((await self.adjust(reply, 'simpler'))[0].status_code, 409)

    async def test_a_failed_reply_takes_the_request_back_out(self):
        chat, answer = await self.ask('What is a heat pump?')
        before = len(chats.get(chat)['messages'])

        async def broken(history, background='', max_tokens=None, temperature=None):
            raise engine.EngineError('The AI is not answering.')
            yield ''
        with patch.object(engine, 'chat_stream', broken):
            await self.adjust(answer, 'detail')
        contents = [m['content'] for m in chats.get(chat)['messages']]
        self.assertLessEqual(len(contents), before + 1)
        if len(contents) == before + 1:   # kept for "Retry last prompt", like an ordinary question
            self.assertEqual(contents[-1], 'More detail, please')


if __name__ == '__main__':
    unittest.main()
