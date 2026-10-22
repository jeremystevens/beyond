"""Text-only installer. Runs with BEYOND's Python 3.14 environment; no app imports at module load."""
import argparse
import contextlib
import ctypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import struct
import time
import tempfile
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024 ** 3
MIB = 1024 ** 2
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class InstallError(RuntimeError):
    pass


class ResourceError(InstallError):
    pass


class Cancelled(InstallError):
    pass


def ask(message, default=""):
    try:
        return input(message).strip() or default
    except EOFError:
        raise Cancelled("No answer received. Run Setup again to continue.")


def confirm(message):
    return ask(message + " [y/N] ", "n").lower() in ("y", "yes")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(MIB), b""):
            h.update(chunk)
    return h.hexdigest()


def verified(path, asset):
    return path.is_file() and path.stat().st_size == asset["size"] and digest(path) == asset["sha256"]


def log_event(message):
    try:
        folder = ROOT / "data" / "setup"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "install.log").open("a", encoding="utf-8") as stream:
            stream.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + message + "\n")
    except OSError:
        pass


def retry_step(label, action):
    while True:
        try:
            print("\n" + label, flush=True)
            value = action()
            log_event(label + ": passed")
            return value
        except (OSError, ValueError, subprocess.SubprocessError, InstallError) as exc:
            if isinstance(exc, Cancelled):
                raise
            log_event(label + ": " + str(exc))
            print("Needs attention: " + str(exc), flush=True)
            print("Completed downloads and settings are preserved.")
            if ask("[R]etry or [C]ancel? ", "c").lower() != "r":
                raise Cancelled(label + " cancelled.") from exc


def check_space(folder, needed):
    while not folder.exists():
        folder = folder.parent
    if shutil.disk_usage(folder).free < needed + 512 * MIB:
        raise InstallError("Not enough disk space. Free space and choose Retry.")


def download(asset, target):
    """Keep transport failures inside the normal retry flow, with partial bytes intact."""
    try:
        return _download(asset, target)
    except urllib.error.HTTPError as exc:
        raise InstallError("Download server returned HTTP %s. Check your connection or try later; "
                           "partial downloads are preserved." % exc.code) from exc
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
        raise InstallError("Download interrupted. Check your Internet connection and choose Retry; "
                           "partial downloads are preserved.") from exc


