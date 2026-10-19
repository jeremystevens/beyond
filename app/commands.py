"""Slash commands typed in the chat, like /calc or /rules. BEYOND answers them itself; they never go to the AI.

Every command is one entry in COMMANDS below: its name, a one-line summary, an example, and the function that
answers it. /help, the command list the page shows when you type "/", and "did you mean…?" are all built from
that list, so a new command only needs adding here.

Buttons: a command can answer with a Reply that has buttons under it. Each button has an action like
"rules:del:5" (handler name, then its details). Pressing it calls ACTIONS["rules"]("del", "5"), which returns the
message's new text and buttons, so the message changes in place. The server only accepts actions that are on that
message's own buttons.
"""
import contextvars
import difflib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import httpx

from app import briefing, chats, checklists, expenses, learning, memory, notes, reminders, rules, search_history, settings
from app.tools import dictionary, jokes, little_lookups, movies, news, qr, rewrite, weather, web_search, wikipedia
from app.tools.calculator import calculate
from app.tools.dice import roll_result
from app import blackjack, engine, followups, games, hangman, study_quiz, tictactoe, trivia
from app.tools.units import convert
from app.tools.imagine import HELP as IMAGINE_HELP
from app.tools import speech
from app.tools.vision import HELP as LOOK_HELP
from app.tools.scan import HELP as SCAN_HELP
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
    save_message: Callable = None  # optional atomic storage for private game state
    game: dict | None = None  # menu or dice result, saved and rendered by the browser
    speech_text: str | None = None  # empty string = read the last AI answer; None = no speech request
    on_saved: Callable = None  # called with the chat's id once the reply is saved (e.g. where a reminder goes off)
    lookup_context: dict | None = None  # real lookup data for short follow-ups in this chat only
    pending_lookup: dict | None = None  # a location/correction waiting for the next user turn


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


# ---------- checklists ----------

def _list_view(list_id, intro=''):
    """One list: a button per item (tap to check or uncheck), then 🧹 Clear checked and 🗑 Delete list."""
    found = checklists.get_list(list_id)
    if not found:
        return Reply('That list no longer exists. /list shows your lists.')
    name = found[1]
    title = f'{checklists.emoji(name)} {name.title()}'
    items = checklists.items_of(list_id)
    if not items:
        return Reply(f'{intro}{title} is empty.\nAdd items: /list {name} add milk, eggs',
                     [[button('🗑 Delete list', f'list:ask:{list_id}')]])
    done = sum(1 for _, _, checked in items if checked)
    shown = items[:checklists.MAX_BUTTONS]
    more = ''.join(f'\n{n}. {"✅" if checked else "⬜"} {text}' for n, (_, text, checked) in enumerate(items, 1)
                   if n > checklists.MAX_BUTTONS)
    actions = ([button(f'🧹 Clear {done} checked', f'list:clear:{list_id}')] if done else []) + \
        [button('🗑 Delete list', f'list:ask:{list_id}')]
    return Reply(f'{intro}{title} · {done} of {len(items)} done\nTap an item to check it off. Add more: '
                 f'/list {name} add …{more}',
                 [[button(('✅ ' if checked else '⬜ ') + text[:60], f'list:tick:{item_id}')]
                  for item_id, text, checked in shown] + [actions])


def _lists_overview():
    found = checklists.all_lists()
    if not found:
        return Reply("✅ You don't have any lists yet.\n\n" + checklists.HELP)
    lines = [f'{checklists.emoji(name)} {name.title()} — {open_} to do' +
             (f' ({total - open_} checked)' if total - open_ else '') for _, name, open_, total in found]
    return Reply('✅ Your lists:\n\n' + '\n'.join(lines) + '\n\nTap one to open it.',
                 [[button(f'{checklists.emoji(name)} {name.title()}', f'list:open:{list_id}')]
                  for list_id, name, _, _ in found])


def _list(args):
    if args.strip().lower() == 'help':
        return checklists.HELP
    name, action, rest = checklists.parse_command(args)
    try:
        if not name and action == 'show':
            return _lists_overview()
        if action == 'add':
            list_id, _, added, skipped = checklists.add_items(name or checklists.DEFAULT_LIST, rest)
            return _list_view(list_id, f'Added {added} item{"s" if added != 1 else ""}' +
                              (f' ({skipped} already on the list)' if skipped else '') + '.\n')
        found = checklists.find_list(name or checklists.DEFAULT_LIST)
        if not found:
            return (f'You have no list called “{name or checklists.DEFAULT_LIST}”. /list shows your lists; '
                    f'/list {name or "groceries"} add … starts one.')
        list_id, list_name = found
        if action == 'show':
            return _list_view(list_id)
        if action == 'remove':
            number = rest.lstrip('#')
            if not number.isdigit():
                return f'Use /list {list_name} remove <number> (count from the top of the list).'
            removed = checklists.remove_item(list_id, int(number))
            if removed is None:
                return f'“{list_name}” has no item number {number}.'
            return _list_view(list_id, f'Removed “{removed}”.\n')
        if action == 'clear':
            count = checklists.clear_checked(list_id)
            return _list_view(list_id, f'🧹 Cleared {count} checked item{"s" if count != 1 else ""}.\n')
        return _confirm_list_delete(list_id, list_name)
    except checklists.ListError as exc:
        return str(exc)


