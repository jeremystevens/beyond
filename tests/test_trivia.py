"""Trivia source validation, private rounds and atomic shared score/streak updates."""
import asyncio
import copy
import json
import threading
import unittest
from unittest.mock import Mock, patch

import httpx
from app import chats, commands, games, trivia
from app.tools import trivia as source
import test_imagine as ti


def questions(count=5, difficulty=None):
    return [{'question': f'Question {i}?', 'correct': f'Right {i}',
             'wrong': [f'Wrong A {i}', f'Wrong B {i}', f'Wrong C {i}'],
             'difficulty': difficulty or ['easy','medium','hard','easy','hard'][i%5],
             'category': 'Science', 'source': 'Open Trivia DB',
             'answers': [f'Right {i}',f'Wrong A {i}',f'Wrong B {i}',f'Wrong C {i}'],
             'correct_index': 0} for i in range(count)]


class SourceTests(unittest.TestCase):
    def setUp(self):
        source._cache.clear()
        self.last = source._last_opentdb

    def tearDown(self):
        source._cache.clear()
        source._last_opentdb = self.last

    def test_options_aliases_and_invalid_difficulty(self):
        self.assertEqual(source.parse_options('hard video games'.split()), ('videogames','hard'))
        self.assertEqual(source.parse_options('science medium'.split()), ('science','medium'))
        self.assertEqual(source.parse_options([]), (None,None))
        for words in ('easy hard', 'unknown', 'hardware'):
            with self.assertRaises(ValueError):
                source.parse_options(words.split())

    def test_primary_decoding_filters_and_rate_limit(self):
        payload={'response_code':0,'results':[{'question':'A%20%26%20B%3F','correct_answer':'Yes',
                  'incorrect_answers':['No','Maybe','Never'],'difficulty':'easy','category':'Science'}]}
        source._last_opentdb=0
        with patch.object(source,'_get',return_value=payload) as fetch, patch.object(source.time,'monotonic',return_value=100):
            result=source._opentdb('science','easy')
            self.assertEqual(result[0]['question'],'A & B?')
            self.assertEqual(source._opentdb('science','easy'),[])
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(fetch.call_args.args[1]['category'],17)
        self.assertEqual(fetch.call_args.args[1]['difficulty'],'easy')
        self.assertEqual(fetch.call_args.args[1]['encode'],'url3986')

    def test_fallback_cache_and_distinct_questions(self):
        with patch.object(source,'_opentdb',return_value=[]) as primary, \
                patch.object(source,'_trivia_api',return_value=questions(10,'easy')) as fallback:
            first=source.round_questions('science','easy')
            second=source.round_questions('science','easy')
        self.assertEqual(len(first),5)
        self.assertEqual(len(second),5)
        self.assertFalse({q['question'] for q in first}&{q['question'] for q in second})
        self.assertEqual(fallback.call_count,1)
        self.assertEqual(primary.call_count,1)

    def test_bad_questions_and_small_bank(self):
        invalid=questions(1)[0];invalid['wrong'][0]=invalid['correct']
        with patch.object(source,'_opentdb',return_value=[invalid,*questions(3),questions(1)[0]]), \
                patch.object(source,'_trivia_api') as fallback:
            result=source.round_questions()
        self.assertEqual(len(result),3)
        fallback.assert_not_called()
        self.assertFalse(source.valid({**questions(1)[0],'difficulty':'unknown'}))
        self.assertFalse(source.valid({**questions(1)[0],'question':'x'*2001}))
        self.assertFalse(source.valid(questions(1)[0],'hard'))

    def test_unavailable_and_busy_release_lock(self):
        with patch.object(source,'_opentdb',return_value=[]),patch.object(source,'_trivia_api',return_value=[]):
            with self.assertRaises(source.TriviaError):
                source.round_questions()
        self.assertFalse(source._lock.locked())
        source._lock.acquire()
        try:
            with self.assertRaisesRegex(source.TriviaError,'already being fetched'):
                source.round_questions()
        finally:
            source._lock.release()

    def test_http_is_bounded_and_uses_only_filter_parameters(self):
        response=Mock()
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.iter_content.return_value=[b'[]']
        with patch.object(source.requests,'get',return_value=response) as fetch:
            self.assertEqual(source._get('https://opentdb.com/api.php',{'amount':10}),[])
        self.assertEqual(fetch.call_args.kwargs['timeout'],(3,8))
        self.assertEqual(fetch.call_args.kwargs['params'],{'amount':10})
        response.iter_content.return_value=[b'x'*(1024*1024+1)]
        with patch.object(source.requests,'get',return_value=response),self.assertRaises(source.TriviaError):
            source._get('https://opentdb.com/api.php',{})


