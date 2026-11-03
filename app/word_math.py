"""Bounded word-problem arithmetic from explicit user quantities, never model-generated code.

Supported families are budgets, recording time, shelf capacity, sealed-pack prices and
checkout change. Unknown quantities/qualifiers decline to normal chat. All calculations
use the existing safe calculator with integer cents/scaled units to avoid float rounding.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
import re

from app.tools import calculator

NUMBER = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,3})?'
WORDS = dict(zip('one two three four five six seven eight nine ten eleven twelve'.split(), range(1, 13)))
COUNT = r'(?:\d+|' + '|'.join(WORDS) + ')'
MONEY = r'(?P<currency>[$€£])\s*(?P<amount>' + NUMBER + r')'
TIME = r'(?:hours?|hrs?|minutes?|mins?|seconds?|secs?)'
MASS = r'(?:kg|kilograms?|g|grams?)'
UNSAFE = re.compile(r'```|__|\b(?:script|code|import|exec|eval|subprocess|write|rewrite|translate|story|poem|'
                    r'delete|remove|search|discount|interest|reliability|quality|recommend|'
                    r'half|double|twice|triple|refund|refunded|returned|coupon|cashback|rebate|deposit|installments?)\b|'
                    r"\b(?:don'?t|do not)\s+(?:calculate|compute)\b", re.I)


@dataclass
class Calculation:
    text: str
    family: str
    checks: list = field(default_factory=list)


def _number(text):
    value = Decimal(text.replace(',', ''))
    if not value.is_finite() or not 0 <= value <= 1_000_000_000:
        raise ValueError('Quantity outside supported bounds')
    return value


def _count(text):
    value = WORDS[text.lower()] if text.lower() in WORDS else int(text)
    if not 0 <= value <= 10_000:
        raise ValueError('Count outside supported bounds')
    return value


def _cents(match):
    amount = _number(match['amount']) * 100
    if amount != amount.to_integral_value():
        raise ValueError('Money needs whole cents')
    return int(amount)


def _calc(expression, unit, checks):
    if len(expression) > calculator.MAX_EXPRESSION:
        raise ValueError('Calculation too long')
    result = calculator.evaluate(expression)
    if type(result) is not int:
        raise ValueError('Only exact integer arithmetic is used here')
    checks.append({'expression': expression, 'result': result, 'unit': unit})
    return result


def _money(amount, currency):
    return ('-' if amount < 0 else '') + f'{currency}{Decimal(abs(amount)) / 100:,.2f}'


def _quantity(value):
    value = Fraction(value)
    rest = value.denominator
    for factor in (2, 5):
        while rest % factor == 0:
            rest //= factor
    if rest != 1:
        return str(value)
    return format(Decimal(value.numerator) / Decimal(value.denominator), 'f').rstrip('0').rstrip('.') if value.denominator != 1 else str(value.numerator)


def _scaled(values):
    scale = 10 ** max(0, max(-v.as_tuple().exponent for v in values))
    return [int(v * scale) for v in values], scale


def _covered(text, matches):
    """Do not silently drop a numeric condition or a second charge/quantity."""
    spans = [m.span() for m in matches]
    spans += [m.span() for m in re.finditer(r'\b\d+\s+(?:bullet points?|sentences?|lines?)\b', text, re.I)]
    return all(any(a <= m.start() and m.end() <= b for a, b in spans)
               for m in re.finditer(NUMBER, text))


def _label(text):
    text = re.sub(r'^(?:(?:and|a|an|the)\s+)+', '', text.strip(), flags=re.I)
    return text[:1].upper() + text[1:]


def _budget_frame(text, earlier=()):
    if len(text) > 1600 or UNSAFE.search(text):
        return None
    if re.search(r"\b(?:does not|doesn't|not|cannot|can't)\s+(?:cost|finish|have|include)|\b(?:delayed|except|unless|no longer)\b", text, re.I):
        return None
    costs = list(re.finditer(r'(?P<label>[A-Za-z][A-Za-z -]{0,35}?)\s+(?:costs?|is priced at)\s+' + MONEY, text, re.I))
    costs = [m for m in costs if _label(m['label']).lower() != 'budget']
    budgets = list(re.finditer(r'\bbudget\s*(?:(?:was|is|of|:)\s*)?(?:now\s+)?' + MONEY, text, re.I))
    budgets += list(re.finditer(r'\bbut\s+it\s+is\s+now\s+' + MONEY, text, re.I))
    budgets += list(re.finditer(MONEY + r'\s+budget\b', text, re.I))
    budgets.sort(key=lambda m: m.start())
    finish = list(re.finditer(r'\bboth(?:\s+(?:options|choices))?\s+finish\s+on\s+day\s+(\d{1,3})\b', text, re.I))
    if len(finish) > 1 or not budgets or not _covered(text, costs + budgets + finish):
        return None
    if re.search(r'\b(?:tax|fees?|shipping|monthly|annual|per|percent|free|%)\b', text, re.I):
        return None
    money = list(re.finditer(MONEY, text))
    if len(money) != len(costs) + len(budgets):
        return None
    currencies = {m['currency'] for m in money}
    if len(currencies) != 1:
        return None
    if costs:
        if not 2 <= len(costs) <= 6:
            return None
        items = [(_label(m['label']), _cents(m)) for m in costs]
        if len({name.lower() for name, _ in items}) != len(items):
            return None
        day = finish[0][1] if finish else None
    else:
        if not earlier or not re.search(r'\b(?:now|correction|changed|re-evaluate|reevaluate)\b', text, re.I):
            return None
        previous = _budget_frame(earlier[-1], earlier[:-1])
        if previous is None or previous['currency'] not in currencies:
            return None
        items = previous['items']
        day = finish[0][1] if finish else previous['day']
    return {'items': items, 'budget': _cents(budgets[-1]), 'currency': next(iter(currencies)), 'day': day, 'followup': not costs}


def _budget(text, earlier):
    if not re.search(r'\bbudget\b', text, re.I):
        return None
    wanted = re.search(r'\b(?:fits?|afford|remain\w*|left|over|re-evaluate|reevaluate)\b', text, re.I)
    if not wanted and not (earlier and re.search(r'\b(?:correction|now)\b', text, re.I)):
        return None
    if re.search(r'\b(?:together|combined|combine|combination|bundle|buy both|afford both|should|better)\b', text, re.I):
        return None
    if re.search(r'\bcan I afford\b[^?]*\band\b', text, re.I):
        return None
    frame = _budget_frame(text, earlier)
    if frame is None:
        return None
    if not wanted and not frame['followup']:
        return None
    if re.search(r'\bfinish\b', text, re.I) and frame['day'] is None:
        return None
    checks, lines = [], []
    cash = lambda n: _money(n, frame['currency'])
    for name, cost in frame['items']:
        remaining = _calc(f'{frame["budget"]} - {cost}', 'cents', checks)
        balance = f'fits; {cash(remaining)} remains' if remaining >= 0 else f'does not fit; {cash(-remaining)} over budget'
        line = f'{name}: {balance} ({cash(frame["budget"])} − {cash(cost)} = {cash(remaining)}).'
        if frame['day'] is not None:
            line += f' Finishes on day {frame["day"]}.'
        lines.append('- ' + line)
    prose = re.search(r"\b(?:no|without) bullet|\bdon'?t use bullet", text, re.I)
    return Calculation(' '.join(line[2:] for line in lines) if prose else '\n'.join(lines), 'budget', checks)


def _time(text):
    if re.search(r"\b(?:not|never|isn't|doesn't|cannot|can't|no longer|per)\b", text, re.I):
        return None
    target = re.search(r'\bhow many\s+(' + TIME + r')\b', text, re.I)
    initial = re.search(r'(?P<n>' + NUMBER + r')\s*(?P<unit>' + TIME + r')\s+(?:of\s+(?:recording\s+)?(?:space|time|capacity)\s+)?(?:left|remaining)\b', text, re.I)
    work = re.search(r'\b(?P<count>' + COUNT + r')\s+(?:recordings?|sessions?|tasks?|clips?)\s+(?:each\s+)?(?:last|take|run for)\s+(?P<n>' + NUMBER + r')\s*(?P<unit>' + TIME + r')\b', text, re.I)
    if not target or not initial or not work or not _covered(text, [initial, work]):
        return None
    if not re.search(r'\b(?:remain\w*|left)\b', text[target.start():], re.I):
        return None
    if re.search(r'\bbefore\b|\bafter\s+(?:the\s+)?(?:first|one|second)\b', text[target.start():], re.I):
        return None
    if re.search(r'\b(?:another|additional|extra)\b', text, re.I):
        return None
    def seconds(unit):
        return 3600 if unit.lower().startswith(('h',)) else 60 if unit.lower().startswith('m') else 1
    values = [_number(initial['n']) * seconds(initial['unit']), _number(work['n']) * seconds(work['unit'])]
    (available, each), scale = _scaled(values)
    checks = []
    count = _count(work['count'])
    if re.search(r'\bboth\b', text[target.start():], re.I) and count != 2:
        return None
    used = _calc(f'{count} * {each}', 'scaled seconds', checks)
    left = _calc(f'{available} - {used}', 'scaled seconds', checks)
    factor = scale * seconds(target[1])
    show = lambda n: _quantity(Fraction(n, factor))
    unit = target[1].lower()
    if left < 0:
        answer = f'The recordings do not fit: {show(used)} {unit} are needed, exceeding the available {show(available)} {unit} by {show(-left)} {unit}.'
    else:
        answer = f'{show(left)} {unit} remain: {show(available)} {unit} available − ({count} × {show(each)} {unit}) = {show(left)} {unit}.'
    return Calculation(answer, 'time', checks)


def _capacity(text):
    if re.search(r"\b(?:not|never|doesn't|cannot|can't|no longer|less than|under|below|per)\b", text, re.I):
        return None
    if not re.search(r'\b(?:maximum|whole|how many)\b', text, re.I) or not re.search(r'\badd\b', text, re.I):
        return None
    limit = re.search(r'\b(?:supports?|holds?|capacity of)\s+(?:(?:at most|up to)\s+)?(?P<n>' + NUMBER + r')\s*(?P<unit>' + MASS + r')\b', text, re.I)
    current = re.search(r'\b(?:already|currently)\s+(?:holds?|contains?|carries|has)\s+(?P<n>' + NUMBER + r')\s*(?P<unit>' + MASS + r')\b', text, re.I)
    each = re.search(r'\beach\s+(?:new\s+)?(?P<item>[a-z]+)\s+weighs\s+(?P<n>' + NUMBER + r')\s*(?P<unit>' + MASS + r')\b', text, re.I)
    if not limit or not current or not each or not _covered(text, [limit, current, each]):
        return None
    def grams(m):
        return _number(m['n']) * (1000 if m['unit'].lower().startswith(('k',)) else 1)
    (maximum, initial, size), scale = _scaled([grams(limit), grams(current), grams(each)])
    if size <= 0:
        return None
    checks = []
    free = _calc(f'{maximum} - {initial}', 'scaled grams', checks)
    target = 1000 if limit['unit'].lower().startswith('k') else 1
    unit = 'kg' if target == 1000 else 'g'
    show = lambda n: _quantity(Fraction(n, scale * target))
    if free < 0:
        return Calculation(f'No additional items fit; the current load already exceeds the {show(maximum)} {unit} limit by {show(-free)} {unit}.', 'capacity', checks)
    count = _calc(f'{free} // {size}', 'whole items', checks)
    total = _calc(f'{initial} + {count} * {size}', 'scaled grams', checks)
    following = _calc(f'{initial} + ({count} + 1) * {size}', 'scaled grams', checks)
    item = each['item'].lower()
    plural = item + ('es' if item.endswith(('s', 'x', 'ch', 'sh')) else 's')
    answer = (f'{count} whole {item if count == 1 else plural} can be added. '
              f'{show(initial)} {unit} + ({count} × {show(size)} {unit}) = {show(total)} {unit}, within the {show(maximum)} {unit} limit; '
              f'{count + 1} would total {show(following)} {unit}, exceeding it.')
    return Calculation(answer, 'capacity', checks)


def _packs(text):
    if re.search(r'\b(?:combine|combination|mix|per)\b', text, re.I):
        return None
    if re.search(r"\b(?:don't|do not|no longer)\s+need\b", text, re.I):
        return None
    need = re.search(r'\bneed\s+(?:(?P<mode>at least|exactly)\s+)?(?P<n>\d+)\s+(?P<item>[a-z]+)\b', text, re.I)
    rows = list(re.finditer(r'(?P<label>(?:Store|Shop|Supplier|Vendor)\s+[A-Za-z0-9 -]{1,24}?)\s+sells\s+(?:sealed\s+|unopened\s+)?packs?\s+of\s+(?P<n>\d+)\s+(?:(?P<item>[a-z]+)\s+)?for\s+' + MONEY, text, re.I))
    if not need or not 2 <= len(rows) <= 6 or not re.search(r'\b(?:lowest|cheapest|less|cost|spend)\b', text, re.I):
        return None
    if not re.search(r"\bpacks (?:cannot|can not|can't) be split\b", text, re.I):
        return None
    if not _covered(text, [need, *rows]) or len(list(re.finditer(MONEY, text))) != len(rows):
        return None
    if len({m['currency'] for m in rows}) != 1 or len({m['label'].lower() for m in rows}) != len(rows):
        return None
    if any(m['item'] and m['item'].lower().rstrip('s') != need['item'].lower().rstrip('s') for m in rows):
        return None
    required, checks, options, lines = _count(need['n']), [], [], []
    for row in rows:
        size = _count(row['n'])
        if size == 0:
            return None
        label, currency = row['label'].strip(), row['currency']
        packs = _calc(f'({required} + {size} - 1) // {size}', 'whole packs', checks)
        quantity = _calc(f'{packs} * {size}', 'items', checks)
        total = _calc(f'{packs} * {_cents(row)}', 'cents', checks)
        if need['mode'] == 'exactly' and quantity != required:
            lines.append(f'{label}: cannot supply exactly {required} items in whole packs.')
        else:
            options.append((total, label))
            lines.append(f'{label}: {packs} whole packs provide {quantity} items for {_money(total, currency)}.')
    if not options:
        conclusion = 'No store can meet the exact quantity with whole packs.'
    else:
        cheapest = min(v for v, _ in options)
        names = [name for value, name in options if value == cheapest]
        conclusion = ' and '.join(names) + (' tie for the lowest total' if len(names) > 1 else ' has the lowest total') + f': {_money(cheapest, rows[0]["currency"])}.'
    return Calculation(conclusion + '\n' + '\n'.join(lines), 'packs', checks)


def _change(text):
    if not re.search(r'\bhow much\s+(?:change|money back)\b', text, re.I):
        return None
    if re.search(r"\b(?:did not|didn't|don't|do not|never)\s+(?:pay|paid)\b", text, re.I):
        return None
    payment = re.search(r'\b(?:I\s+)?(?:pay|paid|hand over)\s+' + MONEY, text, re.I)
    rows = list(re.finditer(r'(?:(?:\bfor|\band|\bplus)\s+|,\s*)(?P<count>' + COUNT + r')\s+[a-z]+(?:\s+[a-z]+){0,2}?\s+(?:costing|at|priced at)\s+' + MONEY, text, re.I))
    if not payment or not 1 <= len(rows) <= 6 or not _covered(text, [payment, *rows]):
        return None
    if len(list(re.finditer(MONEY, text))) != len(rows) + 1 or any(m['currency'] != payment['currency'] for m in rows):
        return None
    if re.search(r'\b(?:another|additional|extra)\b', text, re.I) or not re.search(r'\bno (?:tax|fees?|(?:other )?charges?)\b', text, re.I):
        return None
    qualified = re.sub(r'\bno tax(?: or (?:other )?charges?)?\b|\bno (?:other )?(?:charges?|fees?)\b', '', text, flags=re.I)
    if re.search(r'\b(?:tax|fees?|charges?|tips?|free|per|return|returning)\b', qualified, re.I):
        return None
    checks, subtotals = [], []
    for row in rows:
        subtotals.append(_calc(f'{_count(row["count"])} * {_cents(row)}', 'cents', checks))
    total = _calc(' + '.join(map(str, subtotals)), 'cents', checks)
    change = _calc(f'{_cents(payment)} - {total}', 'cents', checks)
    cash = lambda n: _money(n, payment['currency'])
    if change < 0:
        answer = f'The payment is {cash(-change)} short: the total is {cash(total)}, exceeding the {cash(_cents(payment))} payment.'
    else:
        answer = f'You receive {cash(change)} in change: items total {" + ".join(cash(n) for n in subtotals)} = {cash(total)}, and {cash(_cents(payment))} − {cash(total)} = {cash(change)}.'
    return Calculation(answer, 'change', checks)


def solve(history):
    """Return a verified supported answer or None; never infer missing quantities from AI replies."""
    if not history or history[-1]['role'] != 'user':
        return None
    text = history[-1]['content'].strip().replace('’', "'")
    if not 20 <= len(text) <= 1600 or text.startswith(('/', '"', "'", '`')) or UNSAFE.search(text):
        return None
    if not re.search(r'\d', text) or re.search(r"\b(?:don't|do not) answer\b|\b(?:wait|just remember)\b", text, re.I):
        return None
    if re.match(r'(?:reference|quoted text|source text|excerpt|summarize|analyse|analyze)\b', text, re.I):
        return None
    if re.search(r'[-−]\s*[$€£]|[$€£]\s*[-−]|\b(?:maybe|approximately|about|estimated|unknown)\b', text, re.I):
        return None
    # Strict parsers decline on extra numeric conditions rather than silently discarding them.
    earlier = [m['content'] for m in history[:-1] if m['role'] == 'user'][-4:]
    try:
        for parse in (lambda s: _budget(s, earlier), _time, _capacity, _packs, _change):
            result = parse(text)
            if result is not None:
                return result
    except (ValueError, ArithmeticError, calculator.CalcError, RecursionError, OverflowError):
        return None
    return None
