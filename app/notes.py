"""/note: a simple notepad. Save short notes, list them, find them later (offline, no AI). Ported from
PromptetheusBot (one user).

Search uses SQLite full-text search (word forms and prefixes: "garag" finds "garage") with a fuzzy fallback for
typos ("grage"), plus simple date words ("today", "yesterday", "last week", "this month"). Notes stay on this PC,
in BEYOND's database. Passwords, codes, card and account numbers are refused (same rule as /remember), because
notes are stored as plain text.
"""
import difflib
import re
from datetime import datetime, timedelta, timezone

from app import chats, memory

MAX_TEXT = 1000
MAX_NOTES = 500
LIST_LIMIT = 10
FIND_LIMIT = 10
HELP = ('📝 Notepad\n'
        '/note garage code is in the blue folder — save a note\n'
        '/note find garage — search your notes (typos are OK)\n'
        '/note find yesterday · /note find last week groceries — search by date\n'
        '/notes — your 10 most recent notes (/notes garage searches)\n'
        '/note delete 12 — delete note #12 · /note clear — delete all (asks first)\n'
        '/note add find a plumber — save a note that starts with a command word\n'
        'Passwords, codes and card numbers are not saved.')
COMMAND_WORDS = {'find', 'search', 'delete', 'del', 'remove', 'clear', 'list', 'help', 'add'}
DATE_PHRASES = [  # longest first, so "last week" wins over "week"
    ('this week', 'this_week'), ('last week', 'last_week'), ('this month', 'this_month'),
    ('last month', 'last_month'), ('today', 'today'), ('yesterday', 'yesterday')]
# Also refused in notes: a code or combination written out ("garage code is 4821", "lock combo 12-34-56").
CODE_RE = re.compile(r'\b(code|combo|combination|passcode|pin)\b\D{0,20}\d{3,}', re.I)
STOP = {'the', 'a', 'an', 'my', 'about', 'note', 'notes', 'for', 'from', 'with', 'and', 'of', 'in', 'on', 'to'}


