"""Saved hangman rounds, shared across chats/devices. The secret word (and the hint until you ask for it) stays
on the server (hangman_rounds): the chat message, and so the browser, only holds the word with blanks."""
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app import chats, games
from app.tools import hangman as rules

router = APIRouter()
HELP = ('/hangman opens the category and difficulty choices; /hangman animals medium starts directly '
        '(categories: animals, movies, technology, geography, random; Easy 4–6, Medium 7–9, Hard 10+ letters). '
        'Tap letters (or type them) to guess the word; six misses and the drawing is complete. One free hint per '
        'round. /hangman stats shows wins, losses and streaks. Rounds survive reloads and each one counts once.')


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS hangman_rounds (
            message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE, state TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS hangman_stats (
            id INTEGER PRIMARY KEY CHECK(id=1), played INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0)''')


def picker(difficulty='easy'):
    return {'type': 'hangman_picker', 'difficulty': difficulty,
            'categories': [{'id': key, 'label': label} for key, label in rules.CATEGORIES.items()],
            'difficulties': [{'id': key, 'label': label} for key, label in rules.DIFFICULTY_LABELS.items()]}


def new(category='random', difficulty='easy'):
    return {**rules.pick(category, difficulty), 'revision': 0}


def public(state, record=None):
    """What the browser may see: blanks for letters not yet found, the hint only once asked for."""
    over = state['result'] is not None
    actual = rules.CATEGORIES[state['actual_category']].split(' ', 1)[1]
    game = {'type': 'hangman', 'revision': state['revision'], 'masked': rules.masked(state),
            'length': len(state['word']), 'category': state['category'], 'difficulty': state['difficulty'],
            'category_label': f'Random → {actual}' if state['category'] == 'random' else actual,
            'guessed': state['guessed'], 'misses': state['misses'], 'max_misses': rules.MAX_MISSES,
            'hint': state['hint'] if state['hint_used'] or over else None, 'hint_used': state['hint_used'],
            'status': state['status'], 'result': state['result'], 'word': state['word'] if over else None}
    if over:
        game['record'] = record or stats()
    return game


def text(game):
    lines = [f"Hangman · {game['category_label']} · {game['difficulty'].title()}", game['masked'],
             f"Misses: {len(game['misses'])}/{game['max_misses']}  {' '.join(game['misses']) or '—'}"]
    if game['hint']:
        lines.append(f"Hint: {game['hint']}")
    if game['result'] == 'win':
        lines.append(f"You got it! The word was {game['word']}.")
    elif game['result'] == 'lose':
        lines.append(f"Game over! The word was {game['word']}.")
    else:
        lines.append(game['status'])
    if game['result']:
        r = game['record']
        lines.append(f"Record: {r['wins']} wins · {r['losses']} losses · "
                     f"streak {r['streak']} · best {r['best_streak']}")
    return '\n'.join(lines)


def stats(db=None):
    if db is None:
        with chats.connect() as connection:
            return stats(connection)
    row = db.execute('SELECT played, wins, losses, streak, best_streak FROM hangman_stats WHERE id = 1').fetchone()
    return dict(row) if row else {'played': 0, 'wins': 0, 'losses': 0, 'streak': 0, 'best_streak': 0}


def stats_text():
    s = stats()
    if not s['played']:
        return 'No hangman games yet. /hangman starts one.'
    return ('Hangman record, shared across your chats and devices\n'
            f"Games: {s['played']} · Wins: {s['wins']} · Losses: {s['losses']} · "
            f"Win rate: {round(100 * s['wins'] / s['played'])}%\n"
            f"Current streak: {s['streak']} · Best streak: {s['best_streak']}")


def _record(db, won):
    db.execute('INSERT OR IGNORE INTO hangman_stats (id) VALUES (1)')
    if won:
        db.execute('''UPDATE hangman_stats SET played = played + 1, wins = wins + 1, streak = streak + 1,
                      best_streak = MAX(best_streak, streak + 1) WHERE id = 1''')
    else:
        db.execute('UPDATE hangman_stats SET played = played + 1, losses = losses + 1, streak = 0 WHERE id = 1')
    games.record('hangman', outcome='win' if won else 'loss', db=db)


def view_in(db, mid, state):
    game = public(state, stats(db) if state['result'] else None)
    return {'id': mid, 'text': text(game), 'buttons': [], 'game': game}


def save_new(chat_id, state):
    game = public(state)
    with chats.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        now = chats._now()
        mid = db.execute("INSERT INTO messages (chat_id, role, content, kind, created_at, game) "
                         "VALUES (?, 'assistant', ?, 'command', ?, ?)",
                         (chat_id, text(game), now, json.dumps(game))).lastrowid
        db.execute('INSERT INTO hangman_rounds (message_id, state) VALUES (?, ?)', (mid, json.dumps(state)))
        db.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (now, chat_id))
    return mid


def load(mid, db):
    row = db.execute("SELECT h.state FROM hangman_rounds h JOIN messages m ON m.id = h.message_id "
                     "WHERE h.message_id = ? AND m.role = 'assistant' AND m.kind = 'command'", (mid,)).fetchone()
    return json.loads(row['state']) if row else None


def change(mid, revision, letter=None):
    """A guess (letter) or the hint (letter=None). Returns (response, HTTP status)."""
    with chats.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        state = load(mid, db)
        if state is None:
            return {'error': 'That game no longer exists. /hangman starts a new one.'}, 404
        if state['revision'] != revision:
            changed = 'This game changed on another device. It has been refreshed.'
            return {**view_in(db, mid, state), 'error': changed}, 409
        if state['result']:
            return {**view_in(db, mid, state), 'error': 'This game is over. Start a new one to play again.'}, 409
        if letter is None:
            if not rules.use_hint(state):
                return {**view_in(db, mid, state), 'error': 'The hint is already showing.'}, 409
        elif not rules.guess(state, letter):
            return {**view_in(db, mid, state), 'error': f'{str(letter).upper()} was already tried.'}, 409
        state['revision'] += 1
        if state['result']:
            _record(db, state['result'] == 'win')
        result = view_in(db, mid, state)
        db.execute('UPDATE hangman_rounds SET state = ? WHERE message_id = ?', (json.dumps(state), mid))
        db.execute('UPDATE messages SET content = ?, game = ? WHERE id = ?',
                   (result['text'], json.dumps(result['game']), mid))
        return result, 200


class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0, le=40)


class Guess(Revision):
    letter: str = Field(min_length=1, max_length=1, pattern='^[A-Za-z]$')


@router.get('/api/hangman/{message_id}')
def get_round(message_id: int):
    with chats.connect() as db:
        state = load(message_id, db)
        if state is None:
            return JSONResponse({'error': 'That game no longer exists.'}, status_code=404)
        return view_in(db, message_id, state)


@router.post('/api/hangman/{message_id}/guess')
def guess(message_id: int, body: Guess):
    response, status = change(message_id, body.revision, body.letter)
    return JSONResponse(response, status_code=status)


@router.post('/api/hangman/{message_id}/hint')
def hint(message_id: int, body: Revision):
    response, status = change(message_id, body.revision)
    return JSONResponse(response, status_code=status)