def _download(asset, target):
    """Pinned assets only. Safe Range resume; never replace an invalid existing final file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if verified(target, asset):
            print("Reusing verified " + target.name)
            return target
        raise InstallError("Existing file failed verification: " + str(target) +
                           ". Move it aside before retrying; it has not been overwritten.")
    partial = target.with_name(target.name + ".part")
    if partial.exists() and partial.stat().st_size > asset["size"]:
        partial.unlink()  # Installer-owned partial, never a user's completed model.
    offset = partial.stat().st_size if partial.exists() else 0
    check_space(target.parent, asset["size"] - offset)
    if offset < asset["size"]:
        request = urllib.request.Request(asset["url"], headers={
            "User-Agent": "BEYOND-Setup/39C", "Accept-Encoding": "identity",
            **({"Range": "bytes=%d-" % offset} if offset else {})})
        with urllib.request.urlopen(request, timeout=45) as response:
            status = response.status
            if offset and status == 206:
                wanted = "bytes %d-" % offset
                content_range = response.headers.get("Content-Range", "")
                if (not content_range.startswith(wanted)
                        or not content_range.endswith("/%d" % asset["size"])):
                    raise InstallError("Server returned an unexpected resume range. Partial file preserved.")
            elif status == 200:
                offset = 0  # Server ignored Range: restart rather than append duplicate bytes.
                check_space(target.parent, asset["size"])
            else:
                raise InstallError("Unexpected download response: HTTP %s" % status)
            last = 0.0
            with partial.open("ab" if offset else "wb") as stream:
                while True:
                    chunk = response.read(MIB)
                    if not chunk:
                        break
                    if offset + len(chunk) > asset["size"]:
                        raise InstallError("Download exceeded its pinned size.")
                    stream.write(chunk)
                    offset += len(chunk)
                    if time.monotonic() - last >= 1:
                        print("%s: %.1f%% (%.0f / %.0f MiB)" %
                              (target.name, offset * 100 / asset["size"], offset / MIB,
                               asset["size"] / MIB), flush=True)
                        last = time.monotonic()
    print("Verifying SHA-256: " + target.name, flush=True)
    if not verified(partial, asset):
        if partial.exists() and partial.stat().st_size == asset["size"]:
            partial.unlink()  # Retry must not repeatedly reuse a complete corrupt partial.
        raise InstallError("Download is incomplete or its SHA-256 does not match. Choose Retry.")
    partial.replace(target)
    return target


def extract_engine(archive, folder, expected_executable="llama-server.exe"):
    """Verify all extracted files against the signed-off archive again on every reuse."""
    with zipfile.ZipFile(archive) as bundle:
        items = bundle.infolist()
        if sum(i.file_size for i in items) > 512 * MIB:
            raise InstallError("Engine archive expands beyond the expected limit.")
        for item in items:
            destination = (folder / item.filename).resolve()
            if (not destination.is_relative_to(folder.resolve())
                    or item.filename.startswith(("/", "\\")) or ":" in item.filename):
                raise InstallError("Unsafe path in engine archive.")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise InstallError("Engine archive contains a link.")
        check_space(folder.parent, sum(i.file_size for i in items))
        for item in items:
            destination = folder / item.filename
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with bundle.open(item) as source:
                for chunk in iter(lambda: source.read(MIB), b""):
                    h.update(chunk)
            expected = h.hexdigest()
            if destination.exists():
                if digest(destination) != expected:
                    raise InstallError("Existing engine file differs from the pinned archive: " +
                                       str(destination) + ". Move the engine folder aside and Retry.")
            else:
                temp = destination.with_name(destination.name + ".tmp")
                with bundle.open(item) as source, temp.open("wb") as out:
                    shutil.copyfileobj(source, out, MIB)
                temp.replace(destination)
    matches = list(folder.rglob(expected_executable))
    if len(matches) != 1:
        raise InstallError("Pinned engine archive did not contain exactly one " + expected_executable + ".")
    return matches[0]


def memory():
    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong),
                    ("page_total", ctypes.c_ulonglong), ("page_available", ctypes.c_ulonglong),
                    ("virtual_total", ctypes.c_ulonglong), ("virtual_available", ctypes.c_ulonglong),
                    ("extended", ctypes.c_ulonglong)]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise InstallError("Windows could not report available memory.")
    return status.total, status.available


def hardware():
    total, available = memory()
    gpus = []
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                                 "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                                capture_output=True, text=True, timeout=20, creationflags=FLAGS)
        if result.returncode == 0:
            gpus = result.stdout.strip().splitlines()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"windows": platform.platform(), "cpu": platform.processor(), "logical_cores": os.cpu_count(),
            "total_ram": total, "available_ram": available, "gpus": gpus,
            "disk_free": shutil.disk_usage(ROOT).free, "backend": "cpu",
            "note": "CPU verified path; GPU acceleration is not enabled by this installer."}


def need_memory(required, can_choose_smaller=False):
    """Temporary contention does not reclassify the machine's installed hardware."""
    while True:
        total, available = memory()
        if available >= required:
            return True
        print("Installed RAM: %.1f GiB; currently available: %.1f GiB." % (total / GIB, available / GIB))
        print("This step estimates %.1f GiB of free memory. Other running apps may be using it." %
              (required / GIB))
        choices = "[R]etry after freeing memory, [T]ry anyway, "
        if can_choose_smaller:
            choices += "[S]elect smaller model, "
        choice = ask(choices + "or [C]ancel? ", "c").lower()
        if choice == "t":
            return True
        if choice == "s" and can_choose_smaller:
            return False
        if choice != "r":
            raise Cancelled("Waiting for memory cancelled. Completed work is preserved.")


def snapshot(path):
    return path.read_bytes() if path.exists() else None


def ensure_app_closed(values):
    from app import config
    port = values.get("web_port", config.WEB_PORT)
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise InstallError("Existing web port setting is invalid; settings were preserved.")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise InstallError("Port %s is in use. Close BEYOND before Setup changes libraries/settings. "
                               "No process has been stopped." % port)


