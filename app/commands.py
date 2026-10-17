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

from app import memory, rules, settings
from app.tools.calculator import calculate
from app.tools.dice import roll_dice
from app.tools.units import convert
from app.tools.world_time import world_time


@dataclass
class Reply:
    """What a command (or a button press) answers: text, optional buttons, and an optional short notice (toast)."""
    text: str
    buttons: list = field(default_factory=list)   # rows of {'label', 'action'}
    toast: str = ''


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
    Command('remember', 'Tell BEYOND something to remember in every chat', '/remember my dog is named Max',
            _remember, group='Memory'),
    Command('memories', 'See what BEYOND remembers about you (and forget things); /memories auto on|off',
            '/memories', _memories, aliases=('facts',), group='Memory'),
    Command('forget', 'Forget one saved fact, or all of them', '/forget 2', _forget, group='Memory'),
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
