"""/writefile checks: python -m unittest discover -s tests -v. Files go to a temporary folder and chats to a
temporary database; requests come from this PC (127.0.0.1) or a phone (192.168.1.50)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import auth, chats, commands, config, files, followups, search_history, settings


class FileRuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = patch.object(files, 'folder', lambda: Path(self.temp.name) / 'files')
        self.folder.start()

    def tearDown(self):
        self.folder.stop()
        self.temp.cleanup()

    def test_only_plain_names_with_an_extension(self):
        for bad in ('../escape.py', 'sub/dir.py', 'C:\\x.py', 'noextension', 'CON.txt', 'nul.py', 'trailing.py ',
                    'dot.', '.hidden', 'a' * 130 + '.py', 'what?.py'):
            with self.subTest(bad=bad), self.assertRaises(files.FileWriteError):
                files.target_path(bad)
        self.assertEqual(files.target_path('hello world.py').name, 'hello world.py')

    def test_writes_once_and_never_overwrites(self):
        target, size = files.create_file('hello.py', "print('hi')")
        self.assertEqual(target.read_text(encoding='utf-8'), "print('hi')\n")
        self.assertEqual(size, 12)
        with self.assertRaises(files.FileWriteError):
            files.create_file('hello.py', 'something else')
        self.assertEqual(target.read_text(encoding='utf-8'), "print('hi')\n")
        with self.assertRaises(files.FileWriteError):
            files.create_file('big.txt', 'x' * (files.MAX_BYTES + 1))
        with self.assertRaises(files.FileWriteError):
            files.create_file('empty.txt', '   ')
        self.assertEqual([f['name'] for f in files.listing()], ['hello.py'])

    def test_waiting_for_the_contents_expires(self):
        files.wait_for(7, 'later.txt')
        self.assertEqual(files.waiting(7), 'later.txt')
        with patch.object(files.time, 'monotonic', return_value=files.time.monotonic() + files.WAIT_SECONDS + 1):
            self.assertIsNone(files.waiting(7))


class ChatTests(unittest.IsolatedAsyncioTestCase):
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
        self.folder = patch.object(files, 'folder', lambda: root / 'files')
        self.folder.start()
        files._pending.clear()
        self.pc = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('127.0.0.1', 5000)),
                                    base_url='http://beyond.test')
        self.phone = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('192.168.1.50', 5000)),
                                       base_url='http://beyond.test')

    async def asyncTearDown(self):
        await self.pc.aclose()
        await self.phone.aclose()
        self.folder.stop()
        config.DATA_DIR, chats.DB_PATH, settings.FILE = self.saved
        self.temp.cleanup()

    async def send(self, text, chat_id=None, client=None):
        response = await (client or self.pc).post('/api/chat/stream', json={'content': text, 'chat_id': chat_id})
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        message = next((e for e in events if e['type'] == 'message'), None)
        return events[0].get('id'), message

    async def test_one_message_with_the_contents(self):
        chat, reply = await self.send("/writefile hello.py\nprint('hi')\n    indented()")
        saved = chats.get(chat)['messages'][-1]['content']
        self.assertIn('Saved hello.py', saved)
        self.assertIn('never run', saved)
        self.assertEqual((files.folder() / 'hello.py').read_text(encoding='utf-8'), "print('hi')\n    indented()\n")
        button = reply['buttons'][0][0]
        self.assertEqual(button['url'], '/api/files/hello.py')
        download = await self.pc.get(button['url'])
        self.assertEqual((download.status_code, download.content), (200, b"print('hi')\n    indented()\n"))
        self.assertIn('attachment', download.headers['content-disposition'])

    async def test_contents_in_the_next_message_and_cancel(self):
        chat, _ = await self.send('/writefile notes.md')
        self.assertEqual(files.waiting(chat), 'notes.md')
        with patch('app.engine.chat_stream') as ai:
            _, reply = await self.send('# Notes\n\n- one', chat)
            ai.assert_not_called()                                   # the contents never go to the AI
        self.assertEqual((files.folder() / 'notes.md').read_text(encoding='utf-8'), '# Notes\n\n- one\n')
        self.assertIsNone(files.waiting(chat))
        await self.send('/writefile later.txt', chat)
        await self.send('/cancelwrite', chat)
        self.assertIsNone(files.waiting(chat))
        _, listing = await self.send('/files', chat)
        self.assertEqual([b['url'] for row in listing['buttons'] for b in row], ['/api/files/notes.md'])

    async def test_existing_files_are_kept(self):
        await self.send('/writefile keep.txt\nfirst')
        _, reply = await self.send('/writefile keep.txt\nsecond')
        self.assertFalse(reply['buttons'])
        self.assertEqual((files.folder() / 'keep.txt').read_text(encoding='utf-8'), 'first\n')

    async def test_other_devices_need_the_administrator_sign_in(self):
        settings.save({'require_sign_in': False})                 # even with sign-in off, writing files is admin-only
        _, reply = await self.send('/writefile phone.py\nprint(1)', client=self.phone)
        self.assertFalse((files.folder() / 'phone.py').exists())
        self.assertFalse(reply['buttons'])
        await self.send('/writefile secret.txt\nshh')
        self.assertEqual((await self.phone.get('/api/files/secret.txt')).status_code, 403)
        with patch.object(auth, 'is_admin', return_value=True):
            self.assertEqual((await self.phone.get('/api/files/secret.txt')).status_code, 200)
            await self.send('/writefile phone.py\nprint(1)', client=self.phone)
        self.assertTrue((files.folder() / 'phone.py').exists())

    async def test_downloads_only_from_the_files_folder(self):
        for name in ('..%2Fsettings.json', '..%5Csettings.json', 'missing.txt'):
            with self.subTest(name=name):
                self.assertIn((await self.pc.get('/api/files/' + name)).status_code, (404, 405))

    def test_listed_in_help(self):
        self.assertIn('/writefile', commands.run('/help').text)

    async def test_file_help_shows_examples_to_anyone(self):
        settings.save({'require_sign_in': False})
        _, reply = await self.send('/filehelp', client=self.phone)        # just help: no administrator needed
        text = chats.get(_)['messages'][-1]['content']
        for example in ('write a python file with a simple animal class', '/writefile animals.py', '/cancelwrite',
                        'never overwrites a file', '/editfile animals.py'):
            self.assertIn(example, text)
        self.assertEqual(reply['buttons'], [[{'label': '📂 My files', 'send': '/files'}]])
        self.assertEqual(commands.run('/writehelp').text, commands.run('/filehelp').text)


if __name__ == '__main__':
    unittest.main()
