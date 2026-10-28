import unittest
from unittest.mock import patch, AsyncMock
from app import break_down, engine

class BreakdownTests(unittest.IsolatedAsyncioTestCase):
    def test_plan_bounds(self):
        self.assertEqual(break_down.parse_steps('["Outline", "Draft"]'), ['Outline', 'Draft'])
        for value in ['[]', '{}', '["a","b","c","d"]', '[""]', 'not json']:
            with self.assertRaises(engine.EngineError):
                break_down.parse_steps(value)

    async def test_steps_then_combination(self):
        calls = []
        async def final(history, background, **kwargs):
            calls.append(history)
            yield 'Combined answer'
        with patch.object(break_down.settings, 'load', return_value={'ai_mode':'external'}), \
             patch.object(engine, 'system_prompt', return_value='System'), \
             patch.object(engine, 'complete', new=AsyncMock(side_effect=['["Outline","Draft"]','Part A','Part B'])) as complete, \
             patch.object(engine, 'chat_stream', side_effect=final):
            pieces = [p async for p in break_down.stream([{'role':'user','content':'Plan a project'}])]
        self.assertEqual(complete.await_count, 3)
        self.assertEqual(pieces[-1], 'Combined answer')
        self.assertEqual(len([p for p in pieces if isinstance(p, break_down.Progress)]), 4)
        self.assertIn('Plan a project', calls[0][-1]['content'])
        self.assertIn('Part A', calls[0][-1]['content'])

    async def test_empty_step_fails_without_combining(self):
        with patch.object(break_down.settings, 'load', return_value={'ai_mode':'external'}), \
             patch.object(engine, 'system_prompt', return_value='System'), \
             patch.object(engine, 'complete', new=AsyncMock(side_effect=['["Draft"]',''])):
            with self.assertRaises(engine.EngineError):
                [p async for p in break_down.stream([{'role':'user','content':'Plan'}])]
