"""Essential model-switch safeguards; temporary files only, no real weights or user settings."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import builtin_engine, config, engine, models, settings


class ModelsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # The real path, as BEYOND stores it: Windows can give the temp folder a short name (C:\Users\RUNNER~1\...).
        self.root = Path(self.temp.name).resolve()
        self.old = config.MODELS_DIR, settings.FILE, builtin_engine._engine
        config.MODELS_DIR, settings.FILE = self.root / 'models', self.root / 'settings.json'
        builtin_engine._engine = builtin_engine._Engine()
        config.MODELS_DIR.mkdir()
        self.a = config.MODELS_DIR / 'first.gguf'
        self.b = config.MODELS_DIR / 'second.gguf'
        self.exe = self.root / 'llama-server.exe'
        for path in (self.a, self.b, self.exe):
            path.write_bytes(b'x')
        settings.save({'engine_executable': str(self.exe), 'engine_model': str(self.a)})
        models.initialize()

    def tearDown(self):
        config.MODELS_DIR, settings.FILE, builtin_engine._engine = self.old
        self.temp.cleanup()

    def ready(self):
        running = builtin_engine._engine
        running.wanted, running.state, running.port = builtin_engine.wanted(settings.load()), 'ready', 50123

    def test_switch_stops_old_routing_and_restores_each_models_settings(self):
        self.ready()
        first = models.model_id(self.a)
        second = models.model_id(self.b)
        models.save_profile(first, {'engine_context': 4096, 'engine_threads': 3})
        models.save_profile(second, {'engine_context': 2048, 'engine_threads': 2, 'engine_thinking': True})
        models.load(second)
        self.assertIsNone(builtin_engine.url())  # never send the next question to the old process
        self.assertEqual(builtin_engine.status()['state'], 'starting')
        with self.assertRaises(engine.EngineError):
            engine._server()
        self.ready()
        self.assertEqual(engine._server()[0], 'http://127.0.0.1:50123')
        self.assertEqual(builtin_engine.model_name(), self.b.name)
        self.assertEqual(settings.load()['engine_context'], 2048)
        models.load(first)
        self.assertEqual((settings.load()['engine_context'], settings.load()['engine_threads']), (4096, 3))
        models.unload()
        self.assertIsNone(builtin_engine.url())
        self.assertIsNone(builtin_engine.wanted(settings.load()))
        self.assertFalse(settings.load()['engine_enabled'])  # persisted, not a temporary stop
        self.assertEqual(settings.load()['engine_model'], str(self.a))
        models.load(second)
        self.assertTrue(settings.load()['engine_enabled'])

    def test_an_answer_cannot_be_interrupted_and_unknown_paths_cannot_be_loaded(self):
        self.ready()
        before = settings.FILE.read_bytes()
        with builtin_engine.using_model():
            for operation in (lambda: models.load(models.model_id(self.b)), models.unload,
                              lambda: models.save_profile(models.model_id(self.a), {'engine_threads': 4})):
                with self.assertRaises(models.ModelError) as caught:
                    operation()
                self.assertEqual(caught.exception.status, 409)
            self.assertEqual(settings.FILE.read_bytes(), before)
        self.assertFalse(builtin_engine.busy())
        with self.assertRaises(models.ModelError):
            models.load('../anything.gguf')
        with self.assertRaises(models.ModelError):
            models.save_profile(models.model_id(self.a), {'engine_executable': 'another.exe'})
        self.assertEqual(settings.FILE.read_bytes(), before)

    def test_unload_interrupts_a_model_while_it_is_loading(self):
        # Fake process only: no real model is loaded or stopped by this check.
        class Process:
            pid = 1
            def poll(self): return None
            def terminate(self): pass
            def wait(self, _timeout): return 0
        async def healthy(_client, _port):
            models.unload()
            return False
        async def run():
            with patch.object(config, 'DATA_DIR', self.root), \
                 patch.object(builtin_engine.subprocess, 'Popen', return_value=Process()), \
                 patch.object(builtin_engine, '_healthy', healthy), \
                 patch.object(builtin_engine.asyncio, 'sleep', new_callable=AsyncMock):
                await builtin_engine.start(settings.load())
            self.assertIsNone(builtin_engine._engine.process)
            self.assertIsNone(builtin_engine.url())
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
