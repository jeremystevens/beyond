"""/qr: a scannable QR code for a link, a Wi-Fi network, or any text (offline, with the segno package).
Ported from PromptetheusBot.

Wi-Fi codes use segno's helper, which escapes special characters in names and passwords. The password is never
shown in the reply, and BEYOND saves the /qr wifi message itself with the password hidden.
"""
import base64
import io
import re

import segno
import segno.helpers

MAX_TEXT = 1000
MIN_PIXELS = 480
USAGE = ('🔳 /qr https://example.com — a link (example.com works too)\n'
         '/qr any text you like — plain text\n'
         '/qr wifi Network Name | password — join Wi-Fi by scanning\n'
         '   add "| WEP" for old routers, or leave out the password for an open network\n'
         f'Up to {MAX_TEXT:,} characters.')
DOMAIN_RE = re.compile(r'^(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:[/:?#]\S*)?$', re.I)
WIFI_RE = re.compile(r'^(?:wi-?fi|wlan)\b[:\s]*(.*)$', re.I | re.S)


class QRError(ValueError):
    """A problem with what was typed, explained in plain words."""


def _png(code):
    scale = max(4, -(-MIN_PIXELS // (code.symbol_size(scale=1, border=4)[0])))  # ceil division
    out = io.BytesIO()
    code.save(out, kind='png', scale=scale, border=4, dark='#000000', light='#ffffff')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


def _wifi(rest):
    # Only "|" separates fields: network names and passwords may contain ";" or ":".
    parts = [p.strip() for p in rest.split('|')]
    ssid = parts[0] if parts else ''
    if not ssid:
        raise QRError('Add the network name: /qr wifi Network Name | password')
    password = parts[1] if len(parts) > 1 else ''
    security = parts[2].upper() if len(parts) > 2 and parts[2] else 'WPA'
    if password.lower() in ('open', 'none', 'nopass', 'no password') or security in ('OPEN', 'NONE', 'NOPASS'):
        password = ''
    if not password:
        security = 'nopass'
    elif security.startswith('WPA'):
        security = 'WPA'
    elif security != 'WEP':
        raise QRError('Security must be WPA (default), WEP, or open.')
    if len(ssid) > 32:
        raise QRError('Wi-Fi network names are at most 32 characters.')
    if security == 'WPA' and not 8 <= len(password) <= 63:
        raise QRError('WPA passwords are 8–63 characters. Check the password, or add "| WEP" for an old router.')
    code = segno.helpers.make_wifi(ssid=ssid, password=password or None,
                                   security=None if security == 'nopass' else security, hidden=False)
    shown = '•' * min(len(password), 10) if password else 'none (open network)'
    caption = (f'📶 Wi-Fi QR code\nNetwork: {ssid}\nPassword: {shown}\nSecurity: '
               f"{'open' if security == 'nopass' else security}\n\nScan it with a phone camera to join.")
    return _png(code), caption


def make_qr(text):
    """(PNG as a data: URL, caption). Raises QRError."""
    text = (text or '').strip()
    if not text:
        raise QRError(USAGE)
    if len(text) > MAX_TEXT:
        raise QRError(f'Please keep QR content under {MAX_TEXT:,} characters ({len(text):,} sent) '
                      'so the code stays easy to scan.')
    match = WIFI_RE.match(text)
    if match:
        return _wifi(match.group(1))
    kind, note = 'text', ''
    if re.match(r'^https?://\S+$', text, re.I):
        kind = 'url'
    elif DOMAIN_RE.match(text):
        text, kind, note = 'https://' + text, 'url', ' (https:// added)'
    code = segno.make(text, error='m', boost_error=True)
    preview = text if len(text) <= 200 else text[:200] + '…'
    return _png(code), f'🔳 QR code · {"🔗 Link" if kind == "url" else "📝 Text"}{note}\n{preview}'


def safe_command(text):
    """How the /qr message is saved in the chat: a Wi-Fi password is replaced by dots."""
    match = WIFI_RE.match(text.strip())
    if not match:
        return None
    parts = match.group(1).split('|')
    if len(parts) > 1 and parts[1].strip():
        parts[1] = ' •••••••• '
    return '/qr wifi ' + '|'.join(parts).strip()
