"""Slash commands typed in the chat, like /calc or /rules. BEYOND answers them itself; they never go to the AI.

Every command is one entry in COMMANDS below: its name, a one-line summary, an example, and the function that
answers it. /help, the command list the page shows when you type "/", and "did you mean…?" are all built from
that list, so a new command only needs adding here.

Buttons: a command can answer with a Reply that has buttons under it. Each button has an action like
"rules:del:5" (handler name, then its details). Pressing it calls ACTIONS["rules"]("del", "5"), which returns the
message's new text and buttons, so the message changes in place. The server only accepts actions that are on that
message's own buttons.
"""
import difflib
from dataclasses import dataclass, field
from typing import Callable

import httpx

from app import chats, learning, memory, notes, rules, settings
from app.tools import dictionary, jokes, little_lookups, movies, news, qr, rewrite, weather, web_search, wikipedia
from app.tools.calculator import calculate
from app.tools.dice import roll_dice
from app.tools.units import convert
from app.tools.web import Unavailable
from app.tools.world_time import world_time


@dataclass
class Reply:
    """What a command (or a button press) answers: text, optional buttons, and an optional short notice (toast)."""
    text: str
    buttons: list = field(default_factory=list)   # rows of {'label', 'action'}
    toast: str = ''
    image: str = ''            # a picture under the text, as a data: URL (e.g. /qr's code)
    saved_command: str = ''    # how to save the typed command instead (e.g. /qr wifi with the password hidden)


def button(label, action):
    return {'label': label, 'action': action}


def rows(buttons, per_row=4):
    """Lay buttons out in rows of `per_row`."""
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


@dataclass(frozen=True)
class Command:
    name: str
    summary: str                     # one line, for /help and the "/" menu
    example: str                     # what to type, for /help and the "/" menu
    run: Callable[[str], str]        # the text after the command -> BEYOND's reply
    aliases: tuple = field(default=())
    group: str = 'Tools'             # heading in /help


# ---------- house rules ----------

RULE_HELP = ('/rule <text> adds a house rule, for example: /rule Always answer in under 3 sentences.\n'
             '/rules lists them. /rule delete <number> removes one.')


def _list_rules(args=''):
    current = rules.all_rules()
    if not current:
        return Reply('There are no house rules yet.\n\n' + RULE_HELP)
    lines = [f'{number}. {rule["text"]}' for number, rule in enumerate(current, 1)]
    return Reply('House rules (added to every chat):\n' + '\n'.join(lines) +
                 '\n\nTap 🗑 to remove one (or type /rule delete <number>).',
                 rows([button(f'🗑 {number}', f'rules:del:{rule["id"]}') for number, rule in enumerate(current, 1)]))


def _rules_button(what, rule_id):
    """🗑 under /rules: remove that rule and show the updated list in the same message."""
    if what == 'del' and rule_id.isdigit():
        gone = next((r['text'] for r in rules.all_rules() if r['id'] == int(rule_id)), None)
        rules.remove(int(rule_id))
        updated = _list_rules()
        updated.toast = f'Removed: {gone}' if gone else 'That rule was already removed.'
        return updated
    return None


# ---------- saved facts ----------

REMEMBER_HELP = ('Tell me what to remember, for example:\n/remember my dog is named Max\n'
                 '/remember I prefer metric units\n/memories shows everything I remember.')


def _remember(args):
    if not args:
        return REMEMBER_HELP
    status, fact = memory.add(args, 'manual')
    return {
        'added': f'🧠 Got it, I\'ll remember: “{fact}”\nI\'ll know it in every chat. /memories shows everything I '
                 'remember.',
        'duplicate': f'I already remember that: “{fact}”',
        'secret': "🔒 I don't save passwords, codes, card or account numbers. Keep those somewhere safe instead.",
        'empty': 'That was too short to remember. Example: /remember my favorite color is green',
        'full': f'My memory is full ({memory.MAX_FACTS} facts). Remove some with /forget <number> first (see '
                '/memories).',
    }[status]


def _pickup_line():
    on = settings.load()['auto_facts']
    return (f"\nAutomatic pickup: {'on' if on else 'off'} "
            f"(/memories auto {'off' if on else 'on'} to turn it {'off' if on else 'on'})")


