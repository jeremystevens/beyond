"""/spent: an expense log with monthly, yearly, and all-time reports and CSV export. Offline, no AI. Ported from
PromptetheusBot (one user); stored in BEYOND's database.

Money is stored as whole cents (no rounding errors). Dates are this PC's local calendar dates, so an expense at
11 PM on the 31st lands in the right month. Categories are matched automatically from built-in keywords and from
words you have taught it; unknown words are saved as "Other" and you pick a category (or keep the word as a new
one) with buttons, which is remembered for next time.
"""
import calendar
import csv
import io
import re
from datetime import date, datetime, timedelta

from app import chats

MAX_CENTS = 100_000_000          # $1,000,000 per expense
MAX_NOTE = 200
CATEGORIES = {   # key: (label, emoji, keywords)
    'dining': ('Dining', '🍔', 'lunch dinner breakfast brunch food restaurant restaurants coffee cafe starbucks takeout '
               'take-out pizza burger burgers tacos sushi mcdonalds chipotle doordash ubereats grubhub snack snacks '
               'drinks bar beer wine dining eat eating meal meals donut donuts boba tea'),
    'groceries': ('Groceries', '🛒', 'grocery groceries supermarket costco safeway trader_joes walmart kroger aldi '
                  'wholefoods whole_foods produce milk eggs bread'),
    'transport': ('Transport', '🚗', 'gas fuel uber lyft taxi parking toll tolls bus train metro bart subway transit '
                  'car carwash oil tires repair mechanic registration dmv'),
    'bills': ('Bills & Housing', '🏠', 'rent mortgage electric electricity power water sewer trash internet wifi phone '
              'cell bill bills utilities utility insurance hoa cable netflix spotify hulu subscription subscriptions'),
    'shopping': ('Shopping', '🛍', 'amazon target clothes clothing shoes shopping mall store electronics walmart.com '
                 'ebay etsy furniture ikea home_depot lowes hardware'),
    'entertainment': ('Entertainment', '🎬', 'movie movies cinema theater concert tickets ticket game games steam '
                      'playstation xbox nintendo bowling golf hobby books book music show shows'),
    'health': ('Health', '💊', 'doctor dentist pharmacy medicine meds prescription copay hospital clinic gym fitness '
               'vitamins therapy glasses contacts'),
    'travel': ('Travel', '✈️', 'flight flights airfare hotel hotels airbnb vacation trip travel luggage rental cruise'),
    'gifts': ('Gifts', '🎁', 'gift gifts present presents donation donations charity birthday christmas wedding'),
    'other': ('Other', '📦', ''),
}
_KEYWORDS = {}
for _key, (_, _, _words) in CATEGORIES.items():
    for _word in _words.split():
        _KEYWORDS.setdefault(_word.replace('_', ' '), _key)   # trader_joes -> 'trader joes'
AMOUNT_RE = re.compile(r'(?<![\w.])\$?\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s?(k)?(?![\w.])', re.I)
FILLER = {'on', 'for', 'at', 'a', 'an', 'the', 'some', 'my', 'dollars', 'dollar', 'bucks', 'usd', 'to', 'from', 'in'}
HELP = ('💸 Expense log\n'
        '/spent 12.50 lunch — log an expense (today)\n'
        '/spent 30 gas yesterday · /spent 120 car repair oct 3 — another day\n'
        '/spent — this month so far · /spent last month · /spent october · /spent 2026-09\n'
        '/spent year — this year so far · /spent 2025 — a whole year · /spent all — everything\n'
        '/spent recent — last 10, with delete buttons · /spent categories\n'
        'Every report has a 📄 Download CSV button (opens in Excel).')


class ExpenseError(ValueError):
    pass


connect = chats.connect   # BEYOND's database


def initialize():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cents INTEGER NOT NULL CHECK(cents > 0),
            category TEXT NOT NULL,          -- a CATEGORIES key, or a user's own category name
            note TEXT NOT NULL DEFAULT '',
            word TEXT NOT NULL DEFAULT '',   -- the word used to pick the category (for "New category")
            spent_on TEXT NOT NULL,          -- YYYY-MM-DD, this PC's local date
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_expenses_day ON expenses(spent_on)')
        db.execute('''CREATE TABLE IF NOT EXISTS expense_words (
            word TEXT PRIMARY KEY, category TEXT NOT NULL)''')


# ---------- money and categories ----------

def money(cents):
    return f'-${abs(cents) / 100:,.2f}' if cents < 0 else f'${cents / 100:,.2f}'


def category_label(category):
    if category in CATEGORIES:
        label, icon, _ = CATEGORIES[category]
        return f'{icon} {label}'
    return f'🏷 {category}'