def _confirm_list_delete(list_id, name):
    return Reply(f'Delete the whole “{name}” list? This can\'t be undone.',
                 [[button('🗑 Yes, delete it', f'list:delete:{list_id}'), button('Keep it', f'list:open:{list_id}')]])


def _list_button(what, detail):
    if not detail.isdigit():
        return None
    number = int(detail)
    if what == 'tick':     # tap an item: check or uncheck it
        list_id = checklists.toggle_item(number)
        return _list_view(list_id) if list_id else Reply('That item is gone. /list shows your lists.')
    if what == 'open':
        return _list_view(number)
    if what == 'clear':
        count = checklists.clear_checked(number)
        updated = _list_view(number)
        updated.toast = f'Cleared {count} checked item{"s" if count != 1 else ""}.'
        return updated
    if what == 'ask':      # 🗑 Delete list: ask first
        found = checklists.get_list(number)
        return _confirm_list_delete(*found) if found else Reply('That list was already deleted.')
    if what == 'delete':
        return Reply('🗑 List deleted.' if checklists.delete_list(number) else 'That list was already deleted.')
    return None


# ---------- expenses ----------

def _spent_saved(cents, category, note, day):
    today = date.today()
    when = 'today' if day == today else 'yesterday' if day == today - timedelta(days=1) else f'{day:%b} {day.day}'
    month = expenses.parse_period(f'{day.year}-{day.month}', today)
    month_total = sum(r[1] for r in expenses._rows(month[1], month[2]))
    label = 'This month' if (day.year, day.month) == (today.year, today.month) else month[3]
    return (f'💸 {expenses.money(cents)} · {expenses.category_label(category)} · {when}' +
            (f'\n“{note}”' if note else '') + f'\n{label}: {expenses.money(month_total)}')


def _spent_done_buttons(expense_id):
    return [[button('↩️ Undo', f'spent:undo:{expense_id}'), button('🏷 Change category', f'spent:pick:{expense_id}')]]


def _spent_picker(expense_id, word):
    """Buttons to pick a category (rows of 3), keep the typed word as a new one, or undo."""
    picks = rows([button(f'{icon} {label}', f'spent:cat:{expense_id}:{key}')
                  for key, (label, icon, _) in expenses.CATEGORIES.items()], 3)
    if word:
        picks.append([button(f'➕ New category “{word.title()[:20]}”', f'spent:new:{expense_id}')])
    return picks + [[button('↩️ Undo', f'spent:undo:{expense_id}')]]


def _spent_report(period):
    text, has_rows = expenses.report(period, date.today())
    # A link, not an action: the page downloads the file from /api/expenses.csv.
    return Reply(text, [[{'label': '📄 Download CSV', 'url': f'/api/expenses.csv?period={period[4]}'}]]
                 if has_rows else [])


def _spent_recent():
    latest = expenses.recent()
    if not latest:
        return Reply('No expenses logged yet.\n\n' + expenses.HELP)
    lines = []
    for number, (_, cents, category, note, spent_on) in enumerate(latest, 1):
        day = date.fromisoformat(spent_on)
        lines.append(f'{number}. {expenses.money(cents)} · {expenses.category_label(category)} · {day:%b} {day.day}' +
                     (f' · {note[:40]}' if note else ''))
    return Reply('💸 Your last expenses:\n\n' + '\n'.join(lines) + '\n\nTap 🗑 and a number to delete that expense.',
                 rows([button(f'🗑 {n}', f'spent:del:{row[0]}') for n, row in enumerate(latest, 1)], 5))


def _spent(args):
    text = args.strip()
    lowered = text.lower()
    if lowered == 'help':
        return expenses.HELP
    if lowered in ('recent', 'list', 'last', 'undo', 'delete'):
        return _spent_recent()
    if lowered in ('categories', 'category'):
        labels = [expenses.category_label(key) for key in expenses.CATEGORIES] + \
            [expenses.category_label(c) for c in expenses.user_categories()]
        return ('Categories (words like "lunch", "gas", "rent" are matched automatically; for unknown words you pick '
                'one or make a new one):\n' + '\n'.join(labels))
    # A report? ("", "october", "2025", "all"…). A bare year like 2026 is a report, not a $2,026 expense.
    period = expenses.parse_period(text, date.today())
    if period:
        return _spent_report(period)
    try:
        plan = expenses.plan_expense(text)
    except expenses.ExpenseError as exc:
        return f'{exc}\n\n{expenses.HELP}' if 'How much' in str(exc) else str(exc)
    expense_id = expenses.add_expense(plan)
    saved = _spent_saved(plan['cents'], plan['category'] or 'other', plan['note'], plan['day'])
    if plan['category']:
        return Reply(saved, _spent_done_buttons(expense_id))
    ask = f'I don\'t know which category “{plan["word"]}” is.' if plan['word'] else 'Which category is this?'
    return Reply(f'{saved}\n\n{ask} Pick one (I\'ll remember it), or keep it as Other:',
                 _spent_picker(expense_id, plan['word']))


