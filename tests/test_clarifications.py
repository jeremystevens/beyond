import unittest
from app import clarifications


class ClarificationTests(unittest.TestCase):
    def test_bare_requests_get_one_specific_question(self):
        for text in ('Reply to this email', 'could you please respond to this message?',
                     'Help me fix this error', 'Please draft a letter.'):
            with self.subTest(text=text):
                result = clarifications.question([{'role': 'user', 'content': text}])
                self.assertTrue(result.endswith('?'))
                self.assertEqual(result.count('?'), 1)

    def test_supplied_content_templates_quotes_and_delegated_choices_are_not_intercepted(self):
        for text in ('Reply to this email: Can you attend Friday?',
                     'Reply to this email\nHi, can you attend Friday?',
                     'Give me a generic polite decline email template',
                     'Write a letter about my broken dishwasher',
                     'Write a letter; choose the details yourself',
                     'Do not reply to this email', 'Explain the phrase "Reply to this email"',
                     'Fix this error: ModuleNotFoundError', 'Help fix this error and delete the file'):
            with self.subTest(text=text):
                self.assertEqual(clarifications.question([{'role': 'user', 'content': text}]), '')

    def test_existing_conversation_is_not_assumed_to_lack_source(self):
        self.assertEqual(clarifications.question([]), '')
        self.assertEqual(clarifications.question([
            {'role': 'user', 'content': 'Hi, can you attend Friday?'},
            {'role': 'assistant', 'content': 'How can I help?'},
            {'role': 'user', 'content': 'Reply to this email'}]), '')
