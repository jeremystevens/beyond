import unittest
from unittest.mock import patch, AsyncMock
from app import engine, host_status, settings

class HostStatusTests(unittest.TestCase):
    def test_snapshot_works_when_ai_is_unreachable_and_does_not_infer(self):
        system = dict(cpu_percent=3, memory_percent=92, memory_total=16*1024**3,
                      memory_available=1024**3, disk_percent=50, disk_free=20*1024**3)
        with patch.object(host_status.diagnostics, 'system_status', return_value=system), \
             patch.object(engine, 'status', new=AsyncMock(return_value={'state':'unreachable'})), \
             patch.object(host_status, 'gpu_status', return_value='GPU: live metrics unavailable.'), \
             patch.object(engine, 'complete') as infer:
            text = host_status.report()
        for expected in ['CPU: 3%', 'RAM: 92%', '20.0 GiB free', 'System uptime:', 'unreachable', 'Model: not confirmed']:
            self.assertIn(expected, text)
        infer.assert_not_called()

    def test_gpu_timeout_is_optional(self):
        import subprocess
        with patch.object(host_status.shutil, 'which', return_value='nvidia-smi'), \
             patch.object(host_status.subprocess, 'run', side_effect=subprocess.TimeoutExpired('nvidia-smi',2)):
            self.assertIn('unavailable',host_status.gpu_status())

    def test_builtin_switch_never_claims_loading_model_is_loaded(self):
        with patch.object(engine.builtin_engine, 'status', return_value={'state':'starting','model':'new.gguf'}), \
             patch.object(settings, 'load', return_value={'ai_mode':'builtin'}):
            self.assertIn('No model is confirmed loaded', engine.model_context())
        with patch.object(engine.builtin_engine, 'status', return_value={'state':'ok','model':'new.gguf'}), \
             patch.object(settings, 'load', return_value={'ai_mode':'builtin'}):
            self.assertIn('Currently loaded model: new.gguf', engine.model_context())

    def test_server_observation_expires_and_settings_changes_invalidate(self):
        values={'ai_mode':'server','ai_server_url':'http://localhost:1234','ai_model':''}
        with patch.object(settings, 'load', return_value=values), patch.object(engine.time, 'monotonic', return_value=100), \
             patch.object(engine, '_observed_model', (engine._model_key(values),99,'actual-model')):
            self.assertIn('actual-model',engine.model_context())
            values['ai_server_url']='http://localhost:5678'
            self.assertIn('not confirmed',engine.model_context())
        with patch.object(settings, 'load', return_value=values), patch.object(engine.time, 'monotonic', return_value=200), \
             patch.object(engine, '_observed_model', (engine._model_key(values),99,'old-model')):
            self.assertNotIn('old-model',engine.model_context())

    def test_natural_model_questions_do_not_capture_other_requests(self):
        for text in ['What model are you running?', 'Which model is currently loaded?',
                     'Can you tell me what model are you using?', 'What LLM are you running?']:
            self.assertTrue(host_status.is_model_question(text), text)
        for text in ['Write a Python model class', 'What model should I download?',
                     'What model are you running? Also delete my chats.']:
            self.assertFalse(host_status.is_model_question(text), text)

    def test_model_report_uses_live_state_without_inference(self):
        with patch.object(engine, 'status', new=AsyncMock(return_value={
                'state':'ok','builtin':True,'model':'actual.gguf'})), patch.object(engine,'complete') as infer:
            self.assertEqual(host_status.model_report(), 'Currently loaded model: actual.gguf.')
        infer.assert_not_called()
