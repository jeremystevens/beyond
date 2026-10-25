"""Optional-installer isolation, recovery and offline-model checks."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("optional_installer", ROOT/"installer"/"add_features.py")
optional = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optional)


class OptionalTests(unittest.TestCase):
    def test_ready_requires_same_files_packages_and_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"model.onnx"; path.write_bytes(b"model")
            record={"status":"passed","packages":{"engine":"1"},"configuration":{"speech_enabled":True},
                    "files":optional.fingerprints([path])}
            with patch.object(optional,"versions",return_value={"engine":"1"}):
                self.assertTrue(optional.ready("kokoro",record,{"speech_enabled":True}))
                self.assertFalse(optional.ready("kokoro",record,{"speech_enabled":False}))
                path.write_bytes(b"changed model")
                self.assertFalse(optional.ready("kokoro",record,{"speech_enabled":True}))

    def test_malformed_status_is_not_treated_as_ready(self):
        for record in (None, [], "bad", {"status":"passed","configuration":[],"files":[]}):
            self.assertFalse(optional.ready("whisper", record, {}))

    def test_unselected_packages_are_not_installed(self):
        with patch.object(optional.subprocess,"run") as run:
            optional.libraries("vision")
            optional.libraries("image")
            run.assert_not_called()

    def test_skip_is_distinct_from_cancel_remaining(self):
        with patch.object(optional.shared,"ask",return_value="s"), redirect_stdout(io.StringIO()):
            with self.assertRaises(optional.Skipped):
                optional.repeat("Test",lambda: (_ for _ in ()).throw(optional.shared.InstallError("failed")))
        with patch.object(optional.shared,"ask",return_value="c"), redirect_stdout(io.StringIO()):
            with self.assertRaises(optional.shared.Cancelled):
                optional.repeat("Test",lambda: (_ for _ in ()).throw(optional.shared.InstallError("failed")))

    def test_optional_manifest_is_pinned(self):
        manifest=json.loads((ROOT/"installer"/"optional-assets.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["groups"]),{"whisper_tiny","whisper_base","kokoro","piper","ocr","vision","image"})
        for group in manifest["groups"].values():
            self.assertTrue(group["license_url"].startswith("https://"))
            for asset in group["assets"]:
                self.assertRegex(asset["sha256"],r"^[a-f0-9]{64}$")
                self.assertGreater(asset["size"],0)
                self.assertTrue(asset["url"].startswith("https://"))
        self.assertTrue(manifest["groups"]["vision"]["accept"])
        self.assertTrue(manifest["groups"]["image"]["accept"])

    def test_piper_fallback_does_not_replace_kokoro(self):
        from app import config
        model=Path("en_US-ryan-high.onnx")
        values={**config.DEFAULTS,"speech_enabled":True,"speech_engine":"kokoro"}
        with patch.object(optional,"group_assets",return_value=[model,Path(str(model)+".json")]):
            changes,_=optional.prepare("piper",{},values,"tiny")
        self.assertNotIn("speech_engine",changes)
        self.assertEqual(changes["speech_piper_model"],str(model))

    def test_whisper_local_path_never_downloads(self):
        from app.tools import speech_to_text
        speech_to_text._model.cache_clear()
        try:
            with tempfile.TemporaryDirectory() as folder:
                (Path(folder)/"model.bin").write_bytes(b"fixture")
                factory=Mock(return_value=object())
                with patch.dict(sys.modules,{"faster_whisper":types.SimpleNamespace(WhisperModel=factory)}), \
                     patch.object(speech_to_text.settings,"load",return_value={"whisper_model_dir":folder,"whisper_threads":2}):
                    speech_to_text._model()
                self.assertTrue(factory.call_args.kwargs["local_files_only"])
                self.assertEqual(factory.call_args.args[0],folder)
                self.assertEqual(factory.call_args.kwargs["device"],"cpu")
        finally:
            speech_to_text._model.cache_clear()

    def test_missing_whisper_directory_is_actionable(self):
        from app.tools import speech_to_text
        speech_to_text._model.cache_clear()
        factory=Mock()
        try:
            with patch.dict(sys.modules,{"faster_whisper":types.SimpleNamespace(WhisperModel=factory)}), \
                 patch.object(speech_to_text.settings,"load",return_value={"whisper_model_dir":"Z:/missing-voice-fixture"}):
                with self.assertRaisesRegex(speech_to_text.SpeechError,"Add-Features"):
                    speech_to_text._model()
                factory.assert_not_called()
        finally:
            speech_to_text._model.cache_clear()

    def test_optional_setting_types_are_validated(self):
        from app import settings
        for change in ({"whisper_model_dir":False},{"ocr_model_dir":[]},{"whisper_threads":True},{"whisper_threads":0}):
            with self.assertRaises(settings.SettingsError):
                settings.validate(change)

    @unittest.skipUnless(sys.platform=="win32","Windows job objects")
    def test_job_close_stops_its_parent_and_child(self):
        import psutil
        sys.path.insert(0,str(ROOT/"installer"))
        from process_guard import JobProcess
        with tempfile.TemporaryDirectory(prefix="beyond job test ") as folder:
            pidfile=Path(folder)/"child.pid"
            code=("import subprocess,sys,time; from pathlib import Path; "
                  "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                  "target=Path(sys.argv[1]); ready=target.with_suffix('.ready'); "
                  "ready.write_text(str(p.pid)); ready.replace(target); time.sleep(60)")
            with JobProcess([sys.executable,"-c",code,str(pidfile)],stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as process:
                deadline=time.monotonic()+10
                while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.05)
                self.assertTrue(pidfile.exists())
                child=int(pidfile.read_text())
                self.assertTrue(psutil.pid_exists(child))
                owned_child=psutil.Process(child)
            # Waiting verifies exit even while Windows retains the PID for an open handle.
            try:owned_child.wait(timeout=5)
            except psutil.NoSuchProcess:pass
            self.assertIsNotNone(process.poll())

    @unittest.skipUnless(sys.platform=="win32","Windows installer")
    def test_failed_feature_does_not_block_next_or_save_failed_settings(self):
        from app import config,settings
        with tempfile.TemporaryDirectory(prefix="beyond optional test ") as folder, ExitStack() as stack:
            root=Path(folder)
            asset=root/"model.onnx"; asset.write_bytes(b"fixture")
            settings_file=root/"settings.json"; settings_file.write_text("{}")
            stack.enter_context(patch.object(optional,"ROOT",root))
            stack.enter_context(patch.object(optional.shared,"ROOT",root))
            stack.enter_context(patch.object(optional.sys,"prefix",str(root/".venv")))
            stack.enter_context(patch.object(settings,"FILE",settings_file))
            stack.enter_context(patch.object(settings,"load",return_value=dict(config.DEFAULTS)))
            stack.enter_context(patch.object(optional.shared,"hardware",return_value={"total_ram":16*optional.shared.GIB}))
            stack.enter_context(patch.object(optional.shared,"confirm",return_value=True))
            stack.enter_context(patch.object(optional.shared,"ask",return_value="s"))
            stack.enter_context(patch.object(optional.shared,"ensure_app_closed"))
            stack.enter_context(patch.object(optional.shared,"need_memory"))
            stack.enter_context(patch.object(optional.shared,"check_runtime"))
            stack.enter_context(patch.object(optional,"libraries"))
            stack.enter_context(patch.object(optional,"versions",return_value={"test":"1"}))
            stack.enter_context(patch.object(optional,"prepare",side_effect=[
                ({"whisper_model_dir":folder},[asset]),({"speech_kokoro_model":str(asset)},[asset])]))
            stack.enter_context(patch.object(optional,"test_feature",side_effect=[
                optional.shared.InstallError("fixture failure"),{"status":"passed","details":{}}]))
            save=stack.enter_context(patch.object(optional.shared,"save_configuration"))
            stack.enter_context(redirect_stdout(io.StringIO()))
            self.assertEqual(optional.main(["--features","whisper","kokoro","--whisper-model","tiny"]),1)
            self.assertEqual(save.call_count,1)
            self.assertIn("speech_kokoro_model",save.call_args.args[0])
            self.assertNotIn("whisper_model_dir",save.call_args.args[0])
            result=json.loads((root/"data"/"setup"/"optional"/"features.json").read_text())
            self.assertEqual(result["whisper"]["status"],"needs_attention")
            self.assertEqual(result["kokoro"]["status"],"passed")


if __name__=="__main__":
    unittest.main()
