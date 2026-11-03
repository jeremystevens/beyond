"""Weather routing must not capture technical reasoning or output instructions."""
import unittest
from app import lookups
import gc
import tempfile
from pathlib import Path
from unittest.mock import patch
from app import chats, config, followups, search_history
from tests.test_followups import WEATHER

REPORTED = ('Only restart the R-7 if its light is steady amber AND its temperature is below 40°C. '
            'Its light is steady amber, but its temperature is exactly 40°C. Should it be restarted? '
            'Explain in one sentence.')

class WeatherIntentTests(unittest.TestCase):
    def test_reported_temperature_reasoning_stays_in_chat(self):
        for question in (REPORTED,
                         'The device temperature is 40°C; explain in one sentence whether that is below 40°C.',
                         'What is the temperature in the R-7 sensor reading?',
                         'What is the temperature in my oven?',
                         'Explain what temperature means in physics.',
                         'What is temperature?',
                         'The water temperature is 90°C. Explain in simple terms.'):
            with self.subTest(question=question):
                self.assertFalse(lookups.weather_intent(question))
                self.assertEqual(lookups.weather_place(question), '')
                self.assertIsNone(lookups.detect(question))

    def test_real_weather_requests_still_extract_locations(self):
        for question, place in (
            ('What is the current temperature in Reykjavík, Iceland, right now?', 'Reykjavík, Iceland'),
            ("What's the temperature in Paris?", 'Paris'),
            ('check the weather in Franklin, Tennessee', 'Franklin, Tennessee'),
            ('weather in paris', 'paris'),
            ('Will it rain in London tomorrow?', 'London'),
            ('Is it hot in Phoenix right now?', 'Phoenix'),
            ('What is the temperature in St. Louis?', 'St. Louis'),
            ('What is the temperature in Paris? Explain in one sentence.', 'Paris')):
            with self.subTest(question=question):
                self.assertEqual(lookups.weather_place(question), place)
                self.assertEqual(lookups.detect(question), ('weather', place))
        for question in ('What is the temperature outside?', 'weather please', 'I meant the weather'):
            self.assertTrue(lookups.weather_intent(question))
        self.assertEqual(lookups.weather_place('What is the temperature? Explain in one sentence.'), '')


class WeatherFollowupIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(chats, 'DB_PATH', Path(self.temp.name)/'chat.sqlite3'),
                        patch.object(config, 'DATA_DIR', Path(self.temp.name))]
        for item in self.patches:
            item.start()
        chats.initialize(); followups.initialize(); search_history.initialize()
        self.chat = chats.create('Weather isolation')

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        gc.collect(); self.temp.cleanup()

    def save(self, tool, query, raw):
        mid = chats.add_message(self.chat, 'assistant', raw, kind='command')
        followups.save(self.chat, mid, followups.snapshot(tool, query, raw))
    def test_device_temperature_never_reuses_weather_state(self):
        from app import followups
        from tests.test_followups import WEATHER
        self.assertIsNone(followups.weather_request(None, REPORTED))
        self.assertIsNone(followups.weather_request(self.chat, REPORTED))
        self.save('weather', 'London', WEATHER)
        self.assertIsNone(followups.weather_request(self.chat, REPORTED))
        self.assertIsNone(followups.resolve(self.chat, REPORTED))
        self.assertIsNone(followups.get(self.chat))
