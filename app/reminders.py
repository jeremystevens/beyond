"""/remind and /reminders: reminders that survive restarts. Ported from PromptetheusBot (one user); stored in
BEYOND's database.

One-time reminders ("30m", "tomorrow at 6pm", "next Friday", "March 3") and repeating ones ("every Monday at
8am", "every weekday", "every 2 hours", "every month on the 1st", "every year on March 3"). Times are in this
PC's time zone. Natural dates are read with `dateparser`; repeating schedules are read here (dateparser doesn't do
those). A repeating reminder keeps one row whose due_at moves to the next time after each delivery. The server
checks for due reminders every few seconds and posts them in the chat where they were set (app/server.py).
"""
import calendar
import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import chats

_TOKEN_RE = re.compile(r'(\d+)([dhms])', re.I)
_DURATION_RE = re.compile(r'^(?:\d+[dhms])+$', re.I)
_UNIT_SECONDS = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
MIN_SECONDS = 10
MAX_SECONDS = 365 * 86400
MAX_ACTIVE = 50          # one-time not yet sent + repeating
MAX_TEXT = 500
FMT = '%Y-%m-%dT%H:%M:%SZ'
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
MONTHS = [m.lower() for m in calendar.month_name[1:]]


class ReminderError(ValueError):
    pass


USAGE = ('⏰ Reminders — examples:\n'
         '/remind 30m stretch\n'
         '/remind tomorrow at 6pm call Dan\n'
         '/remind friday pay rent (a day without a time means 9 AM)\n'
         '/remind March 3 Mom\'s birthday\n'
         '🔁 /remind every Monday at 8am take out the trash\n'
         '🔁 /remind every weekday at 7am stand-up\n'
         '🔁 /remind every 2 hours drink water\n'
         '🔁 /remind every month on the 1st pay rent\n'
         '🔁 /remind every year on March 3 Mom\'s birthday\n'
         '/reminders lists and cancels them. Reminders appear in the chat where you set them.')


def initialize():
    with chats.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,                 -- the chat it was set in (it goes off there, if it still exists)
            message TEXT NOT NULL,
            due_at TEXT NOT NULL,            -- UTC
            recur TEXT,                      -- repeating rule as JSON, or NULL
            tz TEXT,                         -- the time zone the rule uses
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            sent INTEGER NOT NULL DEFAULT 0 CHECK(sent IN (0,1)))''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(sent, due_at)')


def local_zone():
    """This PC's time zone name, e.g. 'America/Los_Angeles' (dateparser's dependency tzlocal finds it)."""
    try:
        from tzlocal import get_localzone_name
        return get_localzone_name() or 'UTC'
    except Exception:
        return 'UTC'


def when_text(due_utc, tz_name=None):
    tz = ZoneInfo(tz_name or local_zone())
    local = due_utc.astimezone(tz)
    today = datetime.now(tz).date()
    day = ('today' if local.date() == today else 'tomorrow' if local.date() == today + timedelta(days=1)
           else f'{local:%a, %b} {local.day}' + (f', {local.year}' if local.year != today.year else ''))
    return f'{day} at {local:%I:%M %p}'.replace(' 0', ' ')


def parse_duration(text: str) -> int:
    """Parse a duration like '30m', '2h', or '1h30m' into whole seconds."""
    token = text.strip().lower()
    if not token or not _DURATION_RE.match(token):
        raise ValueError('Use a duration like 30m, 2h, 1d, or 1h30m.')
    seconds = sum(int(amount) * _UNIT_SECONDS[unit] for amount, unit in _TOKEN_RE.findall(token))
    if seconds < MIN_SECONDS:
        raise ValueError('Minimum reminder delay is 10 seconds.')
    if seconds > MAX_SECONDS:
        raise ValueError('Maximum reminder delay is 365 days.')
    return seconds


