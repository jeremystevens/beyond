"""Hangman rules, ported from PromptetheusBot (offline): word choice, guessing, the free hint.

Six misses and it's game over. A letter already guessed never costs a miss. One free hint per round. Difficulty
comes from word length (easy 4–6, medium 7–9, hard 10+ letters); "random" picks one of the four categories.
"""
from collections import deque
from random import SystemRandom

from app.tools.hangman_words import WORDS

MAX_MISSES = 6
CATEGORIES = {'animals': '🐾 Animals', 'movies': '🎬 Movies', 'technology': '💻 Technology',
              'geography': '🌎 Geography', 'random': '🎲 Random'}
DIFFICULTIES = {'easy': (4, 6), 'medium': (7, 9), 'hard': (10, 99)}
DIFFICULTY_LABELS = {'easy': 'Easy (4–6 letters)', 'medium': 'Medium (7–9 letters)', 'hard': 'Hard (10+ letters)'}
LETTER_ROWS = ('ABCDEFG', 'HIJKLMN', 'OPQRSTU', 'VWXYZ')
_rand = SystemRandom()
_recent = deque(maxlen=30)   # recently played words, so they don't come straight back


def pick(category='random', difficulty='easy'):
    """A new round's private state."""
    if category not in CATEGORIES or difficulty not in DIFFICULTIES:
        raise ValueError('Choose a category and Easy, Medium or Hard.')
    actual = _rand.choice(list(WORDS)) if category == 'random' else category
    low, high = DIFFICULTIES[difficulty]
    pool = [(w, h) for w, h in WORDS[actual] if low <= len(w) <= high]
    word, hint = _rand.choice([item for item in pool if item[0] not in _recent] or pool)
    _recent.append(word)
    return {'category': category, 'actual_category': actual, 'difficulty': difficulty, 'word': word, 'hint': hint,
            'guessed': [], 'misses': [], 'hint_used': False, 'status': 'Pick a letter!', 'result': None}


def guess(state, letter):
    """Apply one guess. Returns False (nothing changes) for a letter already tried or not A–Z."""
    letter = str(letter).upper()
    if len(letter) != 1 or not 'A' <= letter <= 'Z' or letter in state['guessed'] or state['result']:
        return False
    state['guessed'].append(letter)
    if letter in state['word']:
        count = state['word'].count(letter)
        state['status'] = f"Yes! {letter} appears {count} time{'s' if count > 1 else ''}."
        if set(state['word']) <= set(state['guessed']):
            state['result'] = 'win'
    else:
        state['misses'].append(letter)
        left = MAX_MISSES - len(state['misses'])
        state['status'] = f"No {letter}. {left} miss{'es' if left != 1 else ''} left."
        if len(state['misses']) >= MAX_MISSES:
            state['result'] = 'lose'
    return True


def use_hint(state):
    if state['hint_used'] or state['result']:
        return False
    state['hint_used'] = True
    state['status'] = 'Hint revealed. It costs nothing.'
    return True


def masked(state):
    reveal = state['result'] is not None
    return ' '.join(c if c in state['guessed'] or reveal else '_' for c in state['word'])