def _memories(args=''):
    words = args.lower().split()
    if words[:1] == ['auto'] and words[1:2] in (['on'], ['off']):
        settings.save({'auto_facts': words[1] == 'on'})
        return Reply('🤖 Automatic pickup is on: when you mention something lasting about yourself, I\'ll save it '
                     'and tell you ("🧠 Noted for next time").' if words[1] == 'on' else
                     '🤖 Automatic pickup is off. I\'ll only remember what you add with /remember.')
    facts = memory.all_facts()
    if not facts:
        return Reply("🧠 I don't have any saved facts about you yet.\nAdd one with /remember, for example:\n"
                     '/remember my birthday is March 3' + _pickup_line())
    lines = [f'{n}. {f["fact"]}' + (' 🤖' if f['source'] == 'auto' else '') for n, f in enumerate(facts, 1)]
    note = '\n🤖 = picked up from our chats' if any(f['source'] == 'auto' for f in facts) else ''
    return Reply('🧠 What I remember about you (in every chat):\n\n' + '\n'.join(lines) + note +
                 '\n\nTap 🗑 to forget one, or type /forget <number>.' + _pickup_line(),
                 rows([button(f'🗑 {n}', f'mem:del:{f["id"]}') for n, f in enumerate(facts, 1)]) +
                 [[button('🗑 Forget all', 'mem:all:')]])


def _forget(args):
    word = args.strip().lower().lstrip('#')
    facts = memory.all_facts()
    if word == 'all':
        if not facts:
            return 'There are no saved facts to forget.'
        return _confirm_forget_all(len(facts))
    if not word.isdigit():
        return 'Use /forget <number> (the numbers are in /memories), or /forget all.'
    if not 1 <= int(word) <= len(facts):
        return 'No saved fact has that number. Send /memories to see the list.'
    removed = memory.remove(facts[int(word) - 1]['id'])
    return f'🗑 Forgotten: “{removed}”'


def _confirm_forget_all(count):
    what = 'your 1 saved fact' if count == 1 else f'all {count} saved facts about you'
    return Reply(f'Forget {what}? This can\'t be undone.',
                 [[button('🗑 Yes, forget it' if count == 1 else f'🗑 Yes, forget all {count}', 'mem:wipe:'),
                   button('Keep', 'mem:keep:')]])


def _memory_button(what, detail):
    if what == 'del' and detail.isdigit():   # 🗑 under /memories
        removed = memory.remove(int(detail))
        updated = _memories()
        updated.toast = f'Forgotten: {removed}' if removed else 'That fact was already forgotten.'
        return updated
    if what == 'all':                        # 🗑 Forget all: ask first
        count = len(memory.all_facts())
        return _confirm_forget_all(count) if count else Reply('There are no saved facts to forget.')
    if what == 'wipe':
        count = memory.clear()
        return Reply(f'🗑 Done: forgot {count} saved fact{"s" if count != 1 else ""}. Your chats were not changed.')
    if what == 'keep':
        return Reply('Kept your saved facts. /memories shows them.')
    return None


# ---------- ratings (👍 👎 under every answer) and /learned ----------

def _rate_button(what, detail):
    """👍 / 👎 / a 👎 reason under an AI answer. The answer's text stays the same; only its buttons change.
    (🔄 Try again is handled by the page and the server, because it writes a new answer.)"""
    message_id, _, reason = detail.partition(':')
    message = chats.get_message(int(message_id)) if message_id.isdigit() else None
    if message is None or message['role'] != 'assistant':
        return None
    answer_id, text = message['id'], message['content']
    retry = learning.has_retry(message['buttons'])
    if what == 'up':
        learning.rate(answer_id, 1)
        return Reply(text, learning.done_buttons('👍 Thanks!', answer_id, retry),
                     "Thanks! I'll keep answering like this.")
    if what == 'down':
        learning.rate(answer_id, -1)
        return Reply(text, learning.reason_buttons(answer_id, retry), 'What was wrong with it? (optional)')
    if what == 'why' and (reason in learning.REASONS or reason == 'none'):
        learning.rate(answer_id, -1, None if reason == 'none' else reason)
        label = learning.REASONS[reason][2] if reason in learning.REASONS else 'thanks'
        return Reply(text, learning.done_buttons(f'👎 Noted: {label}', answer_id, retry),
                     "Thanks, I'll adjust. /learned shows what I've picked up.")
    if what == 'done':
        return Reply(text, message['buttons'], 'Already rated. Thanks!')
    return None


