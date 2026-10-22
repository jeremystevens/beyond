"""Phase 30 (study quiz) checks: python -m unittest discover -s tests -v. Uses a temporary database; the AI is
replaced by a stand-in, so no AI server is needed."""
import json
import re
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import httpx

from app import chats, config, engine, settings, study_quiz
from tests.support import closing_connections


class TempDatabase:
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.saved = config.DATA_DIR, chats.DB_PATH, settings.FILE
        config.DATA_DIR = Path(cls.temp.name)
        chats.DB_PATH = config.DATA_DIR / 'test.sqlite3'
        settings.FILE = config.DATA_DIR / 'settings.json'
        cls.connections = patch.object(chats, 'connect', closing_connections())
        cls.connections.start()
        from app import games, rules, memory, learning
        from app import followups, search_history
        for module in (chats, games, rules, memory, learning, study_quiz, followups, search_history):
            module.initialize()

    @classmethod
    def tearDownClass(cls):
        config.DATA_DIR, chats.DB_PATH, settings.FILE = cls.saved
        cls.connections.stop()
        cls.temp.cleanup()

    def setUp(self):
        study_quiz.stop()
        with chats.connect() as db:
            db.execute('DELETE FROM quiz_progress')


def solve(q):
    """The right answer of an offline math question, worked out independently from its text."""
    nums = [int(n) for n in re.findall(r'\d+', q['question'])]
    line = q['question']
    value = (nums[0] + nums[1] if '+' in line else nums[0] - nums[1] if '−' in line else nums[0] * nums[1]
             if '×' in line else Fraction(nums[0], nums[1]) if '÷' in line else Fraction(nums[0] * nums[1], 100)
             if '%' in line else nums[0] ** 2)
    return f'{float(value):g}'


class MathQuestionTests(TempDatabase, unittest.TestCase):
    def test_every_topic_and_level_has_four_distinct_choices_with_the_right_answer(self):
        for topic in study_quiz.MATH_TOPICS + ('7 times table',):
            table = 7 if topic == '7 times table' else None
            base = 'multiplication' if table else topic
            for level in range(1, 6):
                for _ in range(40):
                    q = study_quiz._math_question(base, level, table)
                    with self.subTest(topic=topic, level=level, question=q['question']):
                        self.assertEqual(len(q['choices']), 4)
                        self.assertEqual(len(set(q['choices'])), 4)
                        self.assertEqual(q['choices'][q['answer']], solve(q))
                        self.assertTrue(all(float(c) >= 0 for c in q['choices']))
                        self.assertTrue(q['explanation'])

    def test_topics(self):
        self.assertEqual(study_quiz.resolve_topic('the 7 times table'), ('7 times table', 7))
        self.assertEqual(study_quiz.resolve_topic('times tables of 12'), ('12 times table', 12))
        self.assertEqual(study_quiz.resolve_topic('Maths'), ('mixed math', None))
        self.assertEqual(study_quiz.resolve_topic('about World Capitals?'), ('world capitals', None))
        self.assertFalse(study_quiz.is_math('world capitals'))


class LevelTests(TempDatabase, unittest.TestCase):
    def test_three_right_level_up_two_wrong_level_down(self):
        levels = [study_quiz.record('addition', True)['level'] for _ in range(3)]
        self.assertEqual(levels, [1, 1, 2])
        levels = [study_quiz.record('addition', False)['level'] for _ in range(2)]
        self.assertEqual(levels, [2, 1])
        p = study_quiz.progress('addition')
        self.assertEqual((p['answered'], p['correct'], p['best_streak']), (5, 3, 3))

    def test_level_stays_between_1_and_5(self):
        for _ in range(30):
            study_quiz.record('squares', True)
        self.assertEqual(study_quiz.progress('squares')['level'], 5)
        for _ in range(30):
            study_quiz.record('squares', False)
        self.assertEqual(study_quiz.progress('squares')['level'], 1)


