"""Spoken replies: CPU worker, queue lifecycle, saved playback and command integration."""
import asyncio
import io
import json
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from app import chats, config, settings, speech_jobs
from app.tools import speech, speech_worker
import test_imagine as ti


def clip():
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b'\x10\x00' * 24000)
    return out.getvalue()


class SpeechTests(unittest.TestCase):
    def test_clean_and_bound_text(self):
        self.assertEqual(speech.clean(' **Hello** [Jeremy](https://example.org)\x00 '), ('Hello Jeremy', False))
        self.assertEqual(speech.clean('a'*1801), ('a'*1800, True))
        with self.assertRaises(speech.SpeechError):
            speech.clean('  ')

    def test_audio_validation(self):
        speech.validate_wav(clip())
        for data in (b'', b'not audio', clip()[:-10]):
            with self.assertRaises(speech.SpeechError):
                speech.validate_wav(data)

    def test_settings_reject_invalid_values_and_default_off(self):
        self.assertFalse(config.DEFAULTS['speech_enabled'])
        self.assertFalse(config.DEFAULTS['speech_auto'])
        for change in ({'speech_speed': float('nan')}, {'speech_speed': True},
                       {'speech_threads': 0}, {'speech_timeout': True},
                       {'speech_engine': 'cloud'}, {'speech_voice': 'af_heart; echo hi'},
                       {'speech_kokoro_model': 'bad.exe'}):
            with self.subTest(change=change), self.assertRaises(settings.SettingsError):
                settings.validate(change)

    def test_worker_cpu_threads(self):
        ort = Mock()
        with patch.dict('sys.modules', {'onnxruntime': ort}):
            speech_worker.session('model.onnx', 2)
        self.assertEqual(ort.SessionOptions.return_value.intra_op_num_threads, 2)
        self.assertEqual(ort.InferenceSession.call_args.kwargs['providers'], ['CPUExecutionProvider'])

    def test_fallback_and_direct_piper(self):
        with patch.object(speech_worker, 'kokoro_wav', side_effect=RuntimeError('bad model')) as kokoro, \
                patch.object(speech_worker, 'piper_wav', return_value=clip()):
            result = speech_worker.synthesize('hello', {'speech_engine': 'kokoro'}, '.')
            self.assertEqual(result[1:], ('piper', True))
            result = speech_worker.synthesize('hello', {'speech_engine': 'piper'}, '.')
            self.assertEqual(result[1:], ('piper', False))
            self.assertEqual(kokoro.call_count, 1)

    def test_subprocess_literal_input_output_cleanup(self):
        process = Mock(returncode=0)
        process.poll.return_value = 0
        def communicate(**kwargs):
            output = Path(launch.call_args.args[0][-1])
            output.write_bytes(clip())
            output.with_suffix('.json').write_text('{"engine":"kokoro","fallback":false}')
            return '', ''
        process.communicate.side_effect = communicate
        with patch.object(speech.subprocess, 'Popen', return_value=process) as launch:
            audio, label = speech.synthesize('hello & $(literal)', {**config.DEFAULTS, 'secret': 'omit'})
        self.assertEqual(label, 'Kokoro')
        self.assertEqual(audio, clip())
        payload = json.loads(process.communicate.call_args.kwargs['input'])
        self.assertEqual(payload['text'], 'hello & $(literal)')
        self.assertNotIn('secret', payload['settings'])
        self.assertFalse(launch.call_args.kwargs.get('shell', False))
        self.assertFalse(Path(launch.call_args.args[0][-1]).exists())

    def test_cancel_before_launch(self):
        stop = threading.Event()
        stop.set()
        with patch.object(speech.subprocess, 'Popen') as launch, self.assertRaises(speech.SpeechError):
            speech.synthesize('hello', config.DEFAULTS, stop)
        launch.assert_not_called()