def format_duration(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = [f'{value}{unit}' for value, unit in ((days, 'd'), (hours, 'h'), (minutes, 'm'), (secs, 's')) if value]
    return ' '.join(parts) or '0s'


# ---------- storage ----------

def create(chat_id, message: str, due_at: datetime, recur=None, tz=None) -> int:
    with chats.connect() as db:
        return db.execute('INSERT INTO reminders(chat_id, message, due_at, recur, tz) VALUES (?, ?, ?, ?, ?)',
                          (chat_id, message, due_at.astimezone(timezone.utc).strftime(FMT),
                           json.dumps(recur) if recur else None, tz)).lastrowid


def due(limit: int = 50):
    """Reminders whose time has come: [(id, chat_id, message, recur, tz, due_at)]."""
    now = datetime.now(timezone.utc).strftime(FMT)
    with chats.connect() as db:
        return [tuple(r) for r in db.execute('''SELECT id, chat_id, message, recur, tz, due_at FROM reminders
                                               WHERE sent = 0 AND due_at <= ? ORDER BY due_at LIMIT ?''',
                                            (now, limit))]


def set_chat(reminder_id: int, chat_id: int):
    """Where it goes off: the chat it was set in (known only once that chat is saved)."""
    with chats.connect() as db:
        db.execute('UPDATE reminders SET chat_id = ? WHERE id = ?', (chat_id, int(reminder_id)))


def mark_sent(reminder_id: int):
    with chats.connect() as db:
        db.execute('UPDATE reminders SET sent = 1 WHERE id = ?', (int(reminder_id),))


def reschedule(reminder_id: int, due_at: datetime):
    with chats.connect() as db:
        db.execute('UPDATE reminders SET due_at = ? WHERE id = ?',
                   (due_at.astimezone(timezone.utc).strftime(FMT), int(reminder_id)))


def active():
    """Upcoming reminders, soonest first: [(id, message, due_at_utc, recur_dict_or_None, tz)]."""
    with chats.connect() as db:
        rows = db.execute('SELECT id, message, due_at, recur, tz FROM reminders WHERE sent = 0 ORDER BY due_at').fetchall()
    return [(rid, msg, datetime.strptime(due_at, FMT).replace(tzinfo=timezone.utc), json.loads(recur) if recur else None,
             tz) for rid, msg, due_at, recur, tz in rows]


def get(reminder_id: int):
    """(id, chat_id, message) or None."""
    with chats.connect() as db:
        row = db.execute('SELECT id, chat_id, message FROM reminders WHERE id = ?', (int(reminder_id),)).fetchone()
    return tuple(row) if row else None


def delete(reminder_id: int):
    """Cancel an upcoming reminder; returns its text or None."""
    with chats.connect() as db:
        row = db.execute('SELECT message FROM reminders WHERE id = ? AND sent = 0', (int(reminder_id),)).fetchone()
        if row:
            db.execute('DELETE FROM reminders WHERE id = ?', (int(reminder_id),))
    return row[0] if row else None


def active_count() -> int:
    with chats.connect() as db:
        return db.execute('SELECT COUNT(*) FROM reminders WHERE sent = 0').fetchone()[0]


# ---------- times of day ----------

TIME_RE = r'(?:at\s+|@\s*)?(?P<time>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?|noon|midnight)'


def parse_clock(text):
    """'8am' -> (8, 0); '6' -> (18, 0) (a bare 1–7 means evening); 'noon' -> (12, 0)."""
    text = text.strip().lower().replace('.', '')
    if text == 'noon':
        return 12, 0
    if text == 'midnight':
        return 0, 0
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
    if not match:
        raise ReminderError(f'I could not read the time “{text}”.')
    hour, minute, half = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if minute > 59 or hour > 23 or (half and not 1 <= hour <= 12):
        raise ReminderError(f'“{text}” is not a real time.')
    if half == 'pm' and hour != 12:
        hour += 12
    elif half == 'am' and hour == 12:
        hour = 0
    elif not half and 1 <= hour <= 6 and not match.group(2):
        hour += 12   # "at 6" in a reminder almost always means 6 PM; "at 7" stays 7 AM
    return hour, minute


def clock_text(hour, minute):
    return datetime(2000, 1, 1, hour, minute).strftime('%I:%M %p').lstrip('0')


# ---------- repeating reminders ----------

_DAY = r'(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?s?'
_DAY_FULL = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
_MONTH = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?'
_ORD = r'(\d{1,2})(?:st|nd|rd|th)?'
_PLURAL = r'(?:mon|tues|wednes|thurs|fri|satur|sun)days'
RECUR_PATTERNS = [   # (regex, builder); time of day is matched separately
    (r'(?:every|each)\s+(?P<part>day|morning|afternoon|evening|night)|daily', 'daily'),
    (r'(?:every|each|on)\s+weekdays?|weekdays', 'weekdays'),
    (r'(?:every|each|on)\s+weekends?|weekends', 'weekends'),
    (rf'(?:every|each)\s+(?P<days>{_DAY}(?:\s*(?:,|and|&|\+)\s*(?:and\s+)?{_DAY})*)', 'weekly'),
    # "on Mondays" / "Mondays" (plural = repeating; "on Monday" stays a one-time reminder)
    (rf'(?:on\s+)?(?P<days>{_PLURAL}(?:\s*(?:,|and|&|\+)\s*(?:and\s+)?{_PLURAL})*)', 'weekly'),
    (r'(?:every|each)\s+(?:(?P<hours>\d{1,2})\s+)?(?:hours?|hrs?)|hourly', 'hourly'),
    (r'every\s+(?:(?P<n>\d{1,2})\s+days|other\s+day)', 'days'),
    (rf'(?:every|each)\s+month\s+on\s+the\s+{_ORD}|monthly\s+on\s+the\s+{_ORD}|on\s+the\s+{_ORD}\s+of\s+every\s+month', 'monthly'),
    (rf'(?:every|each)\s+year\s+on\s+(?P<month>{_MONTH})\s+{_ORD}|(?:every|each)\s+(?P<month2>{_MONTH})\s+{_ORD}|'
     rf'(?:yearly|annually)\s+on\s+(?P<month3>{_MONTH})\s+{_ORD}', 'yearly'),
]
_PART_TIMES = {'morning': (8, 0), 'afternoon': (14, 0), 'evening': (18, 0), 'night': (20, 0)}


def _month_number(text):
    text = text.lower().rstrip('.')
    for number, name in enumerate(MONTHS, 1):
        if name.startswith(text[:3]):
            return number
    raise ReminderError(f'Unknown month “{text}”.')


def _build_rule(kind, match):
    groups = {k: v for k, v in match.groupdict().items() if v}
    numbers = [int(n) for n in re.findall(r'\d+', match.group('rec'))]   # from the schedule words only, not the time
    if kind == 'daily':
        return {'kind': 'daily'}, _PART_TIMES.get(groups.get('part'))
    if kind == 'weekdays':
        return {'kind': 'weekly', 'days': [0, 1, 2, 3, 4]}, None
    if kind == 'weekends':
        return {'kind': 'weekly', 'days': [5, 6]}, None
    if kind == 'weekly':
        days = sorted({_DAY_FULL[d[:3]] for d in re.findall(_DAY, groups['days'].lower())})
        return {'kind': 'weekly', 'days': days}, None
    if kind == 'hourly':
        hours = int(groups.get('hours', 1))
        if not 1 <= hours <= 24:
            raise ReminderError('Repeating every 1 to 24 hours is supported.')
        return {'kind': 'hourly', 'every': hours}, None
    if kind == 'days':
        n = int(groups.get('n', 2))
        if not 1 <= n <= 90:
            raise ReminderError('Repeating every 1 to 90 days is supported.')
        return ({'kind': 'daily'} if n == 1 else {'kind': 'days', 'every': n}), None
    if kind == 'monthly':
        day = numbers[0]
        if not 1 <= day <= 31:
            raise ReminderError('Pick a day of the month from 1 to 31.')
        return {'kind': 'monthly', 'day': day}, None
    month = _month_number(groups.get('month') or groups.get('month2') or groups.get('month3'))
    day = numbers[-1]
    if not 1 <= day <= calendar.monthrange(2024, month)[1]:
        raise ReminderError('That date does not exist.')
    return {'kind': 'yearly', 'month': month, 'day': day}, None


def parse_recurring(text):
    """Find a repeating schedule at the start or end of `text`. Returns (rule, message) or None."""
    text = text.strip()
    # Spoken "every two hours" / "every three days": only the number right after "every" is converted,
    # so numbers in the message itself stay as they were said.
    text = re.sub(r'\b(every|each)\s+(\w+(?:[\s-]\w+)?)\s+(hours?|days?)\b',
                  lambda m: f'{m.group(1)} {words_to_numbers(m.group(2))} {m.group(3)}', text, flags=re.I)
    for pattern, kind in RECUR_PATTERNS:
        both = [(rf'^(?:{TIME_RE}\s+)?(?P<rec>{pattern})(?:\s+{TIME_RE.replace("<time>", "<time2>")})?(?=\s|$|[,:.-])', 'start'),
                (rf'(?:^|\s)(?:{TIME_RE}\s+)?(?P<rec>{pattern})(?:\s+{TIME_RE.replace("<time>", "<time2>")})?\s*[.!]?$', 'end')]
        for regex, where in both:
            match = re.search(regex, text, re.I)
            if not match:
                continue
            rule, part_time = _build_rule(kind, match)
            clock = match.group('time') or match.group('time2')
            if rule['kind'] != 'hourly':
                hour, minute = parse_clock(clock) if clock else (part_time or (9, 0))
                rule['time'] = f'{hour:02d}:{minute:02d}'
            message = (text[match.end():] if where == 'start' else text[:match.start()]).strip(' ,:-.')
            return rule, re.sub(r'^(?:to|that|about)\s+', '', message, flags=re.I).strip()
    return None


def describe_rule(rule):
    time_part = ''
    if 'time' in rule:
        hour, minute = map(int, rule['time'].split(':'))
        time_part = ' at ' + clock_text(hour, minute)
    kind = rule['kind']
    if kind == 'daily':
        return 'every day' + time_part
    if kind == 'days':
        return f"every {rule['every']} days" + time_part
    if kind == 'hourly':
        return 'every hour' if rule['every'] == 1 else f"every {rule['every']} hours"
    if kind == 'weekly':
        days = rule['days']
        if days == [0, 1, 2, 3, 4]:
            return 'every weekday' + time_part
        if days == [5, 6]:
            return 'every weekend day' + time_part
        names = [DAYS[d].title() for d in days]
        return 'every ' + (names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]) + time_part
    if kind == 'monthly':
        day = rule['day']
        suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return f'every month on the {day}{suffix}' + time_part + (' (or the last day of shorter months)' if day > 28 else '')
    return f"every year on {calendar.month_name[rule['month']]} {rule['day']}" + time_part


