"""Phase 32 (hangman) checks: python -m unittest discover -s tests -v. Uses a temporary database; the secret word
is chosen by the test where it matters."""
import json
import re
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, games, hangman, settings
from app.tools import hangman as rules
from app.tools.hangman_words import WORDS


class WordBankTests(unittest.TestCase):
    def test_word_bank_rules(self):
        for category, items in WORDS.items():
            words = [w for w, _ in items]
            self.assertEqual(len(words), len(set(words)), category)
            for word, hint in items:
                with self.subTest(word=word):
                    self.assertRegex(word, r'^[A-Z]+$')
                    self.assertNotIn(word.lower(), hint.lower())
            for difficulty, (low, high) in rules.DIFFICULTIES.items():
                self.assertGreaterEqual(sum(low <= len(w) <= high for w in words), 10, (category, difficulty))

    def test_difficulty_sets_the_length(self):
        for difficulty, (low, high) in rules.DIFFICULTIES.items():
            for _ in range(20):
                state = rules.pick('random', difficulty)
                self.assertTrue(low <= len(state['word']) <= high)
                self.assertIn(state['actual_category'], WORDS)

    def test_guessing_rules(self):
        state = {**rules.pick('animals', 'easy'), 'word': 'OTTER'}
        self.assertTrue(rules.guess(state, 't'))
        self.assertEqual(rules.masked(state), '_ T T _ _')
        self.assertFalse(rules.guess(state, 'T'))                  # a repeat never costs a miss
        self.assertFalse(rules.guess(state, '7'))
        for letter in 'ZQXJK':
            rules.guess(state, letter)
        self.assertIsNone(state['result'])
        rules.guess(state, 'W')                                     # the sixth miss
        self.assertEqual((state['result'], rules.masked(state)), ('lose', 'O T T E R'))
        won = {**rules.pick('animals', 'easy'), 'word': 'BEAR'}
        for letter in 'BEAR':
            rules.guess(won, letter)
        self.assertEqual(won['result'], 'win')


class ApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.saved = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR = Path(cls.temp.name)
        chats.DB_PATH = config.DATA_DIR / 'test.sqlite3'
        settings.FILE = config.DATA_DIR / 'settings.json'
        connect = chats.connect

        @contextmanager
        def closed_connection():
            db = connect()
            try:
                with db:
                    yield db
            finally:
                db.close()
        cls.connections = patch.object(chats, 'connect', closed_connection)
        cls.connections.start()
        from app.server import app
        from app import rules as house_rules, memory, learning
        for module in (chats, games, house_rules, memory, learning, hangman):
            module.initialize()
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        config.DATA_DIR, chats.DB_PATH, settings.FILE = cls.saved
        cls.connections.stop()
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')
        with chats.connect() as db:
            db.execute('DELETE FROM hangman_stats')
            db.execute('DELETE FROM game_stats')

    async def asyncTearDown(self):
        await self.client.aclose()

    async def send(self, text, word=None):
        pick = rules.pick
        if word:
            def fixed(category='random', difficulty='easy'):
                return {**pick(category, difficulty), 'word': word, 'hint': 'A secret hint.'}
            patcher = patch.object(rules, 'pick', fixed)
            patcher.start()
        try:
            response = await self.client.post('/api/chat/stream', json={'content': text, 'chat_id': None})
        finally:
            if word:
                patcher.stop()
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        return events[0]['id'], next(e for e in events if e['type'] == 'message')

    async def guess(self, message_id, letter, revision):
        return await self.client.post(f'/api/hangman/{message_id}/guess', json={'revision': revision, 'letter': letter})

    async def test_picker_and_bad_options(self):
        _, message = await self.send('/hangman medium')
        self.assertEqual((message['game']['type'], message['game']['difficulty']), ('hangman_picker', 'medium'))
        _, message = await self.send('/hangman dinosaurs')
        self.assertEqual(message['game']['type'], 'hangman_picker')

    async def test_word_and_hint_stay_private_until_the_end(self):
        chat, message = await self.send('/hangman animals easy', word='OTTER')
        saved = (await self.client.get(f'/api/chats/{chat}')).json()['messages'][-1]
        everything = json.dumps(saved) + (await self.client.get(f"/api/hangman/{message['id']}")).text
        self.assertNotIn('OTTER', everything)
        self.assertNotIn('secret hint', everything)
        hint = await self.client.post(f"/api/hangman/{message['id']}/hint", json={'revision': 0})
        self.assertEqual(hint.json()['game']['hint'], 'A secret hint.')
        self.assertIsNone(hint.json()['game']['word'])
        again = await self.client.post(f"/api/hangman/{message['id']}/hint", json={'revision': 1})
        self.assertEqual(again.status_code, 409)                   # one hint per round

    async def test_win_loss_record_and_stale_guesses(self):
        _, message = await self.send('/hangman animals easy', word='BEAR')
        revision = 0
        for letter in 'BEA':
            response = await self.guess(message['id'], letter, revision)
            revision += 1
        self.assertEqual(response.json()['game']['masked'], 'B E A _')
        self.assertEqual((await self.guess(message['id'], 'B', revision)).status_code, 409)   # already tried
        self.assertEqual((await self.guess(message['id'], 'R', 0)).status_code, 409)          # an old revision
        won = await self.guess(message['id'], 'R', revision)
        self.assertEqual((won.json()['game']['result'], won.json()['game']['word']), ('win', 'BEAR'))
        self.assertEqual(won.json()['game']['record']['wins'], 1)
        self.assertEqual((await self.guess(message['id'], 'Z', revision + 1)).status_code, 409)  # game over

        _, lost = await self.send('/hangman animals easy', word='OTTER')
        for revision, letter in enumerate('ZQXJKW'):
            last = await self.guess(lost['id'], letter, revision)
        game = last.json()['game']
        self.assertEqual((game['result'], len(game['misses']), game['word']), ('lose', 6, 'OTTER'))
        self.assertEqual((game['record']['wins'], game['record']['losses'], game['record']['streak']), (1, 1, 0))
        self.assertEqual(next(r for r in games.stats() if r['game'] == 'hangman')['played'], 2)

    async def test_forged_letters_are_rejected(self):
        _, message = await self.send('/hangman animals easy', word='BEAR')
        for letter in ('7', 'AB', '', 'é'):
            with self.subTest(letter=letter):
                self.assertEqual((await self.guess(message['id'], letter, 0)).status_code, 422)


if __name__ == '__main__':
    unittest.main()
