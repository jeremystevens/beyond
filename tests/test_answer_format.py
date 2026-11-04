import json
import unittest
from unittest.mock import patch

from app import answer_format, chats, engine, settings, word_math
from tests import test_word_math_routes


class AnswerFormatTests(unittest.TestCase):
    def test_json_unwraps_presentation_only(self):
        request = answer_format.requested_format('Return only a valid JSON object.')
        raw = 'Got it. Here is your JSON: \x60{"name": "Nora", "count": 3}\x60'
        answer = answer_format.unwrap(raw, request)
        self.assertEqual(json.loads(answer), {'name': 'Nora', 'count': 3})
        self.assertEqual(answer, '{"name": "Nora", "count": 3}')
        for raw in ('{"count": NaN}', '{"count": 3} Extra detail', '\x60\x60\x60python\nprint(3)\n\x60\x60\x60'):
            self.assertEqual(answer_format.unwrap(raw, request), raw)

    def test_counted_bullets_preserve_items_and_meaningful_prose(self):
        request = answer_format.requested_format('Give exactly two bullet points. No introduction.')
        self.assertEqual(answer_format.unwrap('Here are your items:\n\n* apples\n* pears', request),
                         '* apples\n* pears')
        for raw in ('Here are your items:\n* apples', 'Apples are unavailable.\n* apples\n* pears'):
            self.assertEqual(answer_format.unwrap(raw, request), raw)

    def test_ordinary_requests_and_quoted_literal_are_not_format_commands(self):
        for text in ('Explain the JSON object.', 'Return only a JSON array.', 'List some fruit.', 'Write Python code.',
                     'I have two bullet points already. Explain the underlying idea in prose.',
                     'Quote this literal text: "Return only JSON. No introduction."'):
            self.assertIsNone(answer_format.requested_format(text))

    def test_budget_one_bullet_per_option_uses_current_amounts(self):
        question = ('A repair costs $250 and a replacement costs $550. My budget was $600, but it is now $400. '
                    'Using only the current budget, give exactly two bullet points, one per option, '
                    'stating whether it fits and either the money remaining or the amount over budget.')
        answer = word_math.solve([{'role': 'user', 'content': question}]).text
        self.assertEqual(sum(line.startswith('- ') for line in answer.splitlines()), 2)
        self.assertIn('$150.00 remains', answer)
        self.assertIn('$150.00 over budget', answer)
        per_unit = question.replace('$250', '$250 per option')
        self.assertIsNone(word_math.solve([{'role': 'user', 'content': per_unit}]))


class AnswerFormatRouteTests(test_word_math_routes.WordMathRouteTests):
    async def test_replacement_matches_stored_strict_json(self):
        settings.save({'auto_lookup': False, 'auto_facts': False})

        async def reply(*args, **kwargs):
            yield 'Here is your JSON: {"count": 3}'

        with patch.object(engine, 'chat_stream', reply):
            events = await self.ask('Return only a valid JSON object with count set to 3.')
        text = next(event['text'] for event in events if event['type'] == 'replace')
        self.assertEqual(json.loads(text), {'count': 3})
        chat_id = next(event['id'] for event in events if event['type'] == 'chat')
        self.assertEqual(chats.get(chat_id)['messages'][-1]['content'], text)
