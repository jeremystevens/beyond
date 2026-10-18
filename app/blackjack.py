"""Saved blackjack hands, shared across chats/devices. The deck and the dealer's face-down card stay on the server
(blackjack_hands): the chat message, and so the browser, only ever holds the cards that are face up."""
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app import chats, games
from app.tools import blackjack as rules

router = APIRouter()
HELP = ('/blackjack deals a hand against the dealer (/bj also works). Tap Hit to take a card or Stand to keep your '
        'hand; the dealer then plays and draws to 17. /blackjack stats shows wins, losses, pushes and blackjacks; '
        '/blackjack rules explains the game. No betting. Hands survive reloads/restarts and each one counts once '
        'in the shared game stats.')


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS blackjack_hands (
            message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE, state TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS blackjack_stats (
            id INTEGER PRIMARY KEY CHECK(id=1), wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
            pushes INTEGER NOT NULL DEFAULT 0, blackjacks INTEGER NOT NULL DEFAULT 0)''')


def new():
    """A freshly dealt hand (private state, with its revision)."""
    return {**rules.deal(), 'revision': 0}


def public(state, record=None):
    """What the browser may see: your cards, and the dealer's face-up card (both once the hand is over).
    `record`: the win/loss record to show under a finished hand."""
    over = state['result'] is not None
    dealer = state['dealer'] if over else state['dealer'][:1]
    player_total, soft = rules.hand_value(state['player'])
    game = {'type': 'blackjack', 'revision': state['revision'], 'player': state['player'],
            'player_total': player_total, 'player_soft': soft and player_total < 21,
            'dealer': dealer, 'dealer_hidden': 0 if over else len(state['dealer']) - 1,
            'dealer_total': rules.hand_value(dealer)[0], 'result': state['result'],
            'message': rules.OUTCOMES[state['result']][0] if over else None,
            'note': rules.DEAL_NOTES.get(state['result']) if state.get('natural') else None}
    if over:
        game['record'] = record or stats()
    return game


def text(game):
    dealer = ' '.join(game['dealer']) + (' 🂠' * game['dealer_hidden'])
    shown = 'showing ' if game['dealer_hidden'] else ''
    lines = ['Blackjack', f"Dealer: {dealer}  ({shown}{game['dealer_total']})",
             f"You: {' '.join(game['player'])}  ({'soft ' if game['player_soft'] else ''}{game['player_total']})"]
    if game['result']:
        lines.append(game['message'])
        if game['note']:
            lines.append(game['note'])
        r = game['record']
        lines.append(f"Record: {r['wins']}W · {r['losses']}L · {r['pushes']}P · Blackjacks: {r['blackjacks']}")
    else:
        lines.append('Hit or Stand?')
    return '\n'.join(lines)


def _record(db, result):
    column = rules.OUTCOMES[result][2]
    db.execute('INSERT OR IGNORE INTO blackjack_stats (id) VALUES (1)')
    db.execute(f'UPDATE blackjack_stats SET {column} = {column} + 1, blackjacks = blackjacks + ? WHERE id = 1',
               (int(result == 'blackjack'),))
    games.record('blackjack', outcome=rules.OUTCOMES[result][1], db=db)


def save_new(chat_id, state):
    """Save a dealt hand as a chat message (a natural is recorded at once, with the message)."""
    with chats.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if state['result']:
            _record(db, state['result'])
        game = public_in(db, state)
        now = chats._now()
        mid = db.execute("INSERT INTO messages (chat_id, role, content, kind, created_at, game) "
                         "VALUES (?, 'assistant', ?, 'command', ?, ?)",
                         (chat_id, text(game), now, json.dumps(game))).lastrowid
        db.execute('INSERT INTO blackjack_hands (message_id, state) VALUES (?, ?)', (mid, json.dumps(state)))
        db.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (now, chat_id))
    return mid


def public_in(db, state):
    """public() inside an open transaction, so a just-recorded result is included in the record shown."""
    return public(state, stats(db) if state['result'] else None)


def load(mid, db):
    row = db.execute("SELECT b.state FROM blackjack_hands b JOIN messages m ON m.id = b.message_id "
                     "WHERE b.message_id = ? AND m.role = 'assistant' AND m.kind = 'command'", (mid,)).fetchone()
    return json.loads(row['state']) if row else None


def stats(db=None):
    if db is None:
        with chats.connect() as connection:
            return stats(connection)
    row = db.execute('SELECT wins, losses, pushes, blackjacks FROM blackjack_stats WHERE id = 1').fetchone()
    return dict(row) if row else {'wins': 0, 'losses': 0, 'pushes': 0, 'blackjacks': 0}


def stats_text():
    s = stats()
    played = s['wins'] + s['losses'] + s['pushes']
    if not played:
        return 'No blackjack hands yet. /blackjack deals one.'
    return (f"Blackjack record ({played} hands), shared across your chats and devices\n"
            f"Wins: {s['wins']} ({round(100 * s['wins'] / played)}%) · Losses: {s['losses']} · "
            f"Pushes: {s['pushes']}\n"
            f"Blackjacks: {s['blackjacks']}")


def play(mid, revision, move):
    """Hit or Stand on a saved hand. Returns (response, HTTP status)."""
    with chats.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        state = load(mid, db)
        if state is None:
            return {'error': 'That hand no longer exists. /blackjack deals a new one.'}, 404
        if state['revision'] != revision:
            changed = 'This hand changed on another device. It has been refreshed.'
            return {**view_in(db, mid, state), 'error': changed}, 409
        if state['result']:
            return {**view_in(db, mid, state), 'error': 'This hand is over. Deal a new one to play again.'}, 409
        rules.hit(state) if move == 'hit' else rules.finish(state)
        state['revision'] += 1
        if state['result']:
            _record(db, state['result'])
        result = view_in(db, mid, state)
        db.execute('UPDATE blackjack_hands SET state = ? WHERE message_id = ?', (json.dumps(state), mid))
        db.execute('UPDATE messages SET content = ?, game = ? WHERE id = ?',
                   (result['text'], json.dumps(result['game']), mid))
        return result, 200


def view_in(db, mid, state):
    game = public_in(db, state)
    return {'id': mid, 'text': text(game), 'buttons': [], 'game': game}


class Move(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0, le=12)


@router.get('/api/blackjack/{message_id}')
def get_hand(message_id: int):
    with chats.connect() as db:
        state = load(message_id, db)
        if state is None:
            return JSONResponse({'error': 'That hand no longer exists.'}, status_code=404)
        return view_in(db, message_id, state)


@router.post('/api/blackjack/{message_id}/hit')
def hit(message_id: int, body: Move):
    response, status = play(message_id, body.revision, 'hit')
    return JSONResponse(response, status_code=status)


@router.post('/api/blackjack/{message_id}/stand')
def stand(message_id: int, body: Move):
    response, status = play(message_id, body.revision, 'stand')
    return JSONResponse(response, status_code=status)
