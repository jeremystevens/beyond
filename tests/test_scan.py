"""Phase 21 checks: python -m unittest discover -s tests -v. Uses a temporary database."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from PIL import Image, ImageDraw, ImageFont
from app import chats, config, settings
from tests.support import closing_connections
from app.tools import scan


def png(text=True):
    image = Image.new('RGB', (900, 600), 'white')
    if text:
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 40)
        for y, line in enumerate(['MARKET RECEIPT', 'Milk  3.50', 'Bread  2.00', 'TOTAL  5.50']):
            draw.text((60, 60 + y * 100), line, font=font, fill='black')
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


class PreparationTests(unittest.TestCase):
    def test_invalid_and_oversized_files(self):
        for data in (b'', b'not an image', b'x' * (scan.MAX_PHOTO_BYTES + 1)):
            with self.subTest(size=len(data)), self.assertRaises(scan.ScanError):
                scan.prepare(data)

    def test_scaling_and_pixel_limit(self):
        image = Image.new('RGB', (3000, 1000), 'white')
        out = io.BytesIO()
        image.save(out, format='JPEG')
        with Image.open(io.BytesIO(scan.prepare(out.getvalue()))) as result:
            self.assertEqual(result.size, (2048, 683))
            self.assertFalse(result.getexif())
        with patch.object(scan, 'MAX_PIXELS', 10), self.assertRaises(scan.ScanError):
            scan.prepare(png(False))

    def test_receipt_columns_and_confidence(self):
        box = lambda x, y: [[x, y], [x+60, y], [x+60, y+20], [x, y+20]]
        self.assertEqual(scan.group_lines([(box(10, 10), 'Milk', .99), (box(200, 10), '3.50', .99),
                                          (box(10, 60), 'TOTAL', .99), (box(10, 90), 'noise', .1)]),
                         ['Milk   3.50', 'TOTAL'])

    def test_busy_reader(self):
        scan._lock.acquire()
        try:
            with self.assertRaises(scan.ScanBusy):
                scan.read_photo(png(False))
        finally:
            scan._lock.release()


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
        # The server may already be imported by another test class; initialize this new temporary database.
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

    async def test_real_receipt_and_saved_history(self):
        response = await self.client.post('/api/scan', content=png(), headers={'Content-Type': 'image/png'})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertIn('TOTAL', result['text'].upper())
        self.assertIn('5.50', result['text'])
        self.assertTrue(result['has_text'])
        saved = (await self.client.get('/api/chats/' + str(result['chat_id']))).json()
        self.assertEqual([m['kind'] for m in saved['messages']], ['photo', 'scan'])
        self.assertEqual(saved['messages'][0]['image'], result['image'])
        self.assertEqual(saved['messages'][1]['content'], result['text'])
        self.assertEqual(chats.recent_messages(result['chat_id'], 12), [])
        await self.client.delete('/api/chats/' + str(result['chat_id']))
        self.assertFalse(chats.exists(result['chat_id']))

    async def test_bad_upload_does_not_create_a_chat(self):
        before = len(chats.list_chats())
        for data, code in [(b'invalid', 400), (b'x' * (scan.MAX_PHOTO_BYTES + 1), 413)]:
            response = await self.client.post('/api/scan', content=data)
            self.assertEqual(response.status_code, code, response.text)
        self.assertEqual(len(chats.list_chats()), before)

    async def test_missing_chat_and_busy_reader(self):
        missing = await self.client.post('/api/scan?chat_id=999999', content=png(False))
        self.assertEqual(missing.status_code, 404)
        with patch.object(scan, 'read_photo', side_effect=scan.ScanBusy('Reader busy')):
            busy = await self.client.post('/api/scan', content=png(False))
        self.assertEqual(busy.status_code, 409)

    async def test_blank_result_and_command_help(self):
        with patch.object(scan, 'read_photo', return_value=(png(False), '', .1)):
            response = await self.client.post('/api/scan', content=png(False))
        self.assertFalse(response.json()['has_text'])
        self.assertIn("couldn't find", response.json()['text'])
        from app import commands
        self.assertIn('Attach a photo', commands.run('/scan').text)


if __name__ == '__main__':
    unittest.main()
