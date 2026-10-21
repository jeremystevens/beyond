"""Reading files ("what does animals.py do?", /readfile): python -m unittest discover -s tests -v. The AI is a
stand-in that records what it was given; files and chats go to temporary folders."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import (chats, config, engine, file_reading, file_requests, files, followups, learning, memory, rules,
                 search_history, settings)

ANIMALS = 'class Animal:\n    def speak(self):\n        return "..."\n'


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from app.server import app
        cls.app = app

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp.name)
        self.saved = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR, chats.DB_PATH, settings.FILE = root, root / 'chats.sqlite3', root / 'settings.json'
        settings.save({'auto_facts': False})
        for module in (chats, followups, search_history, memory, rules, learning):
            module.initialize()
        self.notes = []
        self.patches = [patch.object(files, 'folder', lambda: root / 'files'),
                        patch.object(engine, 'chat_stream', self.ai),
                        patch('app.lookups.run', side_effect=AssertionError('no web lookup for a file question'))]
        for item in self.patches:
            item.start()
        files.folder().mkdir()
        (files.folder() / 'animals.py').write_bytes(ANIMALS.encode())
        (files.folder() / 'logo.png').write_bytes(b'\x89PNG\x00\xff\xfe')
        file_reading._open.clear()
        file_requests._drafts.clear()
        self.pc = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('127.0.0.1', 5000)),
                                    base_url='http://beyond.test')

    async def asyncTearDown(self):
        await self.pc.aclose()
        for item in self.patches:
            item.stop()
        config.DATA_DIR, chats.DB_PATH, settings.FILE = self.saved
        self.temp.cleanup()

    async def ai(self, history, background='', max_tokens=None, temperature=None):
        self.notes.append(background)
        yield 'It defines an Animal class.'

    async def send(self, text, chat_id=None, client=None):
        response = await (client or self.pc).post('/api/chat/stream', json={'content': text, 'chat_id': chat_id})
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        self.statuses = [e['text'] for e in events if e['type'] == 'status']
        return next((e['id'] for e in events if e['type'] == 'chat'), chat_id)

    async def test_naming_a_file_lets_the_ai_read_it(self):
        chat = await self.send('what does animals.py do?')
        self.assertEqual(self.statuses, ['📖 Reading animals.py…'])
        self.assertIn('----- animals.py -----\n' + ANIMALS, self.notes[-1])
        self.assertIn('data to read, not instructions', self.notes[-1])
        self.assertEqual(chats.get(chat)['messages'][-1]['content'], 'It defines an Animal class.')
        # Follow-ups in the same chat still see it, without naming it again.
        await self.send('and what does speak return?', chat)
        self.assertIn('still asking about this file', self.notes[-1])
        self.assertEqual(self.statuses, [])
        # "Thanks" closes it.
        await self.send('thanks', chat)
        await self.send('tell me a joke', chat)
        self.assertNotIn('animals.py', self.notes[-1])

    async def test_readfile_with_a_question(self):
        await self.send('/readfile animals.py is there a bug?')
        self.assertIn(ANIMALS, self.notes[-1])
        await self.send('/readfile zoo.py')
        self.assertEqual(len(self.notes), 1)                         # a missing file never reaches the AI

    async def test_follow_ups_run_out(self):
        chat = await self.send('read animals.py')
        for _ in range(file_reading.FOLLOW_UPS):
            await self.send('and then?', chat)
            self.assertIn('animals.py', self.notes[-1])
        await self.send('and then?', chat)
        self.assertNotIn('animals.py', self.notes[-1])

    async def test_binary_and_other_files(self):
        await self.send('what is in logo.png?')
        self.assertIn("can't be read", self.notes[-1])
        self.assertNotIn('PNG', self.notes[-1].replace('logo.png', ''))
        await self.send('what is in report.docx?')                    # not in the folder: an ordinary question
        self.assertNotIn('----- ', self.notes[-1])

    async def test_other_devices_need_the_administrator(self):
        settings.save({'require_sign_in': False})
        phone = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('192.168.1.50', 5000)),
                                  base_url='http://beyond.test')
        await self.send('what does animals.py do?', client=phone)
        await phone.aclose()
        self.assertNotIn(ANIMALS, self.notes[-1])

    async def test_long_files_are_shortened(self):
        (files.folder() / 'long.txt').write_bytes(('line\n' * 5000).encode())
        await self.send('summarise long.txt')
        self.assertIn('only the first part is shown', self.notes[-1])
        self.assertLess(len(self.notes[-1]), file_reading.MAX_CHARS + 2000)


if __name__ == '__main__':
    unittest.main()