class SessionTests(TempDatabase, unittest.TestCase):
    def test_answer_skip_and_stale_questions(self):
        q = study_quiz.start('addition')
        self.assertIsNone(study_quiz.answer('not-this-one', 0))
        graded = study_quiz.answer(q['id'], q['answer'])
        self.assertTrue(graded[1])
        self.assertIsNone(study_quiz.answer(q['id'], q['answer']))          # answered already
        q2 = study_quiz.next_question()
        self.assertEqual(study_quiz.skip(q2['id'])['id'], q2['id'])
        self.assertIsNone(study_quiz.skip(q2['id']))
        ended = study_quiz.stop()
        self.assertEqual((ended['answered'], ended['right']), (1, 1))
        self.assertIsNone(study_quiz.next_question())

    def test_idle_quiz_ends(self):
        study_quiz.start('addition')
        with patch.object(study_quiz.time, 'monotonic', return_value=10 ** 9):
            self.assertIsNone(study_quiz.current())

    def test_ai_question_retry_and_failure(self):
        good = json.dumps({'question': 'Capital of Peru?', 'choices': ['Lima', 'Quito', 'Bogotá', 'La Paz'],
                           'answer': 0, 'explanation': 'Lima is the capital of Peru.'})
        with patch.object(engine, 'complete_blocking', side_effect=['not json', good]) as ai:
            q = study_quiz.start('world capitals')
        self.assertEqual(ai.call_count, 2)
        self.assertEqual((q['kind'], q['choices'][q['answer']]), ('ai', 'Lima'))
        self.assertIn('may contain mistakes', study_quiz.question_text(q))
        study_quiz.stop()
        bad = json.dumps({'question': 'x', 'choices': ['a', 'a', 'b', 'c'], 'answer': 0})   # duplicate choices
        with patch.object(engine, 'complete_blocking', return_value=bad), self.assertRaises(study_quiz.QuizError):
            study_quiz.start('world capitals')
        self.assertIsNone(study_quiz.current())                             # a failed start leaves no quiz


class ApiTests(TempDatabase, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from app.server import app
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()

    async def send(self, text, chat_id=None):
        response = await self.client.post('/api/chat/stream', json={'content': text, 'chat_id': chat_id})
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        return events[0]['id'], next(e for e in events if e['type'] == 'message')

    async def press(self, message_id, action):
        return await self.client.post(f'/api/messages/{message_id}/press', json={'action': action})

    async def test_play_through_buttons(self):
        chat, menu = await self.send('/quizme')
        self.assertIn('/quizme multiplication', [b.get('send') for row in menu['buttons'] for b in row])
        chat, question = await self.send('/quizme multiplication', chat)
        answers = [b['action'] for b in question['buttons'][0] + question['buttons'][1]]
        q = study_quiz.current()['question']
        right = await self.press(question['id'], answers[q['answer']])
        self.assertEqual(right.status_code, 200)
        self.assertIn('✅ Correct!', right.json()['text'])
        self.assertEqual(right.json()['buttons'][0][0]['send'], '/quizme next')
        stale = await self.press(question['id'], answers[q['answer']])
        self.assertEqual(stale.status_code, 409)                            # those answer buttons are gone
        chat, nxt = await self.send('/quizme next', chat)
        stop = await self.press(nxt['id'], 'quiz:stop:')
        self.assertIn('Quiz stopped: 1 of 1 right', stop.json()['text'])
        _, stats = await self.send('/quizme stats', chat)
        self.assertEqual(stats['buttons'][0][0]['send'], '/quizme')
        from app import games
        self.assertEqual(next(r for r in games.stats() if r['game'] == 'quiz')['wins'], 1)

    async def test_no_ai_server_is_explained(self):
        with patch.object(engine, 'complete_blocking', side_effect=engine.EngineError('No AI is set up yet.')):
            _, reply = await self.send('/quizme spanish verbs')
        self.assertIsNone(study_quiz.current())
        self.assertEqual(reply['buttons'][0][0]['send'], '/quizme')


if __name__ == '__main__':
    unittest.main()