def _spent_button(what, detail):
    expense_id, _, key = detail.partition(':')
    if not expense_id.isdigit():
        return None
    expense_id = int(expense_id)
    if what in ('undo', 'del'):
        removed = expenses.delete_expense(expense_id)
        if what == 'del':   # 🗑 under /spent recent
            updated = _spent_recent()
            updated.toast = f'Deleted {expenses.money(removed[1])}' if removed else 'That expense was already deleted.'
            return updated
        return Reply(f'↩️ Undone: {expenses.money(removed[1])} removed.' if removed else
                     'That expense was already deleted.')
    row = expenses.get_expense(expense_id)
    if not row:
        return Reply('That expense was deleted.')
    if what == 'pick':      # 🏷 Change category: show the choices
        return Reply(_spent_saved(row[1], row[2], row[3], date.fromisoformat(row[5])), _spent_picker(expense_id, row[4]))
    if what == 'cat' and key in expenses.CATEGORIES:
        category = key
    elif what == 'new' and row[4]:   # keep the typed word as a new category
        category = row[4].title()[:30]
    else:
        return None
    expenses.set_category(expense_id, category)
    updated = Reply(_spent_saved(row[1], category, row[3], date.fromisoformat(row[5])), _spent_done_buttons(expense_id))
    updated.toast = f'Saved as {expenses.category_label(category)}' + (f' · “{row[4]}” remembered' if row[4] else '')
    return updated


# ---------- reminders ----------

def _remind(args):
    if not args or args.lower() == 'help':
        return reminders.USAGE
    if reminders.active_count() >= reminders.MAX_ACTIVE:
        return f'You already have {reminders.MAX_ACTIVE} reminders. Cancel some with /reminders first.'
    try:
        plan = reminders.plan_reminder(args)
    except reminders.ReminderError as exc:
        return str(exc)
    reminder_id = reminders.create(None, plan['message'], plan['due'], plan['recur'], plan['tz'])
    when = reminders.when_text(plan['due'], plan['tz'])
    text = (f'🔁 Got it: “{plan["message"]}” {reminders.describe_rule(plan["recur"])}.\nNext: {when}.'
            if plan['recur'] else f'⏰ Got it: “{plan["message"]}” {when}.')
    return Reply(text + '\nIt will pop up in this chat. /reminders lists or cancels it.',
                 [[button('↩️ Undo', f'remind:undo:{reminder_id}')]],
                 on_saved=lambda chat_id: reminders.set_chat(reminder_id, chat_id))


def _reminders_list():
    upcoming = reminders.active()
    if not upcoming:
        return Reply('⏰ You have no upcoming reminders.\n\n' + reminders.USAGE)
    lines = []
    for number, (_, message, due_at, recur, tz) in enumerate(upcoming[:30], 1):
        repeat = f' 🔁 {reminders.describe_rule(recur)}' if recur else ''
        lines.append(f'{number}. {message[:120]}\n    ⏰ {reminders.when_text(due_at, tz)}{repeat}')
    more = f'\n…and {len(upcoming) - 30} more.' if len(upcoming) > 30 else ''
    return Reply(f'⏰ Your reminders ({len(upcoming)}):\n\n' + '\n'.join(lines) + more +
                 '\n\nTap 🗑 and a number to cancel that reminder.',
                 rows([button(f'🗑 {n}', f'remind:del:{row[0]}') for n, row in enumerate(upcoming[:30], 1)], 5))


def _reminders(args=''):
    words = args.lower().split()
    if words[:1] in (['delete'], ['cancel'], ['remove']) and len(words) > 1 and words[1].lstrip('#').isdigit():
        upcoming = reminders.active()
        number = int(words[1].lstrip('#'))
        if not 1 <= number <= len(upcoming):
            return 'No reminder has that number. Send /reminders to see the list.'
        return f'🗑 Cancelled: “{reminders.delete(upcoming[number - 1][0])}”'
    return _reminders_list()


def reminder_buttons(reminder_id):
    """Under a reminder that went off."""
    return [[button('✅ Done', f'remind:done:{reminder_id}'), button('😴 10 min', f'remind:snooze:{reminder_id}:10'),
             button('😴 1 hour', f'remind:snooze:{reminder_id}:60')]]


def _remind_button(what, detail):
    number, _, minutes = detail.partition(':')
    if not number.isdigit():
        return None
    reminder_id = int(number)
    if what == 'undo':
        removed = reminders.delete(reminder_id)
        return Reply(f'↩️ Undone: “{removed}” was removed.' if removed else
                     'That reminder was already cancelled or has gone off.')
    if what == 'del':   # 🗑 under /reminders
        removed = reminders.delete(reminder_id)
        updated = _reminders_list()
        updated.toast = f'Cancelled: {removed[:80]}' if removed else 'That reminder is already gone.'
        return updated
    pressed = PRESSED.get()
    if pressed is None:
        return None
    if what == 'done':
        return Reply(pressed['content'], [[button('✅ Done', f'remind:ok:{reminder_id}')]], 'Marked as done.')
    if what == 'ok':
        return Reply(pressed['content'], pressed['buttons'])
    if what == 'snooze' and minutes in ('10', '60'):
        found = reminders.get(reminder_id)
        if not found:
            return Reply(pressed['content'], [], 'That reminder is no longer available.')
        due_at = datetime.now(timezone.utc) + timedelta(minutes=int(minutes))
        reminders.create(pressed['chat_id'], found[2], due_at)
        label = '1 hour' if minutes == '60' else '10 minutes'
        return Reply(pressed['content'], [[button(f'😴 Snoozed {label}', f'remind:ok:{reminder_id}')]],
                     f'Snoozed: it will pop up again in {label}.')
    return None