class TriviaApiTests(unittest.IsolatedAsyncioTestCase):
    setUpClass=classmethod(ti.ImagineApiTests.setUpClass.__func__)
    tearDownClass=classmethod(ti.ImagineApiTests.tearDownClass.__func__)

    async def asyncSetUp(self):
        games.initialize();trivia.initialize()
        with chats.connect() as db:
            db.execute('DELETE FROM game_stats')
            db.execute('DELETE FROM trivia_scores')
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test')
        self.created=[]

    async def asyncTearDown(self):
        for cid in self.created:
            await self.client.delete('/api/chats/'+str(cid))
        await self.client.aclose()

    def start(self, count=5):
        cid=chats.create('Trivia check');self.created.append(cid)
        state={'questions':questions(count),'category':'science','difficulty':None,'index':0,'revision':0,
               'selected':None,'answered':0,'correct':0,'points':0}
        mid=trivia.save_new(cid,state)
        return cid,mid,state

    async def answer(self,mid,revision,choice):
        return await self.client.post(f'/api/trivia/{mid}/answer',json={'revision':revision,'choice':choice})

    async def test_command_picker_categories_score_and_real_round_storage(self):
        with patch.object(source,'round_questions',return_value=questions(5,'easy')) as fetch:
            for command in ('/trivia','/trivia categories','/help trivia','/trivia score','/trivia start science easy'):
                response=await self.client.post('/api/chat/stream',json={'content':command})
                events=[json.loads(line) for line in response.text.splitlines()]
                cid=next(item['id'] for item in events if item['type']=='chat');self.created.append(cid)
                self.assertEqual(chats.recent_messages(cid,12),[])
            message=next(item for item in events if item['type']=='message')
        fetch.assert_called_once_with('science','easy')
        self.assertEqual(message['game']['type'],'trivia')
        self.assertEqual(message['game']['length'],5)
        self.assertEqual((await self.client.get(f"/api/trivia/{message['id']}")).status_code,200)
        self.assertTrue(next(item for item in games.menu()['items'] if item['id']=='trivia')['available'])
        self.assertIn('/trivia score',commands.run('/help trivia').text)

    async def test_complete_round_points_accuracy_and_streak_rules(self):
        _,mid,_=self.start()
        revision=0
        for index,choice in enumerate([0,1,0,0,0]):
            response=await self.answer(mid,revision,choice)
            self.assertEqual(response.status_code,200,response.text)
            game=response.json()['game'];revision=game['revision']
            self.assertIn('correct_index',game)
            if index<4:
                response=await self.client.post(f'/api/trivia/{mid}/next',json={'revision':revision})
                self.assertEqual(response.status_code,200,response.text)
                game=response.json()['game'];revision=game['revision']
                self.assertNotIn('correct_index',game)
        self.assertTrue(game['finished'])
        self.assertEqual((game['points'],game['correct'],game['answered']),(8,4,5))
        self.assertEqual(trivia.stats(),dict(points=8,answered=5,correct=4,streak=3,best_streak=3))
        self.assertEqual(games.stats()[0]['score'],8)
        self.assertEqual(games.stats()[0]['played'],5)
        self.assertIn('80%',trivia.stats_text())

    async def test_correct_answers_and_future_questions_are_private(self):
        cid,mid,_=self.start()
        response=await self.client.get(f'/api/trivia/{mid}')
        self.assertNotIn('correct_index',response.text)
        self.assertNotIn('Right 1',response.text)
        self.assertNotIn('questions',response.json()['game'])
        saved=json.dumps(chats.get(cid))
        self.assertNotIn('Right 1',saved)
        self.assertNotIn('correct_index',saved)

    async def test_duplicate_answers_from_two_devices_count_once(self):
        _,mid,_=self.start(1)
        responses=await asyncio.gather(self.answer(mid,0,0),self.answer(mid,0,1))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(trivia.stats()['answered'],1)
        self.assertEqual(games.stats()[0]['played'],1)
        self.assertEqual((await self.answer(mid,1,2)).status_code,409)

    async def test_next_requires_answer_stale_and_forged_inputs_rejected(self):
        _,mid,_=self.start()
        self.assertEqual((await self.client.post(f'/api/trivia/{mid}/next',json={'revision':0})).status_code,409)
        for body in ({'revision':True,'choice':0},{'revision':0,'choice':'1'},
                     {'revision':0,'choice':4},{'revision':0,'choice':0,'points':999}):
            self.assertEqual((await self.client.post(f'/api/trivia/{mid}/answer',json=body)).status_code,422)
        self.assertEqual(trivia.stats()['answered'],0)
        await self.answer(mid,0,0)
        stale=await self.client.post(f'/api/trivia/{mid}/next',json={'revision':0})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.json()['game']['revision'],1)

    async def test_reload_and_restart_initialization_then_delete_preserves_score(self):
        cid,mid,_=self.start()
        await self.answer(mid,0,0)
        trivia.initialize()
        self.assertEqual((await self.client.get(f'/api/trivia/{mid}')).json()['game']['selected'],0)
        with patch.object(source,'round_questions',side_effect=AssertionError('No fetch while playing')):
            response=await self.client.post(f'/api/trivia/{mid}/next',json={'revision':1})
        self.assertEqual(response.status_code,200)
        await self.client.delete('/api/chats/'+str(cid))
        self.assertEqual((await self.client.get(f'/api/trivia/{mid}')).status_code,404)
        self.assertEqual((await self.answer(mid,2,0)).status_code,404)
        self.assertEqual(trivia.stats()['points'],1)

    async def test_recording_failure_rolls_back_answer_and_both_scores(self):
        _,mid,_=self.start()
        with patch.object(games,'record',side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError,'injected'):
                trivia.change(mid,0,0)
        self.assertEqual(trivia.stats()['answered'],0)
        self.assertEqual(games.stats(),[])
        game=(await self.client.get(f'/api/trivia/{mid}')).json()['game']
        self.assertEqual(game['revision'],0)
        self.assertIsNone(game['selected'])

    async def test_source_failure_keeps_retry_filters_and_does_not_count(self):
        with patch.object(source,'round_questions',side_effect=source.TriviaError('Offline')):
            reply=await asyncio.to_thread(commands.run,'/trivia science hard')
        self.assertEqual(reply.game['type'],'trivia_picker')
        self.assertEqual((reply.game['category'],reply.game['difficulty']),('science','hard'))
        self.assertIsNone(reply.save_message)
        self.assertEqual(trivia.stats()['answered'],0)
        with patch.object(source,'round_questions') as fetch:
            reply=commands.run('/trivia unknown')
        fetch.assert_not_called()
        self.assertIn('Unknown trivia category',reply.text)

    async def test_slow_fetch_keeps_other_chat_commands_available(self):
        entered,release=threading.Event(),threading.Event()
        def fetch(*args):
            entered.set()
            if not release.wait(20):
                raise source.TriviaError('Timed out')
            return questions(1,'easy')
        with patch.object(source,'round_questions',side_effect=fetch):
            pending=asyncio.create_task(self.client.post('/api/chat/stream',json={'content':'/trivia easy'}))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait,5))
                response=await self.client.post('/api/chat/stream',json={'content':'/calc 2+2'})
                self.assertIn('4',response.text)
                events=[json.loads(line) for line in response.text.splitlines()]
                self.created.append(next(item['id'] for item in events if item['type']=='chat'))
                self.assertFalse(pending.done())
            finally:
                release.set()
                response=await pending
                events=[json.loads(line) for line in response.text.splitlines()]
                self.created.append(next(item['id'] for item in events if item['type']=='chat'))


if __name__=='__main__':
    unittest.main()
