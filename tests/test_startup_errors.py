"""Phase 42 startup regressions. Disposable data/ports; never restart the live application."""
import importlib.util
import io
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from app import config, ports, settings


class StartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Port preflight never enters the ASGI app. Stub that import so these launcher tests
        # neither initialize databases nor depend on SQLite finalization timing on Windows.
        fake_server=types.SimpleNamespace(app=types.SimpleNamespace(state=types.SimpleNamespace()))
        with patch.dict(sys.modules,{"app.server":fake_server}):
            spec=importlib.util.spec_from_file_location("beyond_startup_test",config.ROOT/"beyond.py")
            cls.entry=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.entry)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="BEYOND startup spaces ")
        self.filepatch=patch.object(settings,"FILE",Path(self.temp.name)/"settings.json")
        self.filepatch.start()
        self.output=redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None,None,None)
        self.filepatch.stop()
        self.temp.cleanup()

    @unittest.skipUnless(sys.platform == "win32", "Windows native dialog")
    def test_hidden_console_startup_reports_visible_error(self):
        with patch.object(sys,"platform","win32"), patch.object(sys,"argv",["beyond.py"]), \
             patch.object(self.entry.ctypes.windll.user32,"MessageBoxW",return_value=1) as dialog:
            self.entry.report_startup_problem("Port conflict fixture")
        self.assertEqual(dialog.call_args.args[1],"Port conflict fixture")
        self.assertEqual(dialog.call_args.args[2],"BEYOND could not start")
        self.assertTrue(dialog.call_args.args[3] & 0x10)

    @unittest.skipUnless(sys.platform == "win32", "Windows native dialog")
    def test_console_startup_does_not_open_a_dialog(self):
        with patch.object(sys,"platform","win32"), patch.object(sys,"argv",["beyond.py","--console"]), \
             patch.object(self.entry.ctypes.windll.user32,"MessageBoxW") as dialog:
            self.entry.report_startup_problem("Port conflict fixture")
            dialog.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32", "Windows native dialog")
    def test_dialog_failure_keeps_console_or_log_explanation(self):
        with patch.object(sys,"platform","win32"), patch.object(sys,"argv",["beyond.py"]), \
             patch.object(self.entry.ctypes.windll.user32,"MessageBoxW",side_effect=OSError("fixture")):
            self.entry.report_startup_problem("Port conflict fixture")

    def test_real_occupied_port_fails_before_server_and_leaves_listener_alone(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0))
            listener.listen()
            port=listener.getsockname()[1]
            values={**config.DEFAULTS,"web_port":port}
            with patch.object(settings,"load",return_value=values), \
                 patch.object(ports,"users_of",return_value=[]), \
                 patch.object(self.entry,"report_startup_problem") as report, \
                 patch.object(self.entry.uvicorn,"Server") as server:
                self.assertEqual(self.entry.serve(),1)
                server.assert_not_called()
                text=report.call_args.args[0]
                self.assertIn(str(port),text)
                self.assertIn("web_port",text)
                self.assertIn(str(settings.FILE),text)
                self.assertNotIn("Phase 4",text)
                self.assertNotIn("app/config.py",text)
                self.assertFalse(ports.can_bind("127.0.0.1",port))
        self.assertTrue(ports.can_bind("127.0.0.1",port))

    def test_conflict_names_the_program_without_old_instructions(self):
        with patch.object(ports,"users_of",return_value=[(123,"fixture.exe","fixture")]):
            text=ports.problem("127.0.0.1",7770)
        self.assertIn("fixture.exe (process 123)",text)
        self.assertIn("Settings > Address and network",text)
        self.assertNotIn("arrives in Phase",text)

    def test_existing_beyond_has_its_own_message(self):
        with patch.object(ports,"users_of",return_value=[(123,"pythonw.exe","pythonw beyond.py")]):
            text=ports.problem("127.0.0.1",7770)
        self.assertIn("already running",text)
        self.assertIn("http://127.0.0.1:7770",text)

    def test_free_port_has_no_error(self):
        with patch.object(ports,"users_of",return_value=[]), patch.object(ports,"can_bind",return_value=True):
            self.assertIsNone(ports.problem("127.0.0.1",7770))

    def test_tray_is_ready_before_failed_server_can_stop_it(self):
        events=[]
        class Icon:
            def __init__(self,*args):
                self.ready=False
            def run(self,setup):
                self.ready=True
                events.append("ready")
                setup(self)
            def stop(self):
                if not self.ready:
                    raise AssertionError("Stopped before tray ready")
                events.append("stopped")
        fake=types.SimpleNamespace(Icon=Icon,Menu=Mock(),MenuItem=Mock())
        fake.Menu.SEPARATOR=object()
        with patch.dict(sys.modules,{"pystray":fake}), \
             patch.object(self.entry.notify,"icon_image",return_value=object()), \
             patch.object(self.entry,"serve",return_value=1):
            self.assertEqual(self.entry.run_with_tray(),1)
        self.assertEqual(events,["ready","stopped"])


if __name__=="__main__":
    unittest.main()