class NoteError(ValueError):
    """A problem with what was typed, explained in plain words."""


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num INTEGER NOT NULL UNIQUE,       -- the note's number (#1, #2...); never reused
            text TEXT NOT NULL,
            created_at TEXT NOT NULL)''')
        db.execute('CREATE TABLE IF NOT EXISTS note_counter (id INTEGER PRIMARY KEY CHECK (id = 1), '
                   'last_num INTEGER NOT NULL)')
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(text, content='notes', content_rowid='id', "
                   "tokenize='porter unicode61')")
        db.execute('''CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
            INSERT INTO notes_fts(rowid, text) VALUES (new.id, new.text); END''')
        db.execute('''CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, text) VALUES ('delete', old.id, old.text); END''')


def _local(created_at):
    return datetime.fromisoformat(created_at).astimezone()


def format_note(num, text, created_at):
    when = _local(created_at)
    return f'#{num} · {when:%b} {when.day}, {when:%I:%M %p}'.replace(' 0', ' ') + f'\n{text}'


def add(text):
    """Save a note; returns its number. Raises NoteError with a friendly message."""
    text = re.sub(r'[ \t]+', ' ', str(text)).strip()
    if len(text) < 2:
        raise NoteError('What should I write down? Example: /note garage code is in the blue folder')
    if len(text) > MAX_TEXT:
        raise NoteError(f'That note is too long ({len(text):,} characters). Keep notes under {MAX_TEXT:,}.')
    if memory.is_secret(text) or CODE_RE.search(text):
        raise NoteError("🔒 I don't save passwords, codes, card or account numbers in notes (they're stored as plain "
                        'text). Write down where to find it instead, like "garage code is in the blue folder".')
    with chats.connect() as db:
        if db.execute('SELECT COUNT(*) FROM notes').fetchone()[0] >= MAX_NOTES:
            raise NoteError(f'Your notepad is full ({MAX_NOTES} notes). Delete some with /note delete <number>.')
        row = db.execute('SELECT last_num FROM note_counter WHERE id = 1').fetchone()
        num = (row[0] if row else 0) + 1
        db.execute('INSERT INTO note_counter (id, last_num) VALUES (1, ?) '
                   'ON CONFLICT(id) DO UPDATE SET last_num = excluded.last_num', (num,))
        db.execute('INSERT INTO notes (num, text, created_at) VALUES (?, ?, ?)',
                   (num, text, datetime.now(timezone.utc).isoformat(timespec='seconds')))
    return num


def recent(limit=LIST_LIMIT):
    """([(num, text, created_at)] newest first, total count)."""
    with chats.connect() as db:
        rows = db.execute('SELECT num, text, created_at FROM notes ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        total = db.execute('SELECT COUNT(*) FROM notes').fetchone()[0]
    return [tuple(r) for r in rows], total


def _date_range(kind, now=None):
    """(start, end) in local time for a date word."""
    now = now or datetime.now().astimezone()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=today.weekday())   # weeks start on Monday
    month = today.replace(day=1)
    ranges = {'today': (today, today + timedelta(days=1)),
              'yesterday': (today - timedelta(days=1), today),
              'this_week': (week, week + timedelta(days=7)),
              'last_week': (week - timedelta(days=7), week),
              'this_month': (month, (month + timedelta(days=32)).replace(day=1)),
              'last_month': ((month - timedelta(days=1)).replace(day=1), month)}
    return ranges[kind]


def parse_query(query):
    """Split 'last week groceries' into (date kind or None, search words)."""
    text = ' ' + query.lower().strip() + ' '
    kind = None
    for phrase, name in DATE_PHRASES:
        if f' {phrase} ' in text:
            kind = name
            text = text.replace(f' {phrase} ', ' ', 1)
            break
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9'’-]*", text) if w not in STOP]
    return kind, list(dict.fromkeys(words))[:10]


def find(query, now=None):
    """Matching notes, best first: ([(num, text, created_at)], how), where how says whether the match was exact
    words ('words'), close spelling ('fuzzy'), or date only ('date')."""
    kind, words = parse_query(query)
    if not kind and not words:
        raise NoteError('What should I look for? Example: /note find garage')
    with chats.connect() as db:
        rows = [tuple(r) for r in db.execute('SELECT id, num, text, created_at FROM notes ORDER BY id DESC')]
        if kind:
            start, end = _date_range(kind, now)
            rows = [r for r in rows if start <= _local(r[3]) < end]
        if not words:
            return [r[1:] for r in rows[:FIND_LIMIT]], 'date'
        allowed = {r[0] for r in rows}
        # Every word must match (as a word or the start of one, any word form). Best match first.
        query_text = ' AND '.join('"' + w.replace('"', '') + '"*' for w in words)
        hits = db.execute('''SELECT n.id, n.num, n.text, n.created_at FROM notes_fts f JOIN notes n ON n.id = f.rowid
                             WHERE notes_fts MATCH ? ORDER BY bm25(notes_fts)''', (query_text,)).fetchall()
    hits = [tuple(h)[1:] for h in hits if h[0] in allowed]
    if hits:
        return hits[:FIND_LIMIT], 'words'
    # No exact match: allow small typos ("grage" -> "garage"); every search word must be close to a note word.
    scored = []
    for _, num, text, created_at in rows:
        note_words = set(re.findall(r"[a-z0-9][a-z0-9'’-]*", text.lower()))
        scores = [max((difflib.SequenceMatcher(None, w, nw).ratio() for nw in note_words), default=0) for w in words]
        if scores and min(scores) >= 0.75:
            scored.append((sum(scores), num, text, created_at))
    scored.sort(key=lambda s: -s[0])
    return [s[1:] for s in scored[:FIND_LIMIT]], 'fuzzy'


def delete(num):
    """Delete note #num; returns its text, or None if there's no such note."""
    with chats.connect() as db:
        row = db.execute('SELECT text FROM notes WHERE num = ?', (num,)).fetchone()
        if row:
            db.execute('DELETE FROM notes WHERE num = ?', (num,))
    return row[0] if row else None


def clear():
    with chats.connect() as db:
        return db.execute('DELETE FROM notes').rowcount


def count():
    with chats.connect() as db:
        return db.execute('SELECT COUNT(*) FROM notes').fetchone()[0]
