"""Conversation branches (Phase 47): python -m unittest tests.test_branches -v. The AI is a stand-in; chats go to a
temporary folder."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, engine, followups, learning, memory, rules, search_history, settings


class BranchTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from app.server import app
        cls.app = app

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp.name)
        self.saved = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR, chats.DB_PATH, settings.FILE = root, root / 'chats.sqlite3', root / 'settings.json'
        settings.save({'auto_facts': False, 'auto_lookup': False})
        for module in (chats, followups, search_history, memory, rules, learning):
            module.initialize()
        self.calls = []
        self.engine = patch.object(engine, 'chat_stream', self.ai)
        self.engine.start()
        self.pc = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('127.0.0.1', 5000)),
                                    base_url='http://beyond.test')

    async def asyncTearDown(self):
        await self.pc.aclose()
        self.engine.stop()
        config.DATA_DIR, chats.DB_PATH, settings.FILE = self.saved
        self.temp.cleanup()

    async def ai(self, history, background='', max_tokens=None, temperature=None):
        self.calls.append((history, background))
        yield f'Answer about {history[-1]["content"]}'

    async def ask(self, text, chat=None):
        response = await self.pc.post('/api/chat/stream', json={'content': text, 'chat_id': chat})
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        return (next(e['id'] for e in events if e['type'] == 'chat'),
                next(e['id'] for e in events if e['type'] == 'message'))

    async def branch(self, message_id):
        return await self.pc.post(f'/api/messages/{message_id}/branch')

    async def vacation(self):
        chat, a1 = await self.ask('Plan a summer vacation')
        _, a2 = await self.ask('Where should we go?', chat)
        _, a3 = await self.ask('What about camping there?', chat)
        learning.rate(a2, 1, '')
        return chat, a1, a2, a3

    async def test_a_branch_copies_the_conversation_up_to_the_chosen_answer(self):
        chat, a1, a2, a3 = await self.vacation()
        reply = await self.branch(a2)
        self.assertEqual(reply.status_code, 200)
        branch = chats.get(reply.json()['id'])
        self.assertEqual(branch['title'], 'Plan a summer vacation (branch)')
        self.assertEqual((branch['branched_from'], branch['branched_at'], branch['branched_from_title']),
                         (chat, a2, 'Plan a summer vacation'))
        self.assertEqual([m['content'] for m in branch['messages']],
                         ['Plan a summer vacation', 'Answer about Plan a summer vacation',
                          'Where should we go?', 'Answer about Where should we go?'])
        # Only the branch's newest answer has 👍 👎 🔄; ratings stay with the original.
        self.assertTrue(learning.has_retry(branch['messages'][-1]['buttons']))
        self.assertEqual(branch['messages'][1]['buttons'], [])
        copied = chats.get_message(branch['messages'][-1]['id'])
        self.assertIsNone(copied['rating'])
        # The original is unchanged, and the branch shows in the list with its mark.
        self.assertEqual(len(chats.get(chat)['messages']), 6)
        listed = {c['id']: c for c in chats.list_chats()}
        self.assertEqual(listed[branch['id']]['branched_from'], chat)
        self.assertIsNone(listed[chat]['branched_from'])

    async def test_the_branch_continues_on_its_own(self):
        chat, a1, a2, a3 = await self.vacation()
        branch = (await self.branch(a2)).json()['id']
        await self.ask('What about hotels instead?', branch)
        history, _ = self.calls[-1]
        self.assertEqual([m['content'] for m in history],
                         ['Plan a summer vacation', 'Answer about Plan a summer vacation', 'Where should we go?',
                          'Answer about Where should we go?', 'What about hotels instead?'])
        self.assertNotIn('camping', json.dumps(history))
        self.assertEqual(len(chats.get(chat)['messages']), 6)   # the original didn't get the new question

    async def test_only_ai_answers_can_be_branched_from(self):
        chat, a1, a2, a3 = await self.vacation()
        question = chats.get(chat)['messages'][0]['id']
        self.assertEqual((await self.branch(question)).status_code, 409)
        _, help_reply = await self.ask('/help', chat)
        self.assertEqual((await self.branch(help_reply)).status_code, 409)
        self.assertEqual((await self.branch(999999)).status_code, 409)
        chats.set_buttons(a3, [], kind='retried')   # an answer replaced by Try again
        self.assertEqual((await self.branch(a3)).status_code, 409)

    async def test_deleting_either_chat_keeps_the_other(self):
        chat, a1, a2, a3 = await self.vacation()
        branch = (await self.branch(a2)).json()['id']
        second = (await self.branch(a3)).json()['id']
        await self.pc.delete(f'/api/chats/{branch}')
        self.assertIsNotNone(chats.get(chat))
        await self.pc.delete(f'/api/chats/{chat}')
        kept = chats.get(second)
        self.assertEqual(len(kept['messages']), 6)
        self.assertIsNone(kept['branched_from_title'])   # the page says the original was deleted

    async def test_a_branch_of_a_branch_keeps_one_suffix(self):
        chat, a1, a2, a3 = await self.vacation()
        first = chats.get((await self.branch(a3)).json()['id'])
        again = chats.get((await self.branch(first['messages'][-1]['id'])).json()['id'])
        self.assertEqual(again['title'], 'Plan a summer vacation (branch)')
        self.assertEqual(again['branched_from'], first['id'])

    async def test_recall_finds_each_exchange_once(self):
        chat, a1, a2, a3 = await self.vacation()
        branch = (await self.branch(a3)).json()['id']
        # From a third chat, the vacation exchange is recalled once, not once per copy.
        found = memory.search('summer vacation camping plan', ())
        self.assertEqual(len([f for f in found if 'summer vacation' in f['user'].lower()]), 1)
        # In the branch, the original's copy of what's already in the conversation isn't recalled again.
        sent = [m['id'] for m in chats.get(branch)['messages']]
        found = memory.search('summer vacation camping plan', sent)
        self.assertFalse([f for f in found if 'summer vacation' in f['user'].lower()])


if __name__ == '__main__':
    unittest.main()
