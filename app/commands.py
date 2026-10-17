"""Slash commands typed in the chat, like /rules. Handled by BEYOND itself, never sent to the AI.

Phase 7 starts with the house-rule commands; Phase 8 turns this into the full command system (a command list
when you type /, /help, "did you mean…?" and more commands).
"""
from app import rules

RULE_HELP = ('/rule <text> adds a house rule, for example: /rule Always answer in under 3 sentences.\n'
             '/rules lists them. /rule delete <number> removes one.')


def _list_rules():
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


COMMANDS = {
    'rule': _rule,
    'rules': lambda args: _list_rules(),
}


def run(text):
    """Run a /command. Returns its reply, or None if `text` isn't a command BEYOND knows."""
    if not text.startswith('/'):
        return None
    name, _, args = text[1:].partition(' ')
    handler = COMMANDS.get(name.lower().split('@')[0])
    if handler is None:
        return None
    return handler(args.strip())


def unknown_reply(text):
    name = text.split()[0]
    return (f"I don't know the command {name}. Commands so far: " + ', '.join('/' + c for c in COMMANDS) +
            '. More arrive soon.')
