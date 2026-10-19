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

    def test_weather_location_and_confirmation_complete_only_a_recent_user_request(self):
        # Reproduce the reported sequence, including an old mistaken movie lookup.
        chats.add_message(self.chat,'user','what about alanta georgia',kind='command')
        chats.add_message(self.chat,'assistant','No movie or TV show found',kind='command')
        request='hmm nah i was actually talking about the weather'
        self.assertEqual(followups.weather_request(self.chat,request)['kind'],'weather_place')
        chats.add_message(self.chat,'user',request)
        chats.add_message(self.chat,'assistant','Which city or town should I check?',kind='command')
        location="I rather see what's its like in franklin Tennessee"
        action=followups.weather_request(self.chat,location)
        self.assertEqual(action['command'],'/weather franklin, Tennessee')
        self.assertIsNone(followups.weather_request(self.other,location))
        chats.add_message(self.chat,'user',location)
        chats.add_message(self.chat,'assistant',"I'll check the current weather.")
        self.assertEqual(followups.weather_request(self.chat,'that would be great')['command'],
                         '/weather franklin, Tennessee')
        self.assertIsNone(followups.weather_request(self.chat,'Help me write a letter'))
        self.assertIsNone(followups.weather_request(self.chat,'Tell me a joke'))
        chats.add_message(self.chat,'user','Tell me a joke')
        chats.add_message(self.chat,'assistant','Here is a joke.')
        self.assertIsNone(followups.weather_request(self.chat,'that would be great'))
        self.assertIsNone(followups.weather_request(self.chat,'Paris'))
        self.assertEqual(followups.weather_request(None,'check the weather in Franklin, Tennessee')['command'],
                         '/weather Franklin, Tennessee')
        chats.add_message(self.other,'user','weather please')
        chats.add_message(self.other,'assistant','Which city or town should I check?',kind='command')
        self.assertEqual(followups.weather_request(self.other,'Franklin, Tennessee')['command'],
                         '/weather Franklin, Tennessee')
        chats.add_message(self.other,'user','Franklin, Tennessee',kind='command')
        chats.add_message(self.other,'assistant',WEATHER,kind='command')
        self.assertIsNone(followups.weather_request(self.other,'that would be great'))
        self.assertIsNone(followups.weather_request(None,'What is my CPU temperature?'))
        # Exercise the actual stream handler with a stand-in tool, without invoking the model.
        import asyncio
        import json
        from app import server
        pending=chats.create('Weather clarification')
        chats.add_message(pending,'user','I meant the weather')
        chats.add_message(pending,'assistant','Which city?',kind='command')
        seen=[]
        def weather(query):
            seen.append(query)
            return WEATHER.replace('London, UK','Franklin, Tennessee')
        async def send():
            response=await server.chat_stream(server.SendRequest(chat_id=pending,content=location))
            return [json.loads(event) async for event in response.body_iterator]
        with patch.object(server.settings,'load',return_value={'auto_lookup':True}), \
             patch.dict(commands._BY_NAME,{'weather':Command('weather','fake','/weather',weather)}), \
             patch.object(server.engine,'chat_stream',side_effect=AssertionError('Model must not handle this lookup')):
            events=asyncio.run(send())
        self.assertEqual(seen,['franklin, Tennessee'])
        self.assertTrue(any(event['type']=='status' for event in events))
        self.assertTrue(any(event.get('text','').startswith('Weather for Franklin') for event in events))
        self.assertEqual(search_history.browse()['total'],1)
        self.assertEqual(followups.get(pending)['query'],'franklin, Tennessee')

    def test_missing_comma_is_handled_by_the_shared_place_finder(self):
        from app.tools import places
        from unittest.mock import Mock
        denver={'name':'Denver','admin1':'Colorado','country':'United States','country_code':'US',
                'latitude':39.74,'longitude':-104.99}
        wrong={'name':'Denver','admin1':'North Carolina','country':'United States','country_code':'US'}
        response=Mock()
        response.json.return_value={'results':[wrong,denver]}
        with patch.object(places.httpx,'get',return_value=response) as fetch:
            self.assertEqual(places.geocode('Denver Colorado'),denver)
            self.assertEqual(fetch.call_args.kwargs['params']['name'],'Denver')
            self.assertEqual(fetch.call_args.kwargs['params']['countryCode'],'US')
            self.assertEqual(places.geocode('Denver CO'),denver)
            self.assertEqual(places.geocode('Denver, Colorado'),denver)
        for original,normalized in [('Franklin Tennessee','Franklin, Tennessee'),('New York NY','New York, NY'),
                                    ('San Francisco California','San Francisco, California'),
                                    ('New York','New York'),('Mexico City','Mexico City'),('Paris','Paris')]:
            self.assertEqual(places.normalize_location(original),normalized)
        chats.add_message(self.chat,'user','weather please')
        chats.add_message(self.chat,'assistant','Which city or town should I check?',kind='command')
        self.assertEqual(followups.weather_request(self.chat,'Denver Colorado')['command'],
                         '/weather Denver, Colorado')
        chats.add_message(self.chat,'user','Denver Colorado',kind='command')
        chats.add_message(self.chat,'assistant',"I couldn't find a place called: Denver Colorado",kind='command')
        self.assertEqual(followups.weather_request(self.chat,'how about Franklin Tennessee')['command'],
                         '/weather Franklin, Tennessee')
        self.assertIsNone(followups.weather_request(self.chat,'Help me write a letter'))

    def test_typo_suggestion_and_natural_confirmation_execute_the_weather_tool(self):
        import asyncio
        import json
        from app import server
        from app.tools import places
        seen=[]
        def weather(query):
            seen.append(query)
            if query=='Denver, CO':
                return "I couldn't find a place called: Denver, CO"
            return WEATHER.replace('London, UK','Franklin, Tennessee')
        async def send(text,chat=None):
            response=await server.chat_stream(server.SendRequest(chat_id=chat or self.chat,content=text))
            return [json.loads(event) async for event in response.body_iterator]
        with patch.object(server.settings,'load',return_value={'auto_lookup':True}), \
             patch.dict(commands._BY_NAME,{'weather':Command('weather','fake','/weather',weather)}), \
             patch.object(server.engine,'chat_stream',side_effect=AssertionError('No model should handle a pending weather request')):
            asyncio.run(send('/weather Denver, CO'))
            self.assertEqual(followups.pending(self.chat)['status'],'location')
            events=asyncio.run(send('how about franklin tennese'))
            self.assertEqual(seen,['Denver, CO'])  # a spelling suggestion is not a search
            self.assertTrue(any('Did you mean franklin, Tennessee?' in e.get('text','') for e in events))
            message=next(e for e in events if e['type']=='message')
            self.assertEqual(message['buttons'][0][0]['send'],'/weather franklin, Tennessee')
            self.assertEqual(followups.pending(self.chat)['query'],'franklin, Tennessee')
            followups.initialize()
            self.assertIsNone(followups.pending(self.other))
            events=asyncio.run(send('yes thats what i want!!'))
            self.assertEqual(seen,['Denver, CO','franklin, Tennessee'])
            self.assertTrue(any(e['type']=='status' for e in events))
            self.assertTrue(any(e.get('text','').startswith('Weather for Franklin') for e in events))
            self.assertIsNone(followups.pending(self.chat))
            self.assertEqual(followups.get(self.chat)['query'],'franklin, Tennessee')
        self.assertEqual(places.suggest_location('Franklin tennese'),'Franklin, Tennessee')
        self.assertEqual(places.suggest_location('Franklin, Tennese'),'Franklin, Tennessee')
        self.assertIsNone(places.suggest_location('Mexico City'))
        self.assertIsNone(places.suggest_location('New York'))
        self.assertIsNone(places.suggest_location('Denver, CO'))
        for text in ('yes thats what i want!!','yep that excatly what i meant go ahead!','yes, please do','yes'):
            self.assertTrue(followups.is_confirmation(text),text)
        for text in ('yes but write a letter','yes I moved to Paris','no thanks'):
            self.assertFalse(followups.is_confirmation(text),text)

    def test_pending_correction_is_bound_to_the_current_chat_and_turn(self):
        reply=commands.run('/weather Franklin tennese')
        self.assertIn('Did you mean Franklin, Tennessee?',reply.text)
        self.assertEqual(reply.pending_lookup['status'],'confirm')
        mid=chats.add_message(self.chat,'assistant',reply.text,kind='command',buttons=reply.buttons)
        followups.save_pending(self.chat,mid,reply.pending_lookup)
        self.assertEqual(followups.weather_request(self.chat,'yes thats what i want!!')['command'],
                         '/weather Franklin, Tennessee')
        self.assertIsNone(followups.weather_request(self.other,'yes thats what i want!!'))
        self.assertIsNone(followups.weather_request(self.chat,'Help me write a letter'))
        chats.add_message(self.chat,'user','Help me write a letter')
        chats.add_message(self.chat,'assistant','Here is a letter.')
        self.assertIsNone(followups.pending(self.chat))
        self.assertIsNone(followups.weather_request(self.chat,'yes thats what i want!!'))
        chats.delete(self.chat)
        self.assertIsNone(followups.pending(self.chat))

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
