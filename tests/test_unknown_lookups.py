"""Looking up things the AI may not know: python -m unittest discover -s tests -v. No network or AI is used."""
import unittest
from unittest.mock import patch

from app import followups, lookups


class EntityQuestionTests(unittest.TestCase):
    def test_named_things_are_looked_up(self):
        for question, query in (("have you ever heard of Omarchy linux?", 'Omarchy linux'),
                                ("have you heard of omarchy", 'omarchy'),
                                ("What is Omarchy Linux?", 'Omarchy Linux'),
                                ("Do you know anything about NixOS?", 'NixOS'),
                                ("tell me about Hyprland", 'Hyprland'),
                                ("who is Linus Torvalds?", 'Linus Torvalds')):
            with self.subTest(question=question):
                self.assertEqual(lookups.detect(question), ('web', query))

    def test_general_and_personal_questions_are_not(self):
        for question in ("what is a fever?", "what is the capital of France?", "who are you?", "how are you today?",
                         "what is your name?", "have you heard of my dog?", "explain recursion"):
            with self.subTest(question=question):
                self.assertIsNone(lookups.detect(question))


class UnsureAnswerTests(unittest.TestCase):
    def test_an_unsure_answer_offers_a_search(self):
        answer = ("Omarchy Linux is a lesser-known distribution. If you need more, I can look it up for you. "
                  "Would you like me to search for more details?")
        self.assertEqual(lookups.offer_search('have you ever heard of Omarchy linux?', answer), 'Omarchy linux')
        self.assertEqual(lookups.offer_search('does the Framework 16 laptop support Linux well?',
                                              "I'm not sure about the latest firmware."),
                         'does the Framework 16 laptop support Linux well')

    def test_a_confident_or_chatty_answer_does_not(self):
        self.assertEqual(lookups.offer_search('how are you?', "I'm doing well, thanks!"), '')
        self.assertEqual(lookups.offer_search('what is a fever?', 'A fever is a raised body temperature.'), '')
        self.assertEqual(lookups.offer_search('/joke cats', "I'm not sure this one is funny."), '')


class SearchNudgeTests(unittest.TestCase):
    def test_a_correction_asking_for_a_search_searches_the_last_topic(self):
        rows = [{'content': 'have you ever heard of Omarchy linux?', 'kind': 'chat'}]

        class FakeDb:
            def execute(self, *args):
                return self

            def fetchall(self):
                return rows

            def close(self):
                pass

        with patch.object(followups.chats, 'connect', return_value=FakeDb()):
            request = followups.web_request(1, "that is incorrect information you shouldn't lie if you don't know "
                                               "the answer you should always look up the information")
        self.assertEqual(request, {'kind': 'command', 'command': '/web Omarchy linux'})

    def test_not_for_a_refusal(self):
        self.assertFalse(followups._web_reference("please don't look it up, just guess"))
        self.assertFalse(followups._web_reference('what did you have for breakfast'))


if __name__ == '__main__':
    unittest.main()
