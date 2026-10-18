"""Phase 23: process lifecycle, background APIs, downloads and popup previews."""
import asyncio
import io
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
from PIL import Image

from app import chats, config, image_jobs, notify, settings
from app.tools import imagine
import test_vision as vt


def picture(size=256):
    data = io.BytesIO()
    Image.new('RGB', (size, size), 'orange').save(data, 'PNG')
    return data.getvalue()


class ImagineProcessTests(unittest.TestCase):
    def values(self):
        return {'image_executable': 'cpu/sd-cli.exe', 'image_model': 'dream.safetensors',
                'image_threads': 12, 'image_timeout': 60}

    def test_presets_launch_bounded_cpu_worker(self):
        for preset, spec in imagine.PRESETS.items():
            process = Mock(returncode=0)
            process.poll.return_value = 0
            def communicate(**kwargs):
                output = Path(launch.call_args.args[0][-1])
                output.write_bytes(picture(spec['size']))
                return '', ''
            process.communicate.side_effect = communicate
            with self.subTest(preset=preset), patch.object(imagine.subprocess, 'Popen', return_value=process) as launch:
                png = imagine.generate('a cat & literal $(text)', preset, self.values())
            args, kwargs = launch.call_args.args[0], launch.call_args.kwargs
            self.assertEqual(args[args.index('--width')+1], str(spec['size']))
            self.assertEqual(args[args.index('--steps')+1], str(spec['steps']))
            self.assertEqual(args[args.index('--seed')+1], '-1')
            self.assertEqual(args[args.index('--prompt')+1], 'a cat & literal $(text)')
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertFalse(kwargs.get('shell', False))
            self.assertNotIn('--vae-tiling', args)
            self.assertFalse(Path(args[-1]).exists())
            with Image.open(io.BytesIO(png)) as image:
                self.assertEqual(image.size, (spec['size'], spec['size']))

    def test_timeout_kills_and_reaps_child(self):
        process = Mock(returncode=0)
        process.poll.return_value = None
        with patch.object(imagine.subprocess, 'Popen', return_value=process), \
                patch.object(imagine.time, 'monotonic', side_effect=[0, 61]), self.assertRaises(imagine.ImagineError):
            imagine.generate('cat', 'quick', self.values())
        process.kill.assert_called_once()
        process.communicate.assert_called_once()

    def test_shutdown_cancels_child(self):
        stop = threading.Event()
        process = Mock(returncode=0)
        process.poll.return_value = None
        count = []
        def communicate(**kwargs):
            if not count:
                count.append(1)
                stop.set()
                raise subprocess.TimeoutExpired('sd', .5)
            return '', ''
        process.communicate.side_effect = communicate
        with patch.object(imagine.subprocess, 'Popen', return_value=process), self.assertRaises(imagine.ImagineError):
            imagine.generate('cat', 'quick', self.values(), stop)
        process.kill.assert_called_once()

    def test_start_exit_and_invalid_output_errors(self):
        with patch.object(imagine.subprocess, 'Popen', side_effect=OSError('missing')), self.assertRaises(imagine.ImagineError):
            imagine.generate('cat', 'quick', self.values())
        for code in (1, 0):
            process = Mock(returncode=code)
            process.poll.return_value = code
            process.communicate.return_value = ('', 'error')
            with patch.object(imagine.subprocess, 'Popen', return_value=process), self.assertRaises(imagine.ImagineError):
                imagine.generate('cat', 'quick', self.values())
        process = Mock(returncode=0)
        process.poll.return_value = 0
        def invalid(**kwargs):
            Path(launch.call_args.args[0][-1]).write_bytes(b'not a PNG')
            return '', ''
        process.communicate.side_effect = invalid
        with patch.object(imagine.subprocess, 'Popen', return_value=process) as launch, self.assertRaises(imagine.ImagineError):
            imagine.generate('cat', 'quick', self.values())

    def test_clean_defaults_settings_and_cpu_folder(self):
        self.assertFalse(config.DEFAULTS['image_enabled'])
        self.assertEqual(config.DEFAULTS['image_model'], '')
        for change in ({'image_threads': 0}, {'image_timeout': True},
                       {'image_executable': 'bad.cmd'}, {'image_model': 'bad.gguf'}):
            with self.subTest(change=change), self.assertRaises(settings.SettingsError):
                settings.validate(change)
        for enabled, exe in [(False, ''), (True, 'vulkan/sd-cli.exe')]:
            values = {**config.DEFAULTS, 'image_enabled': enabled, 'image_executable': exe}
            with patch.object(settings, 'load', return_value=values), self.assertRaises(imagine.ImagineError):
                imagine.configuration()


