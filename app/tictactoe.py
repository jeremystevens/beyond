"""Saved tic-tac-toe boards and atomic results, shared across chats/devices."""
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app import chats, games
from app.tools import tictactoe as rules

router = APIRouter()
HELP = ('/tictactoe opens the difficulty picker (/ttt also works). '
        '/tictactoe easy, /tictactoe normal or /tictactoe impossible starts a game. '
        'You are X and go first; BEYOND is O. Click an empty square. '
        'Easy plays randomly, Normal takes wins and blocks with occasional loose moves, '
        'and Impossible uses minimax and never loses. '
        '/tictactoe stats shows wins, losses and draws by difficulty. '
        'Boards survive reloads/restarts; each completed game counts once in shared local stats.')


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS tictactoe_stats (
            difficulty TEXT PRIMARY KEY, wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0, draws INTEGER NOT NULL DEFAULT 0)''')


def picker():
    return {'type': 'tictactoe_picker'}


def new(difficulty):
    if difficulty not in rules.DIFFICULTIES:
        raise ValueError('Choose Easy, Normal or Impossible.')
    return {'type': 'tictactoe', 'board': ' ' * 9, 'difficulty': difficulty,
            'revision': 0, 'result': None, 'winning': []}


def text(game):
    result = game['result']
    status = {'X': 'You win!', 'O': 'BEYOND wins.', 'draw': "It's a draw!"}.get(
        result, 'Your turn. Choose an empty square.')
    return f"Tic-tac-toe · {game['difficulty'].title()}\nYou are X · BEYOND is O\n{status}"


def view(message_id, game):
    return {'id': message_id, 'text': text(game), 'buttons': [], 'game': game}


def state(message_id, db):
    row = db.execute("SELECT game FROM messages WHERE id=? AND role='assistant' AND kind='command'",
                     (message_id,)).fetchone()
    if not row or not row['game']:
        return None
    game = json.loads(row['game'])
    return game if game.get('type') == 'tictactoe' else None


def play(message_id, revision, cell):
    with chats.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        game = state(message_id, db)
        if game is None:
            return {'error': 'That game no longer exists.'}, 404
        if game['revision'] != revision:
            return {**view(message_id, game), 'error': 'This board changed on another device. It has been refreshed.'}, 409
        if game['result']:
            return {**view(message_id, game), 'error': 'This game has finished. Start another game to play again.'}, 409
        board = game['board']
        if not 0 <= cell <= 8 or board[cell] != ' ':
            return {**view(message_id, game), 'error': 'That square is already taken. Choose an empty square.'}, 409
        board = board[:cell] + 'X' + board[cell+1:]
        if not rules.winner(board):
            move = rules.bot_move(board, game['difficulty'])
            board = board[:move] + 'O' + board[move+1:]
        result = rules.winner(board)
        game.update(board=board, result=result, revision=revision+1,
                    winning=list(next((line for line in rules.LINES
                                       if result in ('X', 'O') and all(board[i] == result for i in line)), ())))
        if result:
            column = {'X': 'wins', 'O': 'losses', 'draw': 'draws'}[result]
            db.execute('INSERT OR IGNORE INTO tictactoe_stats (difficulty) VALUES (?)', (game['difficulty'],))
            db.execute(f'UPDATE tictactoe_stats SET {column}={column}+1 WHERE difficulty=?', (game['difficulty'],))
            games.record('tictactoe', outcome={'X': 'win', 'O': 'loss', 'draw': 'draw'}[result], db=db)
        db.execute('UPDATE messages SET content=?, game=? WHERE id=?',
                   (text(game), json.dumps(game), message_id))
        return view(message_id, game), 200


def stats_text():
    with chats.connect() as db:
        rows = {row['difficulty']: dict(row) for row in db.execute('SELECT * FROM tictactoe_stats')}
    lines = ['Tic-tac-toe record — shared across your chats and devices']
    for difficulty in rules.DIFFICULTIES:
        row = rows.get(difficulty, {'wins': 0, 'losses': 0, 'draws': 0})
        lines.append(f"{difficulty.title()}: {row['wins']} wins · {row['losses']} losses · {row['draws']} draws")
    if not rows:
        lines.append('No completed games yet. /tictactoe starts one.')
    return '\n'.join(lines)


class Move(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0, le=9)
    cell: StrictInt = Field(ge=0, le=8)


@router.get('/api/tictactoe/{message_id}')
def get_game(message_id: int):
    with chats.connect() as db:
        game = state(message_id, db)
    if game is None:
        return JSONResponse({'error': 'That game no longer exists.'}, status_code=404)
    return view(message_id, game)


@router.post('/api/tictactoe/{message_id}/move')
def move(message_id: int, body: Move):
    response, status = play(message_id, body.revision, body.cell)
    return JSONResponse(response, status_code=status)
