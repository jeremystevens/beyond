"""Sign-in for other devices (Phase 38), with a separate administrator sign-in.

The PC BEYOND runs on never needs to sign in, and can change everything. Every other device (a phone or laptop on
your network, or over the internet) signs in before it can open a page or use the API, unless "Require other
devices to sign in" is switched off in Settings. There are two passwords:

- the **sign-in password**, for people who use BEYOND: chat, house rules, persona, models and so on;
- the **administrator password**, for changing what otherwise only this PC can: Settings, model downloads and file
  paths, and the sign-in itself. An administrator device can do everything this PC can.

The two passwords must differ. Neither is stored, only a salted scrypt hash of each. A sign-in gives the device a
random session key in an HttpOnly cookie; only a SHA-256 of that key is saved, in data/auth.json, so a copy of the
file can't be used to sign in. Wrong passwords are slowed down per device address. Signed-in devices are listed in
Settings, each with Sign out. Changing or removing a password signs out the devices that used it.
"""
import hashlib
import hmac
import json
import secrets
import threading
import time

from app import config

COOKIE = 'beyond_session'
MIN_LENGTH = 8
MAX_LENGTH = 200
REMEMBER_DAYS = 30            # "Keep me signed in on this device"
ADMIN_REMEMBER_DAYS = 7       # administrator sign-ins last less long
SHORT_HOURS = 12              # without "Keep me signed in"
MAX_SESSIONS = 50
SCRYPT = {'n': 2 ** 14, 'r': 8, 'p': 1, 'dklen': 32}
LOCAL_HOSTS = ('127.0.0.1', '::1', 'localhost')
ROLES = {'user': 'password', 'admin': 'admin_password'}     # role -> where its password hash is saved
NAMES = {'user': 'sign-in password', 'admin': 'administrator password'}

_lock = threading.RLock()
_failures = {}                # address -> (count, locked_until)


class AuthError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _file():
    return config.DATA_DIR / 'auth.json'


def _load():
    try:
        data = json.loads(_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    for field in ROLES.values():
        data.setdefault(field, None)
    data.setdefault('sessions', [])
    for session in data['sessions']:
        session.setdefault('role', 'user')
    return data


def _save(data):
    config.DATA_DIR.mkdir(exist_ok=True)
    temp = _file().with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=1), encoding='utf-8')
    temp.replace(_file())


def _hash_password(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, **SCRYPT).hex()


def _key_hash(key):
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def _matches(data, role, password):
    saved = data[ROLES[role]]
    if not saved or not isinstance(password, str) or len(password) > MAX_LENGTH:
        return False
    return hmac.compare_digest(_hash_password(password, bytes.fromhex(saved['salt'])), saved['hash'])


def is_local(host):
    return host in LOCAL_HOSTS


def has_password(role='user'):
    with _lock:
        return bool(_load()[ROLES[role]])


# ---------- the passwords ----------

def set_password(new, current=None, role='user'):
    """Set or change one of the two passwords. Changing it signs out the devices that signed in with it."""
    if not isinstance(new, str) or not MIN_LENGTH <= len(new) <= MAX_LENGTH:
        raise AuthError(f'Use a password of at least {MIN_LENGTH} characters.')
    if new.strip() != new or not new.strip():
        raise AuthError("The password can't start or end with a space.")
    other = 'admin' if role == 'user' else 'user'
    with _lock:
        data = _load()
        if data[ROLES[role]] and not _matches(data, role, current or ''):
            raise AuthError(f'The current {NAMES[role]} is wrong.', 403)
        if _matches(data, other, new):
            raise AuthError('Use a different password from the ' + NAMES[other] + '.')
        salt = secrets.token_bytes(16)
        data[ROLES[role]] = {'salt': salt.hex(), 'hash': _hash_password(new, salt), 'set': time.time()}
        data['sessions'] = [s for s in data['sessions'] if s['role'] != role]
        _save(data)


def remove_password(current, role='user'):
    """Remove one of the passwords and sign out the devices that used it."""
    with _lock:
        data = _load()
        if not data[ROLES[role]]:
            return
        if not _matches(data, role, current or ''):
            raise AuthError(f'The current {NAMES[role]} is wrong.', 403)
        data[ROLES[role]] = None
        data['sessions'] = [s for s in data['sessions'] if s['role'] != role]
        _save(data)


# ---------- signing in and out ----------

def _wait_for(address):
    count, until = _failures.get(address, (0, 0))
    return max(0, until - time.monotonic())


