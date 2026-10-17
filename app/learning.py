"""Ratings that teach BEYOND (👍 👎 🔄 under every answer). Ported from PromptetheusBot's answer_feedback (one user).

The AI model itself isn't retrained (not practical on a home PC). Instead, ratings change what the AI is told
before it answers:
1. 👎 asks why (too long, too short, wrong, not helpful, wrong tone, didn't understand me). Each reason adds a
   point to a preference; at 2 points a hint is added to every reply ("keep answers short"), and "too long" also
   sets a firm word budget. 👍 slowly fades old complaints. /learned shows them, with a reset.
2. Similar questions: an earlier answer you rated 👍 to a similar question is shown to the AI as a good example, a
   👎 one as a mistake to avoid.
Ratings are stored on the answer itself (columns rating and reason in messages); preferences in the prefs table.
"""
from datetime import datetime, timezone

from app import chats, memory

THRESHOLD = 2.0              # points before a preference is used
MAX_SCORE = 6.0
SHORT_ANSWER_TOKENS = 180    # about 120 words: the firm limit once "too long" is learned
REASONS = {   # key: (button label, preference it feeds, words for "👎 Noted: …")
    'long': ('📏 Too long', 'shorter', 'too long'),
    'short': ('🔎 Too short', 'longer', 'too short'),
    'wrong': ('❌ Wrong / made up', 'accuracy', 'wrong or made up'),
    'unhelpful': ('🤷 Not helpful', 'helpful', 'not helpful'),
    'tone': ('🎭 Wrong tone', 'tone', 'wrong tone'),
    'misread': ("🙉 Didn't understand me", 'understand', "didn't understand"),
}
HINTS = {
    'shorter': 'The user prefers short answers: usually 2–4 sentences, unless they ask for more detail.',
    'longer': ('The user likes thorough answers: several paragraphs with detail and examples, not just 2–4 '
               'sentences.'),
    'accuracy': ('The user has flagged wrong or made-up answers before: only state facts you are sure of, and say '
                 'plainly when you are not sure.'),
    'helpful': 'The user found some answers unhelpful: answer their actual question directly and practically first.',
    'tone': 'The user prefers a straightforward tone: little humour, sarcasm, or playfulness.',
    'understand': ('The user has felt misunderstood: if a request could mean different things, ask one short '
                   'clarifying question before answering.'),
}
NAMES = {   # how /learned describes each preference
    'shorter': 'shorter answers', 'longer': 'more detailed answers', 'accuracy': 'extra care with facts',
    'helpful': 'getting straight to the point', 'tone': 'a plainer tone (less joking)',
    'understand': 'asking when something is unclear',
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def initialize():
    with chats.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS prefs (key TEXT PRIMARY KEY, score REAL NOT NULL, updated TEXT NOT NULL)')


# ---------- buttons under an answer ----------

def _retry(message_id):
    return {'label': '🔄 Try again', 'action': f'rate:retry:{message_id}'}


def rating_buttons(message_id):
    return [[{'label': '👍', 'action': f'rate:up:{message_id}'}, {'label': '👎', 'action': f'rate:down:{message_id}'},
             _retry(message_id)]]


def reason_buttons(message_id, retry=True):
    reasons = [{'label': label, 'action': f'rate:why:{message_id}:{key}'} for key, (label, _, _) in REASONS.items()]
    return ([reasons[i:i + 2] for i in range(0, len(reasons), 2)] +
            [[{'label': 'Skip', 'action': f'rate:why:{message_id}:none'}] + ([_retry(message_id)] if retry else [])])


def done_buttons(label, message_id, retry=True):
    return [[{'label': label, 'action': f'rate:done:{message_id}'}] + ([_retry(message_id)] if retry else [])]


def has_retry(buttons):
    return any(b.get('action', '').startswith('rate:retry:') for row in buttons for b in row)


def without_retry(buttons):
    return [row for row in ([b for b in row if not b.get('action', '').startswith('rate:retry:')] for row in buttons)
            if row]


# ---------- ratings and preferences ----------

def _adjust(db, key, delta):
    row = db.execute('SELECT score FROM prefs WHERE key = ?', (key,)).fetchone()
    score = max(0.0, min(MAX_SCORE, (row['score'] if row else 0.0) + delta))
    db.execute('INSERT INTO prefs (key, score, updated) VALUES (?, ?, ?) ON CONFLICT(key) '
               'DO UPDATE SET score = excluded.score, updated = excluded.updated', (key, score, _now()))


def rate(message_id, rating, reason=None):
    """Record 👍 (1) or 👎 (-1, with an optional REASONS key, or 'retry' for 🔄) and update the preferences.
    The same rating twice counts once."""
    with chats.connect() as db:
        row = db.execute('SELECT rating, reason FROM messages WHERE id = ?', (message_id,)).fetchone()
        if row is None:
            return False
        db.execute('UPDATE messages SET rating = ?, reason = ? WHERE id = ?', (rating, reason, message_id))
        if rating == 1 and row['rating'] != 1:
            # a good answer: old complaints fade a little
            for (key,) in db.execute('SELECT key FROM prefs WHERE score > 0').fetchall():
                _adjust(db, key, -0.5)
        elif reason in REASONS and reason != row['reason']:
            preference = REASONS[reason][1]
            _adjust(db, preference, 1.0)
            opposite = {'shorter': 'longer', 'longer': 'shorter'}.get(preference)
            if opposite:
                _adjust(db, opposite, -1.0)
    return True


def set_rating(message_id, rating, reason):
    """Put a rating back as it was (when 🔄 Try again couldn't get a new answer). Preferences are unchanged."""
    with chats.connect() as db:
        db.execute('UPDATE messages SET rating = ?, reason = ? WHERE id = ?', (rating, reason, message_id))


def preferences():
    """{key: score} of what has been noticed so far."""
    with chats.connect() as db:
        return {row['key']: row['score'] for row in db.execute('SELECT key, score FROM prefs WHERE score > 0')}


def active():
    return [key for key, score in preferences().items() if score >= THRESHOLD and key in HINTS]


def reset():
    with chats.connect() as db:
        return db.execute('DELETE FROM prefs').rowcount


def max_tokens():
    """A firm word budget once "too long" is learned (the hint alone isn't always followed); None = the default."""
    return SHORT_ANSWER_TOKENS if 'shorter' in active() else None


# ---------- what the AI is told ----------

def _similar(question, rating, skip_ids):
    """An earlier question like this one whose answer got `rating`: (question, answer, reason) or None."""
    terms = memory.keywords(question)
    if len(terms) < 2:
        return None
    query = ' OR '.join('"' + term.replace('"', '') + '"' for term in terms)
    with chats.connect() as db:
        rows = db.execute("""SELECT m.id, m.chat_id, m.content FROM messages_fts f JOIN messages m ON m.id = f.rowid
                             WHERE messages_fts MATCH ? AND m.kind = 'chat' AND m.role = 'user'
                             ORDER BY bm25(messages_fts) LIMIT 20""", (query,)).fetchall()
        for row in rows:
            if row['id'] in skip_ids:
                continue
            if sum(memory._stem_hit(term, row['content'].lower()) for term in terms) < 2:
                continue
            # an answer to that question (the first one, or a later 🔄 one) with this rating
            answer = db.execute("""SELECT content, reason FROM messages WHERE chat_id = ? AND id > ? AND role = 'assistant'
                                   AND kind IN ('chat', 'retried') AND rating = ? AND id < COALESCE((SELECT MIN(id)
                                   FROM messages WHERE chat_id = ? AND id > ? AND role = 'user' AND kind = 'chat'),
                                   9e18) ORDER BY id LIMIT 1""",
                                (row['chat_id'], row['id'], rating, row['chat_id'], row['id'])).fetchone()
            if answer:
                return row['content'], answer['content'], answer['reason']
    return None


def prompt_block(question, skip_ids=()):
    """Notes for this reply: learned preferences, and at most one liked and one disliked earlier answer to a
    similar question ('' if there's nothing)."""
    parts = []
    learned = [HINTS[key] for key in active()]
    if learned:
        parts.append("What the user's ratings of your answers say (follow this; it overrides the usual answer length "
                     'and style):\n' +
                     '\n'.join(f'- {hint}' for hint in learned))
    good = _similar(question, 1, skip_ids)
    bad = _similar(question, -1, skip_ids)
    if good:
        parts.append('The user liked this earlier answer to a similar question; use it as a guide for style and '
                     f'accuracy, not to copy:\nQ: {good[0][:300]}\nA: {good[1][:600]}')
    if bad:
        why = 'they asked for a different answer' if bad[2] == 'retry' else \
            REASONS.get(bad[2], ('', '', 'not good'))[2]
        parts.append(f'The user rated this earlier answer badly ({why}); avoid the same mistake:\n'
                     f'Q: {bad[0][:300]}\nA: {bad[1][:400]}')
    return '\n\n'.join(parts)


def retry_note(previous_answer):
    return ('The user pressed "Try again": they want a different answer to their message below. Your previous '
            f'answer was:\n«{previous_answer[:1200]}»\nWrite a noticeably different and better answer (a different '
            'angle, structure, or level of detail). Do not mention this note or apologise.')
