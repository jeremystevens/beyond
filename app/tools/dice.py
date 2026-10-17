"""Dice roller (offline). Uses the OS's secure random source so rolls can't be predicted.

Notation: NdM (d6, 2d20, d% = d100), modifiers (+3, -1), several terms (2d6+1d4+2),
keep/drop (4d6kh3, 2d20kl1, 4d6dl1, 5d10dh1), adv/dis (2d20 keep high/low),
repeats ("6x 4d6kh3"), and "coin".
"""
import re
import secrets

MAX_DICE, MAX_SIDES, MAX_TERMS, MAX_REPEATS = 100, 1000, 10, 10
USAGE = ('🎲 Usage: /roll <dice>\n'
         '/roll d20 · /roll 2d20+3 · /roll 3d6+1d4-2 · /roll d%\n'
         '/roll 4d6kh3 (keep highest 3) · /roll 2d20kl1 · /roll 4d6dl1 (drop lowest)\n'
         '/roll adv+5 · /roll dis · /roll 6x 4d6kh3 (character stats) · /roll coin\n'
         '/roll alone rolls 1d6.')
TERM = re.compile(r'([+-]?)\s*(?:(\d*)d(\d+|%)(?:(kh|kl|dh|dl|k|d)(\d+))?|(\d+))', re.I)


class DiceError(ValueError):
    pass


def _roll(count, sides):
    return [secrets.randbelow(sides) + 1 for _ in range(count)]


def _keep(rolls, mode, n):
    """Return (kept indexes) for keep/drop modes."""
    order = sorted(range(len(rolls)), key=lambda i: rolls[i])          # lowest first
    if n > len(rolls):
        raise DiceError(f'Cannot keep/drop {n} of {len(rolls)} dice.')
    if mode in ('kh', 'k'):
        return set(order[len(rolls) - n:])
    if mode == 'kl':
        return set(order[:n])
    if mode in ('dl', 'd'):
        return set(order[n:])
    return set(order[:len(rolls) - n])                                   # dh


def roll_expression(expression):
    """Return (total, detail text, natural d20 value or None)."""
    text = expression.lower().replace(' ', '')
    text = re.sub(r'^adv', '2d20kh1', text)
    text = re.sub(r'^dis', '2d20kl1', text)
    if not text:
        raise DiceError('Nothing to roll.')
    position, total, parts, terms, natural = 0, 0, [], 0, None
    for match in TERM.finditer(text):
        if match.start() != position or (position and not match.group(1)):
            raise DiceError(f'I could not read "{expression}".')
        position = match.end()
        terms += 1
        if terms > MAX_TERMS:
            raise DiceError(f'Use at most {MAX_TERMS} terms.')
        sign = -1 if match.group(1) == '-' else 1
        prefix = ('- ' if sign < 0 else '+ ') if parts else ('-' if sign < 0 else '')
        if match.group(6):                                               # plain modifier
            value = int(match.group(6))
            total += sign * value
            parts.append(f'{prefix}{value}')
            continue
        count = int(match.group(2) or 1)
        sides = 100 if match.group(3) == '%' else int(match.group(3))
        if not 1 <= count <= MAX_DICE:
            raise DiceError(f'Roll between 1 and {MAX_DICE} dice at a time.')
        if not 2 <= sides <= MAX_SIDES:
            raise DiceError(f'Dice need between 2 and {MAX_SIDES} sides.')
        rolls = _roll(count, sides)
        kept = _keep(rolls, match.group(4).lower(), int(match.group(5))) if match.group(4) else set(range(count))
        subtotal = sum(rolls[i] for i in kept)
        total += sign * subtotal
        shown = ', '.join(str(r) if i in kept else f'({r})' for i, r in enumerate(rolls))
        parts.append(f'{prefix}[{shown}]')
        if sides == 20 and len(kept) == 1 and terms == 1:
            natural = rolls[next(iter(kept))]
    if position != len(text):
        raise DiceError(f'I could not read "{expression}".')
    return total, ' '.join(parts), natural


def roll_dice(expression: str = '') -> str:
    expression = re.sub(r'\s+', ' ', (expression or '').strip())
    lowered = expression.lower()
    if lowered in ('help', '?'):
        return USAGE
    if lowered in ('coin', 'a coin', 'flip', 'coin flip'):
        return f"🪙 {'Heads' if secrets.randbelow(2) else 'Tails'}!"
    if len(expression) > 80:
        return '🎲 Please keep dice rolls under 80 characters.'
    repeats, notation = 1, expression or '1d6'
    match = re.match(r'^(\d+)\s*[x×]\s*(.+)$', notation, re.I)
    if match:
        repeats, notation = int(match.group(1)), match.group(2)
        if not 1 <= repeats <= MAX_REPEATS:
            return f'🎲 Repeat a roll at most {MAX_REPEATS} times.'
    if notation.isdigit():
        notation = f'1d{notation}'  # "/roll 20" means one twenty-sided die
    try:
        results = [roll_expression(notation) for _ in range(repeats)]
    except DiceError as exc:
        return f'🎲 {exc}\n\n{USAGE}'
    if repeats == 1:
        total, detail, natural = results[0]
        line = f'🎲 {notation}: {detail} = {total}'
        if natural == 20:
            line += '\n✨ Natural 20!'
        elif natural == 1:
            line += '\n💀 Natural 1!'
        return line
    lines = [f'🎲 {repeats}× {notation}:']
    lines += [f'{i}. {detail} = {total}' for i, (total, detail, _) in enumerate(results, 1)]
    lines.append(f'Total of all rolls: {sum(total for total, _, _ in results)}')
    return '\n'.join(lines)