# ---------- morning briefing ----------

def _morning_buttons(s):
    toggles = [button(('✅ ' if key in s['sections'] else '▫️ ') + label.split(' ', 1)[1], f'morning:sec:{key}')
               for key, label in briefing.SECTIONS.items()]
    return [[button('⏹ Turn off' if s['enabled'] else '▶️ Turn on', 'morning:toggle:')],
            [button(f"⏰ Weekdays {briefing.display_time(s['weekday_time'])}", 'morning:pick:wd'),
             button(f"🛋 Weekends {briefing.display_time(s['weekend_time'])}", 'morning:pick:we')],
            toggles[:2], toggles[2:],
            [button(f"📰 News: {s['news']} ▸", 'morning:news:'), button(f"💬 Ending: {s['closer']} ▸", 'morning:closer:')],
            [button('📨 Send it now', 'morning:now:')]]


def _morning_menu(s, note=''):
    return Reply((note + '\n\n' if note else '') + briefing.menu_text(s), _morning_buttons(s))


def _remember_chat(s):
    """The briefing arrives in the chat where /morning was last used."""
    def save(chat_id):
        current = briefing.get_settings()
        current['chat_id'] = chat_id
        briefing.save_settings(current)
    return save


def _morning(args):
    s = briefing.get_settings()
    first, _, rest = args.strip().partition(' ')
    first, rest = first.lower(), rest.strip()
    note = ''
    try:
        if not first:
            pass
        elif first == 'help':
            return briefing.HELP
        elif first == 'on':
            if not s['timezone']:
                return 'First tell me your city (it also sets the time zone):\n/morning city San Carlos, CA'
            s['enabled'] = 1
            briefing.skip_today_if_passed(s)
            note = '✅ Morning briefing is on. It will arrive in this chat, with a popup.'
        elif first == 'off':
            s['enabled'] = 0
            note = '⏹ Morning briefing is off.'
        elif first == 'now':
            if not s['timezone']:
                return 'Set your city first: /morning city San Carlos, CA'
            return Reply(briefing.build(s), on_saved=_remember_chat(s))
        elif first == 'city':
            if not rest:
                return 'Usage: /morning city San Carlos, CA'
            try:
                briefing.set_city(s, rest)
            except httpx.HTTPError:
                return "🌐 I couldn't reach the place lookup (Open-Meteo). Is this computer connected to the internet?"
            briefing.skip_today_if_passed(s)
            note = f"📍 City set to {s['place']} ({s['timezone']})."
        elif first == 'name':
            s['name'] = ' '.join(rest.split())[:40] or None
            note = f"👋 I'll say good morning to {s['name']}." if s['name'] else '👋 No name in the greeting.'
        elif first in ('weekday', 'weekdays', 'weekend', 'weekends'):
            key = 'weekday_time' if first.startswith('weekday') else 'weekend_time'
            s[key] = briefing.parse_time(rest)
            briefing.skip_today_if_passed(s)
            note = f"⏰ {first.rstrip('s').title()}s: {briefing.display_time(s[key])}."
        elif first == 'news' and rest.lower() not in ('on', 'off'):
            topic = {'technology': 'tech', 'u.s.': 'us', 'usa': 'us', 'sport': 'sports'}.get(rest.lower(), rest.lower())
            if topic not in briefing.NEWS_CHOICES:
                return 'News choices: ' + ', '.join(briefing.NEWS_CHOICES)
            s['news'] = topic
            note = f'📰 Headlines: {topic}.'
        elif first in ('quote', 'joke') or (first == 'ending' and rest.lower() in ('quote', 'joke')):
            s['closer'] = first if first in ('quote', 'joke') else rest.lower()
            note = f"💬 Ending with a {s['closer']}."
        elif first in ('weather', 'reminders', 'headlines', 'news', 'closer') and rest.lower() in ('on', 'off'):
            key = 'headlines' if first == 'news' else first
            chosen = [k for k in s['sections'] if k != key] + ([key] if rest.lower() == 'on' else [])
            s['sections'] = [k for k in briefing.SECTIONS if k in chosen]
            note = f'{key.title()} {rest.lower()}.'
        else:
            value = briefing.parse_time(args)   # "/morning 7:30" sets weekdays and weekends
            if value == 'off':
                return 'Use /morning off to stop the briefing.'
            s['weekday_time'] = s['weekend_time'] = value
            briefing.skip_today_if_passed(s)
            note = f'⏰ Every day at {briefing.display_time(value)}.'
    except ValueError as exc:
        return f'{exc}\n\n{briefing.HELP}'
    briefing.save_settings(s)
    menu = _morning_menu(s, note)
    menu.on_saved = _remember_chat(s)
    return menu