def next_due(rule, tz_name, now_utc=None, previous_utc=None):
    """The first time this rule fires after now (UTC)."""
    tz = ZoneInfo(tz_name)
    now_utc = now_utc or datetime.now(timezone.utc)
    now = now_utc.astimezone(tz)
    kind = rule['kind']
    if kind == 'hourly':
        step = timedelta(hours=rule['every'])
        due = (previous_utc or now_utc) + step
        while due <= now_utc:
            due += step
        return due
    hour, minute = map(int, rule['time'].split(':'))

    def at(day):
        return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)

    if kind == 'days':
        if previous_utc:
            due = at(previous_utc.astimezone(tz).date() + timedelta(days=rule['every']))
        else:
            due = at(now.date())
        while due <= now:
            due = at(due.date() + timedelta(days=rule['every']))
        return due.astimezone(timezone.utc)
    if kind in ('daily', 'weekly'):
        days = rule.get('days', list(range(7)))
        for offset in range(0, 15):
            day = now.date() + timedelta(days=offset)
            if day.weekday() in days and at(day) > now:
                return at(day).astimezone(timezone.utc)
    if kind == 'monthly':
        year, month = now.year, now.month
        for _ in range(14):
            day = min(rule['day'], calendar.monthrange(year, month)[1])
            due = datetime(year, month, day, hour, minute, tzinfo=tz)
            if due > now:
                return due.astimezone(timezone.utc)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if kind == 'yearly':
        for year in range(now.year, now.year + 9):
            day = min(rule['day'], calendar.monthrange(year, rule['month'])[1])   # Feb 29 -> Feb 28
            due = datetime(year, rule['month'], day, hour, minute, tzinfo=tz)
            if due > now:
                return due.astimezone(timezone.utc)
    raise ReminderError('Could not work out the next time for that schedule.')


