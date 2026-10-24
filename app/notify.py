"""Windows popups (notifications): one shared "notify" feature that every part of BEYOND uses.

    notify.show('reply', 'BEYOND replied', 'The weather in Paris is…', chat_id=12)

A popup is shown only when it's useful: its kind is switched on in Settings, it isn't quiet hours, popups aren't
paused from the tray icon, and you aren't looking at BEYOND's page right now (the page tells the server while it's
visible; see page_seen). Clicking a popup opens BEYOND at that chat; a popup can also have buttons (a reminder's
Done and Snooze), which call back into BEYOND while it's running.

Uses the Windows-Toasts package. BEYOND registers its own name and icon for popups under your Windows user
(HKCU\\Software\\Classes\\AppUserModelId\\BEYOND.LocalAI), which Windows needs before a popup's buttons work. On
other systems, or if anything goes wrong, popups are simply skipped (and logged).
"""
import logging
import sys
import threading
import time
import webbrowser
from datetime import datetime

from app import config, settings

APP_ID = 'BEYOND.LocalAI'
KINDS = {'reply': 'popup_replies', 'reminder': 'popup_reminders', 'briefing': 'popup_reminders',
         'error': 'popup_errors',
         'update': 'update_auto_check'}   # a new version: only found when checking is on, or after Check now
PAGE_GRACE_SECONDS = 25        # the page says "I'm visible" every 10 s; this long without word = not looking
ICON = config.DATA_DIR / 'beyond-icon.png'

paused = False                 # "Pause popups" in the tray menu (until BEYOND restarts)
base_url = 'http://127.0.0.1:7770'   # set by beyond.py to the address BEYOND is really running on
_last_seen = 0.0
_toaster = None
_lock = threading.Lock()


def page_seen(visible=True):
    """The page reports whether it's on screen (a browser tab in front, on any device)."""
    global _last_seen
    _last_seen = time.monotonic() if visible else 0.0


def watching():
    return time.monotonic() - _last_seen < PAGE_GRACE_SECONDS


def in_quiet_hours(values, now=None):
    start, end = values.get('quiet_start'), values.get('quiet_end')
    if not start or not end or start == end:
        return False
    now = (now or datetime.now()).strftime('%H:%M')
    return start <= now < end if start < end else now >= start or now < end   # e.g. 22:00–07:00 crosses midnight


def why_not(kind):
    """Why a popup of this kind wouldn't be shown right now ('' = it would)."""
    values = settings.load()
    if not values.get(KINDS[kind], True):
        return 'switched off in Settings'
    if paused:
        return 'paused from the tray icon'
    if in_quiet_hours(values):
        return 'quiet hours'
    if watching():
        return "you're looking at BEYOND's page"
    return ''


def chat_url(chat_id=None):
    return base_url + (f'/#chat={chat_id}' if chat_id else '/')


def icon_image(size=64):
    """BEYOND's icon (also used for the tray): an orange rounded square with a white B."""
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=(217, 98, 43, 255))
    try:
        font = ImageFont.truetype('segoeuib.ttf', int(size * 0.68))
    except OSError:
        font = ImageFont.load_default()
    draw.text((size / 2, size / 2), 'B', font=font, fill='white', anchor='mm')
    return image


def _register():
    """Tell Windows BEYOND's name and icon for popups (per user; needed for popup buttons to work)."""
    import winreg
    config.DATA_DIR.mkdir(exist_ok=True)
    if not ICON.exists():
        icon_image(256).save(ICON)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf'Software\Classes\AppUserModelId\{APP_ID}') as key:
        winreg.SetValueEx(key, 'DisplayName', 0, winreg.REG_SZ, 'BEYOND')
        winreg.SetValueEx(key, 'IconUri', 0, winreg.REG_SZ, str(ICON))


def _get_toaster():
    global _toaster
    with _lock:
        if _toaster is None:
            from windows_toasts import InteractableWindowsToaster
            _register()
            _toaster = InteractableWindowsToaster('BEYOND', APP_ID)
        return _toaster


def show(kind, title, body, chat_id=None, buttons=(), on_button=None, force=False, image_path=None):
    """Show a popup if it's wanted right now (or always, with force=True, for "Send a test popup").
    `buttons`: [(label, argument)]; pressing one calls on_button(argument). Clicking the popup itself opens the
    chat. Returns '' if it was shown, or why it wasn't."""
    reason = '' if force else why_not(kind)
    if reason:
        return reason
    if sys.platform != 'win32':
        return 'popups need Windows'
    threading.Thread(target=_show, args=(title, body, chat_id, list(buttons), on_button, image_path), daemon=True).start()
    return ''


def _show(title, body, chat_id, buttons, on_button, image_path=None):
    try:
        from windows_toasts import Toast, ToastButton
        toast = Toast(text_fields=[title[:120], body[:300]], launch_action=f'open:{chat_id or ""}')
        if image_path:
            try:
                from windows_toasts import ToastDisplayImage
                toast.AddImage(ToastDisplayImage.fromPath(image_path, altText='Your generated picture'))
            except Exception:
                logging.exception('Could not attach the popup preview; sending text only')
        for label, argument in buttons:
            toast.AddAction(ToastButton(label, argument))
        toast.on_activated = lambda event: _activated(getattr(event, 'arguments', '') or '', chat_id, on_button)
        _get_toaster().show_toast(toast)
    except Exception:
        logging.exception('Could not show a popup')


def _activated(argument, chat_id, on_button):
    """A popup (or one of its buttons) was clicked."""
    try:
        if argument.startswith('open:') or not argument or on_button is None:
            webbrowser.open(chat_url(chat_id))
        else:
            on_button(argument)
    except Exception:
        logging.exception('A popup click failed')