class SpeechApiTests(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(ti.ImagineApiTests.setUpClass.__func__)
    tearDownClass = classmethod(ti.ImagineApiTests.tearDownClass.__func__)

    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')
        self.configure = patch.object(speech, 'configuration', return_value=config.DEFAULTS.copy())
        self.configure.start()
        self.chat = chats.create('Speech test')
        self.mid = chats.add_message(self.chat, 'assistant', 'Hello Jeremy.')

    async def asyncTearDown(self):
        await speech_jobs.shutdown()
        await asyncio.sleep(0)
        await self.client.delete('/api/chats/' + str(self.chat))
        await self.client.aclose()
        self.configure.stop()

    async def finish(self):
        await asyncio.gather(*(t for t, _ in list(speech_jobs._jobs.values())))
        await asyncio.sleep(0)

    async def test_saved_clip_cache_status_range_and_delete(self):
        with patch.object(speech, 'synthesize', return_value=(clip(), 'Kokoro')) as generate:
            response = await self.client.post('/api/speech', json={'message_id': self.mid})
            self.assertEqual(response.status_code, 202, response.text)
            await self.finish()
            response = await self.client.post('/api/speech', json={'message_id': self.mid})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(generate.call_count, 1)
        item = chats.get(self.chat)['messages'][0]
        self.assertEqual(item['speech']['engine'], 'Kokoro')
        self.assertNotIn('audio', item)
        url = item['speech']['url']
        full = await self.client.get(url)
        self.assertEqual(full.content, clip())
        self.assertIn('audio/wav', full.headers['content-type'])
        for span, expected in [('bytes=0-43', clip()[:44]), ('bytes=-10', clip()[-10:])]:
            partial = await self.client.get(url, headers={'Range': span})
            self.assertEqual(partial.status_code, 206)
            self.assertEqual(partial.content, expected)
        for span in ('bytes=999999-', 'bytes=-0', 'bytes=1-0', 'bytes=x-y', 'bytes=0-2,5-8'):
            self.assertEqual((await self.client.get(url, headers={'Range': span})).status_code, 416)
        status = (await self.client.get('/api/speech/status', params={'chat_id': self.chat})).json()
        self.assertEqual(status['items'][0]['state'], 'ready')
        await self.client.delete('/api/chats/' + str(self.chat))
        self.assertEqual((await self.client.get(url)).status_code, 404)

    async def test_queue_bounded_deduplicated_and_chat_responsive(self):
        release = threading.Event()
        def slow(text, values, stop):
            while not release.wait(.02):
                if stop.is_set():
                    raise speech.SpeechError('stopped')
            return clip(), 'Piper'
        with patch.object(speech, 'synthesize', side_effect=slow) as generate:
            try:
                ids = [self.mid] + [chats.add_message(self.chat, 'assistant', 'more') for _ in range(4)]
                for mid in ids[:4]:
                    self.assertEqual((await self.client.post('/api/speech', json={'message_id': mid})).status_code, 202)
                self.assertEqual((await self.client.post('/api/speech', json={'message_id': ids[0]})).status_code, 202)
                self.assertEqual((await self.client.post('/api/speech', json={'message_id': ids[4]})).status_code, 503)
                response = await asyncio.wait_for(self.client.post('/api/chat/stream', json={'content': '/calc 2+2'}), 30)
                self.assertIn('4', response.text)
                self.assertFalse(release.is_set())
                self.assertEqual(chats.get_message(self.mid)['speech_state'], 'pending')
                cid = next(json.loads(line)['id'] for line in response.text.splitlines() if json.loads(line)['type'] == 'chat')
                await self.client.delete('/api/chats/' + str(cid))
            finally:
                release.set()
                await self.finish()
        self.assertEqual(generate.call_count, 4)

    async def test_failure_retry_and_recovery(self):
        with patch.object(speech, 'synthesize', side_effect=speech.SpeechError('Voice missing')):
            speech_jobs.start(self.mid)
            await self.finish()
        self.assertEqual(chats.get_message(self.mid)['speech_state'], 'error')
        with patch.object(speech, 'synthesize', return_value=(clip(), 'Piper fallback')):
            speech_jobs.start(self.mid)
            await self.finish()
        self.assertEqual(chats.get_message(self.mid)['speech_state'], 'ready')
        with chats.connect() as db:
            db.execute("UPDATE messages SET speech_state='pending' WHERE id=?", (self.mid,))
        speech_jobs.recover()
        self.assertEqual(chats.get_message(self.mid)['speech_state'], 'error')

    async def test_deleted_answer_is_not_recreated(self):
        with patch.object(speech, 'synthesize', return_value=(clip(), 'Kokoro')):
            speech_jobs.start(self.mid)
            await self.client.delete('/api/chats/' + str(self.chat))
            await self.finish()
        self.assertIsNone(chats.get_message(self.mid))

    async def test_speak_last_answer_and_custom_text_help(self):
        with patch.object(speech, 'synthesize', return_value=(clip(), 'Kokoro')) as generate:
            for command, expected in [('/speak', 'Hello Jeremy.'), ('/speak My own words.', 'My own words.')]:
                response = await self.client.post('/api/chat/stream', json={'chat_id': self.chat, 'content': command})
                self.assertEqual(response.status_code, 200)
                await self.finish()
                self.assertEqual(generate.call_args.args[0], expected)
                self.assertIn('"speak_requested": true', response.text)
        response = await self.client.post('/api/chat/stream', json={'chat_id': self.chat, 'content': '/help speak'})
        self.assertIn('/speak', response.text)
        self.assertIn('Kokoro', response.text)

    async def test_automatic_reading_preserves_answer_and_does_not_wait(self):
        from app import engine, notify
        async def answer(*args, **kwargs):
            yield 'An answer ready for speech.'
        values = {**config.DEFAULTS, 'speech_enabled': True, 'speech_auto': True,
                  'auto_facts': False, 'auto_lookup': False, 'recall': False}
        with patch.object(settings, 'load', return_value=values), \
                patch.object(engine, 'chat_stream', side_effect=answer), \
                patch.object(speech, 'synthesize', return_value=(clip(), 'Kokoro')), patch.object(notify, 'show'):
            response = await self.client.post('/api/chat/stream', json={'chat_id': self.chat, 'content': 'Say hello'})
            events = [json.loads(line) for line in response.text.splitlines()]
            self.assertTrue(any(item['type'] == 'done' for item in events))
            saved = next(item for item in events if item['type'] == 'message')
            self.assertEqual(saved['speech']['state'], 'pending')
            await self.finish()
        self.assertEqual(chats.get_message(saved['id'])['content'], 'An answer ready for speech.')
        self.assertEqual(chats.get_message(saved['id'])['speech_state'], 'ready')

    async def test_shutdown_stops_active_and_queued_jobs(self):
        def stop_aware(text, values, stop):
            stop.wait(5)
            if stop.is_set():
                raise speech.SpeechError('Interrupted')
            return clip(), 'Kokoro'
        with patch.object(speech, 'synthesize', side_effect=stop_aware):
            speech_jobs.start(self.mid)
            second = chats.add_message(self.chat, 'assistant', 'Queued answer')
            speech_jobs.start(second)
            await asyncio.sleep(.05)
            await asyncio.wait_for(speech_jobs.shutdown(), 5)
            await asyncio.sleep(0)
        self.assertFalse(speech_jobs._jobs)
        for mid in (self.mid, second):
            self.assertEqual(chats.get_message(mid)['speech_state'], 'error')

    async def test_user_and_missing_message_rejected(self):
        user = chats.add_message(self.chat, 'user', 'not an answer')
        self.assertEqual((await self.client.post('/api/speech', json={'message_id': user})).status_code, 503)
        self.assertEqual((await self.client.post('/api/speech', json={'message_id': -1})).status_code, 404)


if __name__ == '__main__':
    unittest.main()
