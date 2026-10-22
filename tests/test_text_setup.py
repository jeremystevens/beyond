"""Installer failure/recovery tests. Local HTTP fixtures only; no external downloads."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch, MagicMock
import zipfile

spec = importlib.util.spec_from_file_location("text_setup", Path(__file__).resolve().parents[1] / "installer" / "text_setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="beyond installer ")
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(setup, "ROOT", self.root)
        self.root_patch.start()
        self.output = redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None, None, None)
        self.root_patch.stop()
        self.temp.cleanup()

    def asset(self, payload):
        return {"file": "test.gguf", "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(), "url": ""}

    def test_existing_invalid_final_is_not_overwritten(self):
        path = self.root / "model.gguf"
        path.write_bytes(b"mine")
        with self.assertRaises(setup.InstallError):
            setup.download(self.asset(b"expected"), path)
        self.assertEqual(path.read_bytes(), b"mine")

    def test_complete_corrupt_partial_is_removed_for_retry(self):
        path = self.root / "model.gguf"
        path.with_name(path.name + ".part").write_bytes(b"broken")
        with self.assertRaises(setup.InstallError):
            setup.download(self.asset(b"good!!"), path)
        self.assertFalse(path.with_name(path.name + ".part").exists())

    def run_download(self, ignore_range=False):
        payload = b"GGUF" + b"data" * 1000
        asset = self.asset(payload)
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                start = int(self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0])
                requests.append(start)
                if ignore_range:
                    start = 0
                    self.send_response(200)
                else:
                    self.send_response(206 if start else 200)
                    if start:
                        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, len(payload)-1, len(payload)))
                self.send_header("Content-Length", str(len(payload) - start))
                self.end_headers()
                self.wfile.write(payload[start:])
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        path = self.root / "model.gguf"
        path.with_name(path.name + ".part").write_bytes(payload[:32])
        asset["url"] = "http://127.0.0.1:%d/model" % server.server_port
        try:
            setup.download(asset, path)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(requests, [32])
        self.assertEqual(path.read_bytes(), payload)
        self.assertFalse(path.with_name(path.name + ".part").exists())

    def test_range_resume(self):
        self.run_download()

    def test_server_ignoring_range_restarts_safely(self):
        self.run_download(ignore_range=True)

    def test_archive_traversal_is_rejected(self):
        archive = self.root / "engine.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape.exe", b"bad")
        with self.assertRaises(setup.InstallError):
            setup.extract_engine(archive, self.root / "engine")
        self.assertFalse((self.root / "escape.exe").exists())

    def test_changed_extracted_engine_is_not_overwritten(self):
        archive = self.root / "engine.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("llama-server.exe", b"expected")
            bundle.writestr("ggml.dll", b"library")
        engine = setup.extract_engine(archive, self.root / "engine")
        engine.write_bytes(b"user change")
        with self.assertRaises(setup.InstallError):
            setup.extract_engine(archive, self.root / "engine")
        self.assertEqual(engine.read_bytes(), b"user change")

    def test_memory_retry_rechecks_available_not_total_ram(self):
        with patch.object(setup, "memory", side_effect=[(16*setup.GIB, 100), (16*setup.GIB, 5*setup.GIB)]) as memory, \
             patch.object(setup, "ask", return_value="r"):
            self.assertTrue(setup.need_memory(4*setup.GIB, can_choose_smaller=True))
            self.assertEqual(memory.call_count, 2)

    def test_smaller_model_requires_explicit_choice(self):
        with patch.object(setup, "memory", return_value=(16*setup.GIB, 100)), \
             patch.object(setup, "ask", return_value="s"):
            self.assertFalse(setup.need_memory(4*setup.GIB, can_choose_smaller=True))

    def test_non_memory_engine_failure_does_not_download_fallback(self):
        model = self.root / "model.gguf"
        model.write_bytes(b"GGUF")
        with patch.object(setup, "need_memory"), \
             patch.object(setup, "test_chat", side_effect=setup.InstallError("bad engine")), \
             patch.object(setup, "ask", return_value="s"), \
             patch.object(setup, "get_model") as get_model:
            with self.assertRaises(setup.Cancelled):
                setup.verify_model(Path("engine.exe"), model, 2, 2048, "starter", {}, self.root/"log")
            get_model.assert_not_called()

    def test_resource_failure_can_lower_context(self):
        model = self.root / "model.gguf"
        model.write_bytes(b"GGUF")
        with patch.object(setup, "need_memory"), \
             patch.object(setup, "test_chat", side_effect=[setup.ResourceError("out of memory"), {"ok": True}]) as chat, \
             patch.object(setup, "ask", return_value="l"):
            result, _, context = setup.verify_model(Path("engine.exe"), model, 2, 2048, "starter", {}, self.root/"log")
            self.assertEqual(context, 1024)
            self.assertEqual(chat.call_args.args[3], 1024)

    def test_concurrent_settings_change_is_preserved(self):
        from app import settings
        path = self.root / "settings.json"
        path.write_bytes(b'{"engine_threads": 2}')
        with patch.object(settings, "FILE", path):
            with self.assertRaises(setup.InstallError):
                setup.save_configuration({"engine_threads": 4}, b"old")
        self.assertEqual(path.read_bytes(), b'{"engine_threads": 2}')

    def test_inference_failure_stops_only_its_owned_process(self):
        from app import builtin_engine
        model = self.root / "model.gguf"
        model.write_bytes(b"GGUF")
        process = MagicMock()
        process.poll.return_value = None
        with patch.object(setup.subprocess, "Popen", return_value=process), \
             patch.object(setup, "request_json", side_effect=[{"status":"ok"}, OSError("timeout")]), \
             patch.object(builtin_engine, "free_port", return_value=54321):
            with self.assertRaises(OSError):
                setup.test_chat(self.root/"llama-server.exe", model, 2, 1024, self.root/"engine.log")
        process.terminate.assert_called_once()
        process.wait.assert_called_once()

    def test_manifest_models_and_lock_have_no_voice_or_ocr_packages(self):
        import json
        source_root = Path(__file__).resolve().parents[1]
        manifest = json.loads((source_root/"installer"/"assets.json").read_text())
        self.assertEqual(set(manifest["models"]), {"starter", "fallback"})
        for asset in [manifest["engine"], *manifest["models"].values()]:
            self.assertRegex(asset["sha256"], r"^[a-f0-9]{64}$")
            self.assertTrue(asset["url"].startswith("https://"))
        lock = (source_root/"requirements-text-lock.txt").read_text().lower()
        for name in ("onnxruntime==", "faster-whisper==", "kokoro-onnx==", "piper-tts==", "opencv", "rapidocr=="):
            self.assertNotIn(name, lock)


if __name__ == "__main__":
    unittest.main()
