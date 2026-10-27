"""Focused prompt selection/persistence checks; no model requests or live user settings."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import chats, config, engine, prompts, settings


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patchers=[
            patch.object(chats,'DB_PATH',Path(self.temp.name)/'beyond.sqlite3'),
            patch.object(settings,'FILE',Path(self.temp.name)/'settings.json'),
            patch.object(config,'DATA_DIR',Path(self.temp.name)),
            patch.object(engine.rules,'prompt_block',return_value='\nHOUSE RULES'),
            patch.object(engine.rules,'all_rules',return_value=[]),
            patch.object(engine.memory,'prompt_block',return_value='\nSAVED MEMORIES')]
        for item in self.patchers: item.start()

    def tearDown(self):
        for item in reversed(self.patchers): item.stop()
        gc.collect()
        self.temp.cleanup()

    def test_default_prompt_has_a_small_budget_and_keeps_the_app_contract(self):
        self.assertFalse(settings.load()['custom_prompt_enabled'])
        self.assertLess(len((prompts.default_prompt()+prompts.APP_CONTRACT).split()),600)
        text=engine.system_prompt()
        self.assertIn(prompts.default_prompt(),text)
        self.assertIn('Python runs tools',text)
        self.assertIn('built-in web search: /web <query>',text)
        self.assertTrue(text.endswith('\nHOUSE RULES\nSAVED MEMORIES'))
        self.assertNotIn('## Selected persona:',text)
        with patch.object(config,'PERSONALITY_FILE',Path(self.temp.name)/'missing.md'):
            self.assertIn(prompts.FALLBACK,engine.system_prompt())

    def test_custom_prompt_api_persists_and_default_restore_keeps_saved_text(self):
        from app import server
        custom='Be a patient teacher. Explain things with simple examples.'
        response=server.save_prompt(server.PromptChoice(custom_prompt=custom,custom_prompt_enabled=True))
        self.assertEqual(response,{'custom_prompt':custom,'custom_prompt_enabled':True})
        text=engine.system_prompt()
        self.assertTrue(text.startswith(custom))
        self.assertNotIn('You are BEYOND (Built Entirely',text)
        self.assertIn('Python runs tools',text)
        self.assertIn('built-in web search: /web <query>',text)
        self.assertTrue(text.endswith('\nHOUSE RULES\nSAVED MEMORIES'))
        self.assertEqual(settings.load()['custom_prompt'],custom)
        response=server.save_prompt(server.PromptChoice(custom_prompt=custom,custom_prompt_enabled=False))
        self.assertFalse(response['custom_prompt_enabled'])
        self.assertEqual(settings.load()['custom_prompt'],custom)
        self.assertTrue(engine.system_prompt().startswith(prompts.default_prompt()))
        saved=settings.FILE.read_text(encoding='utf-8')
        with self.assertRaises(settings.SettingsError):
            settings.save({'custom_prompt':'  ','custom_prompt_enabled':True})
        self.assertEqual(settings.FILE.read_text(encoding='utf-8'),saved)
        for bad in (123,'x'*(prompts.MAX_CUSTOM_CHARS+1)):
            with self.assertRaises(settings.SettingsError):
                settings.validate({'custom_prompt':bad})

    def test_improvement_returns_a_draft_without_changing_saved_settings(self):
        import asyncio
        from unittest.mock import AsyncMock
        from app import server
        settings.save({'custom_prompt':'Existing saved prompt.','custom_prompt_enabled':True})
        before=settings.FILE.read_text(encoding='utf-8')
        body=server.PromptDraft(prompt='Be a teacher. Be helpful. Explain things simply.')
        with patch.object(server.builtin_engine,'busy',return_value=False), \
             patch.object(server.engine,'complete',new_callable=AsyncMock,return_value='Explain concepts clearly with simple examples.') as complete:
            result=asyncio.run(server.improve_prompt(body))
            self.assertEqual(result['prompt'],'Explain concepts clearly with simple examples.')
            sent=complete.call_args.args[0]
            self.assertEqual(sent[-1],{'role':'user','content':body.prompt})
            self.assertNotIn('Existing saved prompt.',str(sent))
        self.assertEqual(settings.FILE.read_text(encoding='utf-8'),before)
        with patch.object(server.builtin_engine,'busy',return_value=True), \
             patch.object(server.engine,'complete',new_callable=AsyncMock) as complete:
            self.assertEqual(asyncio.run(server.improve_prompt(body)).status_code,409)
            complete.assert_not_awaited()
        with patch.object(server.builtin_engine,'busy',return_value=False), \
             patch.object(server.engine,'complete',new_callable=AsyncMock,side_effect=engine.EngineError('AI unavailable')):
            self.assertEqual(asyncio.run(server.improve_prompt(body)).status_code,503)
        self.assertEqual(settings.FILE.read_text(encoding='utf-8'),before)
        self.assertEqual(asyncio.run(server.improve_prompt(server.PromptDraft(prompt=' '))).status_code,400)

    def test_clarification_contract_preserves_context_in_default_and_custom_chat(self):
        history = [
            {'role': 'user', 'content': 'Python says ModuleNotFoundError: No module named requests.'},
            {'role': 'assistant', 'content': 'Which interpreter are you using?'},
            {'role': 'user', 'content': 'Python 3.14 in my project environment.'}]
        original = [dict(message) for message in history]
        for custom in (False, True):
            settings.save({'custom_prompt_enabled': custom, 'custom_prompt': 'Be a helpful teacher.'})
            for stream in (False, True):
                with self.subTest(custom=custom, stream=stream), \
                     patch.object(engine, '_server', return_value=('http://model.test', 'test-model')), \
                     patch.object(engine, 'model_context', return_value=''):
                    _, _, payload = engine._prepare(history, stream, 'Working context: the environment is on Windows.')
                sent = payload['messages']
                self.assertEqual(sent[0]['content'].count(prompts.CLARIFICATION_POLICY), 1)
                self.assertEqual(sent[1:-1], history[:-1])
                self.assertIn('Working context: the environment is on Windows.', sent[-1]['content'])
                self.assertTrue(sent[-1]['content'].endswith(history[-1]['content']))
                self.assertEqual(payload['stream'], stream)
        self.assertEqual(history, original)

    def test_writing_request_carries_prose_boundary_with_custom_prompt(self):
        settings.save({'custom_prompt_enabled': True, 'custom_prompt': 'Be a helpful writer.'})
        request = [{'role': 'user', 'content': 'Give me a generic polite email template declining an invitation.'}]
        with patch.object(engine, '_server', return_value=('http://model.test', 'test-model')), \
             patch.object(engine, 'model_context', return_value=''):
            _, _, payload = engine._prepare(request, True)
        self.assertIn('Emails, letters, templates and explanations are ordinary text.', payload['messages'][0]['content'])
        self.assertIn('Fulfil writing requests as prose', payload['messages'][-1]['content'])
        self.assertTrue(payload['messages'][-1]['content'].endswith(request[-1]['content']))
        self.assertEqual(request[0]['content'], 'Give me a generic polite email template declining an invitation.')

    def test_one_off_job_does_not_inherit_chat_clarification_instructions(self):
        import asyncio
        import json
        from contextlib import nullcontext
        import httpx
        sent = []
        messages = [{'role': 'system', 'content': 'Rewrite the supplied text only.'},
                    {'role': 'user', 'content': 'Thanks for the invitation.'}]
        def respond(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={'choices': [{'message': {'content': 'Thank you for inviting me.'}}]})
        with patch.object(engine, '_server', return_value=('http://model.test', '')), \
             patch.object(engine.builtin_engine, 'using_model', return_value=nullcontext()), \
             patch.object(engine, '_client', side_effect=lambda: httpx.AsyncClient(transport=httpx.MockTransport(respond))):
            result = asyncio.run(engine.complete(messages, max_tokens=60, temperature=0))
        self.assertEqual(result, 'Thank you for inviting me.')
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['messages'], messages)
        self.assertNotIn(prompts.CLARIFICATION_POLICY, str(sent))

    def test_tool_details_are_attached_only_to_relevant_user_turns(self):
        greeting=[{'role':'user','content':'Hello how are you?'}]
        self.assertEqual(engine.with_reply_notes(greeting),greeting)
        messages=[{'role':'assistant','content':'Earlier answer.'},
                  {'role':'user','content':'What is the weather in Franklin, Tennessee?'}]
        prepared=engine.with_reply_notes(messages,'A real forecast.')
        self.assertEqual(prepared[0],messages[0])
        self.assertIn('/weather <city',prepared[-1]['content'])
        self.assertIn('A real forecast.',prepared[-1]['content'])
        self.assertNotIn('/blackjack',prepared[-1]['content'])
        self.assertEqual(messages[-1]['content'],'What is the weather in Franklin, Tennessee?')
        with patch.object(engine.rules,'all_rules',return_value=[{'text':'Use short answers'}]):
            self.assertIn('Follow the house rules: Use short answers.',engine.with_reply_notes(greeting)[-1]['content'])
        self.assertIn('/look',prompts.tool_notes('Can you describe this photo?'))
        self.assertIn('/hangman',prompts.tool_notes('What games can we play?'))


if __name__=='__main__':
    unittest.main()