def _learned(args=''):
    scores = learning.preferences()
    if not scores:
        return Reply("🧠 Nothing learned from your ratings yet. Tap 👍 or 👎 under my answers (👎 asks why) and "
                     "I'll adjust to what you like.")
    applied = [key for key, score in scores.items() if score >= learning.THRESHOLD]
    noticing = [key for key, score in scores.items() if score < learning.THRESHOLD]
    text = '🧠 From your ratings:'
    if applied:
        text += "\n\nI'm now doing:\n" + '\n'.join(f'• {learning.NAMES.get(k, k)}' for k in applied)
    if noticing:
        text += '\n\nNoticing (not applied yet):\n' + '\n'.join(f'• {learning.NAMES.get(k, k)}' for k in noticing)
    text += '\n\n👍 on answers you like slowly undoes these. I also look at answers you rated to similar questions.'
    return Reply(text, [[button('🧽 Reset what you learned', 'learn:reset:')]])


def _learn_button(what, detail):
    if what == 'reset':
        count = learning.reset()
        return Reply("🧽 Done: I've forgotten what I learned from your ratings and will start fresh. (Your ratings "
                     'of answers to similar questions are still used.)' if count else
                     'There was nothing learned to reset.')
    return None


# ---------- online lookups ----------

def _online(lookup, service):
    """Wrap a lookup so a connection problem becomes a reply in plain words instead of an error."""
    def run(args):
        try:
            return lookup(args)
        except Unavailable as exc:
            return f"🌐 I couldn't get an answer from {exc} right now. Please try again in a minute."
        except httpx.HTTPStatusError as exc:
            return f'🌐 {service} answered with an error (HTTP {exc.response.status_code}). Please try again later.'
        except httpx.HTTPError:
            return f"🌐 I couldn't reach {service}. Is this computer connected to the internet?"
    return run


# ---------- notes ----------

def _note_list():
    latest, total = notes.recent()
    if not latest:
        return Reply('📝 Your notepad is empty.\n\n' + notes.HELP)
    shown = f'your {len(latest)} most recent of {total}' if total > len(latest) else f'all {total}'
    return Reply(f'📝 Notes ({shown}):\n\n' + '\n\n'.join(notes.format_note(*row) for row in latest) +
                 '\n\nTap 🗑 to delete one · /note find <words> searches',
                 rows([button(f'🗑 #{num}', f'note:del:{num}') for num, _, _ in latest]))


def _note(args):
    first, _, rest = args.partition(' ')
    word, rest = first.lower(), rest.strip()
    try:
        if not args or word == 'list':
            return _note_list()
        if word == 'help':
            return notes.HELP
        if word in ('find', 'search'):
            found, how = notes.find(rest)
            if not found:
                return f'🔍 No notes match “{rest}”. /notes shows your recent notes.'
            label = {'fuzzy': ' (close spellings)', 'date': ''}.get(how, '')
            return (f'🔍 {len(found)} note{"s" if len(found) != 1 else ""} for “{rest}”{label}:\n\n' +
                    '\n\n'.join(notes.format_note(*row) for row in found))
        if word in ('delete', 'del', 'remove'):
            number = rest.lstrip('#')
            if not number.isdigit():
                return 'Use /note delete <number>; the numbers are shown in /notes and search results.'
            removed = notes.delete(int(number))
            return (f'You have no note #{number}. /notes shows your notes.' if removed is None
                    else f'🗑 Deleted note #{number}: {removed[:200]}')
        if word == 'clear':
            total = notes.count()
            if not total:
                return 'Your notepad is already empty.'
            one = total == 1
            return Reply(f'Delete {"your only note" if one else f"all {total} of your notes"}? This can\'t be undone.',
                         [[button('🗑 Yes, delete it' if one else f'🗑 Yes, delete all {total}', 'note:wipe:'),
                           button('Keep it' if one else 'Keep them', 'note:keep:')]])
        body = rest if word == 'add' else args
        num = notes.add(body)
        return Reply(f'📝 Saved as note #{num}: {body.strip()[:200]}\n/note find <word> to search · /notes to list',
                     [[button('↩️ Undo', f'note:undo:{num}')]])
    except notes.NoteError as exc:
        return str(exc)


def _notes(args=''):
    """/notes lists them; "/notes garage" searches, like "/note find garage"."""
    words = args.strip()
    return _note(words if not words or words.split()[0].lower() in notes.COMMAND_WORDS else 'find ' + words)