def sign_in(password, address, device='', remember=True, admin=False):
    """Check the password and start a session. Returns (key, max_age or None)."""
    role = 'admin' if admin else 'user'
    with _lock:
        wait = _wait_for(address)
        if wait:
            raise AuthError(f'Too many wrong passwords. Try again in {int(wait) + 1} seconds.', 429)
        data = _load()
        if not data[ROLES[role]]:
            raise AuthError(('No administrator password is set yet. Set one on the PC running BEYOND, in Settings → '
                             'Sign-in.') if admin else
                            'No password is set yet. On the PC running BEYOND, open Settings → Sign-in and set one.',
                            409)
        if not _matches(data, role, password):
            count = _failures.get(address, (0, 0))[0] + 1
            # A few tries are free, then each wrong one waits longer (up to 5 minutes).
            delay = 0 if count < 5 else min(300, 2 ** (count - 4) * 15)
            _failures[address] = (count, time.monotonic() + delay)
            raise AuthError('That password is wrong.', 401)
        _failures.pop(address, None)
        key = secrets.token_urlsafe(32)
        now = time.time()
        days = ADMIN_REMEMBER_DAYS if admin else REMEMBER_DAYS
        life = days * 86400 if remember else SHORT_HOURS * 3600
        data['sessions'].append({'id': secrets.token_hex(6), 'key': _key_hash(key), 'role': role,
                                 'device': device[:120], 'address': address, 'created': now, 'used': now,
                                 'expires': now + life, 'remember': remember})
        data['sessions'] = sorted(data['sessions'], key=lambda s: s['used'])[-MAX_SESSIONS:]
        _save(data)
    return key, (life if remember else None)


def check(key):
    """The session for this cookie value, or None. Keeps a remembered session alive while it's being used."""
    if not key or len(key) > 100:
        return None
    hashed = _key_hash(key)
    with _lock:
        data = _load()
        now = time.time()
        session = next((s for s in data['sessions'] if hmac.compare_digest(s['key'], hashed)), None)
        if session is None or session['expires'] < now or not data[ROLES[session['role']]]:
            return None
        if now - session['used'] > 600:   # note activity at most every ten minutes
            session['used'] = now
            if session['remember']:
                days = ADMIN_REMEMBER_DAYS if session['role'] == 'admin' else REMEMBER_DAYS
                session['expires'] = now + days * 86400
            _save(data)
        return session


def is_admin(key):
    session = check(key)
    return bool(session and session['role'] == 'admin')


def sign_out(key):
    if not key:
        return
    hashed = _key_hash(key)
    with _lock:
        data = _load()
        data['sessions'] = [s for s in data['sessions'] if not hmac.compare_digest(s['key'], hashed)]
        _save(data)


def sign_out_device(session_id):
    with _lock:
        data = _load()
        data['sessions'] = [s for s in data['sessions'] if s['id'] != session_id]
        _save(data)


def sign_out_all():
    with _lock:
        data = _load()
        data['sessions'] = []
        _save(data)


def view(current_key=None):
    """For Settings: which passwords are set, and which devices are signed in."""
    hashed = _key_hash(current_key) if current_key else None
    now = time.time()
    with _lock:
        data = _load()
    devices = [{'id': s['id'], 'device': s['device'] or 'Unknown device', 'address': s['address'], 'role': s['role'],
                'created': s['created'], 'used': s['used'], 'this': s['key'] == hashed}
               for s in sorted(data['sessions'], key=lambda s: -s['used'])
               if s['expires'] >= now and data[ROLES[s['role']]]]
    return {'password_set': bool(data['password']), 'admin_set': bool(data['admin_password']), 'devices': devices}


def device_name(user_agent):
    """A short, readable name for a browser ("Chrome on Android")."""
    ua = user_agent or ''
    system = next((name for marker, name in (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'),
                                             ('Windows', 'Windows'), ('Mac OS', 'Mac'), ('CrOS', 'Chromebook'),
                                             ('Linux', 'Linux')) if marker in ua), '')
    browser = next((name for marker, name in (('Edg/', 'Edge'), ('OPR/', 'Opera'), ('SamsungBrowser', 'Samsung Internet'),
                                              ('Firefox/', 'Firefox'), ('Chrome/', 'Chrome'), ('Safari/', 'Safari'))
                    if marker in ua), 'Browser')
    return f'{browser} on {system}' if system else browser


# ---------- which requests need a sign-in ----------

# Reachable without signing in: the sign-in page and what it needs, and the certificate download (public, and
# needed before a device trusts BEYOND's secure address).
OPEN_PATHS = {'/login', '/api/login', '/api/auth/state', '/static/style.css', '/static/app-height.js',
              '/static/auth.js', '/static/login.js', '/api/https/certificate', '/favicon.ico'}


def needs_sign_in(path):
    return path not in OPEN_PATHS


def same_site(origin, host):
    """A browser request from another website (Origin from elsewhere) is refused, whatever cookies it carries."""
    if not origin:
        return True
    return origin.split('://', 1)[-1].rstrip('/').lower() == (host or '').lower()