def _morning_button(what, detail):
    s = briefing.get_settings()
    pressed = PRESSED.get()
    if what == 'pick' and detail in ('wd', 'we'):
        times = list(briefing.TIME_CHOICES) + (['off'] if detail == 'we' else [])
        picks = rows([button(briefing.display_time(t) if t != 'off' else 'Off', f"morning:t:{detail}{t.replace(':', '')}")
                      for t in times], 3)
        label = 'weekdays' if detail == 'wd' else 'weekends'
        return Reply(f'⏰ Pick a time for {label} (or type /morning {label} 7:15):',
                     picks + [[button('⬅ Back', 'morning:back:')]])
    if what == 'now':
        if not s['timezone']:
            return Reply(briefing.menu_text(s), _morning_buttons(s), 'Set your city first: /morning city San Carlos, CA')
        if pressed:   # the briefing arrives as a new message in this chat, like a scheduled one
            s['chat_id'] = pressed['chat_id']
            briefing.save_settings(s)
            chats.add_message(pressed['chat_id'], 'assistant', briefing.build(s), kind='briefing')
        return Reply(briefing.menu_text(s), _morning_buttons(s), 'Sent: it appears below in a moment.')
    toast = ''
    if what == 'toggle':
        if not s['enabled'] and not s['timezone']:
            return Reply(briefing.menu_text(s), _morning_buttons(s), 'First set your city: /morning city San Carlos, CA')
        s['enabled'] = 0 if s['enabled'] else 1
        if s['enabled']:
            briefing.skip_today_if_passed(s)
        toast = 'Morning briefing on.' if s['enabled'] else 'Morning briefing off.'
    elif what == 't' and len(detail) in (5, 6):   # wd0730, weoff
        which, value = detail[:2], detail[2:]
        if value != 'off' and not value.isdigit():
            return None
        s['weekday_time' if which == 'wd' else 'weekend_time'] = 'off' if value == 'off' else f'{value[:2]}:{value[2:]}'
        briefing.skip_today_if_passed(s)
    elif what == 'sec' and detail in briefing.SECTIONS:
        s['sections'] = [k for k in briefing.SECTIONS if (k in s['sections']) != (k == detail)]
    elif what == 'news':
        choices = briefing.NEWS_CHOICES
        s['news'] = choices[(choices.index(s['news']) + 1) % len(choices)] if s['news'] in choices else 'top'
    elif what == 'closer':
        s['closer'] = 'joke' if s['closer'] == 'quote' else 'quote'
    elif what != 'back':
        return None
    if pressed:
        s['chat_id'] = pressed['chat_id']
    briefing.save_settings(s)
    return Reply(briefing.menu_text(s), _morning_buttons(s), toast)


# ---------- /qr ----------

def _qr(args):
    try:
        image, caption = qr.make_qr(args)
    except qr.QRError as exc:
        return Reply(str(exc), saved_command=qr.safe_command(args) or '')
    return Reply(caption, image=image, saved_command=qr.safe_command(args) or '')


# ---------- dice ----------

def _trivia(args=''):
    requested = args.strip().lower()
    if requested in ('score', 'scores', 'stats', 'me'):
        return Reply(trivia.stats_text())
    if requested in ('categories', 'category', 'list'):
        return Reply('Trivia categories:\n' + ', '.join(sorted(trivia.source.CATEGORIES)) + '\n\n' + trivia.HELP,
                     game=trivia.picker())
    if requested in ('', 'help', '?'):
        return Reply('Trivia\nChoose a category and difficulty for a round of up to five questions. Internet is needed to fetch questions.',
                     game=trivia.picker())
    try:
        words = requested.split()
        category, difficulty = trivia.source.parse_options(words[1:] if words[0] == 'start' else words)
    except ValueError as exc:
        return Reply(str(exc) + '\n\n' + trivia.HELP, game=trivia.picker())
    try:
        state = trivia.prepare(category, difficulty)
    except trivia.source.TriviaError as exc:
        return Reply(str(exc), game=trivia.picker(category, difficulty))
    game = trivia.public(state)
    return Reply(trivia.text(game), game=game, save_message=lambda cid: trivia.save_new(cid, state))


def _blackjack(args=''):
    requested = args.strip().lower()
    if requested in ('stats', 'score', 'record', 'me'):
        return Reply(blackjack.stats_text())
    if requested in ('rules', 'help', 'how', '?'):
        return Reply(blackjack.rules.RULES)
    state = blackjack.new()
    game = blackjack.public(state)
    reply = Reply(blackjack.text(game), game=game)

    def save(chat_id):
        """Save the hand (a natural is recorded with it), then show exactly what was saved, record included."""
        message_id = blackjack.save_new(chat_id, state)
        with chats.connect() as db:
            saved = blackjack.view_in(db, message_id, blackjack.load(message_id, db))
        reply.text, reply.game = saved['text'], saved['game']
        return message_id
    reply.save_message = save
    return reply


def _hangman(args=''):
    words = args.strip().lower().split()
    if words[:1] in (['stats'], ['score'], ['record'], ['me']):
        return Reply(hangman.stats_text())
    if words[:1] in (['help'], ['?'], ['rules']):
        return Reply(hangman.HELP)
    category = next((w for w in words if w in hangman.rules.CATEGORIES), None)
    difficulty = next((w for w in words if w in hangman.rules.DIFFICULTIES), 'easy')
    unknown = [w for w in words if w not in hangman.rules.CATEGORIES and w not in hangman.rules.DIFFICULTIES]
    if unknown:
        return Reply(f"I don't know “{' '.join(unknown)}”.\n\n" + hangman.HELP, game=hangman.picker(difficulty))
    if category is None:   # just a difficulty, or nothing: show the choices
        return Reply('Hangman\nGuess the secret word one letter at a time. Six misses and the drawing is complete!\n'
                     'Pick a category to start.', game=hangman.picker(difficulty))
    state = hangman.new(category, difficulty)
    game = hangman.public(state)
    return Reply(hangman.text(game), game=game, save_message=lambda cid: hangman.save_new(cid, state))


