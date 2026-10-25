"""On-demand host report. No model inference, downloads or GPU initialization."""
import asyncio
import csv
import io
import platform
import shutil
import subprocess
import time
from pathlib import PureWindowsPath

import psutil
from app import config, diagnostics, engine


def gpu_status():
    executable = shutil.which('nvidia-smi')
    if not executable:
        return 'GPU: live metrics unavailable (optional NVIDIA tool not installed).'
    try:
        result = subprocess.run([executable,
            '--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total',
            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=2,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
        lines = []
        for row in list(csv.reader(io.StringIO(result.stdout)))[:8]:
            if len(row) == 5:
                name, load, temperature, used, total = [cell.strip() for cell in row]
                lines.append(f'GPU ({name}): {load}% load | {temperature}°C | VRAM {used}/{total} MiB')
        return '\n'.join(lines) or 'GPU: live metrics unavailable.'
    except (OSError, subprocess.SubprocessError):
        return 'GPU: live metrics unavailable.'


def report(args=''):
    if args:
        return 'Use /status with no arguments to check the computer running BEYOND.'
    system = diagnostics.system_status()
    gib = 1024**3
    minutes = max(0, int(time.time() - psutil.boot_time()) // 60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    ai = asyncio.run(engine.status())
    state = ai.get('state', 'unknown')
    name = PureWindowsPath(str(ai.get('model') or '')).name
    model = (f'{"Loaded model" if ai.get("builtin") else "Selected server model"}: {name}' if state == 'ok' else
             f'Configured model: {name} (not confirmed loaded)') if name else 'Model: not confirmed'
    return '\n'.join([
        f'BEYOND — {platform.system()} host status',
        f"CPU: {system['cpu_percent']:.0f}%",
        f"RAM: {system['memory_percent']:.0f}% ({(system['memory_total']-system['memory_available'])/gib:.1f} / {system['memory_total']/gib:.1f} GiB; {system['memory_available']/gib:.1f} GiB available)",
        f"BEYOND drive ({config.ROOT.anchor}): {system['disk_percent']:.0f}% used ({system['disk_free']/gib:.1f} GiB free)",
        f'System uptime: {days}d {hours}h {minutes}m', gpu_status(),
        f'AI connection: {state}', model,
        'Snapshot of the computer running BEYOND, not the device viewing this chat.'])


def is_model_question(text):
    """Narrow whole-message matches: never intercept writing/code/model advice requests."""
    import re
    text = re.sub(r"[^a-z0-9' ]", ' ', text.lower())
    text = ' '.join(text.split())
    text = re.sub(r'^(?:please |can you tell me |could you tell me |tell me )', '', text)
    return bool(re.fullmatch(
        r"(?:(?:what|which) (?:ai |llm |language )?model (?:are you (?:currently )?(?:running|using)|"
        r"is (?:currently )?(?:loaded|running)|(?:do you|does beyond) use)|"
        r"what (?:llm|language model) are you(?: currently)? (?:running|using)|"
        r"what is (?:your|the current) (?:ai |language )?model)", text))


def model_report(args=''):
    if args:
        return 'Use /model with no arguments to see the active model.'
    ai = asyncio.run(engine.status())
    name = PureWindowsPath(str(ai.get('model') or '')).name
    if ai.get('state') == 'ok':
        label = 'Currently loaded model' if ai.get('builtin') else 'Selected model on the connected AI server'
        return f'{label}: {name or "server default (name not reported)"}.'
    return (f"AI engine: {ai.get('state', 'unknown')}. No model is confirmed loaded." +
            (f' Configured model: {name}.' if name else ''))
