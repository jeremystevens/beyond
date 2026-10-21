"""Editing files ("add a speak method to animals.py", /editfile, /fileundo): python -m unittest discover -s tests
-v. The AI is replaced by a stand-in; files and chats go to temporary folders."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, engine, file_requests, files, followups, search_history, settings

ORIGINAL = 'class Animal:\n    def __init__(self, name):\n        self.name = name\n'
SPEAK = ORIGINAL + '\n    def speak(self):\n        return f"{self.name} makes a sound"\n'
TIDY = '"""Animals."""\n\n\n' + ORIGINAL


class EditRuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = patch.object(files, 'folder', lambda: Path(self.temp.name))
        self.folder.start()
        (Path(self.temp.name) / 'animals.py').write_text(ORIGINAL, encoding='utf-8')

    def tearDown(self):
        self.folder.stop()
        self.temp.cleanup()

    def test_what_counts_as_an_edit(self):
        self.assertEqual(file_requests.edit_request('add a speak method to animals.py')['name'], 'animals.py')
        self.assertEqual(file_requests.edit_request('improve animals.py')['instruction'], file_requests.JUDGEMENT_TEXT)
        self.assertEqual(file_requests.edit_request('fix the bugs in animals.py')['instruction'], file_requests.JUDGEMENT_TEXT)
        self.assertEqual(file_requests.edit_request('edit animals.py')['instruction'], '')
        self.assertEqual(file_requests.edit_request('edit zoo.py'), {'missing': 'zoo.py'})
        for text in ('what is in animals.py?', 'write a file called notes.md and add my list', 'improve my mood',
                     'write a python file with an animal class'):
            with self.subTest(text=text):
                self.assertIsNone(file_requests.edit_request(text))

    def test_everyday_add_and_make_never_start_a_file(self):
        for text in ('add 5 and 7', 'I need to add milk to my list', 'can you add that to my notes',
                     "let's add some spice to the recipe", "I'll add animals.py to GitHub later",
                     'I added animals.py yesterday', 'make a workout program for me', 'build a document for school',
                     "let's save it as a surprise for mom", 'add some salt', 'how do I add a printer?'):
            with self.subTest(text=text):
                self.assertIsNone(file_requests.edit_request(text))
                self.assertIsNone(file_requests.understand(text))
                self.assertIsNone(file_requests.plan(None, text, True))
        for text in ('can you add a repr to animals.py', 'please improve animals.py', 'ok, add a docstring to animals.py'):
            with self.subTest(text=text):
                self.assertEqual(file_requests.edit_request(text)['name'], 'animals.py')

    def test_saving_keeps_a_version_for_undo(self):
        files.save_edit('animals.py', SPEAK, ORIGINAL)
        self.assertEqual(files.read('animals.py'), SPEAK)
        files.save_edit('animals.py', TIDY, SPEAK)
        files.undo('animals.py')
        self.assertEqual(files.read('animals.py'), SPEAK)
        files.undo('animals.py')
        self.assertEqual(files.read('animals.py'), ORIGINAL)
        with self.assertRaises(files.FileWriteError):
            files.undo('animals.py')                                   # nothing earlier
        self.assertEqual([f['name'] for f in files.listing()], ['animals.py'])   # versions aren't listed

    def test_a_file_changed_meanwhile_is_not_overwritten(self):
        (Path(self.temp.name) / 'animals.py').write_text('changed elsewhere\n', encoding='utf-8')
        with self.assertRaises(files.FileWriteError):
            files.save_edit('animals.py', SPEAK, ORIGINAL)
        self.assertEqual(files.read('animals.py'), 'changed elsewhere\n')

    def test_only_text_files_in_the_folder(self):
        (Path(self.temp.name) / 'image.png').write_bytes(b'\x89PNG\x00\xff\xfe')
        for name in ('image.png', 'missing.py', '../animals.py'):
            with self.subTest(name=name), self.assertRaises(files.FileWriteError):
                files.read(name)


class EditConversationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from app.server import app
        cls.app = app

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp.name)
        self.saved = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR, chats.DB_PATH, settings.FILE = root, root / 'chats.sqlite3', root / 'settings.json'
        for module in (chats, followups, search_history):
            module.initialize()
        self.patches = [patch.object(files, 'folder', lambda: root / 'files'),
                        patch.object(engine, 'complete_blocking', side_effect=self.ai)]
        for item in self.patches:
            item.start()
        files.folder().mkdir()
        (files.folder() / 'animals.py').write_text(ORIGINAL, encoding='utf-8')
        file_requests._drafts.clear()
        self.asked = []
        self.pc = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('127.0.0.1', 5000)),
                                    base_url='http://beyond.test')

    async def asyncTearDown(self):
        await self.pc.aclose()
        for item in self.patches:
            item.stop()
        config.DATA_DIR, chats.DB_PATH, settings.FILE = self.saved
        self.temp.cleanup()

    def ai(self, messages, max_tokens, temperature):
        self.asked.append(messages)
        request = messages[1]['content']
        if 'best judgement' in request:
            return '```python\n' + TIDY + '```'
        if 'nothing' in request:
            return request.split('\n', 1)[1].split('\n\nChange to make')[0]
        return SPEAK

    async def send(self, text, chat_id=None):
        response = await self.pc.post('/api/chat/stream', json={'content': text, 'chat_id': chat_id})
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        chat = next((e['id'] for e in events if e['type'] == 'chat'), chat_id)
        message = next((e for e in events if e['type'] == 'message'), {})
        self.statuses = [e['text'] for e in events if e['type'] == 'status']
        sends = [b.get('send') for row in message.get('buttons') or [] for b in row]
        return chat, chats.get(chat)['messages'][-1]['content'], sends

    def current(self):
        return (files.folder() / 'animals.py').read_text(encoding='utf-8')

    async def test_plain_words_edit_with_a_diff_then_save_and_undo(self):
        chat, text, sends = await self.send('add a speak method to animals.py')
        self.assertEqual(self.statuses, ['✍️ Editing animals.py…'])
        self.assertIn('Here are the changes to animals.py (3 lines added, 0 removed', text)
        self.assertIn('+    def speak(self):', text)
        self.assertNotIn('+class Animal', text)                          # only what changed
        self.assertIn(ORIGINAL, self.asked[0][1]['content'])            # the AI sees the file
        self.assertEqual(self.current(), ORIGINAL)                       # nothing saved yet
        self.assertEqual(sends, ['/draft save', '/draft change', '/draft cancel'])
        chat, text, sends = await self.send('yes', chat)
        self.assertIn('Saved the changes to animals.py', text)
        self.assertEqual(self.current(), SPEAK)
        self.assertIn('/fileundo animals.py', sends)
        await self.send('/fileundo animals.py', chat)
        self.assertEqual(self.current(), ORIGINAL)

    async def test_asks_what_to_change_or_uses_its_judgement(self):
        chat, text, sends = await self.send('edit animals.py')
        self.assertIn('What should change in animals.py', text)
        self.assertEqual(sends, ['/draft judgement', '/draft cancel'])
        self.assertEqual(self.asked, [])
        _, text, _ = await self.send('/draft judgement', chat)
        self.assertIn('best judgement', self.asked[-1][1]['content'])
        self.assertIn('+"""Animals."""', text)
        await self.send('/draft save', chat)
        self.assertEqual(self.current(), TIDY)

    async def test_editfile_command_and_a_further_change(self):
        chat, text, _ = await self.send('/editfile animals.py\nimprove')
        self.assertIn('+"""Animals."""', text)                           # "improve" alone: its own judgement
        _, text, _ = await self.send('/draft change', chat)
        self.assertIn('What should change', text)
        _, text, _ = await self.send('add a speak method', chat)
        self.assertIn(TIDY, self.asked[-1][1]['content'])               # builds on the draft, not the original
        _, text, _ = await self.send('/draft cancel', chat)
        self.assertIn('unchanged', text)
        self.assertEqual(self.current(), ORIGINAL)
        chat, text, _ = await self.send('/editfile animals.py')
        self.assertIn('What should change in animals.py', text)
        _, text, _ = await self.send('add a speak method', chat)
        self.assertIn('+    def speak(self):', text)

    async def test_no_change_and_missing_files(self):
        chat, text, _ = await self.send('/editfile animals.py\nchange nothing at all')
        self.assertIn("didn't change anything", text)
        _, text, sends = await self.send('/editfile zoo.py\nadd a lion')
        self.assertIn("There's no zoo.py", text)
        self.assertEqual(self.asked[-1:], self.asked[-1:])   # the AI isn't asked about a missing file
        self.assertEqual(len(self.asked), 1)


if __name__ == '__main__':
    unittest.main()