def _user_words():
    with connect() as db:
        return dict(db.execute('SELECT word, category FROM expense_words').fetchall())


def match_category(words):
    """(category or None, word that matched or the first word). Words you taught it win over built-ins."""
    learned = _user_words()
    cleaned = [w.lower().strip(".,!?'’") for w in words]
    cleaned = [w[:-2] if w.endswith("'s") else w for w in cleaned]
    for i, word in enumerate(cleaned):
        pair = f'{word} {cleaned[i + 1]}' if i + 1 < len(cleaned) else None
        for candidate in (pair, word):
            if candidate and candidate in learned:
                return learned[candidate], candidate
    for i, word in enumerate(cleaned):
        pair = f'{word} {cleaned[i + 1]}' if i + 1 < len(cleaned) else None
        for candidate in (pair, word, word.rstrip('s')):
            if candidate and candidate in _KEYWORDS:
                return _KEYWORDS[candidate], candidate
    first = next((w for w in cleaned if w and w not in FILLER and not w.isdigit()), '')
    return None, first


def learn_word(word, category):
    if not word:
        return
    with connect() as db:
        db.execute('INSERT INTO expense_words(word, category) VALUES (?, ?) '
                   'ON CONFLICT(word) DO UPDATE SET category=excluded.category', (word.lower(), category))


# ---------- adding ----------

def parse_amount(text):
    """First money amount in the text -> (cents, text without it)."""
    match = AMOUNT_RE.search(text)
    if not match:
        return None, text
    whole, frac, thousands = match.group(1).replace(',', ''), match.group(2) or '0', match.group(3)
    cents = int(whole) * 100 + int(frac.ljust(2, '0'))
    if thousands:
        cents *= 1000
    return cents, (text[:match.start()] + ' ' + text[match.end():]).strip()


_DATE_HINT = re.compile(r'\b(?:today|yesterday|tomorrow|ago|last|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\b|'
                        r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b',
                        re.I)


def parse_day(text, today=None):
    """A date phrase at the end (or start) of `text` -> (date, rest of text). Defaults to today."""
    today = today or date.today()
    words = text.split()
    if not _DATE_HINT.search(text):
        return today, text
    import dateparser
    for size in range(min(4, len(words)), 0, -1):
        for phrase, rest in ((' '.join(words[-size:]), ' '.join(words[:-size])), (' '.join(words[:size]), ' '.join(words[size:]))):
            # "last friday" -> "friday" (dateparser can't read the first), but "last month" stays as it is.
            phrase = re.sub(r'^(?:on|last\s+(?=(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\b))\s*', '',
                            phrase.strip(' ,.'), flags=re.I)
            if not phrase or not _DATE_HINT.search(phrase):
                continue
            found = dateparser.parse(phrase, languages=['en'], settings={
                'PREFER_DATES_FROM': 'past', 'RELATIVE_BASE': datetime(today.year, today.month, today.day, 12)})
            if found:
                day = found.date()
                if day > today:
                    raise ExpenseError("That date is in the future. Log expenses on or before today.")
                if day < today - timedelta(days=3660):
                    raise ExpenseError('That date is more than 10 years ago.')
                return day, re.sub(r'\s+(?:on|from)$', '', rest.strip(' ,.'), flags=re.I)
    return today, text


def plan_expense(text, today=None):
    """'12.50 lunch at chipotle yesterday' -> dict(cents, category or None, word, note, day)."""
    text = re.sub(r'^(?:i\s+)?(?:just\s+)?(?:spent|paid)\s+', '', text.strip(), flags=re.I)
    cents, rest = parse_amount(text)
    if cents is None:
        raise ExpenseError('How much? Example: /spent 12.50 lunch')
    if not 0 < cents <= MAX_CENTS:
        raise ExpenseError('Amounts must be between $0.01 and $1,000,000.')
    day, rest = parse_day(rest, today)
    rest = re.sub(r'^(?:on|for|at)\s+', '', rest.strip(' ,.-'), flags=re.I).strip()
    category, word = match_category(rest.split())
    return {'cents': cents, 'category': category, 'word': word, 'note': rest[:MAX_NOTE], 'day': day}


def add_expense(plan):
    with connect() as db:
        return db.execute('INSERT INTO expenses(cents, category, note, word, spent_on) VALUES (?, ?, ?, ?, ?)',
                          (plan['cents'], plan['category'] or 'other', plan['note'], plan['word'],
                           plan['day'].isoformat())).lastrowid


def get_expense(expense_id):
    with connect() as db:
        return db.execute('SELECT id, cents, category, note, word, spent_on FROM expenses WHERE id=?',
                          (expense_id,)).fetchone()


