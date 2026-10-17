"""Saved conversations: a small SQLite database in data/beyond.sqlite3 (git-ignored, like everything in data/).

Each chat has a title and its messages. A new chat is titled from its first message; it can be renamed or deleted.
"""
import sqlite3
from datetime import datetime, timezone

from app import config

DB_PATH = config.DATA_DIR / 'beyond.sqlite3'
TITLE_LENGTH = 60


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def connect():
    config.DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('PRAGMA busy_timeout = 10000')
    return db


def initialize():
    with connect() as db:
        db.execute('PRAGMA journal_mode = WAL')   # reading the chat list while an answer is being saved
        db.execute('''CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            stopped INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, id)')
        # 'chat' = part of the conversation the AI sees; 'command' = a /command and its reply, kept in the chat for
        # you but never sent to the AI. (Added in Phase 7; older databases get the column here.)
        columns = [row['name'] for row in db.execute('PRAGMA table_info(messages)')]
        if 'kind' not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat'")


def title_from(text):
    """A chat's first title: the start of its first message, on one line."""
    title = ' '.join(text.split())
    return title if len(title) <= TITLE_LENGTH else title[:TITLE_LENGTH - 1].rstrip() + '…'


def create(first_message):
    now = _now()
    with connect() as db:
        return db.execute('INSERT INTO chats (title, created_at, updated_at) VALUES (?, ?, ?)',
                          (title_from(first_message), now, now)).lastrowid


def exists(chat_id):
    with connect() as db:
        return db.execute('SELECT 1 FROM chats WHERE id = ?', (chat_id,)).fetchone() is not None


def add_message(chat_id, role, content, stopped=False, kind='chat'):
    now = _now()
    with connect() as db:
        message_id = db.execute('INSERT INTO messages (chat_id, role, content, stopped, created_at, kind) '
                                'VALUES (?, ?, ?, ?, ?, ?)', (chat_id, role, content, int(stopped), now, kind)).lastrowid
        db.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (now, chat_id))
    return message_id


def remove_message(message_id):
    with connect() as db:
        db.execute('DELETE FROM messages WHERE id = ?', (message_id,))


def recent_messages(chat_id, limit):
    """The last `limit` conversation messages (not commands), oldest first, in the form the AI expects."""
    with connect() as db:
        rows = db.execute("SELECT role, content FROM messages WHERE chat_id = ? AND kind = 'chat' "
                          'ORDER BY id DESC LIMIT ?', (chat_id, limit)).fetchall()
    return [{'role': row['role'], 'content': row['content']} for row in reversed(rows)]


def message_count(chat_id, kind='chat'):
    """Messages in a chat: conversation messages only by default, or all of them with kind=None."""
    with connect() as db:
        if kind is None:
            return db.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,)).fetchone()[0]
        return db.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND kind = ?',
                          (chat_id, kind)).fetchone()[0]


def list_chats():
    with connect() as db:
        rows = db.execute('SELECT id, title, updated_at FROM chats ORDER BY updated_at DESC, id DESC').fetchall()
    return [dict(row) for row in rows]


def get(chat_id):
    """A chat and all its messages, or None."""
    with connect() as db:
        chat = db.execute('SELECT id, title, created_at, updated_at FROM chats WHERE id = ?', (chat_id,)).fetchone()
        if chat is None:
            return None
        messages = db.execute('SELECT role, content, stopped, created_at, kind FROM messages WHERE chat_id = ? '
                              'ORDER BY id', (chat_id,)).fetchall()
    return {**dict(chat), 'messages': [{**dict(m), 'stopped': bool(m['stopped'])} for m in messages]}


def rename(chat_id, title):
    title = ' '.join(title.split())[:200]
    if not title:
        raise ValueError('The name can\'t be empty.')
    with connect() as db:
        return db.execute('UPDATE chats SET title = ? WHERE id = ?', (title, chat_id)).rowcount > 0


def delete(chat_id):
    with connect() as db:
        return db.execute('DELETE FROM chats WHERE id = ?', (chat_id,)).rowcount > 0
