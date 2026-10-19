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
        self.assertLess(len((prompts.default_prompt()+prompts.APP_CONTRACT).split()),500)
        text=engine.system_prompt()
        self.assertIn(prompts.default_prompt(),text)
        self.assertIn('Python controls tools',text)
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
        self.assertIn('Python controls tools',text)
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
