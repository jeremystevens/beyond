"""Narrow routing/isolation checks; temporary SQLite and fake tool results only."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import chats, commands, config, followups, search_history
from app.commands import Command

ALIEN = ('🎬 Alien (1979)\nDirected by Ridley Scott · 117 min\nStarring: Sigourney Weaver, Tom Skerritt\n'
         '⭐ IMDb 8.5/10\n\nA space crew encounters a dangerous alien.\n\nSources: Wikidata, Wikipedia — https://en.wikipedia.org/wiki/Alien_(film)')
WEATHER = ('Weather for London, UK\nLocal time: 2026-10-18 12:00\n\nNow: sunny, 17°C\n\n'
           '3-day forecast:\nToday: Sunny, 10–17°C\nTomorrow: Rain, 9–14°C, ☔ 80%\n\nSource: Open-Meteo.com')


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patchers=[patch.object(chats,'DB_PATH',Path(self.temp.name)/'beyond.sqlite3'),
                       patch.object(config,'DATA_DIR',Path(self.temp.name))]
        for item in self.patchers: item.start()
        chats.initialize(); search_history.initialize(); followups.initialize()
        self.chat=chats.create('Follow-up check')
        self.other=chats.create('Another chat')

    def tearDown(self):
        for item in reversed(self.patchers): item.stop()
        gc.collect(); self.temp.cleanup()

    def save(self, tool, query, raw, chat=None):
        target=chat or self.chat
        mid=chats.add_message(target,'assistant',raw,kind='command')
        state=followups.snapshot(tool,query,raw)
        followups.save(target,mid,state)
        return state

    def test_weather_replacement_and_fresh_day_lookup_keep_query_and_are_recorded_once(self):
        self.save('weather','London',WEATHER)
        action=followups.resolve(self.chat,'What about Paris?')
        self.assertEqual(action['command'],'/weather Paris')
        action=followups.resolve(self.chat,'Will it rain there tomorrow?')
        self.assertEqual((action['kind'],action['day'],action['command']),('weather_day','Tomorrow','/weather London'))
        seen=[]
        def weather(query):
            seen.append(query); return WEATHER
        with patch.dict(commands._BY_NAME,{'weather':Command('weather','fake','/weather',weather)}):
            reply=commands.run(action['command'])
        reply=followups.weather_answer(reply,action['day'])
        self.assertEqual(seen,['London'])
        self.assertIn('Tomorrow: Rain',reply.text)
        self.assertNotIn('Today: Sunny',reply.text)
        self.assertIn('Today: Sunny',reply.lookup_context['raw'])
        self.assertEqual(search_history.browse()['total'],1)

    def test_media_facts_use_the_resolved_title_and_never_invent_missing_details(self):
        state=self.save('movie','Alien',ALIEN)
        for question,expected in [('Who directed it?','Ridley Scott'),('Who stars in it?','Sigourney Weaver'),
                                  ('How long is it?','117 minutes'),('When did it come out?','1979'),
                                  ('What is it rated?','IMDb 8.5'),('What is it about?','space crew')]:
            reply=followups.answer(followups.resolve(self.chat,question))
            self.assertIn(expected,reply.text)
            self.assertIn('Alien (1979)',reply.text)
            self.assertEqual(reply.lookup_context,state)
        self.assertEqual(search_history.browse()['total'],0)  # reading a cached fact is not a new search
        self.save('movie','Alien','🎬 Alien (1979 film)\n\nAlien is a science fiction film directed by Ridley Scott and written by Dan O’Bannon.\n\nSource: Wikipedia')
        self.assertIn('Directed by Ridley Scott\n',followups.answer(followups.resolve(self.chat,'Who directed it?')).text)
        self.save('tv','Breaking Bad','📺 Breaking Bad (2008–2013)\nStarring: Bryan Cranston\n\nA teacher becomes a criminal.\n\nSource: TVmaze')
        self.assertIn('2008',followups.answer(followups.resolve(self.chat,'When did it come out?')).text)
        self.assertIn('particular episode',followups.answer(followups.resolve(self.chat,'Who directed it?')).text)

    def test_context_is_chat_local_persistent_and_cleared_by_topic_changes_or_failed_lookups(self):
        self.save('movie','Alien',ALIEN)
        followups.initialize()
        self.assertIsNotNone(followups.get(self.chat))
        self.assertIsNone(followups.resolve(self.other,'Who directed it?'))
        original=followups.get(self.chat)
        reply_id=chats.add_message(self.chat,'assistant','The film is scary.')
        followups.save(self.chat,reply_id,original,for_retry=True)
        self.save('weather','London',WEATHER)
        self.assertEqual(followups.for_message(reply_id)['query'],'Alien')
        self.assertEqual(followups.get(self.chat)['query'],'London')
        self.save('movie','Alien',ALIEN)
        self.assertEqual(followups.resolve(self.chat,'Thanks!')['kind'],'ack')
        self.assertEqual(followups.resolve(self.chat,'Is it scary?')['kind'],'context')
        self.assertIsNone(followups.resolve(self.chat,'Help me write a birthday greeting'))
        self.assertIsNone(followups.get(self.chat))
        self.save('web','Python read files','1. A real result\nhttps://example.org')
        self.assertEqual(followups.resolve(self.chat,'What about Java?')['kind'],'clarify_search')
        self.save('weather','Paris',"🌐 I couldn't reach the weather service.")
        self.assertIsNone(followups.get(self.chat))
        self.save('movie','Alien',ALIEN)
        chats.delete(self.chat)
        self.assertIsNone(followups.get(self.chat))
        self.assertIsNone(followups.for_message(reply_id))


if __name__=='__main__':
    unittest.main()
