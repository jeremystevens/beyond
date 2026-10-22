"""39E recovery checks: disposable files, local HTTP and installer-owned workers only."""
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from installer import text_setup as shared
from installer import add_features as optional


class RecoveryTests(unittest.TestCase):
    def test_interrupted_transfer_resumes_without_replacing_settings(self):
        payload = b"recovery fixture" * 100000
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                start = int(self.headers.get("Range", "bytes=0-")[6:-1])
                requests.append(start)
                self.send_response(206 if start else 200)
                self.send_header("Content-Length", str(len(payload)-start))
                if start:
                    self.send_header("Content-Range", "bytes %d-%d/%d" %
                                     (start, len(payload)-1, len(payload)))
                self.end_headers()
                if len(requests) == 1:
                    self.wfile.write(payload[:shared.MIB])
                    self.wfile.flush()
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                else:
                    self.wfile.write(payload[start:])
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="BEYOND recovery spaces ") as folder:
                target = Path(folder)/"model.gguf"
                settings = Path(folder)/"settings.json"
                settings.write_bytes(b'{"existing":true}')
                asset = {"url":"http://127.0.0.1:%d/file" % server.server_port,
                         "size":len(payload), "sha256":hashlib.sha256(payload).hexdigest()}
                with redirect_stdout(io.StringIO()):
                    with self.assertRaises(shared.InstallError):
                        shared.download(asset, target)
                    self.assertFalse(target.exists())
                    self.assertGreater(target.with_suffix(".gguf.part").stat().st_size, 0)
                    shared.download(asset, target)
                    shared.download(asset, target)
                self.assertEqual(requests, [0, shared.MIB])
                self.assertEqual(target.read_bytes(), payload)
                self.assertEqual(settings.read_bytes(), b'{"existing":true}')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_transport_exception_is_retryable(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(shared.urllib.request, "urlopen",
                              side_effect=http.client.IncompleteRead(b"fragment")), \
                 patch.object(shared, "check_space"):
                with self.assertRaisesRegex(shared.InstallError, "Retry"):
                    shared.download({"url":"http://127.0.0.1/file","size":100},
                                    Path(folder)/"download")

    def test_invalid_feature_number_does_not_install_valid_subset(self):
        with patch.object(optional.shared, "ask", return_value="1,99"), \
             patch.object(optional, "ready", return_value=False), redirect_stdout(io.StringIO()):
            with self.assertRaises(optional.shared.InstallError):
                optional.select_features(list(optional.FEATURES), {}, {})

    @unittest.skipUnless(sys.platform == "win32", "Windows job ownership")
    def test_logged_worker_timeout_stops_owned_process_and_keeps_log(self):
        import psutil
        with tempfile.TemporaryDirectory(prefix="BEYOND worker spaces ") as folder:
            root = Path(folder)
            pidfile = root/"worker.pid"
            log = root/"install.log"
            code = ("import os,sys,time; from pathlib import Path; "
                    "Path(sys.argv[1]).write_text(str(os.getpid())); "
                    "print('started',flush=True); time.sleep(60)")
            with patch.object(shared, "ROOT", root), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(shared.InstallError, "timed out"):
                    shared.run_logged([sys.executable,"-c",code,str(pidfile)],"Fixture",log,timeout=2)
            self.assertTrue(pidfile.exists())
            self.assertFalse(psutil.pid_exists(int(pidfile.read_text())))
            self.assertIn("started", log.read_text())

    @unittest.skipUnless(sys.platform == "win32", "Windows job ownership")
    def test_keyboard_cancellation_closes_owned_worker(self):
        import psutil
        import time
        from installer import process_guard
        real_job = process_guard.JobProcess
        class InterruptJob(real_job):
            def __enter__(self):
                process = super().__enter__()
                self.pid = process.pid
                self.original_wait = process.wait
                def interrupt(timeout=None):
                    raise KeyboardInterrupt()
                process.wait = interrupt
                return process
            def __exit__(self, *error):
                self.process.wait = self.original_wait
                return super().__exit__(*error)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            jobs = []
            def make_job(*args, **kwargs):
                job = InterruptJob(*args, **kwargs)
                jobs.append(job)
                return job
            with patch.object(shared, "ROOT", root), \
                 patch.object(process_guard, "JobProcess", side_effect=make_job), \
                 redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    shared.run_logged([sys.executable,"-c","import time; time.sleep(60)"],
                                      "Fixture",root/"cancel.log")
            self.assertFalse(psutil.pid_exists(jobs[0].pid))

    @unittest.skipUnless(sys.platform == "win32", "Windows job ownership")
    def test_failed_library_command_is_actionable_and_can_be_rerun(self):
        with tempfile.TemporaryDirectory(prefix="BEYOND logs spaces ") as folder:
            root = Path(folder)
            with patch.object(shared, "ROOT", root), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(shared.InstallError, "Retry"):
                    shared.run_logged([sys.executable,"-c","print('failure details'); raise SystemExit(7)"],
                                      "Fixture",root/"pip.log")
                self.assertIn("failure details",(root/"pip.log").read_text())
                shared.run_logged([sys.executable,"-c","print('recovered')"],"Fixture",root/"pip.log")
                self.assertIn("recovered",(root/"pip.log").read_text())


if __name__ == "__main__":
    unittest.main()