# ---------- one-time reminders in plain English ----------

_TIME_WORDS = re.compile(r'\d|\b(?:today|tonight|tomorrow|tmrw|noon|midnight|morning|afternoon|evening|night|'
                         r'mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\b|\b(?:hour|minute|min|week|month|year)s?\b',
                         re.I)
_HAS_CLOCK = re.compile(r'\d{1,2}:\d{2}|\d\s*(?:a\.?m|p\.?m)\b|\bnoon\b|\bmidnight\b|\bin\s+\d|\b\d+\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?)\b|'
                        r'\b(?:at|@)\s*\d', re.I)
_HAS_DATE = re.compile(r'\b(?:today|yesterday|tomorrow|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\b|\d{1,2}/\d{1,2}|'
                       r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b|\bin\s+\d|\bnext\b|\b\d+(?:st|nd|rd|th)\b', re.I)
_NORMALIZE = [
    (r'\btmrw\b', 'tomorrow'),
    (r'\btonight\s+at\s+(\d{1,2}(?::\d{2})?)\b(?!\s*[ap])', r'today at \1pm'),
    (r'\btonight\b', 'today at 8pm'),
    (r'\bthis\s+(morning|afternoon|evening)\b', r'today \1'),
    (r'\b(today|tomorrow)\s+morning\b', r'\1 at 9am'),
    (r'\b(today|tomorrow)\s+afternoon\b', r'\1 at 2pm'),
    (r'\b(today|tomorrow)\s+evening\b', r'\1 at 6pm'),
    (r'\b(today|tomorrow)\s+night\b', r'\1 at 8pm'),
    (r'\b(?:next|this|on)\s+((?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*)\b', r'\1'),
    (r'^on\s+', ''),
]


_ONES = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
         'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
         'seventeen': 17, 'eighteen': 18, 'nineteen': 19}
_TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60}
_NUMBER_WORDS = re.compile(r'\b(?:(' + '|'.join(_TENS) + r')(?:[\s-]+(' + '|'.join(list(_ONES)[:9]) + r'))?|(' +
                           '|'.join(_ONES) + r'))\b', re.I)


def words_to_numbers(text):
    """Spoken numbers, as voice notes are often transcribed: 'in two hours' -> 'in 2 hours',
    'twenty five minutes' -> '25 minutes', 'half an hour' -> '30 minutes', 'an hour' -> '1 hour'."""
    text = re.sub(r'\b(?:a\s+)?half\s+(?:an\s+)?hour\b', '30 minutes', text, flags=re.I)
    text = re.sub(r'\ba\s+couple\s+(?:of\s+)?(hours?|minutes?|days?)\b', r'2 \1', text, flags=re.I)
    text = re.sub(r'\b(?:an|a|one)\s+(hour|minute|day|week)\b', r'1 \1', text, flags=re.I)

    def number(match):
        if match.group(3):
            return str(_ONES[match.group(3).lower()])
        return str(_TENS[match.group(1).lower()] + (_ONES[match.group(2).lower()] if match.group(2) else 0))
    return _NUMBER_WORDS.sub(number, text)


def _normalize(phrase):
    phrase = words_to_numbers(phrase.strip().lower())
    for pattern, replacement in _NORMALIZE:
        phrase = re.sub(pattern, replacement, phrase)
    # "at 6" with no am/pm: a bare 1–6 means evening
    phrase = re.sub(r'\b(at|@)\s*([1-6])(?!\s*(?::|\d|a\.?m|p\.?m))', r'\1 \2pm', phrase)
    return phrase


_parser_ready = False


