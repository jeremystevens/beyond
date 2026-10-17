"""Slash commands typed in the chat, like /calc or /rules. BEYOND answers them itself; they never go to the AI.

Every command is one entry in COMMANDS below: its name, a one-line summary, an example, and the function that
answers it. /help, the command list the page shows when you type "/", and "did you mean…?" are all built from
that list, so a new command only needs adding here.
"""
import difflib
from dataclasses import dataclass, field
from typing import Callable

from app import rules
from app.tools.calculator import calculate
from app.tools.dice import roll_dice
from app.tools.units import convert
from app.tools.world_time import world_time


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
        return 'There are no house rules yet.\n\n' + RULE_HELP
    lines = [f'{number}. {rule["text"]}' for number, rule in enumerate(current, 1)]
    return 'House rules (added to every chat):\n' + '\n'.join(lines) + '\n\nRemove one with /rule delete <number>.'


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
            return f"There's no /{wanted} command. " + did_you_mean(wanted)
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
    Command('roll', 'Roll dice or flip a coin', '/roll 2d20+3', roll_dice),
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


def run(text):
    """Answer a /command. Unknown commands get a "did you mean…?" reply. Blocking (some commands look things up
    online), so call it from a thread."""
    name, _, args = text[1:].strip().partition(' ')
    name = name.split('@')[0]
    command = find(name)
    if command is None:
        return f"I don't know the command /{name}. " + did_you_mean(name)
    return command.run(args.strip())


def menu():
    """The list the page shows when you type "/"."""
    return [{'name': c.name, 'summary': c.summary, 'example': c.example} for c in COMMANDS]
