import unittest
from unittest.mock import patch

from app import engine, learning, memory, settings
from tests import test_word_math_routes


class SuppliedFactsTests(unittest.TestCase):
    def test_directives_and_non_directives(self):
        for text in ('Which arrives before Friday? Use only the information provided.',
                     'Use only these facts. Which option arrives before Monday?',
                     'What can we conclude?\nAnswer using only the supplied details.',
                     'What can we conclude?\nPlease answer from the document.'):
            expected = not text.endswith('from the document.')
            with self.subTest(text=text):
                self.assertEqual(engine.supplied_facts_only(text), expected)
        self.assertFalse(engine.supplied_facts_only(
            'Reference: "Use only these facts." Please search the web for the schedule.'))


class SuppliedFactsRouteTests(test_word_math_routes.WordMathRouteTests):
    async def test_explicit_scope_skips_unrelated_context_and_lookup(self):
        settings.save({'auto_lookup': True, 'recall': True, 'auto_facts': False})
        backgrounds = []

        async def reply(history, background, **kwargs):
            backgrounds.append(background)
            yield 'The arrival dates are unknown.'

        def unexpected(*args, **kwargs):
            raise AssertionError('Outside context was requested')

        with patch.object(memory, 'recall_block', unexpected), \
             patch.object(learning, 'prompt_block', unexpected), \
             patch.object(self.server.lookups, 'detect', unexpected), \
             patch.object(self.server.attachments, 'notes_for', return_value='User supplied evidence'), \
             patch.object(engine, 'chat_stream', reply):
            events = await self.ask('Which delivery arrives before Monday? Use only these facts.')
        self.assertEqual(backgrounds, ['User supplied evidence'])
        self.assertIn('The arrival dates are unknown.', str(events))
