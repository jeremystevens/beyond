"""Saved facts: short things you asked BEYOND to remember (/remember my dog is named Max). They're added to every
chat, so BEYOND knows them in any conversation, new or old.

Stored in data/beyond.sqlite3. Ported from PromptetheusBot's memory_store (single user here). Facts are either typed
by you ('manual') or, from Phase 11, picked up automatically from chats ('auto').
"""
import re
from datetime import datetime, timezone

from app import chats

MAX_FACTS = 40
MAX_FACT_CHARS = 200
# Never stored as a fact, whether typed with /remember or picked up automatically.
SECRET_RE = re.compile(r'pass ?(word|code|phrase)|\bpin\b|api[ _-]?key|\btoken\b|secret|\bssn\b|social security|'
                       r'credit card|debit card|card number|\bcvv\b|routing number|account number|\biban\b|'
                       r'\d{4}[ -]?\d{4}[ -]?\d{4}|\b\d{9,}\b', re.I)
# The AI sometimes "picks up" that it found nothing ("The user's favorite color is not mentioned"): not a fact.
NON_FACT_RE = re.compile(r"\b(not (mentioned|specified|stated|given|provided|known|clear)|unknown|no (information|facts?|"
                         r"details?)|(is|are) (unspecified|unclear)|doesn'?t say|did not (say|mention)|none)\b", re.I)
FACT_FILLER = {'the', 'user', 'users', "user's", 'my', 'i', 'im', "i'm", 'is', 'am', 'are', 'a', 'an', 'has', 'have',
               'was', 'and', 'of', 'to', 'their', 'his', 'her', 'called'}


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('manual', 'auto')),
            created_at TEXT NOT NULL)''')


def clean_fact(text):
    text = re.sub(r'\s+', ' ', str(text)).strip().strip('"“”').strip()
    text = re.sub(r'^(that|to remember( that)?)\s+', '', text, flags=re.I)
    return text[:MAX_FACT_CHARS].rstrip()


def _fact_words(text):
    """Words that carry the meaning: 'My dog is named Max' and "The user's dog is named Max" match."""
    return {w for w in re.findall(r"[a-z0-9']+", text.lower().replace('’', "'")) if w not in FACT_FILLER}


def is_secret(text):
    return SECRET_RE.search(text) is not None


def all_facts():
    """Every fact, oldest first, as [{'id', 'fact', 'source', 'created_at'}]."""
    with chats.connect() as db:
        return [dict(row) for row in db.execute('SELECT id, fact, source, created_at FROM facts ORDER BY id')]


def add(text, source='manual'):
    """Save a fact. Returns (status, fact): status is 'added', 'duplicate', 'secret', 'empty' or 'full'."""
    fact = clean_fact(text)
    if len(fact) < 3:
        return 'empty', fact
    if is_secret(fact):
        return 'secret', fact
    if source == 'auto' and NON_FACT_RE.search(fact):
        return 'empty', fact
    existing = all_facts()
    words = _fact_words(fact)
    for old in existing:
        old_words = _fact_words(old['fact'])
        # Same meaning words; for picked-up facts also "mostly the same" ("works at X" vs "is a nurse at X").
        if words and (words == old_words or (source == 'auto' and len(words & old_words) >= 0.75 * len(words))):
            return 'duplicate', old['fact']
    with chats.connect() as db:
        if len(existing) >= MAX_FACTS:
            if source == 'auto':
                return 'full', fact
            # A typed /remember always fits: the oldest automatically picked-up fact makes room.
            oldest_auto = next((f['id'] for f in existing if f['source'] == 'auto'), None)
            if oldest_auto is None:
                return 'full', fact
            db.execute('DELETE FROM facts WHERE id = ?', (oldest_auto,))
        db.execute('INSERT INTO facts (fact, source, created_at) VALUES (?, ?, ?)',
                   (fact, source, datetime.now(timezone.utc).isoformat(timespec='seconds')))
    return 'added', fact


def remove(fact_id):
    """Delete one fact by its id. Returns its text, or None if it was already gone."""
    with chats.connect() as db:
        row = db.execute('SELECT fact FROM facts WHERE id = ?', (fact_id,)).fetchone()
        if row is None:
            return None
        db.execute('DELETE FROM facts WHERE id = ?', (fact_id,))
    return row['fact']


def clear():
    with chats.connect() as db:
        return db.execute('DELETE FROM facts').rowcount


def prompt_block():
    """The facts as a section for the system prompt ('' if there are none). They rarely change, so they sit at the
    start of the prompt with the personality, where the AI server can reuse them."""
    facts = all_facts()
    if not facts:
        return ''
    return ('\n\n## What You Remember About the User\n'
            '(Saved facts; "I/my" means the user. Use them naturally when relevant; a newer fact replaces an older '
            'one that conflicts.)\n' + '\n'.join(f'- [{f["created_at"][:10]}] {f["fact"]}' for f in facts))
