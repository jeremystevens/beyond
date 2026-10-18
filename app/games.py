"""Shared local game totals for this BEYOND installation; no Telegram users or sessions."""
from app import chats

CATALOG = (
    ('dice', 'Dice & coins', 'Ready to play', True),
    ('tictactoe', 'Tic-tac-toe', 'Ready to play', True),
    ('trivia', 'Trivia', 'Ready to play', True),
    ('quiz', 'Study quiz', 'Ready to play', True),
    ('blackjack', 'Blackjack', 'Coming in Phase 31', False),
    ('hangman', 'Hangman', 'Coming in Phase 32', False),
)
KEYS = {key for key, *_ in CATALOG} | {'coin'}
HELP = ('/games opens the games menu. Dice, coin flips, tic-tac-toe, trivia and the study quiz (/quizme) are ready now; '
        'other games arrive in later phases. '
        '/games stats shows the saved totals for this BEYOND installation. '
        '/roll rolls a d6; try /roll 2d20+3, /roll 4d6kh3, /roll 6x 4d6kh3 or /roll coin. '
        'Roll again makes a fresh roll. Scores and stats are shared across your chats and devices.')


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS game_stats (
            game TEXT PRIMARY KEY, played INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
            draws INTEGER NOT NULL DEFAULT 0, score TEXT NOT NULL DEFAULT '0',
            best_score TEXT, updated_at TEXT NOT NULL)''')


def record(game, score=None, outcome=None, *, db=None):
    """One completed play; later games can record win/loss/draw and an integer score."""
    if game not in KEYS or outcome not in (None, 'win', 'loss', 'draw'):
        raise ValueError('Unknown game or outcome.')
    if score is not None and (isinstance(score, bool) or not isinstance(score, int)):
        raise ValueError('A score must be a whole number.')
    if db is not None:
        _record(db, game, score, outcome)
        return
    with chats.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        _record(connection, game, score, outcome)


def _record(db, game, score, outcome):
    """Caller owns the write transaction, so a board and its result can commit together."""
    row = db.execute('SELECT * FROM game_stats WHERE game = ?', (game,)).fetchone()
    played, wins, losses, draws, total, best = (
        (row['played'], row['wins'], row['losses'], row['draws'], int(row['score']),
         int(row['best_score']) if row['best_score'] is not None else None)
        if row else (0, 0, 0, 0, 0, None))
    if score is not None:
        total += score
        best = score if best is None else max(best, score)
    db.execute('''INSERT INTO game_stats (game, played, wins, losses, draws, score, best_score, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(game) DO UPDATE SET
        played=excluded.played, wins=excluded.wins, losses=excluded.losses, draws=excluded.draws,
        score=excluded.score, best_score=excluded.best_score, updated_at=excluded.updated_at''',
        (game, played + 1, wins + int(outcome == 'win'), losses + int(outcome == 'loss'),
         draws + int(outcome == 'draw'), str(total), str(best) if best is not None else None, chats._now()))


def stats():
    with chats.connect() as db:
        rows = db.execute('SELECT * FROM game_stats ORDER BY game').fetchall()
    return [{**dict(row), 'score': int(row['score']),
             'best_score': int(row['best_score']) if row['best_score'] is not None else None} for row in rows]


def menu():
    return {'type': 'menu', 'items': [
        {'id': key, 'name': name, 'status': status, 'available': available}
        for key, name, status, available in CATALOG]}


def stats_text():
    rows = stats()
    if not rows:
        return 'Game stats\nNo games played yet. Roll some dice to start.'
    names = {key: name for key, name, *_ in CATALOG}
    names['dice'] = 'Dice rolls'
    names['coin'] = 'Coin flips'
    lines = ['Game stats — shared across your chats and devices']
    for row in rows:
        line = f"{names[row['game']]}: {row['played']} plays"
        if row['game'] == 'dice':
            line += f" · total of rolls {row['score']} · highest total {row['best_score']}"
        elif row['game'] == 'trivia':
            line = f"Trivia: {row['played']} answered · {row['score']} points"
        elif row['game'] != 'coin':
            line += f" · {row['wins']} wins, {row['losses']} losses, {row['draws']} draws"
            if row['best_score'] is not None:
                line += f" · score {row['score']} · best {row['best_score']}"
        lines.append(line)
    lines.append('One dice play is one /roll or Roll again, including any repeated rolls in that request.')
    return '\n'.join(lines)