def _tictactoe(args=''):
    requested = args.strip().lower()
    if requested == 'stats':
        return Reply(tictactoe.stats_text())
    if requested in ('', 'help', '?'):
        return Reply('Tic-tac-toe\nChoose a difficulty. You are X and go first. Impossible never loses.',
                     game=tictactoe.picker())
    if requested not in tictactoe.rules.DIFFICULTIES:
        return Reply(tictactoe.HELP)
    game = tictactoe.new(requested)
    return Reply(tictactoe.text(game), game=game)


# ---------- study quiz ----------

def send_button(label, command):
    """A button that sends a command as if typed (the page shows it and streams the reply), e.g. Next question."""
    return {'label': label, 'send': command}


QUIZ_PICKS = ('multiplication', 'addition', 'percentages', 'mixed math', 'world capitals', 'science')


def _quiz_question(q, intro=''):
    rows = [[button(f'{letter}. {choice[:40]}', f"quiz:ans:{q['id']}:{i}")
             for i, (letter, choice) in enumerate(zip('ABCD', q['choices']))]]
    return Reply(intro + study_quiz.question_text(q),
                 [rows[0][:2], rows[0][2:], [button('Skip', f"quiz:skip:{q['id']}"), button('Stop', 'quiz:stop:')]])


def _quiz_after(text, toast=''):
    return Reply(text, [[send_button('Next question ▶', '/quizme next'), button('Stop', 'quiz:stop:')]], toast)


def _quizme(args=''):
    words = args.strip()
    first = words.lower()
    if first in ('stop', 'end', 'quit', 'done'):
        ended = study_quiz.stop()
        return (f"📚 Quiz stopped: {ended['right']} of {ended['answered']} right. /quizme stats shows your "
                'progress.' if ended else 'No quiz is running. /quizme <topic> starts one.')
    if first in ('stats', 'progress', 'score'):
        return Reply(study_quiz.stats_text(), [[send_button('Start a quiz', '/quizme')]])
    if not words or first in ('topics', 'help', 'list'):
        return Reply(study_quiz.TOPICS_TEXT, rows([send_button(t.title(), f'/quizme {t}') for t in QUIZ_PICKS], 3) +
                     [[send_button('My progress', '/quizme stats')]])
    try:
        if first == 'next':
            if not study_quiz.current():
                return 'No quiz is running. /quizme <topic> starts one.'
            return _quiz_question(study_quiz.next_question())
        topic, table = study_quiz.resolve_topic(words)
        q = study_quiz.start(topic, table)
    except (study_quiz.QuizError, engine.EngineError) as exc:
        return Reply(f'📚 {exc}', [[send_button('Next question ▶', '/quizme next'), button('Stop', 'quiz:stop:')]]
                     if study_quiz.current() else [[send_button('Math topics', '/quizme')]])
    intro = '' if study_quiz.is_math(topic) else ('Questions on this topic are written by your AI, so each takes '
                                                  'a moment.\n\n')
    return _quiz_question(q, intro)


def _quiz_button(what, detail):
    pressed = PRESSED.get()
    if what == 'stop':
        ended = study_quiz.stop()
        summary = f": {ended['right']} of {ended['answered']} right." if ended else '.'
        text = (pressed['content'] if pressed else '') + f'\n\n📚 Quiz stopped{summary} /quizme stats shows your progress.'
        return Reply(text.strip())
    question_id, _, choice = detail.partition(':')
    if what == 'ans' and choice.isdigit():
        graded = study_quiz.answer(question_id, int(choice))
        if graded is None:
            return Reply(pressed['content'] if pressed else '', [], 'That question is no longer open.')
        return _quiz_after(study_quiz.feedback_text(*graded), 'Correct! 🎉' if graded[1] else 'Not quite!')
    if what == 'skip':
        q = study_quiz.skip(question_id)
        if q is None:
            return Reply(pressed['content'] if pressed else '', [], 'That question is no longer open.')
        return _quiz_after(study_quiz.question_text(q).split('\n\n(Written by your AI')[0] +
                           f"\n\n⏭ Skipped. The answer was {study_quiz.answer_text(q)}." +
                           (f"\n💡 {q['explanation']}" if q.get('explanation') else ''))
    return None


def _games(args=''):
    if args.strip().lower() == 'stats':
        return Reply(games.stats_text(), [[button('Back to games', 'games:menu:')]])
    if args.strip().lower() not in ('', 'help', '?'):
        return Reply(games.HELP)
    return Reply('Games\nRoll dice or flip a coin. Pick a quick roll below, or type /roll with your own dice.',
                 [[button('Roll d6', 'roll:again:d6'), button('Roll d20', 'roll:again:d20'),
                   button('Flip a coin', 'roll:again:coin')],
                  [button('Game stats', 'games:stats:')]], game=games.menu())