class ImagineApiTests(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(vt.VisionApiTests.setUpClass.__func__)
    tearDownClass = classmethod(vt.VisionApiTests.tearDownClass.__func__)

    async def asyncSetUp(self):
        self.config_patch = patch.object(imagine, 'configuration', return_value={'test': True})
        self.config_patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')

    async def asyncTearDown(self):
        await image_jobs.shutdown()
        await self.client.aclose()
        self.config_patch.stop()

    async def wait_jobs(self):
        await asyncio.gather(*list(image_jobs._jobs), return_exceptions=True)
        await asyncio.sleep(0)

    async def test_each_preset_persists_downloads_and_sends_preview_popup(self):
        with patch.object(imagine, 'generate', side_effect=lambda p, s, v, stop: picture(imagine.PRESETS[s]['size'])), \
                patch.object(notify, 'show') as popup:
            for preset, spec in imagine.PRESETS.items():
                response = await self.client.post('/api/imagine', json={'prompt': 'a cartoon cat', 'preset': preset})
                self.assertEqual(response.status_code, 202, response.text)
                data = response.json()
                await self.wait_jobs()
                messages = chats.get(data['chat_id'])['messages']
                self.assertEqual([m['kind'] for m in messages], ['image_request', 'image'])
                result = messages[-1]
                downloaded = await self.client.get(result['buttons'][0][0]['url'])
                self.assertEqual(downloaded.status_code, 200)
                self.assertIn('attachment;', downloaded.headers['content-disposition'])
                with Image.open(io.BytesIO(downloaded.content)) as image:
                    self.assertEqual(image.size, (spec['size'], spec['size']))
                arrivals = (await self.client.get('/api/reminders/fired?after=' + str(data['id']))).json()['items']
                self.assertTrue(any(m['id'] == result['id'] and m['image'] for m in arrivals))
                self.assertEqual(chats.recent_messages(data['chat_id'], 12), [])
                path = popup.call_args.kwargs['image_path']
                self.assertTrue(path.is_file())
                self.assertEqual(popup.call_args.args[0], 'reply')
                await self.client.delete('/api/chats/' + str(data['chat_id']))
                self.assertFalse(path.exists())
                self.assertEqual((await self.client.get(result['buttons'][0][0]['url'])).status_code, 404)

    async def test_busy_rejection_and_concurrent_chat(self):
        entered, finish = threading.Event(), threading.Event()
        def worker(*args):
            entered.set()
            while not finish.wait(.02):
                if args[-1].is_set():
                    raise imagine.ImagineError('Interrupted')
            return picture()
        with patch.object(imagine, 'generate', side_effect=worker), patch.object(notify, 'show'):
            first = await self.client.post('/api/imagine', json={'prompt': 'cat'})
            self.assertEqual(first.status_code, 202)
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            second = await self.client.post('/api/imagine', json={'prompt': 'dog'})
            self.assertEqual(second.status_code, 409)
            self.assertTrue((await self.client.get('/api/imagine/status')).json()['busy'])
            with patch('app.engine.chat', new=AsyncMock(return_value='Chat works')):
                chat = await self.client.post('/api/chat', json={'messages': [{'role': 'user', 'content': 'Hi'}]})
            self.assertEqual(chat.json()['reply'], 'Chat works')
            finish.set()
            await self.wait_jobs()
            self.assertFalse(imagine._lock.locked())

    async def test_failure_replaces_progress_and_releases_lock(self):
        with patch.object(imagine, 'generate', side_effect=imagine.ImagineError('Timed out.')), patch.object(notify, 'show') as popup:
            data = (await self.client.post('/api/imagine', json={'prompt': 'cat'})).json()
            await self.wait_jobs()
            self.assertIsNone(chats.get_message(data['id']))
            self.assertEqual(chats.get(data['chat_id'])['messages'][-1]['kind'], 'image_error')
            self.assertFalse(imagine._lock.locked())
            self.assertEqual(popup.call_args.args[0], 'error')

    async def test_deleted_chat_discards_result(self):
        finish = threading.Event()
        def worker(*args):
            finish.wait(2)
            return picture()
        with patch.object(imagine, 'generate', side_effect=worker), patch.object(notify, 'show') as popup:
            data = (await self.client.post('/api/imagine', json={'prompt': 'cat'})).json()
            await self.client.delete('/api/chats/' + str(data['chat_id']))
            finish.set()
            await self.wait_jobs()
            self.assertFalse(chats.exists(data['chat_id']))
            popup.assert_not_called()

    async def test_shutdown_and_restart_recovery(self):
        entered = threading.Event()
        def worker(*args):
            entered.set()
            args[-1].wait(3)
            raise imagine.ImagineError('Interrupted')
        with patch.object(imagine, 'generate', side_effect=worker), patch.object(notify, 'show') as popup:
            data = (await self.client.post('/api/imagine', json={'prompt': 'cat'})).json()
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            await image_jobs.shutdown()
            self.assertEqual(chats.get(data['chat_id'])['messages'][-1]['kind'], 'image_error')
            popup.assert_not_called()
        cid = chats.create('Restart test')
        mid = chats.add_message(cid, 'assistant', 'Working', kind='image_pending')
        image_jobs.recover()
        self.assertIsNone(chats.get_message(mid))
        self.assertEqual(chats.messages_after(('image_error',), mid)[0]['replaces'], mid)

    async def test_validation_and_unconfigured(self):
        before = len(chats.list_chats())
        for body, expected in [({'prompt': ' '}, 400), ({'prompt': ''}, 422),
                               ({'prompt': 'x'*1201}, 422), ({'prompt': 'cat', 'preset': 'huge'}, 422),
                               ({'prompt': 'cat', 'chat_id': 999999}, 404)]:
            self.assertEqual((await self.client.post('/api/imagine', json=body)).status_code, expected)
        with patch.object(imagine, 'configuration', side_effect=imagine.ImagineError('Enable pictures.')):
            self.assertEqual((await self.client.post('/api/imagine', json={'prompt': 'cat'})).status_code, 503)
        self.assertEqual(len(chats.list_chats()), before)
        self.assertFalse(imagine._lock.locked())


class PopupPreviewTests(unittest.TestCase):
    def test_image_attachment_and_text_fallback(self):
        import windows_toasts
        toast = Mock()
        toaster = Mock()
        for failed in (False, True):
            with patch.object(windows_toasts, 'Toast', return_value=toast), \
                    patch.object(windows_toasts.ToastDisplayImage, 'fromPath', side_effect=OSError() if failed else None) as image, \
                    patch.object(notify, '_get_toaster', return_value=toaster):
                notify._show('Ready', 'Your picture', 1, [], None, Path('preview.png'))
                image.assert_called_once()
                toaster.show_toast.assert_called_with(toast)


if __name__ == '__main__':
    unittest.main()
