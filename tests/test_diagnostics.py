"""Phase 36: temporary storage and fake HTTP services only; never runs the app or a model."""
import asyncio
from contextlib import closing
import json
import logging
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import chats, config, diagnostics, settings


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patchers = [
            patch.object(config, 'ROOT', self.root),
            patch.object(config, 'DATA_DIR', self.root),
            patch.object(settings, 'FILE', self.root/'settings.json'),
            patch.object(chats, 'DB_PATH', self.root/'beyond.sqlite3'),
        ]
        for item in self.patchers:
            item.start()
        # Only the fields diagnostics reads, with no application startup hooks.
        with closing(sqlite3.connect(chats.DB_PATH)) as db, db:
            db.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY, role TEXT, kind TEXT, created_at TEXT, stats TEXT)')

    def tearDown(self):
        diagnostics.shutdown()
        for item in reversed(self.patchers):
            item.stop()
        self.temp.cleanup()

    def add(self, stats, kind='chat'):
        with closing(sqlite3.connect(chats.DB_PATH)) as db, db:
            db.execute("INSERT INTO messages(role,kind,created_at,stats) VALUES ('assistant',?,'2026-10-20T20:00:00+00:00',?)",
                       (kind, stats if isinstance(stats,str) else json.dumps(stats)))

    def test_speed_history_is_bounded_handles_bad_stats_and_groups_models(self):
        self.add({'model':'A','tokens':40,'seconds':9,'speed':8})
        self.add({'model':'A','tokens':50,'seconds':10,'speed':10},kind='retried')
        self.add({'model':'B','tokens':10,'seconds':3,'speed':4})
        self.add('not json')
        self.add('[]')
        self.add({'tokens':2,'seconds':1,'speed':float('nan')})
        self.add({'tokens':2,'seconds':-1,'speed':4})
        self.add({'model':'Hidden command','tokens':1,'seconds':1,'speed':1},kind='command')
        data=diagnostics.speed_history(50)
        self.assertEqual([r['model'] for r in data['items']],['B','A','A'])
        self.assertEqual(data['models'][1],{'model':'A','replies':2,'average_speed':9})
        self.assertEqual(len(diagnostics.speed_history(1)['items']),1)
        self.assertNotIn('content',str(data))
        chats.DB_PATH.unlink()
        self.assertEqual(diagnostics.speed_history()['items'],[])

    def test_error_history_survives_reopen_is_bounded_and_excludes_raw_log_data(self):
        with patch.object(diagnostics,'MAX_ERRORS',5):
            for index in range(8):
                diagnostics.record_error('test',f'Fixed diagnostic {index}')
        self.assertEqual(len(diagnostics.errors(200)),5)
        self.assertEqual(diagnostics.errors(200)[-1]['summary'],'Fixed diagnostic 3')
        record=logging.LogRecord('root',logging.ERROR,str(self.root/'app/server.py'),1,
                                 'Private prompt %s',('password-SECRET',),None)
        diagnostics.ErrorHistory().emit(record)
        item=diagnostics.errors(1)[0]
        self.assertEqual(item['source'],'server')
        self.assertNotIn('SECRET',json.dumps(item))
        self.assertNotIn('Private prompt',json.dumps(item))
        outside=logging.LogRecord('third-party',logging.ERROR,str(self.root.parent/'other.py'),1,'x',(),None)
        diagnostics.ErrorHistory().emit(outside)
        self.assertEqual(diagnostics.errors(1)[0],item)
        diagnostics.initialize()
        self.assertEqual(diagnostics.errors(1)[0],item)

    def test_service_targets_are_only_configured_ports_and_do_not_start_models(self):
        values={**config.DEFAULTS}
        targets=diagnostics.service_targets({'port':43001,'https_port':43002},values,
                                            {'state':'ok','port':43003,'model':'A'})
        self.assertEqual([t['port'] for t in targets],[43001,43002,43003])
        targets=diagnostics.service_targets({'port':43001},values,{'state':'off','port':None})
        self.assertEqual(targets[1]['state'],'disabled')
        self.assertEqual(targets[2]['state'],'off')
        external={**values,'ai_mode':'server','ai_server_url':'http://user:private@localhost:43004/v1'}
        targets=diagnostics.service_targets({'port':43001},external,{'state':'external'})
        self.assertEqual(targets[-1]['port'],43004)
        self.assertEqual(targets[-1]['host'],'localhost')
        self.assertTrue(targets[-1]['url'].endswith('/v1/models'))

    def test_probes_validate_service_identity_and_report_failures_without_secrets(self):
        real_client=httpx.AsyncClient
        seen=[]
        def client(**kwargs):
            def reply(request):
                seen.append(request.url.path)
                if request.url.path=='/wrong':
                    return httpx.Response(200,json={'name':'Another app','status':'ok'})
                if request.url.path=='/down':
                    raise httpx.ConnectError('SECRET address info',request=request)
                return httpx.Response(200,json={'name':'BEYOND','status':'ok'})
            return real_client(transport=httpx.MockTransport(reply),**kwargs)
        async def run():
            return [await diagnostics.probe({'name':'Web','host':'127.0.0.1','port':43001,
                    'url':'http://127.0.0.1:43001'+path,'expected':'beyond'}) for path in ('/api/health','/wrong','/down')]
        with patch.object(diagnostics.httpx,'AsyncClient',side_effect=client):
            results=asyncio.run(run())
        self.assertEqual([r['state'] for r in results],['ok','error','error'])
        self.assertNotIn('SECRET',json.dumps(results))
        self.assertNotIn('url',results[0])
        self.assertEqual(seen,['/api/health','/wrong','/down'])

    def test_selftest_is_read_only_handles_optional_features_and_busy_lock(self):
        before=chats.DB_PATH.read_bytes()
        state={'system':{'disk_free':5*1024**3,'memory_available':5*1024**3},'services':[
            {'name':'Web','state':'ok','detail':'Responding.'},
            {'name':'AI','state':'off','detail':'No model loaded.'}]}
        with patch.object(diagnostics,'snapshot',new=AsyncMock(return_value=state)):
            result=asyncio.run(diagnostics.self_test())
        self.assertFalse(result['busy'])
        self.assertEqual(result['counts']['error'],0)
        self.assertEqual(next(c for c in result['checks'] if c['name']=='AI')['state'],'skipped')
        self.assertEqual(chats.DB_PATH.read_bytes(),before)
        self.assertFalse(settings.FILE.exists())
        self.assertFalse(diagnostics.error_file().exists())
        diagnostics._test_lock.acquire()
        try:
            self.assertTrue(asyncio.run(diagnostics.self_test())['busy'])
        finally:
            diagnostics._test_lock.release()
        settings.FILE.write_text('{broken JSON',encoding='utf-8')
        checks=diagnostics.storage_checks()
        self.assertEqual(checks[0]['state'],'error')

    def test_snapshot_never_runs_inference_and_checks_only_its_bound_services(self):
        from app import builtin_engine, engine
        async def reply(target):
            if 'url' not in target:
                return target
            return {'name':target['name'],'host':target['host'],'port':target['port'],'state':'ok','detail':'Responding.'}
        with patch.object(builtin_engine,'status',return_value={'state':'off','port':None,'model':'A'}), \
             patch.object(builtin_engine,'start',side_effect=AssertionError('No model load')), \
             patch.object(engine,'complete',side_effect=AssertionError('No inference')), \
             patch.object(diagnostics,'probe',new=AsyncMock(side_effect=reply)) as probe:
            result=asyncio.run(diagnostics.snapshot({'port':43001,'https_port':None}))
        self.assertEqual(result['ai']['state'],'off')
        self.assertEqual([call.args[0]['port'] for call in probe.await_args_list],[43001,None,None])
        self.assertIn('memory_available',result['system'])
        self.assertIn('disk_free',result['system'])

    def test_optional_missing_files_are_warnings_and_logging_handler_is_removed(self):
        settings.FILE.write_text(json.dumps({'vision_enabled':True}),encoding='utf-8')
        checks=diagnostics.storage_checks()
        self.assertEqual(next(c for c in checks if c['name']=='Photo understanding')['state'],'warning')
        diagnostics.configure({'port':43001})
        handler=diagnostics._handler
        diagnostics.configure({'port':43001})
        self.assertEqual(logging.getLogger().handlers.count(handler),1)
        diagnostics.shutdown()
        self.assertNotIn(handler,logging.getLogger().handlers)

    def test_routes_validate_limits_and_serve_page_without_app_startup(self):
        app=FastAPI()
        app.state.running={'port':43001}
        app.include_router(diagnostics.router)
        with TestClient(app) as client:
            self.assertEqual(client.get('/status').status_code,200)
            self.assertEqual(client.get('/api/status/speed?limit=51').status_code,422)
            self.assertEqual(client.get('/api/status/errors?limit=-1').status_code,422)
            self.assertEqual(client.get('/api/status/errors').json(),{'items':[]})
            with patch.object(diagnostics,'snapshot',new=AsyncMock(return_value={'version':'test'})) as snapshot:
                self.assertEqual(client.get('/api/status').json(),{'version':'test'})
                snapshot.assert_awaited_once_with({'port':43001})
            with patch.object(diagnostics,'self_test',new=AsyncMock(return_value={'busy':True,'summary':'Busy'})):
                self.assertEqual(client.post('/api/status/selftest').status_code,409)

    def test_help_and_commands_are_wired_without_generating_ai(self):
        from app import commands
        self.assertIn('/speed',commands.run('/help').text)
        self.assertIn('/selftest',commands.run('/help').text)
        self.assertIn('No saved reply timings',commands.run('/speed').text)
        self.assertIn('Use /speed',commands.run('/speed 999').text)
        report={'busy':False,'summary':'All checks passed.','checks':[{'name':'Web','state':'ok','detail':'Responding.'}]}
        with patch.object(diagnostics,'self_test',new=AsyncMock(return_value=report)):
            self.assertIn('OK · Web',commands.run('/selftest').text)
        self.assertIn('no arguments',commands.run('/selftest restart').text)


if __name__=='__main__':
    unittest.main()