def _games_button(what, detail):
    if what == 'menu':
        return _games()
    if what == 'stats':
        return _games('stats')
    return None


def _roll(args):
    text, result = roll_result(args)
    if result is None:
        return Reply(text)
    expression = ' '.join(args.split())[:80]
    games.record('coin' if result['type'] == 'coin' else 'dice',
                 score=int(result['total']) if result['type'] == 'dice' else None)
    return Reply(text, [[button('🎲 Roll again', f'roll:again:{expression}'),
                         button('Games', 'games:menu:'), button('Game stats', 'games:stats:')]], game=result)


def _roll_button(what, expression):
    """A fresh roll of the same dice, replacing the old result."""
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


def _speak(args):
    if len(args) > speech.MAX_TEXT:
        return Reply('Use /speak with up to 1800 characters, or /speak to read the last AI answer.')
    return Reply(args or 'Preparing audio for the last answer…', speech_text=args)


# ---------- saved search history ----------

def _history(args=''):
    if args.strip().lower() in ('help','?'):
        return Reply(search_history.HELP, [[{'label':'Open search history', 'page':'/search-history'}]])
    repeat = re.fullmatch(r'repeat (\d+)', args.strip(), re.I)
    if repeat:
        entry = search_history.get(int(repeat[1]))
        if not entry:
            return Reply('That saved search was deleted or no longer exists.')
        return run(entry['command'])
    page = 1
    match = re.match(r'page (\d+)(?:\s+|$)', args, re.I)
    if match:
        page = int(match[1])
        if not 1 <= page <= 100000:
            return Reply('Choose a history page between 1 and 100000.')
        args = args[match.end():]
    try:
        data = search_history.browse(**search_history.filters(args), offset=(page-1)*5, limit=5)
    except (ValueError, OverflowError) as exc:
        return Reply('That history date could not be read. Use Oct 18, 2026 or 2026-10-18.\n' + str(exc))
    if not data['items']:
        return Reply('No saved searches match that date or those words. History starts with this update; deleting a '
                     'chat will not delete these records.\n\n' + search_history.HELP,
                     [[{'label':'Open search history', 'page':'/search-history'}]])
    lines = [f"Saved searches · dates use {data['time_zone']}\n"
             f"Showing {(page-1)*5+1}–{(page-1)*5+len(data['items'])} of {data['total']} matches."]
    buttons = []
    for number,item in enumerate(data['items'],(page-1)*5+1):
        lines.append(f"{number}. {item['when']}\n{item['command']}\n"
                     f"{item['origin'].title()} · {item['status'].replace('_',' ')}\n{item['summary'][:250]}")
        if item['sources']:
            lines.append('Sources: ' + ' · '.join(item['sources'][:2]))
        buttons.append([send_button(f'Search again · {number}', f"/searchhistory repeat {item['id']}")])
    if page*5 < data['total']:
        buttons.append([send_button('More searches', f'/searchhistory page {page+1} {args}'.rstrip())])
    buttons.append([{'label':'Open search history', 'page':'/search-history'}])
    return Reply('\n\n'.join(lines) + '\n\nThese are saved snapshots. Search again fetches fresh results.',buttons)


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
    lines += ['', 'Ask about a past search to recall saved history. Other messages without / go to the AI. /help <command> shows one command.']
    return '\n'.join(lines)