def set_category(expense_id, category, remember=True):
    row = get_expense(expense_id)
    if not row:
        return None
    with connect() as db:
        db.execute('UPDATE expenses SET category=? WHERE id=?', (category, expense_id))
    if remember:
        learn_word(row[4], category)
    return row


def delete_expense(expense_id):
    row = get_expense(expense_id)
    if row:
        with connect() as db:
            db.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
    return row


def recent(limit=10):
    with connect() as db:
        return db.execute('SELECT id, cents, category, note, spent_on FROM expenses '
                          'ORDER BY spent_on DESC, id DESC LIMIT ?', (limit,)).fetchall()


def user_categories():
    """Custom categories you have created (besides the built-in ones)."""
    with connect() as db:
        rows = db.execute('SELECT DISTINCT category FROM expenses UNION '
                          'SELECT DISTINCT category FROM expense_words').fetchall()
    return sorted(c for (c,) in rows if c not in CATEGORIES)


# ---------- periods and reports ----------

MONTH_NAMES = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTH_NAMES.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTH_NAMES['sept'] = 9


def parse_period(text, today):
    """'', 'month', 'last month', 'october', 'oct 2025', '2026-09', 'year', '2025', 'all' ->
    (kind, start, end_exclusive, label, token). kind is 'month', 'year', or 'all'."""
    t = re.sub(r'\b(?:in|for|during|so\s+far|report|summary|total|spending|the)\b', ' ', text.lower())
    t = re.sub(r'\s+', ' ', t).strip(' ?.!')

    def month(year, number):
        start = date(year, number, 1)
        end = date(year + (number == 12), number % 12 + 1, 1)
        return 'month', start, end, f'{calendar.month_name[number]} {year}', f'm{year:04d}{number:02d}'

    def year_(year):
        return 'year', date(year, 1, 1), date(year + 1, 1, 1), str(year), f'y{year:04d}'

    if t in ('', 'month', 'this month', 'mtd'):
        return month(today.year, today.month)
    if t in ('last month', 'previous month'):
        previous = today.replace(day=1) - timedelta(days=1)
        return month(previous.year, previous.month)
    if t in ('year', 'this year', 'ytd'):
        return year_(today.year)
    if t in ('last year', 'previous year'):
        return year_(today.year - 1)
    if t in ('all', 'all time', 'everything', 'ever', 'total'):
        return 'all', None, None, 'All time', 'all'
    m = re.fullmatch(r'(\d{4})', t)
    if m and 2000 <= int(m.group(1)) <= 2100:
        return year_(int(m.group(1)))
    m = re.fullmatch(r'(\d{4})-(\d{1,2})|(\d{1,2})/(\d{4})', t)
    if m:
        year, number = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(4)), int(m.group(3)))
        if 1 <= number <= 12:
            return month(year, number)
    m = re.fullmatch(r'([a-z]+)\.?(?:\s+(\d{4}))?', t)
    if m and m.group(1) in MONTH_NAMES:
        number = MONTH_NAMES[m.group(1)]
        year = int(m.group(2)) if m.group(2) else (today.year if number <= today.month else today.year - 1)
        return month(year, number)
    return None


def _rows(start, end):
    query = 'SELECT id, cents, category, note, spent_on FROM expenses WHERE 1=1'
    args = []
    if start:
        query += ' AND spent_on >= ? AND spent_on < ?'
        args += [start.isoformat(), end.isoformat()]
    with connect() as db:
        return db.execute(query + ' ORDER BY spent_on, id', args).fetchall()


def _sum(rows):
    return sum(r[1] for r in rows)


def _bar(share):
    filled = round(share * 10)
    return '█' * filled + '░' * (10 - filled)


def _change(now_cents, before_cents, label):
    if not before_cents:
        return ''
    change = (now_cents - before_cents) / before_cents * 100
    arrow = '↑' if change > 0 else '↓' if change < 0 else '='
    return f'\n{arrow} {abs(change):.0f}% vs {label} ({money(before_cents)})'


def _categories_block(rows):
    total = _sum(rows)
    by_category = {}
    for _, cents, category, _, _ in rows:
        by_category[category] = by_category.get(category, 0) + cents
    lines = []
    for category, cents in sorted(by_category.items(), key=lambda kv: -kv[1]):
        share = cents / total if total else 0
        lines.append(f'{category_label(category)}  {money(cents)}  ({share * 100:.0f}%)\n   {_bar(share)}')
    return '\n'.join(lines)


