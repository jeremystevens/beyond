"""Phase 31 (blackjack) checks: python -m unittest discover -s tests -v. Uses a temporary database and rigged
decks, so every outcome is tested on purpose rather than by luck."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import blackjack, chats, config, games, settings
from tests.support import closing_connections
from app.tools import blackjack as rules


def rigged(*cards):
    """A deck that deals `cards` in order (deal() pops from the end): player, player, dealer, dealer, then draws."""
    filler = [c for c in (r + s for s in rules.SUITS for r in rules.RANKS) if c not in cards]
    return filler + list(reversed(cards))


class RuleTests(unittest.TestCase):
    def test_hand_values_and_soft_aces(self):
        self.assertEqual(rules.hand_value(['A♠', '6♥']), (17, True))
        self.assertEqual(rules.hand_value(['A♠', '6♥', '10♦']), (17, False))
        self.assertEqual(rules.hand_value(['A♠', 'A♥', '9♦']), (21, True))
        self.assertEqual(rules.hand_value(['K♠', 'Q♥', '2♦']), (22, False))

    def test_naturals_on_the_deal(self):
        self.assertEqual(rules.deal(rigged('A♠', 'K♥', '9♦', '7♣'))['result'], 'blackjack')
        self.assertEqual(rules.deal(rigged('9♠', '7♥', 'A♦', 'Q♣'))['result'], 'dealer_blackjack')
        self.assertEqual(rules.deal(rigged('A♠', 'K♥', 'A♦', 'Q♣'))['result'], 'push')
        self.assertTrue(rules.deal(rigged('A♠', 'K♥', 'A♦', 'Q♣'))['natural'])
        self.assertIsNone(rules.deal(rigged('9♠', '7♥', '9♦', '7♣'))['result'])

    def test_dealer_draws_to_17_and_stands_on_soft_17(self):
        hand = rules.finish(rules.deal(rigged('10♠', '9♥', '10♦', '6♣', '2♠')))   # dealer 16 draws a 2: 18
        self.assertEqual((rules.hand_value(hand['dealer'])[0], hand['result']), (18, 'win'))
        hand = rules.finish(rules.deal(rigged('10♠', '7♥', 'A♦', '6♣', '5♠')))    # soft 17: no draw
        self.assertEqual((len(hand['dealer']), hand['result']), (2, 'push'))
        hand = rules.finish(rules.deal(rigged('10♠', '7♥', '10♦', '6♣', 'K♠')))   # dealer busts
        self.assertEqual(hand['result'], 'dealer_bust')

    def test_hit_bust_and_automatic_stand_on_21(self):
        hand = rules.hit(rules.deal(rigged('10♠', '6♥', '9♦', '8♣', 'K♠')))
        self.assertEqual(hand['result'], 'bust')
        hand = rules.hit(rules.deal(rigged('10♠', '6♥', '9♦', '8♣', '5♠')))       # 21: stands by itself
        self.assertEqual(hand['result'], 'win')


class ApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.saved = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR = Path(cls.temp.name)
        chats.DB_PATH = config.DATA_DIR / 'test.sqlite3'
        settings.FILE = config.DATA_DIR / 'settings.json'
        cls.connections = patch.object(chats, 'connect', closing_connections())
        cls.connections.start()
        from app.server import app
        from app import rules as house_rules, memory, learning
        from app import followups, search_history
        for module in (chats, games, house_rules, memory, learning, blackjack, followups, search_history):
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
            db.execute('DELETE FROM blackjack_stats')
            db.execute('DELETE FROM game_stats')

    async def asyncTearDown(self):
        await self.client.aclose()

    async def deal(self, *cards):
        with patch.object(rules, 'deck', return_value=rigged(*cards)):
            response = await self.client.post('/api/chat/stream', json={'content': '/blackjack', 'chat_id': None})
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        return events[0]['id'], next(e for e in events if e['type'] == 'message')

    async def move(self, message_id, move, revision):
        return await self.client.post(f'/api/blackjack/{message_id}/{move}', json={'revision': revision})

    async def test_hidden_card_and_deck_never_reach_the_page(self):
        chat, message = await self.deal('10♠', '6♥', '9♦', 'Q♣')
        game = message['game']
        self.assertEqual((game['dealer'], game['dealer_hidden'], game['dealer_total']), (['9♦'], 1, 9))
        self.assertNotIn('deck', game)
        saved = (await self.client.get(f'/api/chats/{chat}')).json()['messages'][-1]
        everything = json.dumps(saved) + (await self.client.get(f"/api/blackjack/{message['id']}")).text
        self.assertNotIn('Q♣', everything)                         # the face-down card stays on the server
        self.assertNotIn('deck', everything)

    async def test_hit_stand_record_and_stale_clicks(self):
        _, message = await self.deal('10♠', '6♥', '9♦', '8♣', '3♠')   # you 16 · dealer 17
        hit = await self.move(message['id'], 'hit', 0)
        self.assertEqual(hit.status_code, 200)
        self.assertEqual((hit.json()['game']['player_total'], hit.json()['game']['result']), (19, None))
        self.assertEqual((await self.move(message['id'], 'stand', 0)).status_code, 409)   # an old revision
        stand = await self.move(message['id'], 'stand', 1)
        game = stand.json()['game']
        self.assertEqual((game['result'], game['dealer'], game['dealer_hidden']), ('win', ['9♦', '8♣'], 0))
        self.assertEqual(game['record']['wins'], 1)
        self.assertEqual((await self.move(message['id'], 'hit', 2)).status_code, 409)   # the hand is over
        self.assertEqual(blackjack.stats()['wins'], 1)                                  # counted once
        self.assertEqual(next(r for r in games.stats() if r['game'] == 'blackjack')['wins'], 1)

    async def test_natural_is_recorded_with_the_deal(self):
        _, message = await self.deal('A♠', 'K♥', '9♦', '7♣')
        game = message['game']
        self.assertEqual(game['result'], 'blackjack')
        self.assertEqual(game['record']['blackjacks'], 1)          # the record shown already includes it
        self.assertIn('instant win', game['note'])
        self.assertEqual((await self.move(message['id'], 'hit', 0)).status_code, 409)

    async def test_deleting_the_chat_removes_the_hand(self):
        chat, message = await self.deal('10♠', '6♥', '9♦', '8♣')
        await self.client.delete(f'/api/chats/{chat}')
        self.assertEqual((await self.client.get(f"/api/blackjack/{message['id']}")).status_code, 404)
        with chats.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM blackjack_hands WHERE message_id = ?',
                                         (message['id'],)).fetchone())


if __name__ == '__main__':
    unittest.main()
