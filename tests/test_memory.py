"""Automatic fact pickup checks: python -m unittest discover -s tests -v. Only the quick "is this worth asking
the AI about?" check; the AI itself isn't called."""
import unittest

from app import memory


class WantsPickupTests(unittest.TestCase):
    def test_personal_news_is_checked(self):
        for message in ("I just got a new dog named Rex", "I adopted a cat called Luna last week",
                        "Started a new job at Tesla today", "We moved to Denver in May", "My sister lives in Denver",
                        "Just bought a Tesla Model 3!", "I'm a nurse and I have a cat named Luna",
                        "I drive a blue Civic", "Finally graduated from nursing school."):
            with self.subTest(message=message):
                self.assertTrue(memory.wants_pickup(message))

    def test_questions_and_small_talk_are_skipped(self):
        for message in ("Hello how are you?", "What's the weather like tomorrow?", "Tell me a joke about cats",
                        "Where did I say I work?", "Thanks, that helped a lot", "Who got the most votes in 2020?"):
            with self.subTest(message=message):
                self.assertFalse(memory.wants_pickup(message))


if __name__ == '__main__':
    unittest.main()
