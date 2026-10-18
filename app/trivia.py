"""Saved multiple-choice rounds; answers and scores commit atomically."""
import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app import chats, games
from app.tools import trivia as source

router = APIRouter()
HELP = ('/trivia opens category and difficulty choices. /trivia science hard starts directly. '
        '/trivia categories lists categories; /trivia score (or stats) shows points, accuracy and streaks. '
        'A round has up to five questions, fetched together from Open Trivia DB or The Trivia API. '
        'Pick one answer, then Next question. Correct Easy/Medium/Hard answers earn 1/2/3 points. '
        'Questions show their source and license. Scores and saved rounds are shared across your chats/devices.')


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS trivia_rounds (
            message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE, state TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS trivia_scores (
            id INTEGER PRIMARY KEY CHECK(id=1), points INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 0, best_streak INTEGER NOT NULL DEFAULT 0)''')


def picker(category=None, difficulty=None):
    return {'type': 'trivia_picker', 'category': category, 'difficulty': difficulty,
            'categories': sorted(source.CATEGORIES), 'difficulties': list(source.DIFFICULTIES)}


def prepare(category=None, difficulty=None):
    return {'questions': source.round_questions(category, difficulty),
            'category': category, 'difficulty': difficulty, 'index': 0, 'revision': 0,
            'selected': None, 'answered': 0, 'correct': 0, 'points': 0}


def public(state):
    question = state['questions'][state['index']]
    src = source.SOURCES[question['source']]
    game = {'type': 'trivia', 'revision': state['revision'], 'index': state['index'],
            'length': len(state['questions']), 'question': question['question'],
            'answers': question['answers'], 'difficulty': question['difficulty'],
            'category': question['category'], 'options': {'category': state['category'], 'difficulty': state['difficulty']},
            'selected': state['selected'], 'answered': state['answered'], 'correct': state['correct'],
            'points': state['points'], 'max_points': sum(source.POINTS[q['difficulty']] for q in state['questions']),
            'finished': state['selected'] is not None and state['index'] == len(state['questions'])-1,
            'source': {'name': question['source'], 'url': src[0], 'license': src[1], 'license_url': src[2]}}
    if state['selected'] is not None:
        game['correct_index'] = question['correct_index']
        game['gained'] = source.POINTS[question['difficulty']] if state['selected'] == question['correct_index'] else 0
    return game


def text(game):
    lines = [f"Trivia · {game['category']} · {game['difficulty'].title()}",
             f"Question {game['index']+1} of {game['length']}", game['question']]
    if game['selected'] is not None:
        lines.append(f"Correct! +{game['gained']} point(s)." if game['gained'] else
                     'The correct answer is: ' + game['answers'][game['correct_index']])
    if game['finished']:
        lines.append(f"Round complete: {game['correct']}/{game['length']} correct · {game['points']} points.")
    return '\n'.join(lines)


def view(mid, state):
    game = public(state)
    return {'id': mid, 'text': text(game), 'buttons': [], 'game': game}


def save_new(chat_id, state):
    game = public(state)
    with chats.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        now = chats._now()
        mid = db.execute("INSERT INTO messages(chat_id,role,content,kind,created_at,game) VALUES(?,'assistant',?,'command',?,?)",
                         (chat_id, text(game), now, json.dumps(game))).lastrowid
        db.execute('INSERT INTO trivia_rounds(message_id,state) VALUES(?,?)', (mid, json.dumps(state)))
        db.execute('UPDATE chats SET updated_at=? WHERE id=?', (now, chat_id))
    return mid


def load(mid, db):
    row = db.execute("SELECT t.state FROM trivia_rounds t JOIN messages m ON m.id=t.message_id "
                     "WHERE t.message_id=? AND m.role='assistant' AND m.kind='command'", (mid,)).fetchone()
    return json.loads(row['state']) if row else None


def stats(db=None):
    if db is None:
        with chats.connect() as connection:
            return stats(connection)
    row = db.execute('SELECT points,answered,correct,streak,best_streak FROM trivia_scores WHERE id=1').fetchone()
    return dict(row) if row else dict(points=0, answered=0, correct=0, streak=0, best_streak=0)


def stats_text():
    record = stats()
    accuracy = round(100*record['correct']/record['answered']) if record['answered'] else 0
    return (f"Trivia score: {record['points']} points\nCorrect: {record['correct']}/{record['answered']} ({accuracy}%)\n"
            f"Current streak: {record['streak']} · Best streak: {record['best_streak']}\n"
            'Points: Easy 1 · Medium 2 · Hard 3. Shared across chats and devices.')


def change(mid, revision, choice=None):
    with chats.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        state = load(mid, db)
        if state is None:
            return {'error': 'That trivia round no longer exists.'}, 404
        if state['revision'] != revision:
            return {**view(mid, state), 'error': 'This round changed on another device. It has been refreshed.'}, 409
        game = public(state)
        if choice is None:
            if state['selected'] is None or game['finished']:
                return {**view(mid, state), 'error': 'Answer this question first, or start a new round.'}, 409
            state.update(index=state['index']+1, selected=None)
        else:
            if state['selected'] is not None:
                return {**view(mid, state), 'error': 'This question has already been answered.'}, 409
            question = state['questions'][state['index']]
            correct = choice == question['correct_index']
            gained = source.POINTS[question['difficulty']] if correct else 0
            db.execute('INSERT OR IGNORE INTO trivia_scores(id) VALUES(1)')
            if correct:
                db.execute('''UPDATE trivia_scores SET points=points+?,answered=answered+1,correct=correct+1,
                    streak=streak+1,best_streak=max(best_streak,streak+1) WHERE id=1''', (gained,))
            else:
                db.execute('UPDATE trivia_scores SET answered=answered+1,streak=0 WHERE id=1')
            games.record('trivia', score=gained, db=db)
            state.update(selected=choice, answered=state['answered']+1,
                         correct=state['correct']+int(correct), points=state['points']+gained)
        state['revision'] += 1
        result = view(mid, state)
        db.execute('UPDATE trivia_rounds SET state=? WHERE message_id=?', (json.dumps(state), mid))
        db.execute('UPDATE messages SET content=?,game=? WHERE id=?',
                   (result['text'], json.dumps(result['game']), mid))
        return result, 200


class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0, le=10)


class Answer(Revision):
    choice: StrictInt = Field(ge=0, le=3)


@router.get('/api/trivia/{message_id}')
def get_round(message_id: int):
    with chats.connect() as db:
        state = load(message_id, db)
    if state is None:
        return JSONResponse({'error': 'That trivia round no longer exists.'}, status_code=404)
    return view(message_id, state)


@router.post('/api/trivia/{message_id}/answer')
def answer(message_id: int, body: Answer):
    response, status = change(message_id, body.revision, body.choice)
    return JSONResponse(response, status_code=status)


@router.post('/api/trivia/{message_id}/next')
def next_question(message_id: int, body: Revision):
    response, status = change(message_id, body.revision)
    return JSONResponse(response, status_code=status)