def _note_button(what, detail):
    if what == 'del' and detail.isdigit():     # 🗑 under /notes
        removed = notes.delete(int(detail))
        updated = _note_list()
        updated.toast = f'Deleted #{detail}: {removed[:60]}' if removed else 'That note was already deleted.'
        return updated
    if what == 'undo' and detail.isdigit():    # ↩️ Undo right after saving
        removed = notes.delete(int(detail))
        return Reply('↩️ Undone: that note was removed.' if removed else 'That note was already deleted.')
    if what == 'wipe':
        count = notes.clear()
        return Reply(f'🗑 Deleted all {count} note{"s" if count != 1 else ""}.')
    if what == 'keep':
        return Reply('Kept your notes. /notes shows them.')
    return None


# ---------- /qr ----------

def _qr(args):
    try:
        image, caption = qr.make_qr(args)
    except qr.QRError as exc:
        return Reply(str(exc), saved_command=qr.safe_command(args) or '')
    return Reply(caption, image=image, saved_command=qr.safe_command(args) or '')


# ---------- dice ----------

def _roll(args):
    text = roll_dice(args)
    expression = ' '.join(args.split())[:100]
    rolled = text.startswith('🪙') or (' = ' in text and 'Usage' not in text)   # a coin, or a result with a total
    if not rolled:
        return Reply(text)   # usage or an error: nothing to roll again
    return Reply(text, [[button('🎲 Roll again', f'roll:again:{expression}')]])


def _roll_button(what, expression):
    """🎲 Roll again: a new roll of the same dice, replacing the old result."""
    if what == 'again':
        return _roll(expression)
    return None


def _rule(args):
    if not args:
        return RULE_HELP
    first, _, rest = args.partition(' ')
    if first.lower() in ('delete', 'remove', 'del'):
        current = rules.all_rules()
        number = rest.strip().lstrip('#')
        if not number.isdigit() or not 1 <= int(number) <= len(current):
            return f'Use /rule delete <number>, with a number from /rules (1 to {len(current)}).' if current \
                else 'There are no house rules to delete.'
        rule = current[int(number) - 1]
        rules.remove(rule['id'])
        return f'Removed house rule {number}: {rule["text"]}'
    try:
        rule_id = rules.add(args)
    except ValueError as exc:
        return str(exc)
    if rule_id is None:
        return 'That rule is already there. See them all with /rules.'
    return f'Added house rule: {" ".join(args.split())}\nIt applies to every chat from the next message.'


# ---------- help ----------

def _help(args=''):
    wanted = args.strip().lstrip('/').lower()
    if wanted:
        command = find(wanted)
        if command is None:
            return Reply(f"There's no /{wanted} command. " + did_you_mean(wanted))
        names = ' '.join('/' + n for n in (command.name, *command.aliases))
        return f'{names}\n{command.summary}\nExample: {command.example}'
    lines = ['BEYOND commands (type / in the message box for a quick list):']
    for group in dict.fromkeys(c.group for c in COMMANDS):
        lines.append('')
        lines.append(group)
        for c in COMMANDS:
            if c.group == group:
                lines.append(f'  /{c.name} — {c.summary}  (e.g. {c.example})')
    lines += ['', 'Anything that doesn\'t start with / goes to the AI. /help <command> shows one command.']
    return '\n'.join(lines)


