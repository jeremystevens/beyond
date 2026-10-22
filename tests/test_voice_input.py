"""Phase 26 (voice input) checks: python -m unittest discover -s tests -v. Uses a temporary database; the real Whisper "base"
model (downloaded once) and a question spoken by Windows' built-in voice."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, settings
from tests.support import closing_connections
from app.tools import speech_to_text

QUESTION = 'What is the capital of France?'


def spoken_question():
    """A WAV of QUESTION, read by Windows' System.Speech voice (None if that isn't available)."""
    path = Path(tempfile.gettempdir()) / 'beyond-test-question.wav'
    if not path.exists():
        script = (f"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$s.SetOutputToWaveFile('{path}'); $s.Speak('{QUESTION}'); $s.Dispose()")
        try:
            subprocess.run(['powershell', '-NoProfile', '-Command', script], check=True, timeout=60,
                           capture_output=True)
        except (OSError, subprocess.SubprocessError):
            return None
    return path.read_bytes() if path.exists() else None


class TranscribeTests(unittest.TestCase):
    def test_empty_and_oversized_recordings(self):
        for data in (b'', b'x' * 50, b'x' * (speech_to_text.MAX_RECORDING_BYTES + 1)):
            with self.subTest(size=len(data)), self.assertRaises(speech_to_text.SpeechError):
                speech_to_text.transcribe(data)

    def test_busy(self):
        speech_to_text._lock.acquire()
        try:
            with self.assertRaises(speech_to_text.SpeechBusy):
                speech_to_text.transcribe(b'x' * 1000)
        finally:
            speech_to_text._lock.release()

    def test_unreadable_recording(self):
        with self.assertRaises(speech_to_text.SpeechError):
            speech_to_text.transcribe(bytes(range(256)) * 20)

    def test_real_speech_and_nothing_left_behind(self):
        audio = spoken_question()
        if audio is None:
            self.skipTest("Windows' speech voice isn't available")
        before = set(Path(tempfile.gettempdir()).glob('tmp*.wav'))
        text, seconds = speech_to_text.transcribe(audio, '.wav')
        self.assertIn('capital of france', text.lower())
        self.assertLess(seconds, 30)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob('tmp*.wav')), before)   # temporary file deleted


class ApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.data_dir, cls.db_path, cls.settings_file = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR = Path(cls.temp.name)
        chats.DB_PATH = config.DATA_DIR / 'test.sqlite3'
        settings.FILE = config.DATA_DIR / 'settings.json'
        cls.connections = patch.object(chats, 'connect', closing_connections())
        cls.connections.start()
        from app.server import app
        from app import memory, learning, notes, checklists, expenses, reminders, briefing, rules
        for module in (chats, rules, memory, learning, notes, checklists, expenses, reminders, briefing):
            module.initialize()
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        config.DATA_DIR, chats.DB_PATH, settings.FILE = cls.data_dir, cls.db_path, cls.settings_file
        cls.connections.stop()
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()

    async def post(self, data, kind='audio/webm'):
        return await self.client.post('/api/transcribe', content=data, headers={'Content-Type': kind})

    async def test_spoken_question_is_returned_not_saved(self):
        audio = spoken_question()
        if audio is None:
            self.skipTest("Windows' speech voice isn't available")
        response = await self.post(audio, 'audio/wav')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('capital of france', response.json()['text'].lower())
        self.assertEqual(chats.list_chats(), [])   # only the words go anywhere, and only when the page sends them

    async def test_errors_in_plain_words(self):
        self.assertEqual((await self.post(b'')).status_code, 400)
        self.assertEqual((await self.post(b'x' * (speech_to_text.MAX_RECORDING_BYTES + 1))).status_code, 413)
        with patch.object(speech_to_text, 'transcribe', side_effect=speech_to_text.SpeechBusy('busy')):
            self.assertEqual((await self.post(b'x' * 1000)).status_code, 409)
        with patch.object(speech_to_text, 'transcribe', side_effect=ImportError):
            self.assertEqual((await self.post(b'x' * 1000)).status_code, 503)
        with patch.object(speech_to_text, 'transcribe', return_value=('', 0.5)):
            response = await self.post(b'x' * 1000)
            self.assertEqual(response.status_code, 400)
            self.assertIn("didn't catch any words", response.json()['error'])

    async def test_recording_format_reaches_the_decoder(self):
        for kind, suffix in (('audio/webm;codecs=opus', '.webm'), ('audio/mp4', '.mp4'), ('audio/ogg', '.ogg'),
                             ('audio/wav', '.wav')):
            with self.subTest(kind=kind), patch.object(speech_to_text, 'transcribe', return_value=('hi', 0.1)) as call:
                await self.post(b'x' * 1000, kind)
                self.assertEqual(call.call_args.args[1], suffix)


if __name__ == '__main__':
    unittest.main()