COMMANDS = [
    Command('trivia', 'Play category/difficulty trivia; /trivia score shows points, accuracy and streaks',
            '/trivia science hard', _trivia, group='Games'),
    Command('tictactoe', 'Play Easy, Normal or Impossible (never loses); /tictactoe stats shows your record',
            '/tictactoe normal', _tictactoe, aliases=('ttt',), group='Games'),
    Command('hangman', 'Hangman: pick a category and difficulty, then guess the word letter by letter; /hangman stats',
            '/hangman animals', _hangman, group='Games'),
    Command('blackjack','Blackjack against the dealer: Hit or Stand; /blackjack stats, /blackjack rules',
            '/blackjack', _blackjack, aliases=('bj',), group='Games'),
    Command('quizme','A study quiz that adapts to you: math (instant) or any topic (AI); /quizme stats, /quizme stop',
            '/quizme multiplication', _quizme, aliases=('quiz',), group='Games'),
    Command('games', 'Open the games menu or see shared game stats (/games stats)', '/games', _games, group='Games'),
    Command('speak', 'Read the last AI answer, or supplied text (up to 1800 characters), with local Kokoro/Piper audio; enable Spoken replies in Settings',
            '/speak Hello from BEYOND', _speak, group='Voice'),
    Command('imagine', 'Make a local picture with presets, an optional prompt helper, and automatic defect avoidance',
            '/imagine a cartoon cat in space', lambda _args: IMAGINE_HELP, group='Photos'),
    Command('look', 'Ask the local vision AI about an attached photo; describe it, read a receipt, or ask a question',
            '/look what is in this photo?', lambda _args: LOOK_HELP, group='Photos'),
    Command('scan', 'Read printed text from an attached photo, entirely offline', '/scan',
            lambda _args: SCAN_HELP, group='Photos'),
    Command('help', 'List every command, or explain one', '/help calc', _help, group='Help'),
    Command('calc', 'Calculator: maths, percentages, tips and splitting a bill', '/calc tip 85.50 18% split 4',
            calculate),
    Command('convert', 'Convert units: temperature, distance, weight, cooking, speed and more', '/convert 72 f to c',
            convert),
    Command('time', 'The time in a city, several cities, or convert a time between places',
            '/time 3pm London to Tokyo', world_time),
    Command('roll', 'Roll visual dice or flip a coin; keep/drop, repeats and saved stats', '/roll 2d20+3', _roll, group='Games'),
    Command('searchhistory', 'Recall saved lookups by date, tool or words; repeat them or manage them in Settings',
            '/searchhistory last Thursday', _history, aliases=('searches',), group='Look things up'),
    Command('web', 'Search the web (DuckDuckGo)', '/web best hiking trails near Denver',
            _online(web_search.search_web, 'DuckDuckGo'), aliases=('search',), group='Look things up'),
    Command('weather', 'Weather now, the next hours and 3 days; follow up with What about Paris?', '/weather San Jose, CA',
            _online(weather.get_weather, 'the weather service (Open-Meteo)'), group='Look things up'),
    Command('news', 'Headlines: top, world, us, tech, science, sports… or any topic', '/news tech',
            _online(news.get_news, 'the news feeds'), group='Look things up'),
    Command('wiki', 'A Wikipedia summary', '/wiki Apollo 11', _online(wikipedia.search_wikipedia, 'Wikipedia'),
            group='Look things up'),
    Command('define', 'Dictionary: meaning, pronunciation and examples', '/define serendipity',
            _online(dictionary.define_word, 'the dictionary'), group='Look things up'),
    Command('movie', 'A film: year, director, cast, ratings and summary; follow up with Who directed it?', '/movie Dune 1984',
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
            group='Notes and lists'),
    Command('notes', 'Your recent notes (or /notes <words> to search)', '/notes', _notes, group='Notes and lists'),
    Command('list', 'Checklists: groceries, packing, to-dos; tap items to check them off',
            '/list groceries add milk, eggs, bread', _list, aliases=('lists',), group='Notes and lists'),
    Command('remind', 'A reminder that pops up in this chat: once, or repeating', '/remind tomorrow at 6pm call Dan',
            _remind, aliases=('reminder',), group='Reminders'),
    Command('reminders', 'Your upcoming reminders (and cancel them)', '/reminders', _reminders, group='Reminders'),
    Command('morning', 'A daily morning briefing: weather, reminders, headlines, a quote or joke',
            '/morning city San Carlos, CA', _morning, aliases=('briefing',), group='Reminders'),
    Command('spent', 'Log an expense, or see a report (this month, a month, a year, all) with a CSV download',
            '/spent 12.50 lunch', _spent, aliases=('expenses',), group='Notes and lists'),
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



def weather_confirmation_reply(action):
    return Reply(action['text'],buttons=[[send_button('Yes, check this location',action['command'])]],
                 pending_lookup=action['pending'])


def run(text):
    """Answer a /command with a Reply. Unknown commands get a "did you mean…?" reply. Blocking (some commands look
    things up online), so call it from a thread."""
    name, _, args = text[1:].strip().partition(' ')
    name = name.split('@')[0]
    command = find(name)
    if command is None:
        return Reply(f"I don't know the command /{name}. " + did_you_mean(name))
    arguments = args.strip()
    if command.name=='weather':
        from app.tools.places import suggest_location
        suggestion=suggest_location(arguments)
        if suggestion:
            return weather_confirmation_reply(followups.weather_confirmation(suggestion))
    reply = _as_reply(command.run(arguments))
    if command.name=='weather' and (not arguments or reply.text.startswith(("I couldn't find a place called:",'That place name is too short'))):
        reply.pending_lookup={'tool':'weather','query':arguments,'status':'location'}
    if command.name in search_history.TOOLS and (arguments or command.name == 'news'):
        identifier = search_history.record(command.name, arguments or 'top', reply.text)
        reply.lookup_context = followups.snapshot(command.name, arguments or 'top', reply.text)
        if identifier:
            reply.buttons.append([send_button('Search again', f'/searchhistory repeat {identifier}')])
    return reply


# Button handlers: the first part of a button's action picks the handler; the rest is passed to it.
ACTIONS = {
    'games': _games_button,
    'quiz': _quiz_button,
    'rules': _rules_button,
    'roll': _roll_button,
    'mem': _memory_button,
    'rate': _rate_button,
    'learn': _learn_button,
    'note': _note_button,
    'list': _list_button,
    'spent': _spent_button,
    'remind': _remind_button,
    'morning': _morning_button,
}


PRESSED = contextvars.ContextVar('pressed_message', default=None)   # the message whose button is being pressed


def press(action, message=None):
    """Run a button's action. Returns the message's new Reply, or None if the action isn't understood.
    `message`: the message the button is under (handlers that need its text read PRESSED)."""
    name, _, rest = action.partition(':')
    what, _, detail = rest.partition(':')
    handler = ACTIONS.get(name)
    if not handler:
        return None
    token = PRESSED.set(message)
    try:
        return _as_reply(handler(what, detail))
    finally:
        PRESSED.reset(token)


def menu():
    """The list the page shows when you type "/"."""
    return [{'name': c.name, 'summary': c.summary, 'example': c.example} for c in COMMANDS]
