"""Ported rules, complete rounds, durable boards and exactly-once shared outcomes."""
import asyncio
import json
import unittest
from functools import lru_cache
from unittest.mock import patch

import httpx
from app import chats, commands, games, tictactoe
from app.tools import tictactoe as rules
import test_imagine as ti


def outcome_paths(difficulty):
    """Find real playable rounds using deterministic tie choices."""
    found, seen = {}, set()
    def visit(board, path):
        if board in seen:
            return
        seen.add(board)
        result = rules.winner(board)
        if result:
            found.setdefault(result, path)
            return
        for cell, mark in enumerate(board):
            if mark != ' ':
                continue
            after = board[:cell] + 'X' + board[cell+1:]
            if not rules.winner(after):
                move = rules.bot_move(after, difficulty)
                after = after[:move] + 'O' + after[move+1:]
            visit(after, path + [cell])
    with patch.object(rules._rand, 'choice', side_effect=lambda options: options[0]), \
            patch.object(rules._rand, 'random', return_value=0.0):
        visit(' '*9, [])
    return found


class RulesTests(unittest.TestCase):
    def test_winners_and_draw(self):
        for line in rules.LINES:
            board = [' ']*9
            for cell in line:
                board[cell] = 'X'
            self.assertEqual(rules.winner(''.join(board)), 'X')
        self.assertEqual(rules.winner('XOXOOXXXO'), 'draw')
        self.assertIsNone(rules.winner(' '*9))

    def test_normal_wins_blocks_and_centre(self):
        with patch.object(rules._rand, 'choice', side_effect=lambda options: options[0]), \
                patch.object(rules._rand, 'random', return_value=.9):
            self.assertEqual(rules.bot_move('OO XX    ', 'normal'), 2)
            self.assertEqual(rules.bot_move('XX  O    ', 'normal'), 2)
            self.assertEqual(rules.bot_move('X        ', 'normal'), 4)
            self.assertEqual(rules.bot_move('X   O    ', 'normal'), 2)

    def test_easy_selects_an_empty_square(self):
        with patch.object(rules._rand, 'choice', side_effect=lambda options: options[-1]):
            self.assertEqual(rules.bot_move('X O      ', 'easy'), 8)

    def test_impossible_never_loses_for_any_human_or_best_bot_move(self):
        endings = set()
        @lru_cache(maxsize=None)
        def visit(board):
            result = rules.winner(board)
            if result:
                self.assertNotEqual(result, 'X', board)
                endings.add(result)
                return
            for cell, mark in enumerate(board):
                if mark == ' ':
                    after = board[:cell] + 'X' + board[cell+1:]
                    if rules.winner(after):
                        visit(after)
                    else:
                        for bot in rules._best_moves(after):
                            visit(after[:bot] + 'O' + after[bot+1:])
        visit(' '*9)
        self.assertEqual(endings, {'O', 'draw'})

    def test_expected_outcomes_at_each_level(self):
        for difficulty in rules.DIFFICULTIES:
            self.assertEqual(set(outcome_paths(difficulty)),
                             {'O', 'draw'} if difficulty == 'impossible' else {'X', 'O', 'draw'})


