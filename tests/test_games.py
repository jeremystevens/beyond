"""Games menu, exact dice displays and shared persistent score/stat storage."""
import asyncio
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx
from app import chats, commands, games
from app.tools import dice
import test_imagine as ti


class DiceDisplayTests(unittest.TestCase):
    def test_d6_is_one_server_roll_with_matching_text_and_display(self):
        with patch.object(dice, '_roll', return_value=[4]) as random:
            text, data = dice.roll_result('')
        random.assert_called_once_with(1, 6)
        self.assertIn('[4] = 4', text)
        self.assertEqual(data['total'], '4')
        self.assertEqual(data['rolls'][0]['groups'][0],
                         {'sides': 6, 'values': [4], 'kept': [0], 'sign': 1})

    def test_keep_drop_ties_and_negative_terms(self):
        with patch.object(dice, '_roll', side_effect=[[2, 6, 6, 1], [3]]):
            text, data = dice.roll_result('4d6kh3-1d4+2')
        self.assertEqual(data['total'], '13')
        groups = data['rolls'][0]['groups']
        self.assertEqual(groups[0]['kept'], [0, 1, 2])
        self.assertEqual(groups[1]['sign'], -1)
        self.assertIn('(1)', text)
        with patch.object(dice, '_roll', return_value=[1, 2, 4, 6]):
            _, dropped = dice.roll_result('4d6dl1')
        self.assertEqual(dropped['rolls'][0]['groups'][0]['kept'], [1, 2, 3])

    def test_advantage_disadvantage_and_natural_values(self):
        for notation, total in [('adv+5', '25'), ('dis', '1')]:
            with patch.object(dice, '_roll', return_value=[1, 20]):
                text, data = dice.roll_result(notation)
            self.assertEqual(data['total'], total)
            self.assertIn('Natural ' + ('20' if notation.startswith('adv') else '1'), text)

    def test_repeats_percentile_and_numeric_shorthand(self):
        with patch.object(dice, '_roll', side_effect=[[10], [20]]):
            _, data = dice.roll_result('2x d%')
        self.assertEqual(data['total'], '30')
        self.assertEqual(len(data['rolls']), 2)
        self.assertEqual(data['rolls'][0]['groups'][0]['sides'], 100)
        with patch.object(dice, '_roll', return_value=[7]) as random:
            dice.roll_result('20')
        random.assert_called_once_with(1, 20)

    def test_coin_and_plain_text_compatibility(self):
        with patch.object(dice.secrets, 'randbelow', return_value=1):
            text, data = dice.roll_result('coin')
            self.assertEqual(dice.roll_dice('coin'), text)
        self.assertEqual(data, {'type': 'coin', 'face': 'Heads'})

    def test_bad_notation_limits_and_help_have_no_display(self):
        for notation in ('help', '?', '101d6', 'd1', 'd1001', '11x d6', '4d6kh5', 'd6oops', 'x'*81):
            with self.subTest(notation=notation):
                self.assertIsNone(dice.roll_result(notation)[1])


