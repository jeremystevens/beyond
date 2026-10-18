"""Phase 24: reviewable enhancement, style-aware negatives and reproducible image requests."""
import asyncio
import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
from PIL import Image

from app import chats, engine, image_jobs, notify
from app.tools import image_prompts, imagine
import test_imagine as ti


class NegativePromptTests(unittest.TestCase):
    def test_default_defects_and_explicit_lettering(self):
        normal = image_prompts.negative_prompt('a cat in space').split(', ')
        self.assertIn('blurry', normal)
        self.assertIn('extra fingers', normal)
        self.assertIn('text', normal)
        self.assertNotIn('color', normal)
        for prompt in ('a sign with the words HELLO', 'a poster with bold lettering'):
            self.assertNotIn('text', image_prompts.negative_prompt(prompt).split(', '))
        self.assertIn('text', image_prompts.negative_prompt('a poster with no text').split(', '))

    def test_coloring_book_and_black_ink_with_color(self):
        words = image_prompts.negative_prompt('a monochrome coloring book cat, no shading').split(', ')
        for word in ('color', 'shading', 'gradients'):
            self.assertIn(word, words)
        words = image_prompts.negative_prompt('black ink outlines with a red heart').split(', ')
        self.assertNotIn('color', words)
        self.assertNotIn('shading', words)

    def test_worker_passes_negatives_and_literal_prompt_without_shell(self):
        process = Mock(returncode=0)
        process.poll.return_value = 0
        def communicate(**kwargs):
            Path(launch.call_args.args[0][-1]).write_bytes(ti.picture())
            return '', ''
        process.communicate.side_effect = communicate
        values = ti.ImagineProcessTests().values()
        with patch.object(imagine.subprocess, 'Popen', return_value=process) as launch:
            imagine.generate('a cat & $(literal)', 'quick', values, seed=42)
        args = launch.call_args.args[0]
        self.assertEqual(args[args.index('--seed')+1], '42')
        self.assertIn('blurry', args[args.index('--negative-prompt')+1])
        self.assertEqual(args[args.index('--prompt')+1], 'a cat & $(literal)')
        self.assertFalse(launch.call_args.kwargs.get('shell', False))
        self.assertFalse(Path(args[-1]).exists())


class HelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_dedicated_instructions_and_clean_result(self):
        with patch.object(engine, 'complete', new=AsyncMock(return_value='Prompt: "A cat on a crescent moon."')) as llm:
            result = await image_prompts.improve('a cat in space')
        self.assertTrue(result.startswith('a cat in space, well-lit subject'))
        self.assertIn('A cat on a crescent moon.', result)
        messages = llm.call_args.args[0]
        self.assertIn('Preserve', messages[0]['content'])
        self.assertIn('Do not turn drawings or cartoons into photos', messages[0]['content'])
        self.assertEqual(messages[1]['content'], 'a cat in space')
        self.assertEqual(llm.call_args.kwargs['max_tokens'], 180)

    async def test_visibility_preserves_outline_and_dark_requests(self):
        with patch.object(engine, 'complete', new=AsyncMock(return_value='A clearly framed cat.')):
            normal = await image_prompts.improve('a cat in space')
            outline = await image_prompts.improve('a line drawing of a cat, no shading')
            dark = await image_prompts.improve('a dark cat silhouette')
        self.assertIn('well-lit subject', normal)
        self.assertIn('clear simple outlines', outline)
        self.assertNotIn('well-lit', outline)
        self.assertNotIn('well-lit', dark)
        self.assertTrue(dark.startswith('a dark cat silhouette'))

    async def test_bad_inputs_and_unusable_outputs(self):
        for prompt in (' ', 'x'*1201):
            with self.assertRaises(image_prompts.PromptError):
                await image_prompts.improve(prompt)
        for answer in ('', 'x'*1201):
            with patch.object(engine, 'complete', new=AsyncMock(return_value=answer)), self.assertRaises(image_prompts.PromptError):
                await image_prompts.improve('cat')

    async def test_rejects_unrequested_monochrome_but_keeps_requested_style(self):
        with patch.object(engine, 'complete', new=AsyncMock(return_value='A monochrome cat, no color.')):
            with self.assertRaisesRegex(image_prompts.PromptError, 'changed the requested style'):
                await image_prompts.improve('a cat in space')
            result = await image_prompts.improve('a monochrome cat in space')
            self.assertIn('monochrome', result)

    async def test_offline_timeout_and_cancellation(self):
        with patch.object(engine, 'complete', new=AsyncMock(side_effect=engine.EngineError('AI is offline'))):
            with self.assertRaisesRegex(image_prompts.PromptError, 'offline'):
                await image_prompts.improve('cat')
        cancelled = asyncio.Event()
        async def slow(*args, **kwargs):
            try:
                await asyncio.sleep(2)
            finally:
                cancelled.set()
        with patch.object(engine, 'complete', side_effect=slow), patch.object(image_prompts, 'HELPER_TIMEOUT', .01):
            with self.assertRaisesRegex(image_prompts.PromptError, 'too long'):
                await image_prompts.improve('cat')
        self.assertTrue(cancelled.is_set())


class HelperApiTests(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(ti.ImagineApiTests.setUpClass.__func__)
    tearDownClass = classmethod(ti.ImagineApiTests.tearDownClass.__func__)

    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')

    async def asyncTearDown(self):
        await image_jobs.shutdown()
        await self.client.aclose()

    async def test_helper_does_not_generate_or_save_and_returns_preview(self):
        before = chats.list_chats()
        with patch.object(engine, 'complete', new=AsyncMock(return_value='A monochrome coloring book cat, no shading.')), \
                patch.object(imagine, 'generate') as generate:
            response = await self.client.post('/api/imagine/prompt', json={'prompt': 'a coloring book cat'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('color', response.json()['negative_prompt'])
        generate.assert_not_called()
        self.assertEqual(chats.list_chats(), before)
        self.assertFalse(imagine._lock.locked())

    async def test_helper_errors_leave_storage_untouched(self):
        before = chats.list_chats()
        for prompt, code in [(' ', 400), ('', 422), ('x'*1201, 422)]:
            self.assertEqual((await self.client.post('/api/imagine/prompt', json={'prompt': prompt})).status_code, code)
        with patch.object(engine, 'complete', new=AsyncMock(side_effect=engine.EngineError('Offline'))):
            self.assertEqual((await self.client.post('/api/imagine/prompt', json={'prompt': 'cat'})).status_code, 503)
        self.assertEqual(chats.list_chats(), before)

    async def test_generation_uses_reviewed_prompt_seed_and_saves_avoid_words(self):
        with patch.object(imagine, 'configuration', return_value={}), \
                patch.object(imagine, 'generate', return_value=ti.picture()) as generate, patch.object(notify, 'show'):
            response = await self.client.post('/api/imagine', json={'prompt': 'my edited cat idea', 'seed': 42, 'preset': 'quick'})
            self.assertEqual(response.status_code, 202, response.text)
            await asyncio.gather(*list(image_jobs._jobs))
            await asyncio.sleep(0)
        self.assertEqual(generate.call_args.args[0], 'my edited cat idea')
        self.assertEqual(generate.call_args.kwargs['seed'], 42)
        saved = chats.get(response.json()['chat_id'])['messages']
        self.assertIn('Avoid: blurry', saved[0]['content'])
        self.assertEqual(saved[-1]['kind'], 'image')
        for seed in (True, -2, 2147483648, '42'):
            r = await self.client.post('/api/imagine', json={'prompt': 'cat', 'seed': seed})
            self.assertEqual(r.status_code, 422)


if __name__ == '__main__':
    unittest.main()
