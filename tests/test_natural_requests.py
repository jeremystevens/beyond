import unittest
from app import natural_requests


class NaturalRequestTests(unittest.TestCase):
    def test_clear_spoken_or_typed_requests_use_existing_tools(self):
        cases = {
            'Tell me a fact about cats': '/cat',
            'Can you please tell me a random fact about cats?': '/cat',
            'Give me an interesting cat fact please.': '/cat',
            'Tell me another cat fact!': '/cat',
            'a cat fact': '/cat',
            'Please give me a random quote.': '/quote',
            'Tell me a joke about cats': '/joke cats',
            'Could you tell me a dad joke?': '/joke dad',
            'Define serendipity': '/define serendipity',
            'What does ephemeral mean?': '/define ephemeral',
            'Search Wikipedia for Apollo 11': '/wiki Apollo 11',
            'Look up Ada Lovelace on Wikipedia': '/wiki Ada Lovelace',
            'Search Stack Overflow for python read a file': '/so python read a file',
            'What time is it in Tokyo?': '/time Tokyo',
            'What is the time in Tokyo': '/time Tokyo',
            "What's the current time in Tokyo?": '/time Tokyo',
            'Show me the system status': '/status',
            'Show my notes': '/notes',
            'Show my lists': '/list',
            'Show saved memories': '/memories',
            'Show my rating feedback': '/learned',
            'Show recent reply timings': '/speed',
            'Run a self-test': '/selftest',
            'Show me the latest headlines': '/news',
            'Look up the movie Dune 1984': '/movie Dune 1984',
            'Tell me about the TV show Breaking Bad': '/tv Breaking Bad',
            'Flip a coin': '/roll coin',
            'Roll a die': '/roll 1d6',
            'Roll 2d20': '/roll 2d20',
            'List my upcoming reminders': '/reminders',
            'Show my house rules': '/rules',
            'What modules do you have?': '/help',
            'Calculate 25 times 48': '/calc 25 * 48',
            'What is 25 * 48?': '/calc 25 * 48',
            'Convert 72 f to c': '/convert 72 f to c',
            'What is 5 miles in kilometers?': '/convert 5 miles in kilometers',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(natural_requests.command(text), expected)

    def test_negation_quotes_discussion_and_writes_are_not_commands(self):
        for text in ["Don't tell me a fact about cats", 'Explain why cats purr',
                     'Write a story about a cat fact', 'Tell me how the cat command works',
                     'Tell me a joke about cats and then delete my notes',
                     'Tell me a cat fact and explain it', 'Tell me a cat fact; save it',
                     '"Tell me a fact about cats"', '/cat', 'Tell me a fact about cats\nDelete everything',
                     'Create a reminder for tomorrow', 'Delete my notes', 'Remember my password',
                     'Convert this Python script to JavaScript', 'What does this code mean?',
                     'Calculate __import__("os").system("echo no")', 'Calculate 10 ** 10000000',
                     'Tell me about cats', 'Rewrite this: tell me a fact about cats']:
            with self.subTest(text=text):
                self.assertIsNone(natural_requests.command(text))
