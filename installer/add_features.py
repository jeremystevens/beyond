"""Install selected optional BEYOND features. Uses the existing Python environment."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import text_setup as shared

FEATURES = {
    "whisper": ("Voice input (Whisper)", 1.0, 300),
    "kokoro": ("Spoken replies (Kokoro)", 1.5, 240),
    "piper": ("Piper voice / fallback", 1.0, 240),
    "ocr": ("Read text in photos", 1.5, 240),
    "vision": ("Understand photos (/look)", 6.0, 660),
    "image": ("Generate pictures (/imagine)", 5.0, 1260),
}
PACKAGES = {
    "whisper": ("faster-whisper", "ctranslate2", "av", "onnxruntime"),
    "kokoro": ("kokoro-onnx", "onnxruntime", "numpy"),
    "piper": ("piper-tts", "onnxruntime"),
    "ocr": ("rapidocr", "onnxruntime", "opencv-python-headless", "numpy"),
    "vision": ("pillow",), "image": ("pillow",),
}
PREFIX = {"whisper": "whisper_", "kokoro": "speech_", "piper": "speech_",
          "ocr": "ocr_", "vision": "vision_", "image": "image_"}


class Skipped(shared.InstallError):
    pass


def versions(feature):
    out = {}
    for name in PACKAGES[feature]:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def read_state(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def fingerprints(paths):
    out = []
    for path in dict.fromkeys(str(Path(p).resolve()) for p in paths):
        stat = Path(path).stat()
        out.append({"path": path, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return out


def ready(feature, record, values):
    if (not isinstance(record, dict) or not isinstance(record.get("configuration"), dict)
            or not isinstance(record.get("files"), list)):
        return False
    if record.get("status") != "passed" or record.get("packages") != versions(feature):
        return False
    if any(values.get(key) != value for key, value in record.get("configuration", {}).items()):
        return False
    if not record.get("files"):
        return False
    try:
        return all(Path(item["path"]).stat().st_size == item["size"] and
                   Path(item["path"]).stat().st_mtime_ns == item["mtime_ns"]
                   for item in record["files"])
    except (OSError, KeyError, TypeError, ValueError):
        return False


def repeat(label, action):
    while True:
        try:
            print("\n" + label, flush=True)
            return action()
        except (OSError, ValueError, subprocess.SubprocessError, shared.InstallError) as exc:
            if isinstance(exc, shared.Cancelled):
                raise
            shared.log_event(label + ": " + str(exc))
            print("Needs attention: " + str(exc))
            print("Existing feature settings and completed downloads are preserved.")
            choice = shared.ask("[R]etry, [S]kip this feature, or [C]ancel remaining features? ", "s").lower()
            if choice == "r":
                continue
            if choice == "s":
                raise Skipped(str(exc)) from exc
            raise shared.Cancelled("Remaining optional features cancelled.") from exc


def libraries(feature):
    if feature in ("vision", "image"):
        return
    result = subprocess.run([sys.executable, "-I", "-m", "pip", "install", "--quiet",
                             "--disable-pip-version-check", "--only-binary=:all:",
                             "--timeout", "30", "--retries", "2",
                             "-r", str(ROOT / ("requirements-" + feature + ".txt"))], cwd=ROOT)
    if result.returncode:
        raise shared.InstallError("Optional library installation failed. Check memory and connection, then Retry.")
    result = subprocess.run([sys.executable, "-I", "-m", "pip", "check"], cwd=ROOT)
    if result.returncode:
        raise shared.InstallError("Libraries have a version conflict. No existing optional libraries were removed.")


def acquire(asset, target, candidate=None):
    if candidate and shared.verified(Path(candidate), asset):
        print("Reusing verified " + str(candidate), flush=True)
        return Path(candidate).resolve()
    cache = ROOT / "data" / "setup" / "optional" / "downloads" / asset["file"]
    if not target.exists() and shared.verified(cache, asset):
        target.parent.mkdir(parents=True, exist_ok=True)
        shared.check_space(target.parent, asset["size"])
        temp = target.with_name(target.name + ".part")
        shutil.copyfile(cache, temp)
        if not shared.verified(temp, asset):
            raise shared.InstallError("Cached file copy did not pass verification.")
        temp.replace(target)
        return target
    return shared.download(asset, target)


def group_assets(group, manifest, values, feature):
    assets = manifest["groups"][group]["assets"]
    destination = ROOT / "models" / "optional" / group
    # These formats require their companion files in the same directory.
    folder = None
    if feature == "whisper":
        folder = values.get("whisper_model_dir")
    elif feature == "ocr":
        folder = values.get("ocr_model_dir")
    elif feature == "piper" and values.get("speech_piper_model"):
        folder = str(Path(values["speech_piper_model"]).parent)
    if folder and all(shared.verified(Path(folder) / a["file"], a) for a in assets):
        return [Path(folder).resolve() / a["file"] for a in assets]
    keys = {"kokoro": ("speech_kokoro_model", "speech_kokoro_voices"),
            "vision": ("vision_model", "vision_mmproj"), "image": ("image_model",)}
    return [acquire(a, destination / a["file"],
                    values.get(keys[feature][index]) if feature in keys else None)
            for index, a in enumerate(assets)]


def prepare(feature, manifest, values, whisper_size):
    group = "whisper_" + whisper_size if feature == "whisper" else feature
    paths = group_assets(group, manifest, values, feature)
    threads = max(1, min(4, (os.cpu_count() or 2) // 2))
    changes = {}
    if feature == "whisper":
        changes = {"whisper_model_dir": str(paths[0].parent), "whisper_threads": threads}
    elif feature == "ocr":
        changes = {"ocr_model_dir": str(paths[0].parent)}
    elif feature == "kokoro":
        changes = {"speech_kokoro_model": str(paths[0]), "speech_kokoro_voices": str(paths[1]),
                   "speech_engine": "kokoro", "speech_enabled": True, "speech_threads": min(2, threads)}
    elif feature == "piper":
        changes = {"speech_piper_model": str(paths[0])}
        if not values["speech_enabled"] or values["speech_engine"] == "piper":
            changes.update(speech_engine="piper", speech_enabled=True, speech_threads=min(2, threads))
    elif feature == "vision":
        base = json.loads((HERE / "assets.json").read_text(encoding="utf-8"))["engine"]
        archive = shared.download(base, ROOT / "data" / "setup" / "downloads" / base["file"])
        engine_folder = ROOT / "data" / "setup" / "engines" / "b9668" / "cpu"
        executable = shared.extract_engine(archive, engine_folder, "llama-mtmd-cli.exe")
        paths += [p for p in engine_folder.rglob("*") if p.is_file()]
        changes = {"vision_model": str(paths[0]), "vision_mmproj": str(paths[1]),
                   "vision_executable": str(executable), "vision_threads": threads, "vision_enabled": True}
    elif feature == "image":
        asset = manifest["image_engine"]
        archive = shared.download(asset, ROOT / "data" / "setup" / "downloads" / asset["file"])
        engine_folder = ROOT / "data" / "setup" / "engines" / "sd-a77d362" / "cpu"
        executable = shared.extract_engine(archive, engine_folder, "sd-cli.exe")
        paths += [p for p in engine_folder.rglob("*") if p.is_file()]
        changes = {"image_model": str(paths[0]), "image_executable": str(executable),
                   "image_threads": threads, "image_enabled": True}
    return changes, paths


def test_feature(feature, candidate):
    folder = ROOT / "data" / "setup" / "optional" / "tests" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    request = folder / "request.json"
    shared.atomic_json(request, {"feature": feature, "settings": candidate})
    print("Testing " + FEATURES[feature][0] + " on the CPU. This can take several minutes.", flush=True)
    print("Test log: " + str(folder / "worker.log"), flush=True)
    from process_guard import JobProcess
    with (folder / "worker.log").open("w", encoding="utf-8") as log:
        with JobProcess([sys.executable, "-I", str(HERE / "feature_worker.py"), str(request)],
                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                        creationflags=shared.FLAGS) as process:
            returncode = process.wait(timeout=FEATURES[feature][2])
    state = read_state(folder / "result.json")
    if returncode or state.get("status") != "passed":
        raise shared.InstallError(state.get("error") or "Feature test stopped. See " + str(folder / "worker.log"))
    return state


def select_features(names, values, state):
    for number, feature in enumerate(names, 1):
        status = "Ready (last test passed)" if ready(feature, state.get(feature, {}), values) else "Needs installation/test"
        print("%d. %s - %s" % (number, FEATURES[feature][0], status))
    raw = shared.ask("Choose numbers separated by commas (blank cancels): ")
    if not raw:
        return []
    try:
        selected = list(dict.fromkeys(names[int(n.strip()) - 1] for n in raw.split(",")
                                     if 1 <= int(n.strip()) <= len(names)))
    except (ValueError, IndexError):
        raise shared.InstallError("Enter feature numbers separated by commas.")
    if not selected:
        raise shared.InstallError("No valid feature numbers selected.")
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", nargs="+", choices=tuple(FEATURES))
    parser.add_argument("--whisper-model", choices=("tiny", "base"))
    parser.add_argument("--retest", action="store_true", help="Retest/repair previously verified selections.")
    parser.add_argument("--check", action="store_true", help="Read-only feature status and hardware report.")
    args = parser.parse_args(argv)
    if os.name != "nt" or sys.version_info[:2] != (3, 14) or struct.calcsize("P") != 8:
        raise shared.InstallError("Run Setup.cmd first: Windows x64 and Python 3.14 are required.")
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise shared.InstallError("Use Add-Features.cmd so optional packages go into BEYOND's environment.")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    import setup as bootstrap
    bootstrap.banner("Add Features")
    print("Add Features: install only what you choose. CPU mode.\n", flush=True)
    from app import config, settings
    manifest = json.loads((HERE / "optional-assets.json").read_text(encoding="utf-8"))
    values = settings.load()
    state_file = ROOT / "data" / "setup" / "optional" / "features.json"
    state = {key: value for key, value in read_state(state_file).items()
             if key in FEATURES and isinstance(value, dict)}
    info = shared.hardware()
    prior_variant = state.get("whisper", {}).get("variant", "")
    prior_size = prior_variant[8:] if prior_variant in ("whisper_tiny", "whisper_base") else None
    whisper_size = args.whisper_model or prior_size or ("base" if info["total_ram"] >= 8 * shared.GIB else "tiny")
    if args.check:
        for feature in FEATURES:
            print(FEATURES[feature][0] + ": " +
                  ("Ready (last test passed)" if ready(feature, state.get(feature, {}), values) else "Needs installation/test"))
        print(json.dumps(info, indent=2))
        return 0
    selected = list(dict.fromkeys(args.features)) if args.features else select_features(list(FEATURES), values, state)
    if not selected:
        print("No features selected.")
        return 0
    if ("whisper" in selected and not args.whisper_model and
            (args.retest or not ready("whisper", state.get("whisper", {}), values))):
        print("Whisper tiny: 75 MiB, faster; base: 141 MiB, generally more accurate.")
        print("Recommended for installed RAM: " + whisper_size)
        answer = shared.ask("Choose tiny or base [recommended]: ", whisper_size).lower()
        if answer not in ("tiny", "base"):
            raise shared.InstallError("Choose tiny or base.")
        whisper_size = answer
    shared.retry_step("Check BEYOND is closed", lambda: shared.ensure_app_closed(values))
    lock_path = ROOT / "data" / "setup" / "install.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {}
    with lock_path.open("a+b") as lock:
        import msvcrt
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise shared.InstallError("Another setup is running. Wait and retry.") from exc
        try:
            shared.atomic_json(ROOT / "data" / "setup" / "hardware.json", info)
            for feature in selected:
                values = settings.load()
                variant_changed = (feature == "whisper" and args.whisper_model and
                                   state.get(feature, {}).get("variant") != "whisper_" + args.whisper_model)
                if not args.retest and not variant_changed and ready(feature, state.get(feature, {}), values):
                    summary[feature] = "Already verified; skipped"
                    continue
                group = "whisper_" + whisper_size if feature == "whisper" else feature
                details = manifest["groups"][group]
                size = sum(a["size"] for a in details["assets"])
                print("\n%s: model assets %.0f MiB plus any missing libraries/native engine." %
                      (FEATURES[feature][0], size / shared.MIB))
                print("Estimated free RAM for testing: %.1f GiB. Downloads are reused when verified." % FEATURES[feature][1])
                print("License: " + details["license"] + "\n" + details["license_url"])
                consent = ("Accept the model/voice terms and install/test this feature?" if details.get("accept")
                           else "Install/test this feature?")
                if not shared.confirm(consent):
                    summary[feature] = "Skipped"
                    continue
                initial = shared.snapshot(settings.FILE)
                try:
                    repeat("Check BEYOND is closed", lambda: shared.ensure_app_closed(values))
                    shared.need_memory(int(FEATURES[feature][1] * shared.GIB))
                    repeat("Install selected libraries", lambda: libraries(feature))
                    repeat("Verify text chat remains usable", shared.check_runtime)
                    changes, paths = repeat("Prepare selected feature files", lambda: prepare(
                        feature, manifest, values, whisper_size))
                    candidate = {key: value for key, value in values.items() if key.startswith(PREFIX[feature])}
                    candidate.update(changes)
                    result = repeat("Verify selected feature", lambda: test_feature(feature, candidate))
                    # Reject edits made by another app instead of replacing them.
                    repeat("Check BEYOND is still closed", lambda: shared.ensure_app_closed(values))
                    shared.save_configuration(changes, initial)
                    state[feature] = {"status": "passed", "variant": group, "time": time.time(), "configuration": changes,
                                      "packages": versions(feature), "files": fingerprints(paths),
                                      "license": details["license_url"], "details": result.get("details", {})}
                    summary[feature] = "Ready"
                    shared.atomic_json(state_file, state)
                except Skipped as exc:
                    summary[feature] = "Needs attention; settings preserved"
                    state[feature] = {"status": "needs_attention", "error": str(exc), "time": time.time()}
                    shared.atomic_json(state_file, state)
                except shared.Cancelled:
                    summary[feature] = "Cancelled; settings preserved"
                    break
                except (OSError, ValueError, shared.InstallError, subprocess.SubprocessError) as exc:
                    summary[feature] = "Needs attention; settings preserved"
                    state[feature] = {"status": "needs_attention", "error": str(exc), "time": time.time()}
                    shared.atomic_json(state_file, state)
                    print("This feature was not enabled: " + str(exc))
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    print("\nFeature setup results:")
    for feature in selected:
        print("- " + FEATURES[feature][0] + ": " + summary.get(feature, "Not attempted"))
    print("Text chat and existing feature settings are preserved. Rerun Add-Features.cmd anytime.")
    return 0 if all(value in ("Ready", "Skipped", "Already verified; skipped") for value in summary.values()) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except shared.Cancelled as exc:
        print(str(exc))
        sys.exit(0)
    except (shared.InstallError, OSError, ValueError) as exc:
        print("Add Features needs attention: " + str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Cancelled. Completed downloads and existing settings are preserved.")
        sys.exit(130)
