"""Local text recognition, ported from PromptetheusBot's plugins/scan.py.

RapidOCR's bundled models run on the CPU. One image is read at a time; no photo or
recognized text is sent to an external service or the chat model.
"""
import io
import logging
import threading
import time
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000
MAX_SIDE = 2048
MIN_SCORE = 0.5
MAX_TEXT = 20000
HELP = ("Attach a photo with the photo button or drop it onto the chat, then choose Read text "
        "or type /scan. PNG, JPEG and WebP up to 10 MB. Printed text works best; handwriting "
        "may not read correctly. Photos and results are saved only in this chat on your PC.")
_engine = None
_lock = threading.Lock()


class ScanError(ValueError):
    """A problem with a photo, ready to show to the user."""


class ScanBusy(ScanError):
    """The local reader is already working on another photo."""


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR
        _engine = RapidOCR()
        logging.getLogger('RapidOCR').setLevel(logging.ERROR)
    return _engine


def prepare(image_bytes):
    """Validate, rotate and scale a photo; re-encode as PNG to strip metadata."""
    if not image_bytes or len(image_bytes) > MAX_PHOTO_BYTES:
        raise ScanError('Choose a photo between 1 byte and 10 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as original:
                if original.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ScanError('Choose a PNG, JPEG or WebP photo.')
                if original.width * original.height > MAX_PIXELS:
                    raise ScanError('That photo is too large. Use a photo under 25 megapixels.')
                if getattr(original, 'n_frames', 1) != 1:
                    raise ScanError('Choose a still photo rather than an animation.')
                image = ImageOps.exif_transpose(original).convert('RGBA')
                background = Image.new('RGBA', image.size, 'white')
                background.alpha_composite(image)
                image = background.convert('RGB')
                image.thumbnail((MAX_SIDE, MAX_SIDE))
                out = io.BytesIO()
                image.save(out, format='PNG')
                return out.getvalue()
    except ScanError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ScanError("That file isn't a picture I can read. Try a PNG, JPEG or WebP photo.") from exc


def group_lines(pieces):
    """Keep receipt columns together, correcting a small slope; from the bot."""
    kept = [(box, text.strip()) for box, text, score in pieces if score >= MIN_SCORE and text.strip()]
    slopes = sorted((box[1][1] - box[0][1]) / (box[1][0] - box[0][0]) for box, _ in kept
                    if box[1][0] - box[0][0] > 2 * abs(box[3][1] - box[0][1]) > 0)
    slope = slopes[len(slopes) // 2] if slopes else 0.0
    items = []
    for box, text in kept:
        xs = [point[0] for point in box]
        ys = [point[1] - slope * point[0] for point in box]
        items.append({'top': min(ys), 'bottom': max(ys), 'left': min(xs), 'right': max(xs), 'text': text})
    items.sort(key=lambda i: (i['top'] + i['bottom']) / 2)
    rows = []
    for item in items:
        middle, height = (item['top'] + item['bottom']) / 2, item['bottom'] - item['top']
        row = rows[-1] if rows else None
        if row and abs(middle - row['middle']) < 0.5 * min(height, row['height']):
            row['items'].append(item)
        else:
            rows.append({'middle': middle, 'height': height, 'items': [item]})
    lines = []
    for row in rows:
        parts = sorted(row['items'], key=lambda i: i['left'])
        line = parts[0]['text']
        for previous, part in zip(parts, parts[1:]):
            gap = part['left'] - previous['right']
            line += ('   ' if gap > 1.5 * row['height'] else ' ') + part['text']
        lines.append(line)
    return lines


def read_photo(image_bytes):
    """Return (sanitized PNG, extracted text, elapsed seconds). Call from a worker thread."""
    if not _lock.acquire(blocking=False):
        raise ScanBusy('The text reader is busy with another photo. Please try again in a moment.')
    try:
        png = prepare(image_bytes)
        started = time.monotonic()
        result = _get_engine()(png)
        pieces = list(zip(result.boxes, result.txts, result.scores)) if result.txts else []
        return png, '\n'.join(group_lines(pieces))[:MAX_TEXT], time.monotonic() - started
    finally:
        _lock.release()
