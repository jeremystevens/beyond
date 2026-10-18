"""Voice input: turn a recording from the page's 🎤 button into text, offline, with faster-whisper on the processor.
Ported from PromptetheusBot's voice-note transcription (same model and settings).

The browser records in its own format (WebM/Opus in Chrome and Edge, MP4/AAC in Safari); faster-whisper decodes it
with PyAV. The Whisper model is downloaded once from Hugging Face on first use (about 145 MB for "base") and then
works offline. One recording is transcribed at a time, so the PC isn't swamped; a short question takes a few seconds.
The recording is never saved: it's written to a temporary file for the decoder and deleted straight away.
"""
import os
import tempfile
import threading
import time
from functools import lru_cache

MODEL = 'base'                      # Whisper size: tiny, base, small… ("base" is what the bot uses)
MAX_RECORDING_BYTES = 10 * 1024 * 1024
MAX_TEXT = 4000
_lock = threading.Lock()


class SpeechError(ValueError):
    """A problem with the recording, explained in plain words."""


class SpeechBusy(SpeechError):
    """Another recording is being turned into text right now."""


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel
    return WhisperModel(MODEL, device='cpu', compute_type='int8')   # processor only, small and quick


def warm_up():
    """Load the model ahead of time (the first load reads ~145 MB, or downloads it once)."""
    _model()


def transcribe(audio: bytes, suffix='.webm'):
    """(text, seconds) for a recording. Raises SpeechBusy, SpeechError, or ImportError if not installed."""
    if not audio or len(audio) < 200:
        raise SpeechError("That recording was empty. Hold the 🎤 a little longer and speak, then tap it again.")
    if len(audio) > MAX_RECORDING_BYTES:
        raise SpeechError('That recording is too long. Keep it under two minutes.')
    if not _lock.acquire(blocking=False):
        raise SpeechBusy('Still turning your last recording into text. Please try again in a moment.')
    path = None
    try:
        started = time.monotonic()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            path = temp.name
            temp.write(audio)
        try:
            segments, _ = _model().transcribe(path, beam_size=5, vad_filter=True)
            text = ' '.join(segment.text.strip() for segment in segments).strip()
        except (ValueError, RuntimeError, OSError) as exc:   # e.g. a file the decoder can't read
            raise SpeechError("I couldn't read that recording. Please try again.") from exc
        return text[:MAX_TEXT], time.monotonic() - started
    finally:
        _lock.release()
        if path and os.path.exists(path):
            os.remove(path)
