"""Bounded, cancellable local speech; native engines run in a separate CPU process."""
import io
import json
import logging
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

from app import config, settings

MAX_TEXT = 1800
MAX_AUDIO = 20 * 1024 * 1024
HELP = ('/speak reads the last AI answer in this chat. /speak <text> reads your own text (up to 1800 characters). '
        'You can also press Read aloud under an answer. Audio is made locally with Kokoro, using Piper if needed, '
        'and saved with Play controls in the chat. Long answers read their first 1800 characters. '
        'Enable Spoken replies and select your voice files in Settings first. Read answers aloud automatically '
        'is optional and off by default; a browser may ask you to press Play before it allows automatic playback.')


class SpeechError(RuntimeError):
    pass


def clean(text):
    text = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', text)
    text = text.replace('**', '').replace('`', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    text = ' '.join(text.split())
    truncated = len(text) > MAX_TEXT
    text = text[:MAX_TEXT]
    if not text:
        raise SpeechError('There is no text to read aloud.')
    return text, truncated


def configuration():
    values = settings.load()
    if not values['speech_enabled']:
        raise SpeechError('Spoken replies are off. Enable them in Settings under Spoken replies.')
    kokoro = all(values[k] and Path(values[k]).is_file()
                 for k in ('speech_kokoro_model', 'speech_kokoro_voices'))
    piper = bool(values['speech_piper_model'] and Path(values['speech_piper_model']).is_file()
                 and Path(values['speech_piper_model'] + '.json').is_file())
    if not piper and (values['speech_engine'] == 'piper' or not kokoro):
        raise SpeechError('No usable speech voice files are configured. Check Spoken replies in Settings.')
    return values


def validate_wav(data):
    if not data or len(data) > MAX_AUDIO:
        raise SpeechError('The speech engine returned an invalid audio size.')
    try:
        with wave.open(io.BytesIO(data), 'rb') as wav:
            if (wav.getnchannels() not in (1, 2) or wav.getsampwidth() != 2 or
                    not 8000 <= wav.getframerate() <= 96000 or wav.getnframes() < 1 or
                    wav.getnframes() / wav.getframerate() > 600):
                raise SpeechError('The speech engine returned unsupported audio.')
            expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            if len(wav.readframes(wav.getnframes())) != expected:
                raise SpeechError('The speech engine returned incomplete audio.')
    except (wave.Error, EOFError) as exc:
        raise SpeechError('The speech engine returned unreadable audio.') from exc


def synthesize(text, values, stop=None):
    stop = stop or threading.Event()
    if stop.is_set():
        raise SpeechError('Speech was interrupted when BEYOND stopped. Press Read aloud to try again.')
    with tempfile.TemporaryDirectory(prefix='beyond-speech-') as folder:
        output = Path(folder) / 'speech.wav'
        started = time.monotonic()
        try:
            executable = Path(sys.executable)
            if executable.name.lower() == 'pythonw.exe':
                executable = executable.with_name('python.exe')
            process = subprocess.Popen([str(executable), '-m', 'app.tools.speech_worker', str(output)],
                cwd=config.ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0) |
                               getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)))
        except OSError as exc:
            raise SpeechError('The local speech process could not start.') from exc
        payload = json.dumps({'text': text, 'settings': {k: v for k, v in values.items()
                                                      if k.startswith('speech_')}}, ensure_ascii=True)
        try:
            while True:
                if stop.is_set():
                    raise SpeechError('Speech was interrupted when BEYOND stopped. Press Read aloud to try again.')
                if time.monotonic() - started > values['speech_timeout']:
                    raise SpeechError('Speech took too long. Try shorter text or the Piper voice in Settings.')
                try:
                    stdout, stderr = process.communicate(input=payload, timeout=.5)
                    break
                except subprocess.TimeoutExpired:
                    payload = None   # communicate resumes sending any remaining input itself
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        if process.returncode != 0 or not output.is_file():
            logging.error('Speech worker failed (%s): %s', process.returncode, stderr[-1500:])
            raise SpeechError('Speech could not be generated. Check voice files and dependencies in Settings.')
        if output.stat().st_size > MAX_AUDIO:
            raise SpeechError('The speech output was too large.')
        audio = output.read_bytes()
        validate_wav(audio)
        try:
            info = json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
            engine = info['engine']
            if engine not in ('kokoro', 'piper'):
                raise ValueError('engine')
        except (OSError, ValueError, KeyError) as exc:
            raise SpeechError('The speech process returned an invalid result.') from exc
        label = 'Kokoro' if engine == 'kokoro' else ('Piper fallback' if info.get('fallback') else 'Piper')
        return audio, label
