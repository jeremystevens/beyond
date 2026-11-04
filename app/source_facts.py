"""Read explicit measurements for supported single-fact source questions."""
import re
from decimal import Decimal

_NAME = r'(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)'
_VALUE = r'(?P<value>\d{1,9}(?:\.\d{1,6})?)'
_FACTS = {
    'tank capacity': (
        rf'what is the {_NAME} tank capacity\?\s*(?:answer with the capacity only[.!]?)?',
        rf'(?:the )?{_NAME} tank (?:holds|has a capacity of) {_VALUE} (?P<unit>litres?|liters?)',
    ),
    'battery duration': (
        rf'how long does the {_NAME} battery last\?',
        rf'(?:the )?{_NAME} battery lasts {_VALUE} (?P<unit>hours?|minutes?)',
    ),
    'weight': (
        rf'how much does the {_NAME} weigh\?',
        rf'(?:the )?{_NAME} weighs {_VALUE} (?P<unit>kilograms?|grams?|kg|g)',
    ),
}
_UNIT_ALIASES = {'liter': 'litre', 'kg': 'kilogram', 'g': 'gram'}


def source_request(question):
    """Recognize only direct, single-fact questions."""
    for kind, (pattern, _) in _FACTS.items():
        match = re.fullmatch(pattern, question.strip(), re.I)
        if match:
            return kind, match['name'].casefold()
    return None


def answer(request, sources):
    """Use complete declarative sentences from current sources."""
    kind, subject = request
    _, pattern = _FACTS[kind]
    values = set()
    for source in sources:
        for sentence in re.split(r'[.!?]\s+|\r?\n', source):
            match = re.fullmatch(pattern, sentence.strip().rstrip('.'), re.I)
            if match and match['name'].casefold() == subject:
                unit = match['unit'].lower().rstrip('s')
                values.add((Decimal(match['value']), _UNIT_ALIASES.get(unit, unit)))
    if len(values) != 1:
        return f'I could not verify a single {kind} from the supplied source.'
    value, unit = values.pop()
    number = format(value, 'f')
    if '.' in number:
        number = number.rstrip('0').rstrip('.')
    return f'{number} {unit}' + ('' if value == 1 else 's')
