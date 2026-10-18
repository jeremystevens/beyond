"""CPU DreamShaper worker, ported from PromptetheusBot's image_generation.py."""
import io
import logging
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app import settings
from app.tools.image_prompts import negative_prompt as automatic_negative

PRESETS = {
    'quick': {'label': 'Quick', 'size': 256, 'steps': 8, 'estimate': 'about 1–2 minutes'},
    'good': {'label': 'Good', 'size': 384, 'steps': 12, 'estimate': 'about 3–5 minutes'},
    'best': {'label': 'Best', 'size': 512, 'steps': 15, 'estimate': 'about 9–12 minutes'},
}
HELP = ('Type /imagine followed by a picture idea, then choose Quick, Good or Best. '
        'Quick takes about 1–2 minutes, Good about 3–5 minutes, and Best about 9–12 minutes on this PC; '
        'actual times vary. One picture is made at a time on the CPU. You can keep chatting or close '
        'the browser while it works. The finished picture stays in the chat with a Download PNG button. '
        'A popup with a preview tells you when it is ready, following your popup preferences. '
        'Use Improve prompt to expand your idea with the chat AI, review it, and edit or undo before generating. '
        'Common defects such as blur, watermarks and extra fingers are avoided automatically. '
        'The helper preserves requested styles, including monochrome and coloring-book art. '
        'First enable Picture generation in Settings and select a CPU sd-cli.exe and DreamShaper model.')
_lock = threading.Lock()


class ImagineError(RuntimeError):
    pass


def configuration():
    values = settings.load()
    if not values['image_enabled']:
        raise ImagineError('Picture generation is off. Enable it under Picture generation in Settings.')
    executable = Path(values['image_executable'])
    # This PC crashes with the Vulkan build. Only the separate CPU distribution is supported.
    if executable.name.lower() != 'sd-cli.exe' or executable.parent.name.lower() != 'cpu':
        raise ImagineError('Choose sd-cli.exe from the CPU folder, under Picture generation in Settings.')
    for key, label in [('image_executable', 'CPU picture executable'), ('image_model', 'DreamShaper model')]:
        if not values[key] or not Path(values[key]).is_file():
            raise ImagineError(f'Missing {label}. Check Picture generation in Settings.')
    return values


def reserve():
    return _lock.acquire(blocking=False)


def release():
    _lock.release()


def generate(prompt, preset, values, stop=None, *, negative_prompt=None, seed=-1):
    """Run our own bounded process; never switch or stop Studio's text model."""
    stop = stop or threading.Event()
    if stop.is_set():
        raise ImagineError('Picture generation was interrupted.')
    spec = PRESETS[preset]
    negative_prompt = automatic_negative(prompt) if negative_prompt is None else negative_prompt
    with tempfile.TemporaryDirectory(prefix='beyond-image-') as folder:
        output = Path(folder) / 'image.png'
        args = [values['image_executable'], '--model', values['image_model'], '--prompt', prompt,
                '--width', str(spec['size']), '--height', str(spec['size']), '--steps', str(spec['steps']),
                '--threads', str(values['image_threads']), '--seed', str(seed),
                '--negative-prompt', negative_prompt, '--output', str(output)]
        started = time.monotonic()
        try:
            process = subprocess.Popen(args, cwd=str(Path(values['image_executable']).parent),
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, errors='replace',
                                       creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0) |
                                                      getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)))
        except OSError as exc:
            logging.exception('Could not start the CPU image executable')
            raise ImagineError('The CPU picture process could not start. Check its executable in Settings.') from exc
        try:
            while True:
                if stop.is_set():
                    raise ImagineError('Picture generation was interrupted when BEYOND stopped. Try /imagine again.')
                if time.monotonic() - started > values['image_timeout']:
                    raise ImagineError('Picture generation timed out. Try Quick, or increase its timeout in Settings.')
                try:
                    stdout, stderr = process.communicate(timeout=.5)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        if process.returncode != 0 or not output.is_file():
            logging.error('Image process exited %s: %s', process.returncode, (stderr + stdout)[-2000:])
            raise ImagineError('The picture process failed. Check the CPU executable and DreamShaper model in Settings.')
        try:
            if output.stat().st_size > 10 * 1024 * 1024:
                raise ImagineError('The picture output was too large.')
            with Image.open(output) as image:
                if image.format != 'PNG' or image.size != (spec['size'], spec['size']):
                    raise ImagineError('The picture process returned an unexpected image.')
                clean = io.BytesIO()
                image.convert('RGB').save(clean, format='PNG')
                return clean.getvalue()
        except (OSError, UnidentifiedImageError) as exc:
            raise ImagineError('The picture process returned an unreadable image. Try /imagine again.') from exc
