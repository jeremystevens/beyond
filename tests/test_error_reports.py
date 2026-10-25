"""Report construction never reads chats/logs, probes services, or invokes an AI."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import builtin_engine, config, diagnostics, engine, error_reports, settings


class ErrorReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.patchers=[patch.object(config,'DATA_DIR',Path(self.temp.name)),
          patch.object(settings,'load',return_value={**config.DEFAULTS,'engine_executable':'PRIVATE PATH',
            'engine_model':'PRIVATE MODEL','ai_server_url':'https://secret:password@private.invalid:1'}),
          patch.object(builtin_engine,'status',return_value={'state':'ok','model':'PRIVATE MODEL','port':12345}),
          patch.object(diagnostics,'system_status',return_value={'logical_cpus':8,'memory_total':16*1024**3,
            'memory_available':2*1024**3,'disk_free':50*1024**3,'app_uptime_seconds':42,
            'private_field':'PRIVATE SYSTEM'})]
        for p in self.patchers:p.start();self.addCleanup(p.stop)
        diagnostics.record_error('chat','PRIVATE raw message, credential and exception text')
        self.id=diagnostics.errors(1)[0]['id']
        app=FastAPI();app.include_router(diagnostics.router);self.client=TestClient(app)
        self.addCleanup(self.client.close)

    def build(self,**notes):
        return self.client.post(f'/api/status/errors/{self.id}/report',json=notes)

    def test_fixed_category_allowlist_and_local_environment(self):
        with patch.object(engine,'complete',side_effect=AssertionError('No AI')), \
             patch.object(diagnostics,'snapshot',side_effect=AssertionError('No probes')), \
             patch('app.chats.connect',side_effect=AssertionError('No chat reads')):
            response=self.build(happened='The answer stopped.',expected='A complete reply.',steps='Send hello.',tried='Retry.')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json();text=data['text']
        self.assertIn('An AI reply failed.',text);self.assertIn('What I tried\n',text)
        self.assertIn('2.0 GiB',text);self.assertIn('The answer stopped.',text)
        self.assertNotIn('PRIVATE',text);self.assertNotIn('private.invalid',text)
        self.assertNotIn('12345',text);self.assertFalse(data['simulated'])
        self.assertEqual(data['filename'],f'beyond-error-report-{self.id}.txt')
        self.assertEqual(diagnostics.errors(1)[0]['summary'],'PRIVATE raw message, credential and exception text')

    def test_environment_can_be_omitted_without_readings_or_settings(self):
        with patch.object(settings,'load',side_effect=AssertionError('No settings')), \
             patch.object(diagnostics,'system_status',side_effect=AssertionError('No readings')):
            text=self.build(include_environment=False).json()['text']
        self.assertNotIn('Current app/system information',text)
        self.assertIn('BEYOND release version:',text)

    def test_user_notes_common_sensitive_patterns_are_redacted(self):
        notes='''password="two secret words"
api_key=PRIVATEKEY
Authorization: Bearer VERYPRIVATE
Cookie: session=COOKIETOKEN
https://user:pass@my-private-host.invalid/api?token=secret
someone@example.com
C:\\Users\\Jeremy\\private.txt
/home/jeremy/private.txt
127.0.0.1:7770
sk-abcdefghijklmnopqrst
Safe reproduction step.'''
        response=self.build(happened=notes)
        text=response.json()['text']
        for private in ['two secret words','PRIVATEKEY','VERYPRIVATE','COOKIETOKEN','my-private-host','someone@example.com',
                        'Jeremy','/home/jeremy','127.0.0.1','sk-abcdefghijklmnopqrst']:
            self.assertNotIn(private,text)
        self.assertIn('Safe reproduction step.',text)
        self.assertIn('best effort',text)

    def test_unrecognized_category_and_invalid_timestamp_are_not_exported(self):
        diagnostics.record_error('PRIVATE SOURCE','PRIVATE SUMMARY')
        with diagnostics.closing(diagnostics.sqlite3.connect(diagnostics.error_file())) as db,db:
            db.execute('UPDATE errors SET created_at=?',('PRIVATE TIME',))
        self.id=diagnostics.errors(1)[0]['id']
        text=self.build().json()['text']
        self.assertNotIn('PRIVATE',text);self.assertIn('Error recorded: Unknown',text)
        self.assertIn('Category: App operation',text)

    def test_simulated_entry_is_unmistakable(self):
        diagnostics.record_error('Diagnostic test','PRIVATE')
        self.id=diagnostics.errors(1)[0]['id']
        data=self.build().json()
        self.assertTrue(data['simulated']);self.assertIn('SIMULATED TEST',data['text'])
        self.assertIn('No real service failed.',data['text'])

    def test_missing_or_expired_error_returns_404(self):
        self.id=99999;self.assertEqual(self.build().status_code,404)

    def test_request_validation(self):
        for notes in [{'happened':'x'*2501},{'include_logs':True},{'include_environment':'yes'}]:
            with self.subTest(notes=next(iter(notes))):self.assertEqual(self.build(**notes).status_code,422)
        self.id=0;self.assertEqual(self.build().status_code,422)

    def test_resources_unavailable_still_returns_a_usable_report(self):
        with patch.object(diagnostics,'system_status',side_effect=OSError('PRIVATE filesystem failure')):
            text=self.build().json()['text']
        self.assertIn('resource readings: unavailable',text);self.assertNotIn('PRIVATE',text)

    def test_empty_notes_and_literal_markup(self):
        text=self.build(happened='<script>test only</script>').json()['text']
        self.assertIn('<script>test only</script>',text)
        self.assertIn('Not provided.',text)

    def test_report_does_not_write_files_or_change_history(self):
        before=list(Path(self.temp.name).iterdir());history=diagnostics.errors()
        self.build();self.build()
        self.assertEqual(list(Path(self.temp.name).iterdir()),before)
        self.assertEqual(diagnostics.errors(),history)