class GameApiTests(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(ti.ImagineApiTests.setUpClass.__func__)
    tearDownClass = classmethod(ti.ImagineApiTests.tearDownClass.__func__)

    async def asyncSetUp(self):
        games.initialize()
        with chats.connect() as db:
            db.execute('DELETE FROM game_stats')
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')
        self.created = []

    async def asyncTearDown(self):
        for cid in self.created:
            await self.client.delete('/api/chats/' + str(cid))
        await self.client.aclose()

    async def send(self, content):
        response = await self.client.post('/api/chat/stream', json={'content': content})
        self.assertEqual(response.status_code, 200, response.text)
        events = [json.loads(line) for line in response.text.splitlines()]
        cid = next(item['id'] for item in events if item['type'] == 'chat')
        self.created.append(cid)
        message = next(item for item in events if item['type'] == 'message')
        return cid, message

    async def test_menu_catalog_quick_roll_and_return(self):
        cid, message = await self.send('/games')
        self.assertEqual(message['game']['type'], 'menu')
        self.assertEqual(len(message['game']['items']), 6)
        self.assertEqual(sum(item['available'] for item in message['game']['items']), 3)
        self.assertTrue(next(item for item in message['game']['items'] if item['id'] == 'quiz')['available'])
        self.assertEqual(games.stats(), [])
        with patch.object(dice, '_roll', return_value=[5]):
            r = await self.client.post(f"/api/messages/{message['id']}/press", json={'action': 'roll:again:d6'})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['game']['total'], '5')
        self.assertEqual(chats.get(cid)['messages'][-1]['game'], r.json()['game'])
        back = await self.client.post(f"/api/messages/{message['id']}/press", json={'action': 'games:menu:'})
        self.assertEqual(back.json()['game']['type'], 'menu')
        self.assertEqual(games.stats()[0]['played'], 1)

    async def test_saved_roll_reroll_and_stats_survive_chat_deletion(self):
        with patch.object(dice, '_roll', return_value=[2, 4]):
            cid, message = await self.send('/roll 2d6+3')
        self.assertEqual(message['game']['total'], '9')
        self.assertEqual(chats.get(cid)['messages'][-1]['game']['total'], '9')
        self.assertEqual(chats.recent_messages(cid, 12), [])
        with patch.object(dice, '_roll', return_value=[6, 6]):
            r = await self.client.post(f"/api/messages/{message['id']}/press",
                                       json={'action': 'roll:again:2d6+3'})
        self.assertEqual(r.json()['game']['total'], '15')
        self.assertEqual(games.stats()[0]['score'], 24)
        self.assertEqual(games.stats()[0]['best_score'], 15)
        await self.client.delete('/api/chats/' + str(cid))
        games.initialize()
        self.assertEqual(games.stats()[0]['played'], 2)
        _, stats = await self.send('/games stats')
        self.assertIsNone(stats['game'])
        self.assertIn('highest total 15', chats.get_message(stats['id'])['content'])

    async def test_coin_flips_are_counted_without_fictional_score(self):
        with patch.object(dice.secrets, 'randbelow', return_value=0):
            _, message = await self.send('/roll coin')
        self.assertEqual(message['game']['face'], 'Tails')
        self.assertEqual(games.stats()[0]['game'], 'coin')
        self.assertIsNone(games.stats()[0]['best_score'])

    async def test_errors_and_help_do_not_add_stats(self):
        for text in ('/roll 200d6', '/roll help', '/games help', '/help games', '/help roll'):
            await self.send(text)
        self.assertEqual(games.stats(), [])
        menu = (await self.client.get('/api/commands')).json()
        self.assertTrue(any(c['name'] == 'games' for c in menu))
        self.assertIn('/games stats', commands.run('/help games').text)

    async def test_unlisted_actions_are_rejected(self):
        _, message = await self.send('/games')
        response = await self.client.post(f"/api/messages/{message['id']}/press",
                                          json={'action': 'roll:again:100d1000'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(games.stats(), [])

    async def test_shared_store_outcomes_exact_big_scores_and_concurrent_updates(self):
        huge = 10**60
        games.record('trivia', huge, 'win')
        games.record('trivia', -1, 'loss')
        games.record('trivia', None, 'draw')
        with ThreadPoolExecutor(max_workers=4) as pool:
            await asyncio.to_thread(lambda: list(pool.map(lambda _: games.record('trivia', 2, 'win'), range(8))))
        row = games.stats()[0]
        self.assertEqual((row['played'], row['wins'], row['losses'], row['draws']), (11, 9, 1, 1))
        self.assertEqual(row['score'], huge + 15)
        self.assertEqual(row['best_score'], huge)
        for args in [('unknown', 1, 'win'), ('dice', True, None), ('dice', 1, 'bad')]:
            with self.assertRaises(ValueError):
                games.record(*args)

    async def test_large_dice_modifiers_keep_exact_totals(self):
        huge = 10**60
        with patch.object(dice, '_roll', return_value=[1]):
            _, message = await self.send('/roll d6+' + str(huge))
        self.assertEqual(message['game']['total'], str(huge+1))
        self.assertEqual(games.stats()[0]['score'], huge+1)


if __name__ == '__main__':
    unittest.main()
