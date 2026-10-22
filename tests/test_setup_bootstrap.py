"""Bootstrap checks; no app imports, network access, or changes to the working environment."""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import sys

spec = importlib.util.spec_from_file_location("beyond_setup", Path(__file__).resolve().parents[1] / "setup.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_reject_wrong_version_and_architecture(self):
        for version, bits in (([3, 13, 9], 64), ([3, 14, 1], 32), ([3, 15, 0], 64)):
            self.assertFalse(bootstrap.compatible({"version": version, "bits": bits}))
        self.assertTrue(bootstrap.compatible({"version": [3, 14, 0], "bits": 64}))

    def test_check_does_not_create_environment(self):
        with tempfile.TemporaryDirectory(prefix="beyond setup ") as folder:
            path = Path(folder) / ".venv"
            with redirect_stdout(io.StringIO()):
                self.assertFalse(bootstrap.prepare_environment(path, check_only=True))
            self.assertFalse(path.exists())

    def test_existing_invalid_folder_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".venv"
            path.mkdir()
            marker = path / "keep.txt"
            marker.write_text("preserve")
            with self.assertRaises(bootstrap.SetupError):
                bootstrap.prepare_environment(path, assume_yes=True)
            self.assertEqual(marker.read_text(), "preserve")

    def test_wrong_python_environment_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "pyvenv.cfg").write_text("version = 3.13")
            with patch.object(bootstrap, "probe", return_value={"version": [3, 13, 1], "bits": 64}):
                with self.assertRaises(bootstrap.SetupError):
                    bootstrap.prepare_environment(path, assume_yes=True)
            self.assertTrue((path / "pyvenv.cfg").exists())

    def test_cancel_creates_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".venv"
            with patch("builtins.input", return_value="n"), redirect_stdout(io.StringIO()):
                self.assertFalse(bootstrap.prepare_environment(path))
            self.assertFalse(path.exists())

    def test_eof_defaults_to_no(self):
        with patch("builtins.input", side_effect=EOFError):
            self.assertFalse(bootstrap.confirm("Continue?"))

    def test_probe_timeout_and_bad_json(self):
        import subprocess
        with patch.object(bootstrap.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 20)):
            self.assertIsNone(bootstrap.probe(["python"]))
        with patch.object(bootstrap.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "not json"
            self.assertIsNone(bootstrap.probe(["python"]))

    def test_finds_correct_interpreter_after_wrong_one(self):
        with patch.object(bootstrap, "candidates", return_value=iter([["old"], ["new"]])), \
             patch.object(bootstrap, "probe", side_effect=[
                 {"version": [3, 13, 1], "bits": 64},
                 {"version": [3, 14, 8], "bits": 64, "executable": "new"}]):
            self.assertEqual(bootstrap.find_python()["executable"], "new")

    @unittest.skipUnless(sys.platform == "win32", "Windows")
    def test_old_python_relaunch_preserves_check_flag_and_path(self):
        with patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
             patch.object(bootstrap, "find_python", return_value={"executable": "C:/Python path/python.exe"}), \
             patch.object(bootstrap.subprocess, "call", return_value=0) as call, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(bootstrap.main(["--check"]), 0)
            self.assertEqual(call.call_args.args[0],
                             ["C:/Python path/python.exe", "-I", str(bootstrap.ROOT / "setup.py"), "--check"])

    @unittest.skipUnless(sys.platform == "win32", "Windows")
    def test_missing_python_check_never_installs(self):
        with patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
             patch.object(bootstrap, "find_python", return_value=None), \
             patch.object(bootstrap.subprocess, "call") as call, redirect_stdout(io.StringIO()):
            with self.assertRaises(bootstrap.SetupError):
                bootstrap.main(["--check"])
            call.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32" and sys.version_info[:2] == (3, 14), "Windows Python 3.14")
    def test_create_and_reuse_real_environment_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="beyond setup ") as folder:
            path = Path(folder) / "test environment"
            with redirect_stdout(io.StringIO()):
                self.assertTrue(bootstrap.prepare_environment(path, assume_yes=True))
                self.assertTrue(bootstrap.prepare_environment(path, check_only=True))
            info = bootstrap.environment_status(path)[1]
            self.assertTrue(bootstrap.compatible(info))
            self.assertNotEqual(info["prefix"], info["base"])


if __name__ == "__main__":
    unittest.main()
