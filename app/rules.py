"""House rules: short instructions added to every chat (for example "Always answer in under 3 sentences").

Stored in data/beyond.sqlite3 next to the chats. Ported from PromptetheusBot's house rules (the link from a rule to
automatic web / weather / news lookups comes with those lookups in Phase 14).
"""
import re
from datetime import datetime, timezone

from app import chats

MAX_RULES = 25
MIN_LENGTH, MAX_LENGTH = 5, 300


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL)''')


def all_rules():
    """Every rule, oldest first, as [{'id', 'text', 'created_at'}]."""
    with chats.connect() as db:
        return [dict(row) for row in db.execute('SELECT id, text, created_at FROM rules ORDER BY id')]


def add(text):
    """Add a rule. Returns its id, or None if the same rule already exists. Raises ValueError if it can't be added."""
    text = re.sub(r'\s+', ' ', text or '').strip()
    if len(text) < MIN_LENGTH:
        raise ValueError('That rule is too short. Write it as an instruction, for example: '
                         'Always answer in under 3 sentences.')
    if len(text) > MAX_LENGTH:
        raise ValueError(f'That rule is too long (the limit is {MAX_LENGTH} characters).')
    with chats.connect() as db:
        if db.execute('SELECT 1 FROM rules WHERE lower(text) = lower(?)', (text,)).fetchone():
            return None
        if db.execute('SELECT COUNT(*) FROM rules').fetchone()[0] >= MAX_RULES:
            raise ValueError(f'There are already {MAX_RULES} rules. Remove one first.')
        return db.execute('INSERT INTO rules (text, created_at) VALUES (?, ?)',
                          (text, datetime.now(timezone.utc).isoformat(timespec='seconds'))).lastrowid


def remove(rule_id):
    with chats.connect() as db:
        return db.execute('DELETE FROM rules WHERE id = ?', (rule_id,)).rowcount > 0


def prompt_block():
    """The rules as a section for the end of the system prompt ('' if there are none). Rules rarely change, so they
    sit with the personality at the start of the prompt, where the AI server can reuse them from its cache."""
    rules = all_rules()
    if not rules:
        return ''
    return ('\n\n## House Rules\n'
            'The user set these rules. Always follow them. If one conflicts with anything above (for example the '
            'answer length or style), the rule wins.\n' + '\n'.join(f'- {rule["text"]}' for rule in rules))
