"""Clear, read-only tool requests in ordinary words. No model inference or arbitrary command dispatch."""
import re
from app.tools import calculator, units


def command(message):
    text = message.strip().replace('’', "'")
    if not text or len(text) > 300 or '\n' in text or '\r' in text or text.startswith(('/', '"', "'", '`')):
        return None
    if re.search(r';|\b(?:and|also|then)\s+(?:tell|give|show|explain|write|save|delete|remove|run|search|calculate|convert|remind)\b', text, re.I):
        return None
    text = text.rstrip(' .?!')
    text = re.sub(r'\s+please$', '', text, flags=re.I)
    text = re.sub(r'^(?:hey\s+beyond[, ]+|please\s+)', '', text, flags=re.I)
    text = re.sub(r'^(?:can|could|would|will)\s+you\s+(?:please\s+)?', '', text, flags=re.I)
    text = re.sub(r'^please\s+', '', text, flags=re.I)
    match = lambda pattern: re.fullmatch(pattern, text, re.I)
    ask = r'(?:tell|give|show)\s+me\s+'
    article = r'(?:(?:a|an|one|another)\s+)?'
    modifiers = r'(?:(?:random|interesting|fun|funny|cool|new)\s+){0,2}'
    if match(r'(?:'+ask+r')?'+article+modifiers+r'(?:cat\s+fact|fact\s+about\s+cats?)'):
        return '/cat'
    if match(r'(?:'+ask+r')?'+article+r'(?:(?:random|inspirational|inspiring)\s+)?quote'):
        return '/quote'
    joke = match(r'(?:'+ask+r')'+article+r'(?:(dad|pun|nerd|absurd|random)\s+)?joke(?:\s+about\s+(.+))?')
    if joke:
        argument = joke[2] or joke[1] or ''
        return '/joke' + (' ' + argument if argument else '')
    word = match(r'(?:define\s+|what\s+does\s+|what\s+is\s+the\s+(?:definition|meaning)\s+of\s+)([\w-]+)(?:\s+mean)?')
    if word:
        return '/define ' + word[1]
    wiki = match(r'(?:search\s+wikipedia\s+for|look\s+up)\s+(.+?)(?:\s+on\s+wikipedia)')
    if not wiki:
        wiki = match(r'(?:search\s+wikipedia\s+for|(?:give\s+me\s+)?a?\s*wikipedia\s+summary\s+of)\s+(.+)')
    if wiki:
        return '/wiki ' + wiki[1]
    stack = match(r'(?:search\s+stack\s*overflow\s+for|look\s+up\s+on\s+stack\s*overflow)\s+(.+)')
    if stack:
        return '/so ' + stack[1]
    media = match(r'(?:look\s+up|find|tell\s+me\s+about|give\s+me\s+information\s+(?:on|about))\s+(?:the\s+)?(movie|film|tv\s+show|television\s+show|series)\s+(.+)')
    if media:
        return ('/movie ' if media[1].lower() in ('movie', 'film') else '/tv ') + media[2]
    if match(r'flip\s+(?:a\s+)?coin'):
        return '/roll coin'
    dice = match(r'roll\s+(?:(?:a|one)\s+)?(?:die|dice|([1-9]\d?d(?:4|6|8|10|12|20|100)))')
    if dice:
        return '/roll ' + (dice[1] or '1d6')
    clock = match(r'(?:what\s+time\s+is\s+it\s+in|what(?:\s+is|\'s)\s+the\s+(?:current\s+)?time\s+in|(?:tell\s+me\s+)?the\s+(?:current\s+)?time\s+in)\s+(.+)')
    if clock:
        return '/time ' + clock[1]
    for pattern, route in [
        (r'(?:show|check|tell\s+me)\s+(?:(?:me|the|my)\s+)*(?:pc|computer|host|system|beyond)\s+status', '/status'),
        (r'(?:show|list|read)(?:\s+me)?\s+my\s+notes', '/notes'),
        (r'(?:show|list)(?:\s+me)?\s+my\s+(?:lists|checklists)', '/list'),
        (r'(?:show|list)(?:\s+me)?\s+(?:my|your|saved)\s+memories', '/memories'),
        (r'(?:show|list)(?:\s+me)?\s+(?:my\s+)?(?:learned\s+preferences|rating\s+feedback)', '/learned'),
        (r'(?:show|check)(?:\s+me)?\s+(?:my\s+)?(?:recent\s+)?(?:reply\s+timings|response\s+times)', '/speed'),
        (r'(?:run|perform)\s+(?:a\s+)?self[ -]?test', '/selftest'),
        (r'(?:show|give|get)(?:\s+me)?\s+(?:the\s+)?(?:latest\s+)?headlines', '/news'),
        (r'(?:show|list)(?:\s+me)?\s+my\s+(?:upcoming\s+)?reminders', '/reminders'),
        (r'(?:show|list)(?:\s+me)?\s+(?:my\s+)?(?:house\s+)?rules', '/rules'),
        (r'(?:what\s+(?:tools|commands|modules)\s+(?:do\s+you\s+have|can\s+you\s+use)|(?:show|list)(?:\s+me)?\s+(?:your|available|all)\s+(?:tools|commands|modules))', '/help'),
    ]:
        if match(pattern):
            return route
    conversion = re.sub(r'^(?:convert\s+|what\s+is\s+)', '', text, flags=re.I)
    if units.is_conversion(conversion):
        return '/convert ' + conversion
    expression = re.sub(r'^(?:calculate|compute|work\s+out|what\s+is|what\'s)\s+', '', text, flags=re.I)
    for word, symbol in [('multiplied by', '*'), ('divided by', '/'), ('times', '*'), ('plus', '+'), ('minus', '-')]:
        expression = re.sub(r'\b'+word+r'\b', symbol, expression, flags=re.I)
    # Only a supported arithmetic expression is routed, never arbitrary prose or generated code.
    if re.search(r'\d', expression) and re.search(r'[+*/%^×÷−-]|\b(?:sqrt|round|abs|log|floor|ceil)\s*\(', expression, re.I):
        try:
            calculator.evaluate(expression)
        except (calculator.CalcError, ValueError, OverflowError, ZeroDivisionError):
            return None
        return '/calc ' + expression
    return None
