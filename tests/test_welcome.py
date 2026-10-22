"""Phase 40: isolated first-run state and fixed-prompt checks; no actual AI inference."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app import builtin_engine, config, engine, settings, welcome


class WelcomeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # App imports initialize stores; keep even import-time work away from owner data.
        with tempfile.TemporaryDirectory(prefix="beyond welcome import ") as folder:
            with patch.object(config, "DATA_DIR", Path(folder)), \
                 patch.object(settings, "FILE", Path(folder)/"settings.json"):
                from app.server import app
                cls.app = app

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="BEYOND welcome spaces ")
        self.root = Path(self.temp.name)
        self.data = patch.object(config, "DATA_DIR", self.root)
        self.file = patch.object(settings, "FILE", self.root/"settings.json")
        self.data.start()
        self.file.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(
            app=self.app, client=("127.0.0.1", 50000)), base_url="http://beyond.test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.file.stop()
        self.data.stop()
        self.temp.cleanup()

    def configure(self, server=False):
        settings.save({"ai_mode": "server" if server else "builtin",
                       "ai_server_url": "http://127.0.0.1:12345" if server else "",
                       "engine_model": str(self.root/"model.gguf"),
                       "engine_executable": str(self.root/"llama-server.exe"),
                       "engine_context": 2048, "require_sign_in": False})

    async def successful_test(self):
        with patch.object(engine, "status", AsyncMock(return_value={"state":"ok"})), \
             patch.object(engine, "complete", AsyncMock(return_value="Hello!")):
            return await self.client.post("/api/welcome/test")

    async def test_fresh_start_offers_guide_and_page(self):
        response = await self.client.get("/api/welcome")
        self.assertTrue(response.json()["offer"])
        page = await self.client.get("/welcome")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Make yourself at home", page.text)
        self.assertIn("welcome-check.js", (await self.client.get("/")).text)

    async def test_existing_configuration_is_not_forced_through_welcome(self):
        self.configure(server=True)
        before = settings.FILE.read_bytes()
        self.assertFalse((await self.client.get("/api/welcome")).json()["offer"])
        self.assertEqual(settings.FILE.read_bytes(), before)

    async def test_new_installer_result_offers_welcome_even_when_configured(self):
        self.configure()
        path = self.root/"setup/result.json"
        path.parent.mkdir()
        path.write_text('{"welcome_pending":true}')
        self.assertTrue(welcome.should_offer())

    async def test_skip_persists_without_changing_settings(self):
        before = settings.load()
        self.assertEqual((await self.client.post("/api/welcome/finish",json={"skip":True})).status_code,200)
        self.assertFalse(welcome.should_offer())
        self.assertEqual(before,settings.load())

    async def test_finish_requires_success_for_current_configuration(self):
        self.configure()
        self.assertEqual((await self.client.post("/api/welcome/finish",json={})).status_code,409)
        self.assertEqual((await self.successful_test()).status_code,200)
        settings.save({"engine_context":1024})
        self.assertEqual((await self.client.post("/api/welcome/finish",json={})).status_code,409)

    async def test_success_has_fixed_prompt_and_no_chat_or_memory_context(self):
        self.configure()
        with patch.object(engine,"status",AsyncMock(return_value={"state":"ready"})), \
             patch.object(engine,"complete",AsyncMock(return_value="Hello!")) as complete:
            response=await self.client.post("/api/welcome/test")
        self.assertEqual(response.json(),{"ok":True,"reply":"Hello!"})
        self.assertEqual(complete.call_args.args[0],
                         [{"role":"user","content":"Say hello in one short sentence."}])
        self.assertEqual(complete.call_args.kwargs,{"max_tokens":48,"temperature":0})
        self.assertTrue(welcome.view()["tested"])
        self.assertEqual((await self.client.post("/api/welcome/finish",json={})).status_code,200)
        self.assertFalse(welcome.should_offer())

    async def test_blank_reply_never_passes(self):
        self.configure()
        with patch.object(engine,"status",AsyncMock(return_value={"state":"ok"})), \
             patch.object(engine,"complete",AsyncMock(return_value="  ")):
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code,502)
        self.assertFalse(welcome.view()["tested"])

    async def test_ai_failure_and_retry(self):
        self.configure()
        with patch.object(engine,"status",AsyncMock(return_value={"state":"ok"})), \
             patch.object(engine,"complete",AsyncMock(side_effect=engine.EngineError("Fixture disconnected"))):
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code,502)
        self.assertEqual((await self.successful_test()).status_code,200)

    async def test_model_loading_does_not_start_test(self):
        self.configure()
        with patch.object(engine,"status",AsyncMock(return_value={"state":"starting"})), \
             patch.object(engine,"complete",AsyncMock()) as complete:
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code,409)
            complete.assert_not_called()

    async def test_timeout_releases_welcome_for_retry(self):
        self.configure()
        async def slow(*args,**kwargs):
            await asyncio.sleep(1)
        with patch.object(engine,"status",AsyncMock(return_value={"state":"ok"})), \
             patch.object(engine,"complete",side_effect=slow), patch.object(welcome,"TEST_TIMEOUT",.01):
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code,504)
        self.assertEqual((await self.successful_test()).status_code,200)

    async def test_settings_change_during_test_never_passes(self):
        self.configure()
        async def changing(*args,**kwargs):
            settings.save({"engine_threads":3})
            return "Hello!"
        with patch.object(engine,"status",AsyncMock(return_value={"state":"ok"})), \
             patch.object(engine,"complete",side_effect=changing):
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code,409)
        self.assertFalse(welcome.view()["tested"])

    async def test_presets_are_cpu_only_and_preserve_model_and_personal_preferences(self):
        self.configure()
        settings.save({"persona":"funny","allow_network":True})
        before=settings.load()
        response=await self.client.post("/api/welcome/preset",json={"preset":"light"})
        self.assertEqual(response.status_code,200)
        after=settings.load()
        self.assertEqual(after["engine_context"],1024)
        self.assertLessEqual(after["engine_threads"],4)
        for key in ("engine_model","engine_executable","ai_mode","allow_network","persona"):
            self.assertEqual(before[key],after[key])
        self.assertFalse(response.json()["gpu_supported"])

    async def test_keep_preserves_external_server(self):
        self.configure(server=True)
        before=settings.FILE.read_bytes()
        self.assertEqual((await self.client.post("/api/welcome/preset",json={"preset":"keep"})).status_code,200)
        self.assertEqual((await self.client.post("/api/welcome/preset",json={"preset":"light"})).status_code,409)
        self.assertEqual(settings.FILE.read_bytes(),before)

    async def test_busy_ai_is_not_reconfigured_or_tested(self):
        self.configure()
        with patch.object(builtin_engine,"busy",return_value=True), \
             patch.object(engine,"complete",AsyncMock()) as complete:
            self.assertEqual((await self.client.post("/api/welcome/preset",json={"preset":"light"})).status_code,409)
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code,409)
            complete.assert_not_called()

    async def test_parallel_operations_are_rejected(self):
        self.configure()
        welcome._operation.acquire()
        try:
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code,409)
            self.assertEqual((await self.client.post("/api/welcome/preset",json={"preset":"keep"})).status_code,409)
            self.assertEqual((await self.client.post("/api/welcome/finish",json={"skip":True})).status_code,409)
        finally:
            welcome._operation.release()

    async def test_other_device_cannot_manage_setup(self):
        settings.save({"require_sign_in":False})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(
                app=self.app, client=("192.168.1.50",50000)),base_url="http://beyond.test") as phone:
            self.assertEqual((await phone.get("/api/welcome")).json(),
                             {"can_manage":False,"offer":False})
            for route, body in (("preset",{"preset":"keep"}),("test",{}),("finish",{"skip":True})):
                self.assertEqual((await phone.post("/api/welcome/"+route,json=body)).status_code,403)

    async def test_old_test_expires_and_malformed_state_is_recoverable(self):
        self.configure()
        welcome._file().write_text("broken")
        self.assertFalse(welcome.view()["tested"])
        welcome._save({"tested_configuration":welcome.signature(settings.load()),"tested_at":0})
        self.assertFalse(welcome.view()["tested"])

    async def test_failed_retest_invalidates_prior_success(self):
        self.configure()
        self.assertEqual((await self.successful_test()).status_code, 200)
        with patch.object(engine, "status", AsyncMock(return_value={"state": "starting"})):
            self.assertEqual((await self.client.post("/api/welcome/test")).status_code, 409)
        self.assertFalse(welcome.view()["tested"])
        self.assertEqual((await self.client.post("/api/welcome/finish", json={})).status_code, 409)

    async def test_pending_guide_survives_installer_rerun(self):
        self.configure()
        welcome._save({"status":"pending"})
        path = self.root/"setup/result.json"
        path.parent.mkdir()
        path.write_text('{"welcome_pending":false}')
        self.assertTrue(welcome.should_offer())

    async def test_invalid_preset_is_rejected(self):
        response=await self.client.post("/api/welcome/preset",json={"preset":"gpu"})
        self.assertEqual(response.status_code,422)


if __name__=="__main__":
    unittest.main()
