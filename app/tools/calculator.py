"""Safe calculator: arithmetic, percentages, tips, and bill splitting. No LLM, no network.

Never uses eval(): the expression is parsed with `ast` and only whitelisted numbers,
operators, and math functions are evaluated, with limits on size and exponents.
"""
import ast
import math
import operator
import re
from decimal import ROUND_HALF_UP, Decimal

MAX_EXPRESSION = 200
MAX_EXPONENT = 1000
MAX_MAGNITUDE = 1e100
DEFAULT_TIPS = (15, 18, 20)
USAGE = ('Usage:\n'
         '/calc (45 * 3) + 18\n'
         '/calc 15% of 80   ·   /calc 80 + 15%   ·   /calc sqrt(144)\n'
         '/calc tip 85.50 18%   (no % shows 15/18/20%)\n'
         '/calc tip 85.50 20% split 4\n'
         '/calc split 120 4   ·   /calc split 120 4 tip 18%\n'
         'Functions: sqrt, abs, round, floor, ceil, log, log10, sin, cos, tan · constants: pi, e')

BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
          ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
FUNCTIONS = {'sqrt': math.sqrt, 'abs': abs, 'round': round, 'floor': math.floor, 'ceil': math.ceil,
             'log': math.log, 'ln': math.log, 'log10': math.log10, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan}
CONSTANTS = {'pi': math.pi, 'e': math.e}


class CalcError(ValueError):
    pass


def _check(value):
    if isinstance(value, complex) or (isinstance(value, float) and not math.isfinite(value)):
        raise CalcError('The result is not a real number.')
    if abs(value) > MAX_MAGNITUDE:
        raise CalcError('That number is too large.')
    return value


def _is_pct(node):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'pct'


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return _check(node.value)  # rejects literals like 1e400 (inf)
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return _check(UNARY[type(node.op)](_eval(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
        # "80 + 15%" means 80 increased by 15%; "80 - 20%" means 80 reduced by 20%.
        if isinstance(node.op, (ast.Add, ast.Sub)) and _is_pct(node.right):
            base, rate = _eval(node.left), _eval(node.right.args[0]) / 100
            return _check(base * (1 + rate) if isinstance(node.op, ast.Add) else base * (1 - rate))
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalcError(f'Exponents are limited to {MAX_EXPONENT}.')
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise CalcError('Division by zero.')
        return _check(BINARY[type(node.op)](left, right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        args = [_eval(arg) for arg in node.args]
        if node.func.id == 'pct' and len(args) == 1:
            return args[0] / 100
        if node.func.id in FUNCTIONS and 1 <= len(args) <= 2:
            try:
                return _check(FUNCTIONS[node.func.id](*args))
            except (ValueError, TypeError, OverflowError) as exc:
                raise CalcError(f'{node.func.id}() cannot use that value.') from exc
    raise CalcError('Only numbers, + - * / // % ^, parentheses, and basic math functions are supported.')


def _prepare(expression):
    text = expression.strip().rstrip('=?').strip().lower()
    text = re.sub(r'[$€£¥]', '', text)
    text = text.replace('×', '*').replace('÷', '/').replace('^', '**').replace('−', '-')
    text = re.sub(r'(?<=[\d)])\s*x\s*(?=[\d(])', '*', text)          # 3 x 4
    text = re.sub(r'\bmod\b', '%', text)
    if not re.search(r'[a-z_]+\s*\(', text):                          # thousands separators: 1,200.50
        text = re.sub(r'(?<![\d.])(\d{1,3}(?:,\d{3})+)(?!\d)', lambda m: m.group(1).replace(',', ''), text)
    # Percent (not modulo) when % is followed by "of", an operator, ")", or the end.
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%\s*of\b', r'pct(\1)*', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%(?=\s*(?:$|[)+\-*/,]))', r'pct(\1)', text)
    return text


def evaluate(expression):
    text = _prepare(expression)
    if not text:
        raise CalcError('Enter something to calculate.')
    try:
        tree = ast.parse(text, mode='eval')
    except SyntaxError as exc:
        raise CalcError("I couldn't read that expression. Check the brackets and operators.") from exc
    return _eval(tree)


def _number(value):
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        value = int(value)
    if isinstance(value, int):
        return f'{value:,}'
    text = f'{value:,.10f}'.rstrip('0').rstrip('.')
    return text if abs(value) >= 1e-6 or value == 0 else f'{value:.6g}'


def _money(value):
    # Round half up like a cashier (12.825 -> 12.83); float formatting would give 12.82.
    return f"{Decimal(repr(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


def _amount(text):
    value = evaluate(text)
    if value < 0:
        raise CalcError('Amounts must be positive.')
    return value


def _tip(text):
    """tip <amount> [<pct>%] [split|for|/ <people>]"""
    match = re.match(r'^(.+?)(?:\s+(\d+(?:\.\d+)?)\s*%)?(?:\s+(?:split|for|between|/)\s*(\d+)(?:\s*(?:people|ways|persons))?)?$',
                     text.strip(), re.I)
    if not match:
        raise CalcError('Usage: /calc tip <amount> [percent%] [split <people>]')
    bill = _amount(match.group(1))
    people = int(match.group(3)) if match.group(3) else 1
    if not 1 <= people <= 100:
        raise CalcError('People must be between 1 and 100.')
    rates = (float(match.group(2)),) if match.group(2) else DEFAULT_TIPS
    lines = [f'🧮 Tip on {_money(bill)}' + (f', split {people} ways' if people > 1 else '')]
    for rate in rates:
        tip = bill * rate / 100
        line = f'{_number(rate)}%: tip {_money(tip)} · total {_money(bill + tip)}'
        if people > 1:
            line += f' · {_money((bill + tip) / people)} each'
        lines.append(line)
    return '\n'.join(lines)


def _split(text):
    """split <amount> <people> [tip <pct>%]"""
    match = re.match(r'^(.+?)\s+(?:by\s+|between\s+|into\s+|among\s+|for\s+|/\s*)?(\d+)(?:\s*(?:people|ways|persons))?'
                     r'(?:\s+(?:tip|with|plus)\s+(\d+(?:\.\d+)?)\s*%(?:\s*tip)?)?$', text.strip(), re.I)
    if not match:
        raise CalcError('Usage: /calc split <amount> <people> [tip <percent>%]')
    if match.group(3):
        return _tip(f'{match.group(1)} {match.group(3)}% split {match.group(2)}')
    bill, people = _amount(match.group(1)), int(match.group(2))
    if not 1 <= people <= 100:
        raise CalcError('People must be between 1 and 100.')
    return f'🧮 {_money(bill)} split {people} ways = {_money(bill / people)} each'


def calculate(expression: str) -> str:
    expression = re.sub(r'\s+', ' ', (expression or '').strip())
    if not expression or expression.lower() in ('help', '?'):
        return USAGE
    if len(expression) > MAX_EXPRESSION:
        return f'Please keep calculations under {MAX_EXPRESSION} characters.'
    try:
        command, _, rest = expression.partition(' ')
        if command.lower() == 'tip':
            return _tip(rest)
        if command.lower() == 'split':
            return _split(rest)
        return f'🧮 {expression} = {_number(evaluate(expression))}'
    except CalcError as exc:
        return f'🧮 {exc}\nSend /calc for examples.'
    except (OverflowError, MemoryError, RecursionError):
        return '🧮 That calculation is too large.'
