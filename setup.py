"""BEYOND setup bootstrap (Phase 39B). Standard library only; Python 3.8+."""
import argparse
import json
import os
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
EXPECTED = (3, 14)
PROBE = ("import json,sys,struct; print(json.dumps(dict("
         "executable=sys.executable,version=list(sys.version_info[:3]),"
         "bits=struct.calcsize('P')*8,prefix=sys.prefix,base=sys.base_prefix)))")


class SetupError(RuntimeError):
    pass


def banner(title="text chat"):
    try:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        art = text.split("```", 2)[1].strip()
        art.encode(sys.stdout.encoding or "ascii")
    except (OSError, IndexError, UnicodeError):
        art = "BEYOND"
    print(art)
    print("Built Entirely on Your Own Network & Device")
    print("\nSetup: " + title + "\n", flush=True)


def probe(command):
    try:
        result = subprocess.run(
            list(command) + ["-I", "-c", PROBE],
            capture_output=True, text=True, timeout=20)
        if result.returncode:
            return None
        info = json.loads(result.stdout)
        return info if isinstance(info, dict) else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def compatible(info):
    return bool(isinstance(info, dict) and info.get("version", [])[:2] == list(EXPECTED)
                and info.get("bits") == 64)


def candidates():
    yield [sys.executable]
    yield [str(ROOT / ".venv" / "Scripts" / "python.exe")]
    yield ["py", "-3.14"]
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                for tag in ("3.14", "3.14-64"):
                    try:
                        with winreg.OpenKey(hive, "Software\\Python\\PythonCore\\" + tag +
                                            "\\InstallPath", 0, winreg.KEY_READ | view) as key:
                            folder = winreg.QueryValueEx(key, "")[0]
                            yield [str(Path(folder) / "python.exe")]
                    except OSError:
                        pass
    except ImportError:
        pass
    local = os.environ.get("LOCALAPPDATA")
    if local:
        yield [str(Path(local) / "Programs" / "Python" / "Python314" / "python.exe")]
    yield ["python3.14"]
    yield ["python"]


def find_python():
    seen = set()
    for command in candidates():
        key = tuple(command)
        if key in seen:
            continue
        seen.add(key)
        resolved = shutil.which(command[0]) or command[0]
        if "\\microsoft\\windowsapps\\" in resolved.lower():
            continue
        info = probe(command)
        if compatible(info):
            return info
    return None


def environment_status(path):
    if not path.exists():
        return "missing", None
    if not (path / "pyvenv.cfg").is_file():
        return "invalid", None
    info = probe([str(path / "Scripts" / "python.exe")])
    if (compatible(info) and info.get("prefix") != info.get("base")
            and Path(info["prefix"]).resolve() == path.resolve()):
        return "ready", info
    return "invalid", info


def confirm(message, assume_yes=False):
    if assume_yes:
        return True
    try:
        return input(message + " [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def prepare_environment(path, check_only=False, assume_yes=False):
    state, info = environment_status(path)
    if state == "invalid":
        raise SetupError(
            "The existing .venv is not a valid 64-bit Python 3.14 environment. "
            "It has been left untouched. Close BEYOND and rename that folder "
            "before running Setup again; keep it until a replacement works.")
    if state == "ready":
        print("Existing Python 3.14 environment verified: " + str(path))
        return True
    if check_only:
        print("Python is ready. A new isolated .venv will be needed; no files changed.")
        return False
    if not confirm("Create BEYOND's isolated Python 3.14 environment?", assume_yes):
        print("Cancelled. No environment created.")
        return False
    try:
        path.mkdir()  # Refuse a concurrent setup instead of overwriting its environment.
        venv.EnvBuilder(with_pip=True).create(str(path))
    except (OSError, subprocess.SubprocessError) as exc:
        raise SetupError("Environment creation failed: " + str(exc) +
                         ". Any partial .venv is preserved for inspection.") from exc
    if environment_status(path)[0] != "ready":
        raise SetupError("The new environment did not pass verification. No dependencies installed.")
    result = subprocess.run([str(path / "Scripts" / "python.exe"), "-I", "-m", "pip", "--version"])
    if result.returncode:
        raise SetupError("The new environment's pip check failed. No dependencies installed.")
    print("Created and verified: " + str(path))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only Python/environment check.")
    parser.add_argument("--yes", action="store_true", help="Accept Python installation/environment creation.")
    args = parser.parse_args(argv)
    banner()
    if os.name != "nt":
        raise SetupError("This setup currently supports Windows 10/11 x64.")
    if ("ARM64" in (os.environ.get("PROCESSOR_ARCHITECTURE", ""),
                    os.environ.get("PROCESSOR_ARCHITEW6432", ""))):
        raise SetupError("This setup currently supports Intel/AMD x64 PCs.")
    if sys.getwindowsversion().major < 10:
        raise SetupError("Windows 10 or later is required.")
    if sys.version_info[:2] != EXPECTED or struct.calcsize("P") != 8:
        found = find_python()
        if found:
            print("Continuing with Python 3.14: " + found["executable"])
            return subprocess.call([found["executable"], "-I", str(ROOT / "setup.py")] +
                                   (["--check"] if args.check else []) +
                                   (["--yes"] if args.yes else []))
        if args.check:
            raise SetupError("64-bit Python 3.14 was not found. Run Setup.cmd to install it.")
        if not confirm("Python 3.14 is missing. Open the verified-download bootstrap?", args.yes):
            print("Cancelled. Existing Python installations were not changed.")
            return 0
        return subprocess.call([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(ROOT / "setup.ps1"), "-Yes"])
    print("Python " + ".".join(map(str, sys.version_info[:3])) + " (64-bit)")
    ready = prepare_environment(ROOT / ".venv", args.check, args.yes)
    sys.stdout.flush()
    if args.check:
        return subprocess.call([sys.executable, "-I", str(ROOT / "installer" / "text_setup.py"), "--check"])
    if not ready:
        return 0
    # Run in the exact isolated environment. The installer imports no app code
    # until after its own checks and never uses an unqualified pip.
    return subprocess.call([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-I",
                            str(ROOT / "installer" / "text_setup.py")])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (SetupError, OSError, subprocess.SubprocessError) as error:
        print("\nSetup needs attention: " + str(error), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSetup cancelled. Existing settings and models were preserved.")
        sys.exit(130)
