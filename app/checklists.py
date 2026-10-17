"""/list: checklists (groceries, packing, to-dos) with tap-to-check buttons. Offline, no AI. Ported from
PromptetheusBot (one user); stored in BEYOND's database.

Lists are found by name loosely: "grocery", "groceries", "my grocery list" are the same list.
"""
import re

from app import chats

MAX_LISTS = 20
MAX_ITEMS = 100
MAX_ITEM_CHARS = 100
MAX_NAME_CHARS = 30
MAX_BUTTONS = 60          # item buttons under one message; the rest are listed as text
DEFAULT_LIST = 'to-do'
HELP = ('✅ Checklists\n'
        '/list groceries add milk, eggs, bread — add items (separate with commas)\n'
        '/list groceries — show it; tap an item to check it off\n'
        '/list — all your lists\n'
        '/list add call the bank — add to your to-do list\n'
        '/list groceries remove 2 · /list groceries clear (removes checked items) · /list groceries delete')
ACTIONS = ('add', 'remove', 'clear', 'delete')


class ListError(ValueError):
    pass


connect = chats.connect   # BEYOND's database (foreign keys on, so deleting a list deletes its items)


def initialize():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
            text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_items_list ON list_items(list_id, id)')


def clean_name(name):
    name = re.sub(r'\s+', ' ', name.strip().lower())
    name = re.sub(r'^(?:my|the|our)\s+', '', name)
    name = re.sub(r'\s+(?:list|checklist)$', '', name).strip(' .!?')
    return name


def name_key(name):
    """'Groceries', 'my grocery list' -> 'grocery'; 'to do', 'todo', 'to-do' -> 'todo'."""
    key = re.sub(r'[^a-z0-9]', '', clean_name(name))
    if key.endswith('ies') and len(key) > 4:
        return key[:-3] + 'y'
    return key[:-1] if key.endswith('s') and not key.endswith('ss') and len(key) > 3 else key


def emoji(name):
    """An icon that fits the list's name."""
    key = name_key(name)
    for words, icon in ((('grocery', 'shopping', 'food', 'costco', 'target', 'store'), '🛒'),
                        (('packing', 'pack', 'trip', 'travel', 'vacation'), '🧳'),
                        (('todo', 'task', 'chore', 'errand'), '✅'), (('gift', 'christmas', 'birthday'), '🎁'),
                        (('movie', 'watch', 'show', 'book', 'read'), '🎬')):
        if any(word in key for word in words):
            return icon
    return '📋'


def find_list(name):
    key = name_key(name)
    with connect() as db:
        for list_id, list_name in db.execute('SELECT id, name FROM lists ORDER BY id'):
            if name_key(list_name) == key:
                return list_id, list_name
    return None


def get_or_create(name):
    name = clean_name(name)
    if not name:
        raise ListError('Give the list a name, e.g. /list groceries add milk')
    if len(name) > MAX_NAME_CHARS:
        raise ListError(f'Keep list names under {MAX_NAME_CHARS} characters.')
    found = find_list(name)
    if found:
        return found
    with connect() as db:
        if db.execute('SELECT COUNT(*) FROM lists').fetchone()[0] >= MAX_LISTS:
            raise ListError(f'You have {MAX_LISTS} lists already. Delete one first (/list <name> delete).')
        return db.execute('INSERT INTO lists(name) VALUES (?)', (name,)).lastrowid, name


def split_items(text, natural=False):
    """'milk, eggs; bread' -> 3 items. In plain sentences 'milk and eggs' is two items as well."""
    parts = re.split(r'\s*(?:,|;|\n|\s+and\s+|\s*&\s*)\s*' if natural else r'\s*(?:,|;|\n)\s*', text)
    items = []
    for part in parts:
        part = re.sub(r'^(?:and|some|a|an)\s+', '', part.strip(' .!-•*'), flags=re.I).strip()
        if part:
            items.append(part[:MAX_ITEM_CHARS])
    return items


def add_items(name, text, natural=False):
    """Returns (list_id, list_name, added_count, skipped_duplicates)."""
    items = split_items(text, natural)
    if not items:
        raise ListError('What should I add? Example: /list groceries add milk, eggs')
    list_id, list_name = get_or_create(name)
    with connect() as db:
        existing = {t.lower(): done for t, done in db.execute('SELECT text, done FROM list_items WHERE list_id=?', (list_id,))}
        if len(existing) + len(items) > MAX_ITEMS:
            raise ListError(f'A list can hold {MAX_ITEMS} items. Clear checked items or remove some first.')
        added = skipped = 0
        for item in items:
            if item.lower() in existing:
                if existing[item.lower()]:   # adding a checked item again un-checks it
                    db.execute('UPDATE list_items SET done=0 WHERE list_id=? AND lower(text)=?', (list_id, item.lower()))
                    added += 1
                else:
                    skipped += 1
                continue
            db.execute('INSERT INTO list_items(list_id, text) VALUES (?, ?)', (list_id, item))
            existing[item.lower()] = 0
            added += 1
    return list_id, list_name, added, skipped


def get_list(list_id):
    """(id, name) or None."""
    with connect() as db:
        row = db.execute('SELECT id, name FROM lists WHERE id=?', (list_id,)).fetchone()
    return tuple(row) if row else None


def items_of(list_id):
    """[(item_id, text, done)] unchecked first, then checked, each in the order added."""
    with connect() as db:
        return [tuple(r) for r in db.execute('SELECT id, text, done FROM list_items WHERE list_id=? ORDER BY done, id',
                                             (list_id,))]


def toggle_item(item_id):
    """Check/uncheck an item; returns its list id, or None if it's gone."""
    with connect() as db:
        row = db.execute('SELECT list_id FROM list_items WHERE id=?', (item_id,)).fetchone()
        if row:
            db.execute('UPDATE list_items SET done = 1 - done WHERE id=?', (item_id,))
    return row[0] if row else None


def remove_item(list_id, number):
    """Remove the item shown as `number` in the list; returns its text or None."""
    if not get_list(list_id):
        return None
    rows = items_of(list_id)
    if not 1 <= number <= len(rows):
        return None
    with connect() as db:
        db.execute('DELETE FROM list_items WHERE id=?', (rows[number - 1][0],))
    return rows[number - 1][1]


def clear_checked(list_id):
    if not get_list(list_id):
        return 0
    with connect() as db:
        return db.execute('DELETE FROM list_items WHERE list_id=? AND done=1', (list_id,)).rowcount


def delete_list(list_id):
    with connect() as db:
        return db.execute('DELETE FROM lists WHERE id=?', (list_id,)).rowcount


def all_lists():
    """[(list_id, name, open_count, total)]"""
    with connect() as db:
        return [tuple(r) for r in db.execute('''SELECT l.id, l.name, COALESCE(SUM(i.done = 0), 0), COUNT(i.id)
                                               FROM lists l LEFT JOIN list_items i ON i.list_id = l.id
                                               GROUP BY l.id ORDER BY l.id''')]


def parse_command(text):
    """'/list packing for japan add socks, charger' -> (name, action, rest). Name may be empty."""
    text = text.strip()
    match = re.search(r'(?:^|\s)(add|remove|clear|delete)(?:\s+(.*))?$', text, re.I | re.S)
    if not match:
        return text, 'show', ''
    name = text[:match.start()].strip()
    return name, match.group(1).lower(), (match.group(2) or '').strip()