def _biggest(rows):
    top = max(rows, key=lambda r: r[1])
    day = date.fromisoformat(top[4])
    return f'Biggest: {money(top[1])} · {top[3] or category_label(top[2])} · {day:%b} {day.day}'


def report(period, today):
    """(text, has_rows) for a period from parse_period."""
    kind, start, end, label, _ = period
    rows = _rows(start, end)
    if not rows:
        return f'💸 {label}: no expenses logged.\nLog one with /spent 12.50 lunch', False
    total = _sum(rows)
    lines = []
    if kind == 'month':
        current = start <= today < end
        days = (today - start).days + 1 if current else (end - start).days
        title = f'💸 {label}' + (' (so far)' if current else '')
        lines.append(f'{title}\nTotal: {money(total)} · {len(rows)} expense{"s" if len(rows) != 1 else ""}')
        lines.append(f'Daily average: {money(round(total / days))}')
        previous_start = (start - timedelta(days=1)).replace(day=1)
        if current:   # compare like with like: the same days of last month
            same_day = min(today.day, calendar.monthrange(previous_start.year, previous_start.month)[1])
            before = _sum(_rows(previous_start, previous_start.replace(day=same_day) + timedelta(days=1)))
            change = _change(total, before, f'{previous_start:%B} 1–{same_day}')
        else:
            before = _sum(_rows(previous_start, start))
            change = _change(total, before, f'{previous_start:%B}')
        lines[-1] += change
    elif kind == 'year':
        current = start <= today < end
        title = f'💸 {label}' + (' (so far)' if current else '')
        lines.append(f'{title}\nTotal: {money(total)} · {len(rows)} expenses')
        months_counted = today.month if current else 12
        lines.append(f'Monthly average: {money(round(total / months_counted))}')
        if current:
            days_so_far = (today - start).days + 1
            days_in_year = (end - start).days
            lines.append(f'On pace for: {money(round(total / days_so_far * days_in_year))} this year')
            same_day_last_year = date(start.year - 1, today.month, min(today.day, calendar.monthrange(start.year - 1, today.month)[1]))
            before = _sum(_rows(date(start.year - 1, 1, 1), same_day_last_year + timedelta(days=1)))
            lines[-1] += _change(total, before, f'{start.year - 1} to {same_day_last_year:%b} {same_day_last_year.day}')
        else:
            lines[-1] += _change(total, _sum(_rows(date(start.year - 1, 1, 1), start)), str(start.year - 1))
        by_month = {}
        for _, cents, _, _, spent_on in rows:
            by_month[int(spent_on[5:7])] = by_month.get(int(spent_on[5:7]), 0) + cents
        lines.append('By month:\n' + '\n'.join(f'{calendar.month_abbr[m]}  {money(by_month.get(m, 0))}'
                                               for m in range(1, months_counted + 1)))
    else:
        first = date.fromisoformat(rows[0][4])
        lines.append(f'💸 All time (since {first:%b} {first.day}, {first.year})\nTotal: {money(total)} · {len(rows)} expenses')
        by_year = {}
        for _, cents, _, _, spent_on in rows:
            by_year[spent_on[:4]] = by_year.get(spent_on[:4], 0) + cents
        if len(by_year) > 1:
            lines.append('By year:\n' + '\n'.join(f'{y}  {money(c)}' + (' (so far)' if int(y) == today.year else '')
                                                for y, c in sorted(by_year.items())))
    lines.append('By category:\n' + _categories_block(rows))
    lines.append(_biggest(rows))
    return '\n\n'.join(lines), True


def csv_file(period):
    """(bytes, filename) for the period; UTF-8 with BOM so Excel opens it correctly."""
    kind, start, end, label, token = period
    rows = _rows(start, end)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['Date', 'Amount', 'Category', 'Description'])
    for _, cents, category, note, spent_on in rows:
        writer.writerow([spent_on, f'{cents / 100:.2f}', category_label(category).split(' ', 1)[1], note])
    writer.writerow([])
    writer.writerow(['Total', f'{_sum(rows) / 100:.2f}', '', label])
    name = {'all': 'expenses_all.csv'}.get(token) or f'expenses_{label.replace(" ", "_")}.csv'
    return ('﻿' + out.getvalue()).encode('utf-8'), name


def period_from_token(token):
    if token == 'all':
        return 'all', None, None, 'All time', 'all'
    if token.startswith('y'):
        year = int(token[1:])
        return 'year', date(year, 1, 1), date(year + 1, 1, 1), str(year), token
    year, number = int(token[1:5]), int(token[5:7])
    return ('month', date(year, number, 1), date(year + (number == 12), number % 12 + 1, 1),
            f'{calendar.month_name[number]} {year}', token)
