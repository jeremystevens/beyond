import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit

import httpx
from fastapi import HTTPException
from app import config,diagnostics,error_reports,github_reports

Client=httpx.AsyncClient

class GitHubReportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        p=patch.object(config,'DATA_DIR',Path(self.temp.name));p.start();self.addCleanup(p.stop)
        github_reports._cache.clear()
        diagnostics.record_error('chat','Fixed failure')
        self.id=diagnostics.errors(1)[0]['id']
        self.text='BEYOND report\nWhat happened\n-------------\nThe answer stopped after clicking Send.\n\nSteps to reproduce\n------------------\nSend hello.\n\n'
        self.body=github_reports.ReviewedReport(text=self.text)

    def client(self,handler):
        return patch.object(github_reports.httpx,'AsyncClient',side_effect=lambda **kw:Client(transport=httpx.MockTransport(handler),**kw))

    async def test_exact_reference_matches_without_uploading_report_or_credentials(self):
        requests=[]
        def reply(r):
            requests.append(r)
            return httpx.Response(200,json={'items':[{'number':123,'title':'Reported problem','state':'closed',
                'html_url':'https://github.com/jeremystevens/beyond/issues/123'}]})
        with self.client(reply):result=await github_reports.check(self.id,self.body)
        self.assertTrue(result['checked']);self.assertEqual(result['matches'][0]['state'],'closed')
        self.assertEqual(len(requests),1);self.assertEqual(requests[0].method,'GET')
        self.assertNotIn('The answer stopped',str(requests[0].url));self.assertNotIn('authorization',requests[0].headers)
        query=parse_qs(urlsplit(result['draft_url']).query)
        self.assertIn(self.text.strip(),query['body'][0]);self.assertIn(result['reference'],query['body'][0])

    async def test_category_fallback_and_cache(self):
        calls=[]
        def reply(r):calls.append(r);return httpx.Response(200,json={'items':[]})
        with self.client(reply):
            first=await github_reports.check(self.id,self.body);second=await github_reports.check(self.id,self.body)
        self.assertEqual(len(calls),2);self.assertFalse(first['cached']);self.assertTrue(second['cached'])
        self.assertIn('does not prove',first['note'])

    async def test_rate_limit_offline_and_incomplete_search_are_honest(self):
        for status,data in [(403,{}),(429,{}),(200,{'items':[],'incomplete_results':True})]:
            github_reports._cache.clear()
            with self.client(lambda r:httpx.Response(status,json=data)):
                result=await github_reports.check(self.id,self.body)
            self.assertFalse(result['checked']);self.assertIn('manually',result['note'])
            self.assertTrue(result['draft_url'].startswith('https://github.com/jeremystevens/beyond/issues/new?'))

    async def test_simulated_and_expired_errors_never_contact_github(self):
        diagnostics.record_error('Diagnostic test','Simulated')
        test_id=diagnostics.errors(1)[0]['id']
        with patch.object(github_reports.httpx,'AsyncClient',side_effect=AssertionError('No network')):
            for error_id,code in [(test_id,409),(999999,404)]:
                with self.assertRaises(HTTPException) as caught:await github_reports.check(error_id,self.body)
                self.assertEqual(caught.exception.status_code,code)

    async def test_long_unicode_report_uses_bounded_link_and_paste_instruction(self):
        url,paste=github_reports.draft('AI reply','界'*10000,'BEYOND-report-123')
        self.assertTrue(paste);self.assertLess(len(url),7500);self.assertIn('Paste',parse_qs(urlsplit(url).query)['body'][0])

    async def test_reference_ignores_timestamps_readings_and_local_ids_but_tracks_problem(self):
        key=github_reports.reference('AI reply',self.text)
        self.assertEqual(key,github_reports.reference('AI reply',self.text+'Report generated: tomorrow\nRAM: 5'))
        self.assertNotEqual(key,github_reports.reference('AI reply',self.text.replace('Send hello.','Open the model page.')))
        self.assertNotEqual(key,github_reports.reference('Speech',self.text))

    async def test_public_results_are_bounded_safe_and_issue_only(self):
        items=[{'number':1,'title':'test','html_url':'https://evil.invalid/issues/1'},
               {'number':2,'title':'PR','html_url':'https://github.com/jeremystevens/beyond/issues/2','pull_request':{'url':'x'}}]
        self.assertEqual(github_reports.clean_matches(items,True),[])

    async def test_local_repeated_summaries_are_counted_without_merging_history(self):
        diagnostics.record_error('chat','Fixed failure')
        diagnostics.record_error('chat','Another failure')
        result=error_reports.build(self.id,error_reports.ReportNotes(include_environment=False))
        self.assertEqual(result['occurrences']['count'],2)
        self.assertEqual(len(diagnostics.errors()),3)

    async def test_overlapping_network_check_is_explained(self):
        github_reports._lock.acquire()
        try:
            with self.assertRaises(HTTPException) as caught:await github_reports.check(self.id,self.body)
            self.assertEqual(caught.exception.status_code,409)
        finally:github_reports._lock.release()