class TicTacToeApiTests(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(ti.ImagineApiTests.setUpClass.__func__)
    tearDownClass = classmethod(ti.ImagineApiTests.tearDownClass.__func__)

    async def asyncSetUp(self):
        games.initialize()
        tictactoe.initialize()
        with chats.connect() as db:
            db.execute('DELETE FROM game_stats')
            db.execute('DELETE FROM tictactoe_stats')
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')
        self.created = []

    async def asyncTearDown(self):
        for cid in self.created:
            await self.client.delete('/api/chats/' + str(cid))
        await self.client.aclose()

    def start(self, difficulty='normal', board=None, revision=0):
        cid = chats.create('Tic-tac-toe check')
        self.created.append(cid)
        game = tictactoe.new(difficulty)
        if board is not None:
            game.update(board=board, revision=revision)
        mid = chats.add_message(cid, 'assistant', tictactoe.text(game), kind='command', game=game)
        return cid, mid, game

    async def move(self, mid, revision, cell):
        return await self.client.post(f'/api/tictactoe/{mid}/move', json={'revision': revision, 'cell': cell})

    async def test_command_picker_alias_help_and_menu(self):
        for command, kind in [('/tictactoe', 'tictactoe_picker'), ('/ttt easy', 'tictactoe')]:
            response = await self.client.post('/api/chat/stream', json={'content': command})
            events = [json.loads(line) for line in response.text.splitlines()]
            cid = next(item['id'] for item in events if item['type'] == 'chat')
            self.created.append(cid)
            saved = next(item for item in events if item['type'] == 'message')
            self.assertEqual(saved['game']['type'], kind)
            self.assertEqual(chats.recent_messages(cid, 12), [])
        self.assertIn('never loses', commands.run('/help ttt').text)
        self.assertIn('/tictactoe stats', commands.run('/help tictactoe').text)
        self.assertTrue(next(item for item in games.menu()['items'] if item['id']=='tictactoe')['available'])
        self.assertEqual(games.stats(), [])

    async def test_full_rounds_all_possible_outcomes_at_each_difficulty(self):
        for difficulty in rules.DIFFICULTIES:
            for outcome, cells in outcome_paths(difficulty).items():
                _, mid, game = self.start(difficulty)
                with patch.object(rules._rand, 'choice', side_effect=lambda options: options[0]), \
                        patch.object(rules._rand, 'random', return_value=0.0):
                    for cell in cells:
                        response = await self.move(mid, game['revision'], cell)
                        self.assertEqual(response.status_code, 200, response.text)
                        game = response.json()['game']
                self.assertEqual(game['result'], outcome)
                self.assertEqual(chats.get_message(mid)['game'], game)
        totals = games.stats()[0]
        self.assertEqual((totals['played'], totals['wins'], totals['losses'], totals['draws']), (8, 2, 3, 3))
        text = tictactoe.stats_text()
        self.assertIn('Easy: 1 wins · 1 losses · 1 draws', text)
        self.assertIn('Impossible: 0 wins · 1 losses · 1 draws', text)

    async def test_reload_initialize_and_deletion_preserve_stats(self):
        cid, mid, _ = self.start('easy', 'XX OO    ', 2)
        response = await self.move(mid, 2, 2)
        self.assertEqual(response.json()['game']['winning'], [0, 1, 2])
        tictactoe.initialize()
        self.assertEqual((await self.client.get(f'/api/tictactoe/{mid}')).json()['game']['result'], 'X')
        self.assertEqual(chats.get(cid)['messages'][0]['game']['revision'], 3)
        await self.client.delete('/api/chats/' + str(cid))
        self.assertEqual((await self.client.get(f'/api/tictactoe/{mid}')).status_code, 404)
        self.assertEqual((await self.move(mid, 3, 8)).status_code, 404)
        self.assertEqual(games.stats()[0]['wins'], 1)

    async def test_occupied_invalid_and_stale_moves_do_not_count(self):
        _, mid, _ = self.start('normal', 'X   O    ', 1)
        for revision, cell in [(1, 0), (0, 8)]:
            response = await self.move(mid, revision, cell)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['game']['revision'], 1)
        for body in ({'revision': True, 'cell': 2}, {'revision': 1, 'cell': '2'},
                     {'revision': 1, 'cell': 9}, {'revision': -1, 'cell': 2},
                     {'revision': 1, 'cell': 2, 'board': 'XXXXXXXXX'}):
            self.assertEqual((await self.client.post(f'/api/tictactoe/{mid}/move', json=body)).status_code, 422)
        self.assertEqual(games.stats(), [])
        self.assertEqual(chats.get_message(mid)['game']['board'], 'X   O    ')

    async def test_duplicate_final_moves_count_once_from_two_devices(self):
        _, mid, _ = self.start('easy', 'XX OO    ', 2)
        responses = await asyncio.gather(self.move(mid, 2, 2), self.move(mid, 2, 2))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        self.assertEqual((await self.move(mid, 3, 8)).status_code, 409)
        self.assertEqual(games.stats()[0]['played'], 1)
        self.assertIn('Easy: 1 wins · 0 losses · 0 draws', tictactoe.stats_text())

    async def test_result_failure_rolls_back_board_and_both_stats(self):
        _, mid, _ = self.start('easy', 'XX OO    ', 2)
        with patch.object(games, 'record', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                tictactoe.play(mid, 2, 2)
        self.assertEqual(chats.get_message(mid)['game']['revision'], 2)
        self.assertEqual(games.stats(), [])
        self.assertIn('No completed games yet', tictactoe.stats_text())

    async def test_only_actual_game_messages_accept_moves(self):
        cid = chats.create('not a game'); self.created.append(cid)
        user = chats.add_message(cid, 'user', 'hello', game=tictactoe.new('easy'))
        plain = chats.add_message(cid, 'assistant', 'hello')
        for mid in (user, plain, -1):
            self.assertEqual((await self.move(mid, 0, 0)).status_code, 404)

    async def test_old_saved_menus_show_current_games(self):
        cid = chats.create('old games menu'); self.created.append(cid)
        mid = chats.add_message(cid, 'assistant', 'Games', kind='command',
                                game={'type':'menu','items':[{'id':'tictactoe','available':False}]})
        saved = chats.get_message(mid)['game']
        self.assertEqual(len(saved['items']), 6)
        self.assertTrue(next(item for item in saved['items'] if item['id']=='tictactoe')['available'])


if __name__ == '__main__':
    unittest.main()
