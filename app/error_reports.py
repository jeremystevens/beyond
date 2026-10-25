"""Local, on-demand report previews. No raw logs, chat reads, model requests or external probes."""
import math
import platform
import re
import struct
import sys
from datetime import datetime

import psutil
from fastapi import HTTPException
from pydantic import BaseModel, Field, StrictBool

from app import builtin_engine, config, settings

SOURCES = {
    'chat': ('AI reply', 'An AI reply failed.'),
    'AI server': ('AI server', 'The configured AI server stopped responding.'),
    'AI engine': ('Built-in AI', 'The built-in model could not start or stopped unexpectedly.'),
    'builtin_engine': ('Built-in AI', 'The built-in engine reported an error.'),
    'server': ('App request', 'An app request or background task failed.'),
    'photo_jobs': ('Photo analysis', 'Photo analysis failed.'),
    'image_jobs': ('Picture generation', 'Picture generation failed.'),
    'speech_jobs': ('Speech generation', 'Speech generation failed.'),
    'beyond': ('Application', 'BEYOND reported an application error.'),
    'Diagnostic test': ('Diagnostic test', 'SIMULATED: an AI reply timed out. No real service failed.'),
}
STATES = {'ok', 'off', 'starting', 'stopping', 'not_set', 'error'}


class ReportNotes(BaseModel):
    model_config = {'extra': 'forbid'}
    happened: str = Field(default='', max_length=2500)
    expected: str = Field(default='', max_length=2500)
    steps: str = Field(default='', max_length=2500)
    tried: str = Field(default='', max_length=2500)
    include_environment: StrictBool = True


def redact(text):
    """Best effort for user-entered notes. The editable preview still needs the user's review."""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'(?i)\b(?:https?|ftp)://[^\s<>]+', '[URL removed]', text)
    text = re.sub(r'(?i)\bBearer\s+[^\s,;]+', 'Bearer [secret removed]', text)
    text = re.sub(r'''(?ix)(\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|password|passwd|secret|authorization|cookie)\b\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;]+)''', r'\1[secret removed]', text)
    text = re.sub(r'\b(?:sk-|gh[pousr]_)[A-Za-z0-9_-]{8,}\b', '[secret removed]', text)
    text = re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[secret removed]', text)
    text = re.sub(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email removed]', text)
    text = re.sub(r'(?i)[A-Z]:[\\/][^\r\n<>"\x27]*', '[local path removed]', text)
    text = re.sub(r'\\\\[^\s\\]+\\[^\r\n<>"\x27]*', '[network path removed]', text)
    text = re.sub(r'(?<!\w)/(?:home|Users|root|mnt|media|workspace|tmp|var|etc|opt)/[^\s<>"\x27]*', '[local path removed]', text)
    text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', '[IP address removed]', text)
    return text.strip()


def timestamp(value):
    try:
        return datetime.fromisoformat(value).isoformat(timespec='seconds')
    except (TypeError, ValueError):
        return 'Unknown'


def number(value, suffix='', scale=1):
    try:
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise ValueError()
        return f'{value/scale:.1f}{suffix}'
    except (TypeError, ValueError, OverflowError):
        return 'Unavailable'


def environment():
    """Only explicit low-cost local readings. Never use snapshot(): that probes configured servers."""
    from app import diagnostics
    values = settings.load()
    mode = 'Built-in' if values['ai_mode'] == 'builtin' else 'External server'
    ai = builtin_engine.status() if values['ai_mode'] == 'builtin' else {}
    state = ai.get('state') if ai.get('state') in STATES else 'Not checked'
    os_name = platform.system()
    if os_name not in ('Windows', 'Linux', 'Darwin'):
        os_name = 'Other'
    release = platform.release()
    release = release if re.fullmatch(r'[0-9.]{1,40}', release) else 'Version omitted'
    lines = [f'OS: {os_name} {release}',
             f'Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({struct.calcsize("P")*8}-bit)',
             f'AI mode: {mode}', f'Built-in AI state: {state}',
             'Optional features enabled: ' + ', '.join(label + (' on' if values.get(key) else ' off') for key, label in (
                 ('vision_enabled','Vision'),('image_enabled','Images'),('speech_enabled','Speech')))]
    try:
        data = diagnostics.system_status()
        lines += [f'Logical processors: {number(data["logical_cpus"])}',
                  'RAM total / available: ' + number(data['memory_total'],' GiB',1024**3) + ' / ' + number(data['memory_available'],' GiB',1024**3),
                  'Free disk on BEYOND drive: ' + number(data['disk_free'],' GiB',1024**3),
                  'App uptime: ' + number(data['app_uptime_seconds'],' seconds')]
    except (OSError, psutil.Error):
        lines.append('Current resource readings: unavailable')
    return lines


def build(error_id, notes):
    from app import diagnostics
    entry = next((item for item in diagnostics.errors(200) if item['id'] == error_id), None)
    if entry is None:
        raise HTTPException(404, 'This error is no longer in recent history. Refresh the page and choose another.')
    category, summary = SOURCES.get(entry['source'], ('App operation', 'An app operation failed.'))
    simulated = entry['source'] == 'Diagnostic test'
    version = config.VERSION if re.fullmatch(r'\d+\.\d+\.\d+', config.VERSION) else 'Unknown'
    lines = ['BEYOND local error report', '=========================',
             'SIMULATED TEST — not a real failure' if simulated else 'Recorded application error',
             f'Report generated: {diagnostics.now()}', f'BEYOND release version: {version}',
             'Code may include unreleased changes when installed from git.',
             f'Local error reference: {error_id}', f'Error recorded: {timestamp(entry["created_at"])}',
             f'Category: {category}', f'Summary: {summary}', '']
    for field, title in [('happened','What happened'),('expected','What I expected'),
                         ('steps','Steps to reproduce'),('tried','What I tried')]:
        lines += [title, '-'*len(title), redact(getattr(notes, field)) or 'Not provided.', '']
    if notes.include_environment:
        lines += ['Current app/system information', '------------------------------', *environment(),
                  'These readings describe now, not necessarily the time of the error.',
                  'External server reachability was not checked.', '']
    lines += ['Privacy and limitations', '-----------------------',
              'No chat text, raw logs, exception details, host/user names, model names, file paths, server addresses or credentials were collected automatically.',
              'Common secrets, URLs, email addresses, IP addresses and local paths in your notes were removed where recognized.',
              'Automatic redaction is best effort. Review and edit this report before sharing; later edits are exported exactly as shown.',
              'This report was prepared locally without an AI request. Nothing was sent to GitHub or uploaded.',
              'A fixed error category and current readings do not establish the exact cause.']
    return {'text': '\n'.join(lines)+'\n', 'filename': f'beyond-error-report-{error_id}.txt', 'simulated': simulated}
