"""Plain-words file requests ("write a python file with a simple animal class"): python -m unittest discover -s
tests -v. The AI is replaced by a stand-in; files and chats go to temporary folders."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, engine, file_requests, files, followups, search_history, settings

ANIMAL = 'class Animal:\n    def __init__(self, name):\n        self.name = name\n'


class UnderstandingTests(unittest.TestCase):
    def test_requests_are_understood(self):
        for text, expected in (
                ('write a python file with a simple animal class', ('', '.py', 'a simple animal class')),
                ('create a file', ('', '', '')),
                ('make a text file called notes', ('notes', '.txt', '')),
                ('write a file called shopping.md with my grocery list', ('shopping.md', '.md', 'my grocery list')),
                ('can you create a script that renames photos', ('', '', 'renames photos')),
                ('write me a quick html page that says hello', ('', '.html', 'says hello'))):
            with self.subTest(text=text):
                got = file_requests.understand(text)
                self.assertEqual((got['name'], got['ext'], got['about']), expected)

    def test_ordinary_messages_are_not_file_requests(self):
        for text in ('what is a python file?', 'I wrote a file yesterday', 'how do I make a cake?',
                     'tell me about the class of 2020', '/writefile hello.py'):
            with self.subTest(text=text):
                self.assertIsNone(file_requests.understand(text))

    def test_suggested_names(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(files, 'folder', lambda: Path(folder)):
            self.assertEqual(file_requests.suggest_name('a simple animal class', '.py'), 'animal.py')
            (Path(folder) / 'animal.py').write_text('x')
            self.assertEqual(file_requests.suggest_name('a simple animal class', '.py'), 'animal_2.py')
            self.assertEqual(file_requests.suggest_name('', '.txt'), 'file.txt')


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
        for module in (chats, followups, search_history):
            module.initialize()
        self.patches = [patch.object(files, 'folder', lambda: root / 'files'),
                        patch.object(engine, 'complete_blocking', side_effect=self.ai)]
        for item in self.patches:
            item.start()
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
        if 'speak' in messages[1]['content']:
            return '```python\n' + ANIMAL + '\n    def speak(self):\n        return "..."\n```'
        return '```python\n' + ANIMAL + '```'

    async def send(self, text, chat_id=None, client=None):
        response = await (client or self.pc).post('/api/chat/stream', json={'content': text, 'chat_id': chat_id})
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        chat = next((e['id'] for e in events if e['type'] == 'chat'), chat_id)
        self.statuses = [e['text'] for e in events if e['type'] == 'status']
        message = next((e for e in events if e['type'] == 'message'), {})
        saved = chats.get(chat)['messages'][-1]['content'] if chat else ''
        sends = [b.get('send') for row in message.get('buttons') or [] for b in row]
        return chat, saved, sends

    async def test_the_animal_class_example(self):
        chat, text, sends = await self.send('write a python file with a simple animal class')
        self.assertIn('Here is animal.py', text)
        self.assertEqual(self.statuses, ['✍️ Writing the file…'])     # shown while the AI writes
        self.assertIn('class Animal:', text)
        self.assertNotIn('```', text)                                   # fences are taken off
        self.assertEqual(sends, ['/draft save', '/draft rename', '/draft change', '/draft cancel'])
        self.assertIn('animal.py', self.asked[0][0]['content'])         # the AI is told the name and language
        self.assertIn('Python', self.asked[0][0]['content'])
        self.assertFalse((files.folder() / 'animal.py').exists())      # nothing saved yet
        _, text, sends = await self.send('/draft save', chat)
        self.assertIn('Saved animal.py', text)
        self.assertEqual((files.folder() / 'animal.py').read_text(encoding='utf-8'), ANIMAL)

    async def test_follow_up_questions_for_what_is_missing(self):
        chat, text, sends = await self.send('create a file')
        self.assertIn('What kind of file', text)
        self.assertIn('/draft type .py', sends)
        _, text, _ = await self.send('python', chat)
        self.assertIn('What should be written', text)
        self.assertEqual(self.asked, [])                                # no AI until it knows what to write
        _, text, _ = await self.send('a simple animal class', chat)
        self.assertIn('Here is animal.py', text)
        _, text, _ = await self.send('call it pets', chat)
        self.assertIn('Here is pets.py', text)                         # keeps the extension
        _, text, _ = await self.send('yes', chat)
        self.assertIn('Saved pets.py', text)
        self.assertTrue((files.folder() / 'pets.py').exists())

    async def test_changing_the_draft_and_cancelling(self):
        chat, _, _ = await self.send('write a python file with a simple animal class')
        _, text, _ = await self.send('/draft change', chat)
        self.assertIn('What should change', text)
        _, text, _ = await self.send('add a speak method', chat)
        self.assertIn('def speak', text)
        self.assertIn('Current contents', self.asked[-1][1]['content'])
        _, text, _ = await self.send('/draft cancel', chat)
        self.assertIn('Nothing was saved', text)
        self.assertEqual(list(files.folder().glob('*')) if files.folder().exists() else [], [])
        _, text, _ = await self.send('/draft save', chat)
        self.assertIn('expired', text)

    async def test_save_this_uses_the_last_answer(self):
        chat = chats.create('code')
        chats.add_message(chat, 'user', 'show me hello world in python')
        chats.add_message(chat, 'assistant', "Sure:\n```python\nprint('hello')\n```")
        _, text, _ = await self.send('save this as hello.py', chat)
        self.assertIn('Here is hello.py', text)
        self.assertEqual(self.asked, [])                                # nothing to write: it's the answer itself
        await self.send('/draft save', chat)
        self.assertEqual((files.folder() / 'hello.py').read_text(encoding='utf-8'), "print('hello')\n")

    async def test_an_existing_name_asks_for_another(self):
        files.create_file('animal.py', 'old\n')
        chat, text, _ = await self.send('write a file called animal.py with a simple animal class')
        self.assertIn('Here is animal.py', text)
        _, text, _ = await self.send('/draft save', chat)
        self.assertIn('already exists', text)
        _, text, _ = await self.send('zoo', chat)
        self.assertIn('Here is zoo.py', text)
        await self.send('/draft save', chat)
        self.assertEqual((files.folder() / 'animal.py').read_text(encoding='utf-8'), 'old\n')
        self.assertTrue((files.folder() / 'zoo.py').exists())

    async def test_writefile_with_a_description_writes_the_code(self):
        chat, _, _ = await self.send('/writefile test.py')
        _, text, sends = await self.send('Write a simple python class for different animals types', chat)
        self.assertIn('Here is test.py', text)
        self.assertIn('class Animal:', text)
        self.assertIn('different animals types', self.asked[-1][1]['content'])
        self.assertFalse((files.folder() / 'test.py').exists())         # a draft first
        await self.send('/draft save', chat)
        self.assertEqual((files.folder() / 'test.py').read_text(encoding='utf-8'), ANIMAL)
        # The same in one message.
        chat, text, _ = await self.send('/writefile zoo.py\nCreate a zoo class that holds animals')
        self.assertIn('Here is zoo.py', text)
        # Real contents are still saved exactly as sent, without the AI.
        asked = len(self.asked)
        chat, _, _ = await self.send('/writefile exact.py')
        await self.send("print('as typed')", chat)
        self.assertEqual((files.folder() / 'exact.py').read_text(encoding='utf-8'), "print('as typed')\n")
        self.assertEqual(len(self.asked), asked)

    async def test_other_devices_need_the_administrator(self):
        settings.save({'require_sign_in': False})
        phone = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('192.168.1.50', 5000)),
                                  base_url='http://beyond.test')
        _, text, _ = await self.send('write a python file with a simple animal class', client=phone)
        await phone.aclose()
        self.assertIn('administrator', text)
        self.assertEqual(self.asked, [])


if __name__ == '__main__':
    unittest.main()