def run_logged(command, label, log_path, timeout=1800):
    """Bound package work and own its children; cancellation never leaves pip running."""
    from installer.process_guard import JobProcess
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(label + ". This may take several minutes.\nLog: " + str(log_path), flush=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            with JobProcess(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, creationflags=FLAGS) as process:
                code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise InstallError(label + " timed out. Its worker was stopped. Retry when ready. See " +
                           str(log_path)) from exc
    if code:
        raise InstallError(label + " failed. Check free memory, Internet access and the log: " +
                           str(log_path) + ". Then Retry; installed packages are rechecked.")


def install_dependencies():
    check_space(ROOT, GIB)
    run_logged([sys.executable, "-I", "-m", "pip", "install", "--only-binary=:all:",
                "--disable-pip-version-check", "--quiet", "--timeout", "30", "--retries", "2",
                "-r", str(ROOT / "requirements-text-lock.txt")],
               "Install text-chat libraries", ROOT / "data/setup/libraries.log")
    run_logged([sys.executable, "-I", "-m", "pip", "check"],
               "Check library compatibility", ROOT / "data/setup/libraries-check.log", timeout=120)


def check_runtime():
    """Start the app against disposable stores, never the person's real data."""
    data = Path(tempfile.mkdtemp(prefix="beyond runtime check "))
    code = (
        "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from app import config; config.DATA_DIR=Path(sys.argv[2]); "
        "config.MODELS_DIR=config.DATA_DIR/'models'; "
        "from app import settings; settings.FILE=config.DATA_DIR/'settings.json'; "
        "settings.save(dict(engine_enabled=False,auto_lookup=False)); "
        "import pystray; from app.server import app; "
        "from fastapi.testclient import TestClient; "
        "client=TestClient(app,client=('127.0.0.1',50000)); "
        "client.__enter__(); response=client.get('/api/health'); "
        "assert response.status_code==200 and response.json()['status']=='ok'; "
        "client.__exit__(None,None,None)"
    )
    log = ROOT / "data" / "setup" / "app-test.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT), str(data)],
                                    cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=120, creationflags=FLAGS)
        if result.returncode:
            raise InstallError("Text-chat app startup failed. See " + str(log))
    finally:
        shutil.rmtree(data, ignore_errors=True)


def model_choice(manifest, values, selection=None, custom=None):
    if custom:
        path = Path(custom).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".gguf":
            raise InstallError("Choose an existing .gguf file.")
        return None, path
    if selection:
        return selection, None
    existing = values.get("engine_model", "")
    if existing and Path(existing).is_file() and confirm("Reuse the currently configured model " + Path(existing).name + "?"):
        return None, Path(existing).resolve()
    total, _ = memory()
    recommended = "starter" if total >= 8 * GIB else "fallback"
    print("\n1. Qwen3 1.7B Q8_0: 1.71 GiB, better basic answers")
    print("2. Qwen3 0.6B Q8_0: 610 MiB (639 MB), smaller with simpler answers")
    print("3. Choose a model already on this PC")
    print("Recommended for installed RAM: " + recommended + ". Both use the CPU.")
    selected = ask("Choose 1, 2 or 3 [recommended]: ", "1" if recommended == "starter" else "2")
    if selected == "3":
        return model_choice(manifest, values, custom=ask("Full path to .gguf: ").strip('"'))
    if selected not in ("1", "2"):
        raise InstallError("Choose 1, 2 or 3.")
    return ("starter" if selected == "1" else "fallback"), None


def get_model(asset):
    from app import config
    for path in config.MODELS_DIR.rglob(asset["file"]) if config.MODELS_DIR.exists() else []:
        if verified(path, asset):
            print("Reusing verified model: " + str(path))
            return path.resolve()
    print("%s; %.0f MiB; %s\nLicense: %s" %
          (asset["name"], asset["size"] / MIB, asset["license"], asset["license_url"]))
    if not confirm("Download this model from Hugging Face?"):
        raise Cancelled("Model download cancelled.")
    return retry_step("Download model", lambda: download(
        asset, config.MODELS_DIR / asset["repo"].replace("/", "--") / asset["file"]))


def request_json(url, payload=None, timeout=5):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    # Local compatibility checks must never follow system proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read(1024 * 1024))


