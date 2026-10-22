"""First-run guide: reuse setup choices, explicit CPU presets and a bounded AI check."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import threading
import time

import psutil

from app import builtin_engine, config, engine, settings

_operation = threading.Lock()
TEST_TIMEOUT = 90
TEST_KEYS = ("ai_mode", "ai_server_url", "ai_model", "engine_enabled", *builtin_engine.SETTING_KEYS)


class WelcomeError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def _file():
    return config.DATA_DIR / "welcome.json"


def _read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(value):
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    try:
        temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def signature(values):
    payload = {key: values[key] for key in TEST_KEYS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def configured(values):
    return bool(values["ai_server_url"] if values["ai_mode"] == "server" else
                values["engine_executable"] and values["engine_model"])


def should_offer():
    state = _read(_file())
    if state.get("status") in ("completed", "skipped"):
        return False
    result = _read(config.DATA_DIR / "setup/result.json")
    return bool(state.get("status") == "pending" or result.get("welcome_pending") or
                not configured(settings.load()))


def passed(state, values):
    tested = state.get("tested_at")
    return (state.get("tested_configuration") == signature(values)
            and isinstance(tested, (int, float)) and not isinstance(tested, bool)
            and 0 <= time.time() - tested < 86400)


def view():
    values = settings.load()
    ram = psutil.virtual_memory()
    cores = os.cpu_count() or 2
    state = _read(_file())
    return {
        "offer": should_offer(), "tested": passed(state, values),
        "mode": values["ai_mode"], "configured": configured(values),
        "model": Path(values["engine_model"]).name if values["ai_mode"] == "builtin" else
                 (values["ai_model"] or "Your existing AI server"),
        "hardware": {"total_ram": ram.total, "available_ram": ram.available, "cores": cores},
        "current": {key: values[key] for key in settings.PROFILE_KEYS},
        "recommended": {"threads": max(1, min(8, cores // 2)), "context": 2048},
        "gpu_supported": False,
    }


def apply_preset(preset):
    if preset not in ("keep", "light", "balanced"):
        raise WelcomeError("Choose Keep current, Lighter, or Balanced.", 400)
    if not _operation.acquire(blocking=False):
        raise WelcomeError("A welcome test is running. Wait for its result before changing the preset.")
    try:
        with builtin_engine.control_lock:
            values = settings.load()
            if preset == "keep":
                return view()
            if values["ai_mode"] != "builtin":
                raise WelcomeError("Your existing AI server controls its own hardware settings. Keep current.")
            if not configured(values):
                raise WelcomeError("Run Setup.cmd or choose an engine and model in Settings first.")
            if builtin_engine.busy():
                raise WelcomeError("The AI is answering another request. Try again when it finishes.")
            cores = os.cpu_count() or 2
            changes = {
                "engine_threads": max(1, min(4 if preset == "light" else 8, cores // 2)),
                "engine_context": 1024 if preset == "light" else 2048,
                "engine_cache": "f16", "engine_thinking": False,
            }
            settings.save(changes)
            state = _read(_file())
            state.pop("tested_at", None)
            state.pop("tested_configuration", None)
            _save(state)
        return view()
    finally:
        _operation.release()


async def test_ai():
    if not _operation.acquire(blocking=False):
        raise WelcomeError("A welcome test is already running. Wait for its result.")
    try:
        values = settings.load()
        before = signature(values)
        if not configured(values):
            raise WelcomeError("Run Setup.cmd or configure your AI in Settings, then try again.")
        if builtin_engine.busy():
            raise WelcomeError("The AI is already in use. Try again when the current request finishes.")
        state = _read(_file())
        state.pop("tested_at", None)
        state.pop("tested_configuration", None)
        _save(state)  # A failed retest must not leave an earlier success looking current.
        status = await engine.status()
        if status.get("state") not in ("ok", "ready"):
            raise WelcomeError("The AI is not ready yet. If the model is loading, wait and retry. "
                               "Otherwise check Models or Settings.")
        try:
            reply = await asyncio.wait_for(engine.complete(
                [{"role": "user", "content": "Say hello in one short sentence."}],
                max_tokens=48, temperature=0), timeout=TEST_TIMEOUT)
        except TimeoutError as exc:
            raise WelcomeError("The test timed out. The model may need more time or free memory. "
                               "Retry later or choose Lighter; no apps were stopped.", 504) from exc
        except engine.EngineError as exc:
            raise WelcomeError(str(exc), 502) from exc
        if not isinstance(reply, str) or not reply.strip():
            raise WelcomeError("The AI returned no text. Check the model and try again.", 502)
        if signature(settings.load()) != before:
            raise WelcomeError("AI settings changed during the test. Test the current configuration again.")
        state = _read(_file())
        state.update(tested_configuration=before, tested_at=time.time())
        _save(state)
        return {"ok": True, "reply": reply.strip()[:500]}
    finally:
        _operation.release()


def finish(skip=False):
    if not _operation.acquire(blocking=False):
        raise WelcomeError("Wait for the current welcome test to finish.")
    try:
        state = _read(_file())
        if not skip and not passed(state, settings.load()):
            raise WelcomeError("Test the current AI configuration before finishing, or choose Set up later.")
        state.update(status="skipped" if skip else "completed", finished_at=time.time())
        _save(state)
        return {"ok": True}
    finally:
        _operation.release()
