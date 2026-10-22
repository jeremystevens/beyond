"""Phase 22 lifecycle/API tests. Uses temporary storage and a fake vision worker."""
import asyncio
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app import chats, config, settings
from tests.support import closing_connections
from app.tools import vision
from test_scan import png


class VisionSettingsTests(unittest.TestCase):
    def test_clean_defaults_and_path_validation(self):
        self.assertFalse(config.DEFAULTS['vision_enabled'])
        self.assertEqual(config.DEFAULTS['vision_model'], '')
        for change in ({'vision_threads': 0}, {'vision_timeout': True},
                       {'vision_executable': 'bad.cmd'}, {'vision_model': 'bad.bin'}):
            with self.subTest(change=change), self.assertRaises(settings.SettingsError):
                settings.validate(change)
        self.assertEqual(settings.validate({'vision_threads': 12}), {'vision_threads': 12})
        with patch.object(settings, 'load', return_value=dict(config.DEFAULTS)), self.assertRaises(vision.VisionError):
            vision.configuration()


class VisionProcessTests(unittest.TestCase):
    def values(self):
        return {'vision_executable': 'cpu.exe', 'vision_model': 'model.gguf',
                'vision_mmproj': 'projector.gguf', 'vision_threads': 12, 'vision_timeout': 60}

    def test_cpu_arguments_and_closed_input(self):
        import subprocess
        process = Mock(returncode=0)
        process.communicate.return_value = ('A **red square**.', '')
        process.poll.return_value = 0
        with patch.object(vision.subprocess, 'Popen', return_value=process) as launch:
            answer = vision.ask(png(False), 'Describe it', self.values())
        self.assertEqual(answer, 'A red square.')
        args, kwargs = launch.call_args.args[0], launch.call_args.kwargs
        self.assertEqual(args[args.index('-ngl')+1], '0')
        self.assertIn('--no-mmproj-offload', args)
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.assertFalse(kwargs.get('shell', False))

    def test_timeout_kills_child(self):
        process = Mock(returncode=0)
        process.poll.return_value = None
        process.communicate.return_value = ('', '')
        with patch.object(vision.subprocess, 'Popen', return_value=process), \
                patch.object(vision.time, 'monotonic', side_effect=[0, 61]), self.assertRaises(vision.VisionError):
            vision.ask(png(False), 'Describe it', self.values())
        process.kill.assert_called_once()

    def test_cancellation_kills_child(self):
        import subprocess
        stop = threading.Event()
        process = Mock(returncode=0)
        process.poll.return_value = None
        calls = []
        def communicate(**kwargs):
            if not calls:
                calls.append(True)
                stop.set()
                raise subprocess.TimeoutExpired('vision', .5)
            return '', ''
        process.communicate.side_effect = communicate
        with patch.object(vision.subprocess, 'Popen', return_value=process), self.assertRaises(vision.VisionError):
            vision.ask(png(False), 'Describe it', self.values(), stop)
        process.kill.assert_called_once()

    def test_start_failure_is_explained(self):
        with patch.object(vision.subprocess, 'Popen', side_effect=OSError('missing')), self.assertRaises(vision.VisionError):
            vision.ask(png(False), 'Describe it', self.values())


class VisionApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.old = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR = Path(cls.temp.name)
        chats.DB_PATH = config.DATA_DIR / 'test.sqlite3'
        settings.FILE = config.DATA_DIR / 'settings.json'
        cls.connections = patch.object(chats, 'connect', closing_connections())
        cls.connections.start()
        from app import server, memory, learning, notes, checklists, expenses, reminders, briefing, rules
        from app import followups, search_history
        for module in (chats, rules, memory, learning, notes, checklists, expenses, reminders, briefing, followups,
                       search_history):
            module.initialize()
        cls.app = server.app

    @classmethod
    def tearDownClass(cls):
        config.DATA_DIR, chats.DB_PATH, settings.FILE = cls.old
        cls.connections.stop()
        cls.temp.cleanup()

    async def asyncSetUp(self):
        from app import photo_jobs
        self.jobs = photo_jobs
        self.config_patch = patch.object(vision, 'configuration', return_value={'test': True})
        self.config_patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')

    async def asyncTearDown(self):
        await self.jobs.shutdown()
        await self.client.aclose()
        self.config_patch.stop()

    async def wait_jobs(self):
        await asyncio.gather(*list(self.jobs._jobs), return_exceptions=True)
        await asyncio.sleep(0)

    async def test_background_keeps_chat_usable_and_sends_popup(self):
        entered, finish = threading.Event(), threading.Event()
        def worker(_png, question, values, stop):
            entered.set()
            while not finish.wait(.02):
                if stop.is_set():
                    raise vision.VisionError('Interrupted')
            return 'A red square and a blue circle.'
        with patch.object(vision, 'ask', side_effect=worker), patch('app.notify.show') as popup:
            response = await self.client.post('/api/look', content=png(False))
            self.assertEqual(response.status_code, 202, response.text)
            data = response.json()
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            second = await self.client.post('/api/look', content=png(False))
            self.assertEqual(second.status_code, 409)
            with patch('app.engine.chat', new=AsyncMock(return_value='Chat still works')):
                chat = await self.client.post('/api/chat', json={'messages': [{'role': 'user', 'content': 'Hi'}]})
            self.assertEqual(chat.json()['reply'], 'Chat still works')
            self.assertTrue((await self.client.get('/api/look/status')).json()['busy'])
            finish.set()
            await self.wait_jobs()
            saved = chats.get(data['chat_id'])
            self.assertEqual([m['kind'] for m in saved['messages']], ['photo', 'vision'])
            self.assertIn('red square', saved['messages'][-1]['content'])
            self.assertEqual(chats.recent_messages(data['chat_id'], 12), [])
            popup.assert_called_once_with('reply', 'BEYOND finished looking at your photo',
                                          'A red square and a blue circle.', data['chat_id'])
            arrived = (await self.client.get('/api/reminders/fired?after=0')).json()
            self.assertTrue(any(m['kind'] == 'vision' for m in arrived['items']))

    async def test_deleted_chat_is_not_recreated(self):
        finish = threading.Event()
        def worker(*args):
            finish.wait(2)
            return 'A photo.'
        with patch.object(vision, 'ask', side_effect=worker), patch('app.notify.show') as popup:
            data = (await self.client.post('/api/look', content=png(False))).json()
            await self.client.delete('/api/chats/' + str(data['chat_id']))
            finish.set()
            await self.wait_jobs()
            self.assertFalse(chats.exists(data['chat_id']))
            popup.assert_not_called()

    async def test_failures_replace_progress_and_release_worker(self):
        with patch.object(vision, 'ask', side_effect=vision.VisionError('The model timed out.')), patch('app.notify.show') as popup:
            data = (await self.client.post('/api/look?action=receipt', content=png(False))).json()
            await self.wait_jobs()
            saved = chats.get(data['chat_id'])['messages']
            self.assertEqual(saved[-1]['kind'], 'vision_error')
            self.assertEqual(saved[-1]['content'], 'The model timed out.')
            self.assertFalse(vision._lock.locked())
            self.assertEqual(popup.call_args.args[0], 'error')

    async def test_shutdown_stops_worker_and_marks_interrupted(self):
        entered = threading.Event()
        def worker(_png, question, values, stop):
            entered.set()
            stop.wait(3)
            raise vision.VisionError('Interrupted')
        with patch.object(vision, 'ask', side_effect=worker), patch('app.notify.show') as popup:
            data = (await self.client.post('/api/look', content=png(False))).json()
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            await self.jobs.shutdown()
            await asyncio.sleep(0)
            self.assertEqual(chats.get(data['chat_id'])['messages'][-1]['kind'], 'vision_error')
            self.assertFalse(vision._lock.locked())
            popup.assert_not_called()

    async def test_validation_and_restart_recovery(self):
        before = len(chats.list_chats())
        for route, body, code in [('/api/look', b'invalid', 400),
                                  ('/api/look', b'x' * (10*1024*1024+1), 413),
                                  ('/api/look?action=ask', png(False), 400),
                                  ('/api/look?action=other', png(False), 400),
                                  ('/api/look?chat_id=999999', png(False), 404)]:
            response = await self.client.post(route, content=body)
            self.assertEqual(response.status_code, code, response.text)
        self.assertFalse(vision._lock.locked())
        self.assertEqual(len(chats.list_chats()), before)
        cid = chats.create('Interrupted photo')
        mid = chats.add_message(cid, 'assistant', 'Looking...', kind='vision_pending')
        self.jobs.recover()
        self.assertIsNone(chats.get_message(mid))
        message = chats.get(cid)['messages'][-1]
        self.assertEqual(message['kind'], 'vision_error')
        self.assertIn('interrupted', message['content'])
        arrivals = chats.messages_after(('vision_error',), mid)
        self.assertEqual(arrivals[0]['replaces'], mid)


if __name__ == '__main__':
    unittest.main()
