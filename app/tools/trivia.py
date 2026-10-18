"""Trivia sources/cache adapted from PromptetheusBot; no chat text or personal data is sent."""
import copy
import json
import random
import threading
import time
from urllib.parse import unquote

import requests

POINTS = {'easy': 1, 'medium': 2, 'hard': 3}
DIFFICULTIES = ('easy', 'medium', 'hard')
CATEGORIES = {'general': (9, 'general_knowledge'), 'science': (17, 'science'), 'computers': (18, 'science'), 'math': (19, 'science'), 'history': (23, 'history'), 'geography': (22, 'geography'), 'movies': (11, 'film_and_tv'), 'tv': (14, 'film_and_tv'), 'music': (12, 'music'), 'books': (10, 'arts_and_literature'), 'art': (25, 'arts_and_literature'), 'sports': (21, 'sport_and_leisure'), 'animals': (27, None), 'mythology': (20, None), 'videogames': (15, None), 'boardgames': (16, None), 'vehicles': (28, None), 'gadgets': (30, None), 'anime': (31, None), 'cartoons': (32, None), 'comics': (29, None), 'celebrities': (26, None), 'politics': (24, 'society_and_culture'), 'food': (None, 'food_and_drink')}
ALIASES = {'film': 'movies', 'movie': 'movies', 'television': 'tv', 'sport': 'sports', 'games': 'videogames', 'video games': 'videogames', 'gaming': 'videogames', 'board games': 'boardgames', 'tech': 'computers', 'computer': 'computers', 'maths': 'math', 'mathematics': 'math', 'literature': 'books', 'nature': 'science', 'animal': 'animals', 'geo': 'geography', 'any': 'general', 'random': 'general'}

_cache = {}
_lock = threading.Lock()
_last_opentdb = 0.0
_rand = random.SystemRandom()
SOURCES = {
    'Open Trivia DB': ('https://opentdb.com/', 'CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/'),
    'The Trivia API': ('https://the-trivia-api.com/', 'CC BY-NC 4.0', 'https://creativecommons.org/licenses/by-nc/4.0/'),
}


class TriviaError(RuntimeError):
    pass


def parse_options(words):
    tokens = ' '.join(words).lower().split()
    levels = [word for word in tokens if word in DIFFICULTIES]
    if len(levels) > 1:
        raise ValueError('Choose one difficulty: easy, medium or hard.')
    difficulty = levels[0] if levels else None
    category_text = ' '.join(word for word in tokens if word not in DIFFICULTIES)
    category = ALIASES.get(category_text, category_text.replace(' ', '')) if category_text else None
    if category is not None and category not in CATEGORIES:
        raise ValueError(f'Unknown trivia category "{category_text}".')
    return category, difficulty


def _get(url, params):
    started, body = time.monotonic(), bytearray()
    with requests.get(url, params=params, headers={'User-Agent': 'BEYOND/0.29 (personal local trivia)'},
                      timeout=(3, 8), stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(8192):
            body.extend(chunk)
            if len(body) > 1024*1024 or time.monotonic()-started > 20:
                raise TriviaError('The question service did not return a usable response.')
    return json.loads(body)


def _opentdb(category, difficulty, amount=10, may_wait=False):
    global _last_opentdb
    category_id = CATEGORIES[category][0] if category else None
    if category and category_id is None:
        return []
    wait = 5.2 - (time.monotonic()-_last_opentdb)
    if wait > 0:
        if not may_wait:
            return []
        time.sleep(wait)
    params = {'amount': amount, 'type': 'multiple', 'encode': 'url3986'}
    if category_id:
        params['category'] = category_id
    if difficulty:
        params['difficulty'] = difficulty
    _last_opentdb = time.monotonic()
    data = _get('https://opentdb.com/api.php', params)
    if not isinstance(data, dict) or data.get('response_code') != 0:
        return []
    result = []
    for item in data.get('results', []):
        try:
            result.append({'question': unquote(item['question']), 'correct': unquote(item['correct_answer']),
                           'wrong': [unquote(value) for value in item['incorrect_answers']],
                           'difficulty': item.get('difficulty'), 'category': unquote(item.get('category', '')),
                           'source': 'Open Trivia DB'})
        except (KeyError, TypeError, AttributeError):
            continue
    return result


def _trivia_api(category, difficulty):
    params = {'limit': 10}
    if category:
        mapped = CATEGORIES[category][1]
        if not mapped:
            return []
        params['categories'] = mapped
    if difficulty:
        params['difficulties'] = difficulty
    data = _get('https://the-trivia-api.com/v2/questions', params)
    result = []
    for item in data if isinstance(data, list) else []:
        try:
            result.append({'question': item['question']['text'], 'correct': item['correctAnswer'],
                           'wrong': item['incorrectAnswers'], 'difficulty': item.get('difficulty'),
                           'category': str(item.get('category', '')).replace('_', ' ').title(),
                           'source': 'The Trivia API'})
        except (KeyError, TypeError, AttributeError):
            continue
    return result


def valid(question, difficulty=None):
    if not isinstance(question, dict) or question.get('difficulty') not in POINTS:
        return False
    if difficulty and question['difficulty'] != difficulty:
        return False
    if not isinstance(question.get('category'), str) or len(question['category']) > 160:
        return False
    if question.get('source') not in SOURCES or not isinstance(question.get('wrong'), list):
        return False
    if len(question['wrong']) != 3:
        return False
    strings = [question.get('question'), question.get('correct'), *question['wrong']]
    if not all(isinstance(value, str) and value.strip() for value in strings):
        return False
    if len(strings[0]) > 2000 or any(len(value) > 400 for value in strings[1:]):
        return False
    return len({value.strip().casefold() for value in strings[1:]}) == 4


def round_questions(category=None, difficulty=None):
    if category is not None and category not in CATEGORIES or difficulty is not None and difficulty not in DIFFICULTIES:
        raise ValueError('Choose a listed category and difficulty.')
    if not _lock.acquire(blocking=False):
        raise TriviaError('Trivia questions are already being fetched. Try again shortly.')
    try:
        bank = _cache.setdefault((category, difficulty), [])
        if not bank:
            for fetch in (_opentdb, _trivia_api, lambda c, d: _opentdb(c, d, amount=3, may_wait=True)):
                try:
                    batch = fetch(category, difficulty)
                    seen = set()
                    for question in batch[:50]:
                        if valid(question, difficulty) and question['question'].strip().casefold() not in seen:
                            seen.add(question['question'].strip().casefold())
                            bank.append(question)
                except (requests.RequestException, ValueError, KeyError, TypeError, TriviaError):
                    continue
                if bank:
                    break
        if not bank:
            raise TriviaError('No trivia questions are available right now. Check your connection or try another category.')
        _rand.shuffle(bank)
        selected = []
        for _ in range(min(5, len(bank))):
            question = copy.deepcopy(bank.pop())
            answers = [question['correct'], *question['wrong']]
            _rand.shuffle(answers)
            question.update(answers=answers, correct_index=answers.index(question['correct']))
            selected.append(question)
        return selected
    finally:
        _lock.release()