def warm_up():
    """dateparser's first call takes a few seconds; run this once in the background at startup."""
    global _parser_ready
    if not _parser_ready:
        import dateparser
        dateparser.parse('tomorrow at 6pm', languages=['en'])
        _parser_ready = True


def _parse_when(phrase, tz_name, now_utc):
    if not _TIME_WORDS.search(phrase):
        return None
    words = phrase.lower().split()
    if any(w.strip('.,') in MONTHS + [m[:3] for m in MONTHS] for w in words) and not re.search(r'\d', phrase):
        return None   # a month name alone ("for may") is too likely to be part of the message
    import dateparser
    normal = _normalize(phrase)
    when = dateparser.parse(normal, languages=['en'], settings={
        'PREFER_DATES_FROM': 'future', 'TIMEZONE': tz_name, 'RETURN_AS_TIMEZONE_AWARE': True,
        'RELATIVE_BASE': now_utc.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)})
    if when is None:
        return None
    if not _HAS_CLOCK.search(normal):   # a day without a time means 9 AM that day
        when = when.replace(hour=9, minute=0, second=0, microsecond=0)
    if when.astimezone(timezone.utc) <= now_utc and not _HAS_DATE.search(normal):
        when += timedelta(days=1)       # just a time ("noon", "at 8pm") that already passed today: tomorrow
    return when.astimezone(timezone.utc)


def parse_one_time(text, tz_name, now_utc=None):
    """Find a time at the start or end of `text`. Returns (due_utc, message) or None."""
    now_utc = now_utc or datetime.now(timezone.utc)
    words = text.split()
    first = words[0].lower() if words else ''
    if _DURATION_RE.match(first):   # the original format: /remind 30m stretch
        return now_utc + timedelta(seconds=parse_duration(first)), ' '.join(words[1:])
    best = None
    for size in range(min(8, len(words) - 1), 0, -1):   # longest time phrase first; leave a message
        for phrase, rest in ((' '.join(words[:size]), ' '.join(words[size:])),
                             (' '.join(words[-size:]), ' '.join(words[:-size]))):
            when = _parse_when(phrase.strip(' ,.'), tz_name, now_utc)
            if when:
                best = (when, rest)
                break
        if best:
            break
    if not best:
        return None
    when, message = best
    message = re.sub(r'^(?:to|that|about)\s+', '', message.strip(' ,:-.'), flags=re.I).strip()
    message = re.sub(r'\s+(?:to|at|on|by)$', '', message, flags=re.I).strip()
    return when, message


def plan_reminder(text, tz_name=None, now_utc=None):
    """Turn '/remind ...' text into {'due', 'message', 'recur', 'tz'}; raises ReminderError with a friendly message."""
    tz_name = tz_name or local_zone()
    now_utc = now_utc or datetime.now(timezone.utc)
    text = re.sub(r'^(?:please\s+)?(?:remind\s+me\s+)', '', text.strip(), flags=re.I).strip()
    recurring = parse_recurring(text)
    if recurring:
        rule, message = recurring
        due_at, recur = next_due(rule, tz_name, now_utc), rule
    else:
        try:
            found = parse_one_time(text, tz_name, now_utc)
        except ValueError as exc:
            raise ReminderError(str(exc)) from exc
        if not found:
            raise ReminderError("I couldn't find a time in that. Try:\n/remind 30m stretch\n"
                                '/remind tomorrow at 6pm call Dan\n/remind every Monday at 8am take out the trash')
        due_at, message = found
        recur = None
        if due_at <= now_utc + timedelta(seconds=MIN_SECONDS - 1):
            raise ReminderError('That time has already passed. Pick a time in the future.')
        if due_at > now_utc + timedelta(seconds=MAX_SECONDS):
            raise ReminderError('Reminders can be set up to one year ahead.')
    if not message:
        raise ReminderError('What should I remind you about? Example: /remind tomorrow at 6pm call Dan')
    if len(message) > MAX_TEXT:
        raise ReminderError(f'Please keep reminder text under {MAX_TEXT} characters.')
    return {'due': due_at, 'message': message, 'recur': recur, 'tz': tz_name}
