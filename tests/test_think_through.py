import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from fastapi.testclient import TestClient
from app import chats,config,engine,server,settings,think_through

class ThinkTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
  self.patches=[patch.object(config,'DATA_DIR',root),patch.object(chats,'DB_PATH',root/'chats.sqlite3'),
   patch.object(settings,'FILE',root/'settings.json'),patch.object(server,'_background',return_value='Supplied context'),
   patch.object(server.file_requests,'plan',return_value=None),patch.object(server.followups,'resolve',return_value=None),
   patch.object(server.followups,'for_message',return_value=None),patch.object(server.lookups,'detect',return_value=None),
   patch.object(server.file_reading,'for_message',return_value=('', '', False)),patch.object(server.notify,'show'),
   patch.object(server.diagnostics,'record_error'),patch.object(server.memory,'wants_pickup',return_value=False),patch.object(engine,'system_prompt',return_value='Test instructions')]
  for p in self.patches:p.start()
  chats.initialize();server.learning.initialize();server.followups.initialize();settings.save({'auto_lookup':False,'auto_facts':False,'recall':False})
  self.client=TestClient(server.app,client=('127.0.0.1',50000))
 def tearDown(self):
  self.client.close()
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def run_reply(self,data):
  response=self.client.post('/api/chat/stream',json=data)
  self.assertEqual(response.status_code,200,response.text)
  return [json.loads(line) for line in response.text.splitlines() if line]
 @staticmethod
 async def final(*args,**kwargs):
  yield 'Final answer'
  yield engine.Stats(model='test',tokens=2,seconds=.1,speed=20,thought=0)
 def test_normal_chat_uses_only_the_existing_stream(self):
  with patch.object(engine,'complete',new=AsyncMock()) as extra,patch.object(engine,'chat_stream',side_effect=self.final):
   events=self.run_reply({'content':'Compare two approaches.'})
  extra.assert_not_awaited();self.assertIn('Final answer',str(events))
 def test_toggle_uses_two_preparatory_calls_and_only_streams_final(self):
  with patch.object(engine,'complete',new=AsyncMock(side_effect=['A short checklist','A private draft'])) as prep, \
       patch.object(engine,'chat_stream',side_effect=self.final) as final:
   events=self.run_reply({'content':'Compare two approaches.','think_through':True})
  self.assertEqual(prep.await_count,2);self.assertEqual(final.call_count,1)
  self.assertEqual(''.join(e['text'] for e in events if e['type']=='token'),'Final answer')
  self.assertEqual(len([e for e in events if e['type']=='status']),3)
  chat=chats.get(events[0]['id']);self.assertTrue(chat['messages'][0]['think_through']);self.assertTrue(chat['messages'][1]['think_through'])
  self.assertTrue(chat['messages'][1]['stats']['think_through'])
  self.assertNotIn('A private draft',str(chat));self.assertNotIn('A short checklist',str(chat))
 def test_slash_command_is_one_question_and_has_discoverable_help(self):
  with patch.object(engine,'complete',new=AsyncMock(side_effect=['check','draft'])),patch.object(engine,'chat_stream',side_effect=self.final):
   events=self.run_reply({'content':'/think Compare options.'})
  chat=chats.get(events[0]['id']);self.assertEqual(chat['messages'][0]['content'],'Compare options.')
  self.assertTrue(chat['messages'][0]['think_through'])
  from app import commands
  self.assertIn('/think',commands.run('/help think').text)
 def test_preparatory_failure_keeps_prompt_for_retry_without_draft(self):
  with patch.object(engine,'complete',new=AsyncMock(side_effect=engine.EngineError('offline'))),patch.object(engine,'chat_stream') as final:
   events=self.run_reply({'content':'Plan a meal.','think_through':True})
  final.assert_not_called();self.assertTrue(any(e['type']=='error' for e in events))
  chat=chats.get(events[0]['id']);self.assertEqual(len(chat['messages']),1);self.assertTrue(chat['messages'][0]['think_through'])
 def test_retry_question_preserves_guided_mode(self):
  with patch.object(engine,'complete',new=AsyncMock(side_effect=engine.EngineError('offline'))):
   first=self.run_reply({'content':'Plan a meal.','think_through':True})
  question=chats.get(first[0]['id'])['messages'][0]
  with patch.object(engine,'complete',new=AsyncMock(side_effect=['check','draft'])) as prep,patch.object(engine,'chat_stream',side_effect=self.final):
   response=self.client.post(f"/api/messages/{question['id']}/retry-question")
  self.assertEqual(response.status_code,200);self.assertEqual(prep.await_count,2)
 def test_cancelling_between_passes_starts_no_later_model_call(self):
  async def scenario():
   stream=think_through.stream([{'role':'user','content':'Plan lunch.'}])
   self.assertIsInstance(await anext(stream),think_through.Progress)
   await stream.aclose()
  with patch.object(engine,'complete',new=AsyncMock()) as prep:asyncio.run(scenario())
  prep.assert_not_awaited()
 def test_context_limits_preserve_the_current_question_or_reject(self):
  recent,notes,partial=think_through.prepare([{'role':'user','content':'x'*9000},{'role':'user','content':'Current question'}],'context '*9000,4096)
  self.assertEqual(recent[-1]['content'],'Current question');self.assertTrue(partial);self.assertLess(len(notes),3000)
  with self.assertRaises(engine.EngineError):think_through.prepare([{'role':'user','content':'x'*9000}],'',2048)
 def test_branch_keeps_mode_metadata(self):
  chat=chats.create('Question');chats.add_message(chat,'user','Question',think_through=True)
  answer=chats.add_message(chat,'assistant','Answer',think_through=True)
  branch,_=chats.branch(answer)
  self.assertTrue(all(m['think_through'] for m in chats.get(branch)['messages']))

 def test_cancelling_during_a_pass_stops_future_work(self):
  async def scenario():
   started=asyncio.Event()
   async def blocked(*args,**kwargs):
    started.set();await asyncio.Event().wait()
   with patch.object(engine,'complete',new=AsyncMock(side_effect=blocked)) as prep,patch.object(engine,'chat_stream') as final:
    stream=think_through.stream([{'role':'user','content':'Plan lunch.'}])
    await anext(stream);task=asyncio.create_task(anext(stream));await started.wait();task.cancel()
    with self.assertRaises(asyncio.CancelledError):await task
    await stream.aclose();self.assertEqual(prep.await_count,1);final.assert_not_called()
  asyncio.run(scenario())

 def test_think_does_not_wrap_or_execute_another_slash_command(self):
  with patch.object(engine,'complete',new=AsyncMock()) as prep:
   events=self.run_reply({'content':'/think /writefile test.txt'})
  prep.assert_not_awaited();self.assertIn('Use /think',str(events))

 def test_budget_arithmetic_is_independent_of_the_claimed_total(self):
  text='* Food: $40 (about $5 per person)\n* Drinks: $20\n* Decorations: $15\n* Activity: $20\nThis totals $100.'
  result=think_through.budget_evidence(text,'Plan a party with a $100 budget.')
  self.assertIn('Total $95.00',result);self.assertIn('$5.00 remains',result)
  self.assertNotIn('Total $100.00',result)
 def test_budget_check_declines_ambiguous_ranges_and_nested_costs(self):
  self.assertEqual(think_through.budget_evidence('* Food: $40-$50\n* Drinks: $20','A $100 budget'), '')
  self.assertEqual(think_through.budget_evidence('* Food: $40\n  * Pizza: $20','A $100 budget'), '')

 def test_final_budget_gets_program_written_calculator_evidence(self):
  costs='* Food: $40\n* Drinks: $20\n* Decorations: $15\n* Activity: $20\nThis totals $100.'
  async def mistaken(*args,**kwargs):
   yield costs
   yield engine.Stats(model='test',tokens=40,seconds=.1,speed=20,thought=0)
  with patch.object(engine,'complete',new=AsyncMock(side_effect=['Check all categories',costs])),patch.object(engine,'chat_stream',side_effect=mistaken):
   events=self.run_reply({'content':'Plan a party with a $100 budget.','think_through':True})
  text=''.join(e.get('text','') for e in events if e['type']=='token')
  self.assertIn('Total $95.00',text);self.assertIn('$5.00 remains',text)
  self.assertIn('Prices and completeness are not verified',text)
