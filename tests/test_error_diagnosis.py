"""Temporary data and fake AI only. No model, app lifespan or real failure is started."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import builtin_engine, config, diagnostics, engine, error_diagnosis, settings


class DiagnosisTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        target = Path(self.temp.name)
        for obj, name, value in ((config,'DATA_DIR',target),(settings,'FILE',target/'settings.json')):
            p = patch.object(obj,name,value); p.start(); self.addCleanup(p.stop)
        self.state = {'at':'2026-10-21T01:00:00+00:00',
            'ai':{'state':'ok','busy':False,'model':'PRIVATE model name'},
            'system':{'cpu_percent':12,'memory_percent':50,'memory_available':5*1024**3,'disk_free':50*1024**3},
            'services':[{'name':'Built-in AI','state':'ok','port':43003,'detail':'Responding.',
                         'host':'PRIVATE hostname','url':'PRIVATE URL'}]}
        self.snapshot = patch.object(diagnostics,'snapshot',new=AsyncMock(return_value=self.state))
        self.snapshot.start(); self.addCleanup(self.snapshot.stop)
        p = patch.object(diagnostics,'storage_checks',return_value=[])
        p.start(); self.addCleanup(p.stop)
        p = patch.object(builtin_engine,'busy',return_value=False)
        self.busy = p.start(); self.addCleanup(p.stop)

    def entry(self):
        diagnostics.record_error('chat','An AI reply failed.')
        return diagnostics.errors(1)[0]['id']

    async def test_ai_receives_only_diagnostic_evidence_and_no_private_settings(self):
        settings.FILE.write_text(json.dumps({'custom_prompt':'PRIVATE prompt',
            'ai_server_url':'http://user:PRIVATE@host:1234','engine_model':'PRIVATE path.gguf'}),encoding='utf-8')
        before = settings.FILE.read_bytes()
        with patch.object(engine,'complete',new=AsyncMock(return_value='Likely cause: a temporary interruption.')) as complete:
            result = await error_diagnosis.diagnose(self.entry())
        self.assertEqual(result['mode'],'ai')
        sent = json.dumps(complete.call_args.args[0])
        self.assertNotIn('PRIVATE',sent)
        self.assertIn('current_evidence',sent)
        self.assertIn('not when this error occurred',result['limitation'])
        self.assertEqual(settings.FILE.read_bytes(),before)

    async def test_offline_and_busy_use_basic_advice_without_asking_ai(self):
        with patch.object(engine,'complete',new=AsyncMock()) as complete:
            self.state['ai']['state']='error'
            result = await error_diagnosis.diagnose(self.entry())
            self.assertEqual(result['mode'],'basic')
            self.assertIn('not ready',result['note'])
            self.state['ai']['state']='ok'
            self.busy.return_value=True
            result = await error_diagnosis.diagnose(self.entry())
            self.assertIn('in use',result['note'])
            complete.assert_not_awaited()

    async def test_ai_failure_and_timeout_fall_back_and_release_lock(self):
        for failure in (engine.EngineError('PRIVATE failure text'),asyncio.TimeoutError()):
            with patch.object(engine,'complete',new=AsyncMock(side_effect=failure)):
                result = await error_diagnosis.diagnose(self.entry())
            self.assertEqual(result['mode'],'basic')
            self.assertNotIn('PRIVATE',json.dumps(result))
            self.assertFalse(error_diagnosis._lock.locked())

    async def test_missing_and_concurrent_diagnoses_are_rejected(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as missing:
            await error_diagnosis.diagnose(100)
        self.assertEqual(missing.exception.status_code,404)
        entry = self.entry()
        error_diagnosis._lock.acquire()
        try:
            with self.assertRaises(HTTPException) as busy:
                await error_diagnosis.diagnose(entry)
            self.assertEqual(busy.exception.status_code,409)
        finally:
            error_diagnosis._lock.release()

    async def test_simulated_errors_are_labelled_deduplicated_and_clear_keeps_real_history(self):
        real = self.entry()
        error_diagnosis.test_error()
        error_diagnosis.test_error()
        rows = diagnostics.errors()
        self.assertEqual(len(rows),2)
        simulated = next(r for r in rows if r['source']==error_diagnosis.TEST_SOURCE)
        with patch.object(engine,'complete',new=AsyncMock(return_value='This is a simulated timeout.')) as complete:
            result = await error_diagnosis.diagnose(simulated['id'])
        self.assertTrue(result['simulated'])
        self.assertIn('No repair',result['suggestions'][0])
        self.assertTrue(json.loads(complete.call_args.args[0][1]['content'])['simulated'])
        error_diagnosis.test_error(clear=True)
        self.assertEqual([r['id'] for r in diagnostics.errors()],[real])

    async def test_low_memory_warns_in_selftest_and_alongside_ai_even_for_simulated_error(self):
        self.assertEqual(diagnostics.memory_check({'memory_available':1024**3})['state'],'ok')
        self.assertEqual(diagnostics.memory_check({'memory_available':1024**3-1})['state'],'warning')
        self.state['system']['memory_available']=int(0.6*1024**3)
        report=await diagnostics.self_test()
        self.assertGreater(report['counts']['warning'],0)
        self.assertEqual(report['summary'],'Review the warnings.')
        error_diagnosis.test_error()
        entry=diagnostics.errors(1)[0]
        with patch.object(engine,'complete',new=AsyncMock(return_value='This is a fake error.')) as complete:
            result=await error_diagnosis.diagnose(entry['id'])
        self.assertTrue(result['simulated'])
        self.assertEqual(result['mode'],'ai')
        self.assertIn('Low memory: 0.6 GiB',result['warnings'][0])
        sent=json.loads(complete.call_args.args[0][1]['content'])
        check=next(c for c in sent['current_evidence']['checks'] if c['name']=='Available memory')
        self.assertEqual(check['state'],'warning')
        self.assertIn('Close unused apps',result['suggestions'][-1])

    async def test_routes_validate_ids_and_manage_only_test_errors(self):
        app = FastAPI(); app.state.running = {}; app.include_router(diagnostics.router)
        real = self.entry()
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/status/errors/0/diagnose').status_code,422)
            self.assertEqual(client.post('/api/status/errors/999/diagnose').status_code,404)
            self.assertEqual(client.post('/api/status/errors/test').status_code,200)
            self.assertEqual(len(diagnostics.errors()),2)
            response=client.delete('/api/status/errors/test')
            self.assertEqual([r['id'] for r in response.json()['items']],[real])
            with patch.object(engine,'complete',new=AsyncMock(return_value='Explanation.')):
                self.assertEqual(client.post(f'/api/status/errors/{real}/diagnose').json()['mode'],'ai')