def test_chat(executable, model, threads, context, log_path, timeout=300):
    """Own subprocess only: no app watcher/PID files/settings edits."""
    from app import builtin_engine, config
    with model.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise InstallError("Selected model is not a GGUF file.")
    values = {**config.DEFAULTS, "engine_executable": str(executable), "engine_model": str(model),
              "engine_threads": threads, "engine_context": context, "engine_cache": "f16",
              "engine_thinking": False}
    port = builtin_engine.free_port()
    url = "http://127.0.0.1:%d" % port
    process = None
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(builtin_engine.command(values, port), cwd=executable.parent,
                                       stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       creationflags=FLAGS, env={**os.environ, "CUDA_VISIBLE_DEVICES": "-1"})
            print("Loading model on the CPU; this can take several minutes...", flush=True)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    if process.returncode in (-1073741795, 3221225501):
                        raise InstallError("This engine build requires CPU instructions unavailable on this PC. "
                                           "A compatible engine build is needed; a smaller model will not fix it.")
                    raise InstallError("Engine stopped while loading. See " + str(log_path))
                try:
                    request_json(url + "/health", timeout=3)
                    break
                except (OSError, ValueError):
                    time.sleep(.5)
            else:
                raise InstallError("Model loading timed out; it may need more free memory. See " + str(log_path))
            print("Generating a short test reply...", flush=True)
            answer = request_json(url + "/v1/chat/completions", {
                "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
                "max_tokens": 48, "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False}}, timeout=timeout)
            choices = answer.get("choices") if isinstance(answer, dict) else None
            content = (choices[0].get("message", {}).get("content", "")
                       if isinstance(choices, list) and choices and isinstance(choices[0], dict) else "")
            if not isinstance(content, str) or not content.strip():
                raise InstallError("Engine returned no usable test reply. See " + str(log_path))
            print("Chat test passed: " + content.strip()[:200], flush=True)
    except (OSError, ValueError, InstallError) as exc:
        try:
            with log_path.open("rb") as stream:
                stream.seek(max(0, log_path.stat().st_size - 8192))
                tail = stream.read(8192).decode("utf-8", errors="replace")
            if re.search(r"out of memory|failed to allocate|bad_alloc|not enough memory|cannot allocate", tail, re.I):
                raise ResourceError("The engine reported insufficient memory. " + str(exc)) from exc
        except OSError:
            pass
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    return values


def verify_model(executable, model, threads, context, choice, manifest, log_path):
    while True:
        need_memory(int(model.stat().st_size * 1.5) + GIB)
        try:
            tested = test_chat(executable, model, threads, context, log_path)
            return tested, model, context
        except (OSError, ValueError, InstallError) as exc:
            log_event("Chat compatibility: " + str(exc))
            print("Chat test needs attention: " + str(exc))
            resource = isinstance(exc, ResourceError)
            options = "[R]etry after checking memory"
            if resource and context > 1024:
                options += ", [L]ower context"
            if resource and choice == "starter":
                options += ", [S]elect the smaller model"
            selected = ask(options + ", or [C]ancel? ", "c").lower()
            if selected == "r":
                continue
            if selected == "l" and resource and context > 1024:
                context = 1024
                continue
            if selected == "s" and resource and choice == "starter":
                choice = "fallback"
                model = get_model(manifest["models"]["fallback"])
                context = 1024
                continue
            raise Cancelled("Chat test cancelled. Completed downloads are preserved.") from exc


def save_configuration(changes, initial):
    from app import settings
    if snapshot(settings.FILE) != initial:
        raise InstallError("Settings changed during Setup. They were not overwritten; rerun Setup.")
    settings.validate(changes)
    if initial is not None:
        backup = ROOT / "data" / "setup" / ("settings-before-%d.json" % time.time_ns())
        backup.write_bytes(initial)
    return settings.save(changes)


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def finish(values):
    from app import config
    if confirm("Create a BEYOND desktop shortcut?"):
        pythonw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        script = ("$w=New-Object -ComObject WScript.Shell; "
                  "$p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'BEYOND.lnk'; "
                  "if (Test-Path -LiteralPath $p) { throw 'Desktop shortcut exists; left untouched.' }; "
                  "$s=$w.CreateShortcut($p); $s.TargetPath=" + ps_quote(pythonw) + "; "
                  "$s.Arguments=" + ps_quote('"' + str(ROOT / "beyond.py") + '"') + "; "
                  "$s.WorkingDirectory=" + ps_quote(ROOT) + "; $s.Save()")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], creationflags=FLAGS)
        if result.returncode:
            print("Chat setup succeeded, but the shortcut was not created.")
    if confirm("Open BEYOND now?"):
        subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "pythonw.exe"), str(ROOT / "beyond.py")],
                         cwd=ROOT, creationflags=FLAGS)
        print("BEYOND is starting. Use its tray icon to open the chat.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only hardware/preflight report.")
    models = parser.add_mutually_exclusive_group()
    models.add_argument("--model", choices=("starter", "fallback"))
    models.add_argument("--model-path")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    if os.name != "nt" or sys.version_info[:2] != (3, 14) or struct.calcsize("P") != 8:
        raise InstallError("Use Setup.cmd with 64-bit Windows Python 3.14.")
    sys.path.insert(0, str(ROOT))
    from app import config
    saved_path = config.DATA_DIR / "settings.json"
    initial = snapshot(saved_path)
    try:
        raw = json.loads(initial.decode("utf-8-sig")) if initial else {}
        if not isinstance(raw, dict):
            raise ValueError("Expected a settings object.")
    except (ValueError, UnicodeError) as exc:
        raise InstallError("Existing settings cannot be read. Preserved; repair them before Setup.") from exc
    info = hardware()
    print("Text-only setup: CPU mode. Installed RAM %.1f GiB; available %.1f GiB; free disk %.1f GiB." %
          (info["total_ram"] / GIB, info["available_ram"] / GIB, info["disk_free"] / GIB))
    if args.check:
        print(json.dumps(info, indent=2))
        return 0
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise InstallError("Run this installer through Setup.cmd so it uses BEYOND's isolated environment.")
    if not confirm("Install/update text-chat libraries and prepare a verified CPU engine and model?"):
        raise Cancelled("Setup cancelled.")
    state_dir = config.DATA_DIR / "setup"
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "install.lock").open("a+b") as lock:
        import msvcrt
        lock.seek(0)
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise InstallError("Another setup is running. Wait and rerun Setup.") from exc
        try:
            atomic_json(state_dir / "hardware.json", info)
            retry_step("Check BEYOND is closed", lambda: ensure_app_closed(raw))
            need_memory(GIB)
            retry_step("Install text-chat libraries", install_dependencies)
            retry_step("Check text-chat app startup", check_runtime)
            from app import settings
            values = settings.load()
            manifest = json.loads((Path(__file__).parent / "assets.json").read_text(encoding="utf-8"))
            choice, model = retry_step("Choose a chat model", lambda: model_choice(
                manifest, values, args.model, args.model_path))
            if choice:
                required = manifest["models"][choice]["ram_gib"] * GIB
                if not need_memory(required, choice == "starter"):
                    choice = "fallback"
                    need_memory(manifest["models"][choice]["ram_gib"] * GIB)
                model = get_model(manifest["models"][choice])
            else:
                need_memory(int(model.stat().st_size * 1.5) + GIB)
            print("Engine: %s (%s). License: %s" %
                  (manifest["engine"]["name"], manifest["engine"]["license"], manifest["engine"]["license_url"]))
            archive = retry_step("Download/verify CPU engine", lambda: download(
                manifest["engine"], state_dir / "downloads" / manifest["engine"]["file"]))
            executable = retry_step("Extract/verify engine files", lambda: extract_engine(
                archive, state_dir / "engines" / "b9668" / "cpu"))
            threads = max(1, min(8, (os.cpu_count() or 2) // 2))
            context = 2048
            if choice is None and str(model) == str(values.get("engine_model")):
                threads, context = values["engine_threads"], min(values["engine_context"], 4096)
            tested, model, context = verify_model(executable, model, threads, context, choice,
                                                   manifest, state_dir / "chat-test.log")
            changes = {key: tested[key] for key in ("engine_executable", "engine_model", "engine_threads",
                                                   "engine_context", "engine_cache", "engine_thinking")}
            # Existing external server connections are never silently replaced.
            use_builtin = values["ai_mode"] != "server" or confirm(
                "Text chat passed. Switch from your existing external server to this built-in model?")
            if use_builtin:
                changes.update(ai_mode="builtin", engine_enabled=True)
            else:
                changes = {}  # Preserve the active external configuration and all its profiles.
            retry_step("Save verified settings", lambda: ensure_app_closed(raw))
            if changes:
                save_configuration(changes, initial)
            atomic_json(state_dir / "result.json", {"status": "passed", "time": time.time(),
                        "model": str(model), "engine": str(executable), "backend": "cpu",
                        "threads": threads, "context": context, "activated": use_builtin})
            print("\nText chat compatibility passed. Existing chats and optional features are preserved.")
            finish(values)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Cancelled as exc:
        print("\n" + str(exc))
        sys.exit(0)
    except (InstallError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("\nSetup stopped: " + str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSetup cancelled. Completed downloads are preserved.")
        sys.exit(130)