COMMANDS = [
    Command('help', 'List every command, or explain one', '/help calc', _help, group='Help'),
    Command('calc', 'Calculator: maths, percentages, tips and splitting a bill', '/calc tip 85.50 18% split 4',
            calculate),
    Command('convert', 'Convert units: temperature, distance, weight, cooking, speed and more', '/convert 72 f to c',
            convert),
    Command('time', 'The time in a city, several cities, or convert a time between places',
            '/time 3pm London to Tokyo', world_time),
    Command('roll', 'Roll dice or flip a coin', '/roll 2d20+3', _roll),
    Command('web', 'Search the web (DuckDuckGo)', '/web best hiking trails near Denver',
            _online(web_search.search_web, 'DuckDuckGo'), aliases=('search',), group='Look things up'),
    Command('weather', 'Weather now, the next hours and 3 days', '/weather San Jose, CA',
            _online(weather.get_weather, 'the weather service (Open-Meteo)'), group='Look things up'),
    Command('news', 'Headlines: top, world, us, tech, science, sports… or any topic', '/news tech',
            _online(news.get_news, 'the news feeds'), group='Look things up'),
    Command('wiki', 'A Wikipedia summary', '/wiki Apollo 11', _online(wikipedia.search_wikipedia, 'Wikipedia'),
            group='Look things up'),
    Command('define', 'Dictionary: meaning, pronunciation and examples', '/define serendipity',
            _online(dictionary.define_word, 'the dictionary'), group='Look things up'),
    Command('movie', 'A film: year, director, cast, ratings and summary', '/movie Dune 1984',
            _online(lambda title: movies.get_movie(title, 'movie'), 'the movie services'), aliases=('film',),
            group='Look things up'),
    Command('tv', 'A TV show: years, network, cast, rating and summary', '/tv Breaking Bad',
            _online(lambda title: movies.get_movie(title, 'tv'), 'the TV service'), group='Look things up'),
    Command('joke', 'A joke: dad, pun, nerd, absurd, or about any topic', '/joke cats',
            _online(jokes.get_joke, 'the joke services'), group='Extras'),
    Command('quote', 'A random quote', '/quote', _online(little_lookups.random_quote, 'the quote service'),
            group='Extras'),
    Command('cat', 'A random cat fact', '/cat', _online(little_lookups.cat_fact, 'the cat fact service'),
            aliases=('catfact',), group='Extras'),
    Command('rewrite', 'Say a message in another tone: professional, friendly, funny, polite, dramatic, concise',
            "/rewrite polite I can't come tomorrow", rewrite.rewrite, group='Extras'),
    Command('qr', 'Make a QR code for a link, text, or Wi-Fi (/qr wifi Name | password)', '/qr example.com', _qr,
            group='Extras'),
    Command('so', 'Search Stack Overflow for programming questions', '/so python read a file line by line',
            _online(little_lookups.stack_overflow, 'Stack Overflow'), aliases=('stackoverflow',),
            group='Look things up'),
    Command('note', 'Save a note, or find, delete and clear them', '/note garage key is in the blue folder', _note,
            group='Notes'),
    Command('notes', 'Your recent notes (or /notes <words> to search)', '/notes', _notes, group='Notes'),
    Command('remember', 'Tell BEYOND something to remember in every chat', '/remember my dog is named Max',
            _remember, group='Memory'),
    Command('memories', 'See what BEYOND remembers about you (and forget things); /memories auto on|off',
            '/memories', _memories, aliases=('facts',), group='Memory'),
    Command('forget', 'Forget one saved fact, or all of them', '/forget 2', _forget, group='Memory'),
    Command('learned', 'What BEYOND learned from your 👍 👎 ratings (with a reset)', '/learned', _learned,
            group='Memory'),
    Command('rule', 'Add or delete a house rule BEYOND follows in every chat', '/rule Use metric units', _rule,
            group='House rules'),
    Command('rules', 'List the house rules', '/rules', _list_rules, group='House rules'),
]
_BY_NAME = {name: c for c in COMMANDS for name in (c.name, *c.aliases)}


def find(name):
    return _BY_NAME.get(name.lower())


def did_you_mean(name):
    close = difflib.get_close_matches(name.lower(), list(_BY_NAME), n=2, cutoff=0.6)
    if close:
        return 'Did you mean ' + ' or '.join('/' + c for c in close) + '? Type /help to see every command.'
    return 'Type /help to see every command.'


def _as_reply(answer):
    return answer if isinstance(answer, Reply) else Reply(str(answer))


def run(text):
    """Answer a /command with a Reply. Unknown commands get a "did you mean…?" reply. Blocking (some commands look
    things up online), so call it from a thread."""
    name, _, args = text[1:].strip().partition(' ')
    name = name.split('@')[0]
    command = find(name)
    if command is None:
        return Reply(f"I don't know the command /{name}. " + did_you_mean(name))
    return _as_reply(command.run(args.strip()))


# Button handlers: the first part of a button's action picks the handler; the rest is passed to it.
ACTIONS = {
    'rules': _rules_button,
    'roll': _roll_button,
    'mem': _memory_button,
    'rate': _rate_button,
    'learn': _learn_button,
    'note': _note_button,
}


def press(action):
    """Run a button's action. Returns the message's new Reply, or None if the action isn't understood."""
    name, _, rest = action.partition(':')
    what, _, detail = rest.partition(':')
    handler = ACTIONS.get(name)
    return _as_reply(handler(what, detail)) if handler else None


def menu():
    """The list the page shows when you type "/"."""
    return [{'name': c.name, 'summary': c.summary, 'example': c.example} for c in COMMANDS]
