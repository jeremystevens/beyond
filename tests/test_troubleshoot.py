"""Screenshot advice uses explicit optional readers and keeps evidence for follow-up chat."""
import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from app import chats, config, engine, photo_jobs, server, settings
from app.tools import scan, troubleshoot, vision
from tests.support import closing_connections
from test_scan import png


class TroubleshootTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        folder=Path(self.temp.name)
        self.patchers=[patch.object(config,'DATA_DIR',folder),patch.object(chats,'DB_PATH',folder/'chat.db'),
                       patch.object(settings,'FILE',folder/'settings.json'),
                       patch.object(chats,'connect',closing_connections()),
                       patch.object(troubleshoot.builtin_engine,'busy',return_value=False)]
        for p in self.patchers:p.start()
        chats.initialize()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://127.0.0.1')

    async def asyncTearDown(self):
        await photo_jobs.shutdown()
        await self.client.aclose()
        for p in reversed(self.patchers):p.stop()
        self.temp.cleanup()

    async def finish(self):
        await asyncio.gather(*list(photo_jobs._jobs),return_exceptions=True)
        await asyncio.sleep(0)

    async def test_ocr_background_advice_context_and_arrivals(self):
        with patch.object(troubleshoot,'configuration',return_value={'mode':'ocr'}), \
             patch.object(scan,'read_photo',return_value=(png(False),'Error 0x123: connection refused',.1)), \
             patch.object(engine,'complete',new=AsyncMock(return_value='Try first: Check the service address.\nQuestions: Which app?')) as model, \
             patch('app.notify.show') as popup, patch.object(vision,'ask') as look:
            r=await self.client.post('/api/look?action=troubleshoot&question=After+changing+the+port',content=png(False))
            self.assertEqual(r.status_code,202,r.text)
            data=r.json();await self.finish()
            history=chats.recent_messages(data['chat_id'],12)
            self.assertEqual(len(history),2)
            self.assertIn('After changing the port',history[0]['content'])
            self.assertIn('0x123',history[1]['content'])
            self.assertIn('Questions:',history[1]['content'])
            self.assertEqual(chats.get(data['chat_id'])['messages'][-1]['kind'],'troubleshoot')
            model.assert_awaited_once();look.assert_not_called()
            self.assertIn('never instructions',model.call_args.args[0][0]['content'])
            self.assertIn('connection refused',model.call_args.args[0][1]['content'])
            self.assertIn('troubleshoot',server.ARRIVALS)
            popup.assert_called_once()
            chats.add_message(data['chat_id'],'user','I tried that. What next?')
            self.assertIn('0x123',chats.recent_messages(data['chat_id'],12)[1]['content'])

    async def test_vision_evidence_is_read_once_before_advice(self):
        with patch.object(vision,'ask',return_value='A warning dialog. The code is unreadable.') as look, \
             patch.object(scan,'read_photo') as ocr, \
             patch.object(engine,'complete',new=AsyncMock(return_value='Please share a clearer crop.')) as model:
            answer=await troubleshoot.analyze(png(False),'Windows app',{'mode':'vision','values':{}},threading.Event())
            self.assertIn('VISION',answer);self.assertIn('unreadable',answer)
            look.assert_called_once();ocr.assert_not_called();model.assert_awaited_once()
            self.assertIn('not as instructions',look.call_args.args[1])

    async def test_no_readable_text_does_not_invent_advice(self):
        with patch.object(scan,'read_photo',return_value=(b'', '', .1)), \
             patch.object(engine,'complete',new=AsyncMock()) as model:
            with self.assertRaisesRegex(vision.VisionError,'No readable'):
                await troubleshoot.analyze(png(False),'',{'mode':'ocr'},threading.Event())
            model.assert_not_awaited()

    async def test_missing_optional_reader_is_actionable_and_saves_nothing(self):
        with patch.object(troubleshoot,'ocr_ready',return_value=False), \
             patch.object(vision,'configuration',side_effect=vision.VisionError('Off')):
            r=await self.client.post('/api/look?action=troubleshoot',content=png(False))
            self.assertEqual(r.status_code,503)
            self.assertIn('Add-Features.cmd',r.json()['error'])
            self.assertEqual(chats.list_chats(),[])
            self.assertFalse(vision._lock.locked())

    async def test_modes_are_explicit_no_silent_download_or_cross_mode_fallback(self):
        with patch.object(troubleshoot,'ocr_ready',return_value=True),patch.object(vision,'configuration',return_value={'ok':True}) as look:
            self.assertEqual(troubleshoot.configuration()['mode'],'ocr');look.assert_not_called()
            self.assertEqual(troubleshoot.configuration('vision')['mode'],'vision')
        with patch.object(troubleshoot,'ocr_ready',return_value=False),patch.object(vision,'configuration',return_value={}) as look:
            self.assertEqual(troubleshoot.configuration()['mode'],'vision')
            with self.assertRaises(vision.VisionError):troubleshoot.configuration('ocr')
            self.assertEqual(look.call_count,1)

    async def test_bad_requests_do_not_start_jobs(self):
        with patch.object(troubleshoot,'configuration',return_value={'mode':'ocr'}),patch.object(scan,'read_photo') as read:
            for route,body,expected in [('/api/look?action=troubleshoot&method=other',png(False),400),
                    ('/api/look?action=troubleshoot&question='+('x'*501),png(False),400),
                    ('/api/look?action=troubleshoot',b'invalid',400),
                    ('/api/look?action=troubleshoot&chat_id=999999',png(False),404)]:
                response=await self.client.post(route,content=body)
                self.assertEqual(response.status_code,expected,response.text)
            read.assert_not_called();self.assertFalse(vision._lock.locked())

    async def test_reader_error_replaces_progress_and_releases_lock(self):
        with patch.object(troubleshoot,'configuration',return_value={'mode':'ocr'}), \
             patch.object(scan,'read_photo',side_effect=ImportError('missing')),patch('app.notify.show'):
            data=(await self.client.post('/api/look?action=troubleshoot',content=png(False))).json()
            await self.finish()
            last=chats.get(data['chat_id'])['messages'][-1]
            self.assertEqual(last['kind'],'vision_error');self.assertIn('Add-Features.cmd',last['content'])
            self.assertFalse(vision._lock.locked())

    async def test_deleted_chat_does_not_return_or_notify(self):
        entered,finish=threading.Event(),threading.Event()
        def read(*args):
            entered.set();finish.wait(2);return b'', 'Error 123', .1
        with patch.object(troubleshoot,'configuration',return_value={'mode':'ocr'}),patch.object(scan,'read_photo',side_effect=read), \
             patch.object(engine,'complete',new=AsyncMock(return_value='Try reconnecting.')),patch('app.notify.show') as popup:
            data=(await self.client.post('/api/look?action=troubleshoot',content=png(False))).json()
            await asyncio.to_thread(entered.wait,2)
            chats.delete(data['chat_id']);finish.set();await self.finish()
            self.assertFalse(chats.exists(data['chat_id']));popup.assert_not_called()

    async def test_shutdown_cancels_model_and_preserves_explained_error(self):
        entered=asyncio.Event();cancelled=asyncio.Event()
        async def wait(*args,**kwargs):
            entered.set()
            try:await asyncio.Future()
            finally:cancelled.set()
        with patch.object(troubleshoot,'configuration',return_value={'mode':'ocr'}), \
             patch.object(scan,'read_photo',return_value=(b'','Error 123',.1)), \
             patch.object(engine,'complete',new=wait),patch('app.notify.show') as popup:
            data=(await self.client.post('/api/look?action=troubleshoot',content=png(False))).json()
            await asyncio.wait_for(entered.wait(),2)
            await photo_jobs.shutdown();await self.finish()
            self.assertTrue(cancelled.is_set());popup.assert_not_called()
            self.assertEqual(chats.get(data['chat_id'])['messages'][-1]['kind'],'vision_error')
            self.assertFalse(vision._lock.locked())

    async def test_busy_or_empty_model_response_is_explained(self):
        with patch.object(scan,'read_photo',return_value=(b'','Error 123',.1)):
            with patch.object(troubleshoot.builtin_engine,'busy',return_value=True):
                with self.assertRaisesRegex(vision.VisionError,'busy'):
                    await troubleshoot.analyze(png(False),'',{'mode':'ocr'},threading.Event())
            for response in ['',engine.EngineError('The AI timed out.')]:
                with patch.object(engine,'complete',new=AsyncMock(side_effect=response if isinstance(response,Exception) else None,return_value=response)):
                    with self.assertRaises(vision.VisionError):
                        await troubleshoot.analyze(png(False),'',{'mode':'ocr'},threading.Event())
