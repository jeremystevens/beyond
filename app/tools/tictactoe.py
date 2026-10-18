"""Offline tic-tac-toe rules ported unchanged from PromptetheusBot's plugins/tictactoe.py."""
import random
from functools import lru_cache

DIFFICULTIES = ('easy', 'normal', 'impossible')
LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
_rand = random.SystemRandom()


def winner(board):
    """'X', 'O', 'draw', or None."""
    for a, b, c in LINES:
        if board[a] != ' ' and board[a] == board[b] == board[c]:
            return board[a]
    return 'draw' if ' ' not in board else None


@lru_cache(maxsize=None)
def _score(board, turn):
    """Minimax value from O's point of view (+ = O wins sooner, - = X wins sooner)."""
    result = winner(board)
    if result == 'O':  # faster wins (more empty squares left) score higher
        return 10 + board.count(' ')
    if result == 'X':
        return -10 - board.count(' ')
    if result == 'draw':
        return 0
    scores = [_score(board[:i] + turn + board[i + 1:], 'X' if turn == 'O' else 'O')
              for i in range(9) if board[i] == ' ']
    return max(scores) if turn == 'O' else min(scores)


def _best_moves(board):
    empty = [i for i in range(9) if board[i] == ' ']
    scored = {i: _score(board[:i] + 'O' + board[i + 1:], 'X') for i in empty}
    best = max(scored.values())
    return [i for i, score in scored.items() if score == best]


def _completing(board, player):
    """Squares that would complete a line for `player`."""
    moves = []
    for line in LINES:
        cells = [board[i] for i in line]
        if cells.count(player) == 2 and cells.count(' ') == 1:
            moves.append(line[cells.index(' ')])
    return moves


def bot_move(board, difficulty):
    empty = [i for i in range(9) if board[i] == ' ']
    if difficulty == 'impossible':
        return _rand.choice(_best_moves(board))
    if difficulty == 'normal':
        for player in ('O', 'X'):  # win if possible, otherwise block
            options = _completing(board, player)
            if options:
                return _rand.choice(options)
        if _rand.random() < 0.25:  # an occasional loose move keeps "normal" beatable
            return _rand.choice(empty)
        for group in ([4], [0, 2, 6, 8]):
            options = [i for i in group if board[i] == ' ']
            if options:
                return _rand.choice(options)
    return _rand.choice(empty)


