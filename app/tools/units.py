"""Offline unit conversions (no LLM, no network).

Every unit is defined by a category and a factor to that category's base unit.
Temperature and fuel economy are handled specially because they aren't simple ratios.
The amount is evaluated with the safe calculator, so "1/2 cup" or "1,200 ft" work.
"""
import re

from app.tools.calculator import CalcError, evaluate

# category -> {canonical unit: (factor to base unit, display symbol, [aliases])}
UNITS = {
    'length': {  # base: metre
        'mm': (0.001, 'mm', ['millimeter', 'millimetre']),
        'cm': (0.01, 'cm', ['centimeter', 'centimetre']),
        'm': (1, 'm', ['meter', 'metre']),
        'km': (1000, 'km', ['kilometer', 'kilometre', 'kms']),
        'in': (0.0254, 'in', ['inch', 'inches', '"']),
        'ft': (0.3048, 'ft', ['foot', 'feet', "'"]),
        'yd': (0.9144, 'yd', ['yard']),
        'mi': (1609.344, 'mi', ['mile']),
        'nmi': (1852, 'nmi', ['nautical mile', 'nm']),
    },
    'mass': {  # base: gram
        'mg': (0.001, 'mg', ['milligram']),
        'g': (1, 'g', ['gram', 'gramme', 'gm']),
        'kg': (1000, 'kg', ['kilogram', 'kilo', 'kilos']),
        't': (1_000_000, 't', ['tonne', 'metric ton', 'metric tonne']),
        'oz': (28.349523125, 'oz', ['ounce']),
        'lb': (453.59237, 'lb', ['pound', 'lbs']),
        'st': (6350.29318, 'st', ['stone']),
        'ton': (907184.74, 'US ton', ['us ton', 'short ton']),
    },
    'volume': {  # base: millilitre (US customary cooking units)
        'ml': (1, 'ml', ['milliliter', 'millilitre', 'cc']),
        'l': (1000, 'L', ['liter', 'litre', 'ltr']),
        'tsp': (4.92892159375, 'tsp', ['teaspoon']),
        'tbsp': (14.78676478125, 'tbsp', ['tablespoon', 'tbs']),
        'floz': (29.5735295625, 'fl oz', ['fl oz', 'fluid ounce', 'fl. oz', 'fl.oz']),
        'cup': (236.5882365, 'cup', ['cups']),  # not 'c': that is Celsius
        'pt': (473.176473, 'pt', ['pint']),
        'qt': (946.352946, 'qt', ['quart']),
        'gal': (3785.411784, 'gal', ['gallon', 'us gallon']),
        'impgal': (4546.09, 'imp gal', ['imperial gallon', 'uk gallon']),
        'm3': (1_000_000, 'm³', ['cubic meter', 'cubic metre', 'm³']),
    },
    'area': {  # base: square metre
        'm2': (1, 'm²', ['sq m', 'square meter', 'square metre', 'sqm', 'm²']),
        'km2': (1_000_000, 'km²', ['sq km', 'square kilometer', 'square kilometre', 'km²']),
        'ft2': (0.09290304, 'ft²', ['sq ft', 'square foot', 'square feet', 'sqft', 'ft²']),
        'in2': (0.00064516, 'in²', ['sq in', 'square inch', 'square inches', 'in²']),
        'yd2': (0.83612736, 'yd²', ['sq yd', 'square yard', 'yd²']),
        'mi2': (2_589_988.110336, 'mi²', ['sq mi', 'square mile', 'mi²']),
        'acre': (4046.8564224, 'acre', ['acres', 'ac']),
        'ha': (10_000, 'ha', ['hectare']),
    },
    'speed': {  # base: metre per second
        'mps': (1, 'm/s', ['m/s', 'meters per second', 'metres per second']),
        'kph': (1 / 3.6, 'km/h', ['km/h', 'kmh', 'kmph', 'kilometers per hour', 'kilometres per hour']),
        'mph': (0.44704, 'mph', ['miles per hour', 'mi/h']),
        'knot': (1852 / 3600, 'knot', ['knots', 'kt', 'kn']),
        'fps': (0.3048, 'ft/s', ['ft/s', 'feet per second']),
    },
    'time': {  # base: second
        'ms': (0.001, 'ms', ['millisecond']),
        's': (1, 's', ['sec', 'second', 'secs']),
        'min': (60, 'min', ['minute', 'mins']),
        'h': (3600, 'h', ['hr', 'hour', 'hrs']),
        'day': (86400, 'day', ['days', 'd']),
        'week': (604800, 'week', ['weeks', 'wk']),
        'year': (31_557_600, 'year', ['years', 'yr', 'yrs']),
    },
    'data': {  # base: byte (decimal units, as storage makers use)
        'b': (1, 'B', ['byte', 'bytes']),
        'kb': (1e3, 'KB', ['kilobyte']),
        'mb': (1e6, 'MB', ['megabyte']),
        'gb': (1e9, 'GB', ['gigabyte']),
        'tb': (1e12, 'TB', ['terabyte']),
        'kib': (1024, 'KiB', ['kibibyte']),
        'mib': (1024 ** 2, 'MiB', ['mebibyte']),
        'gib': (1024 ** 3, 'GiB', ['gibibyte']),
        'tib': (1024 ** 4, 'TiB', ['tebibyte']),
    },
    'energy': {  # base: joule
        'j': (1, 'J', ['joule']),
        'kj': (1000, 'kJ', ['kilojoule']),
        'cal': (4.184, 'cal', ['calorie']),
        'kcal': (4184, 'kcal', ['kilocalorie', 'food calorie', 'calories (food)']),
        'wh': (3600, 'Wh', ['watt hour', 'watt-hour']),
        'kwh': (3_600_000, 'kWh', ['kilowatt hour', 'kilowatt-hour']),
        'btu': (1055.05585262, 'BTU', ['btus']),
    },
    'pressure': {  # base: pascal
        'pa': (1, 'Pa', ['pascal']),
        'kpa': (1000, 'kPa', ['kilopascal']),
        'bar': (100_000, 'bar', ['bars']),
        'psi': (6894.757293168, 'psi', []),
        'atm': (101_325, 'atm', ['atmosphere']),
        'mmhg': (133.322387415, 'mmHg', ['mm hg', 'millimeters of mercury']),
    },
}
TEMPERATURE = {'c': ('°C', ['celsius', 'centigrade', '°c', 'degc']),
               'f': ('°F', ['fahrenheit', '°f', 'degf']),
               'k': ('K', ['kelvin', 'kelvins'])}
FUEL = {'mpg': ('mpg (US)', ['miles per gallon', 'mpg us']),
        'mpg_uk': ('mpg (UK)', ['mpg uk', 'imperial mpg', 'miles per imperial gallon']),
        'l100km': ('L/100 km', ['l/100km', 'l/100 km', 'liters per 100 km', 'litres per 100 km'])}
# Suggested targets when the user doesn't name one.
DEFAULT_TARGETS = {
    'c': ['f', 'k'], 'f': ['c'], 'k': ['c', 'f'],
    'km': ['mi'], 'mi': ['km'], 'm': ['ft', 'yd'], 'ft': ['m'], 'in': ['cm'], 'cm': ['in'], 'yd': ['m'],
    'kg': ['lb'], 'lb': ['kg'], 'g': ['oz'], 'oz': ['g'], 'st': ['kg', 'lb'],
    'l': ['gal', 'qt'], 'gal': ['l'], 'ml': ['floz', 'tsp'], 'cup': ['ml', 'tbsp', 'floz'], 'tbsp': ['tsp', 'ml'],
    'tsp': ['ml'], 'floz': ['ml'], 'kph': ['mph'], 'mph': ['kph'], 'm2': ['ft2'], 'ft2': ['m2'],
    'acre': ['ha', 'ft2'], 'ha': ['acre'], 'mpg': ['l100km'], 'l100km': ['mpg'], 'kwh': ['kcal', 'j'],
    'kcal': ['kj'], 'h': ['min'], 'min': ['h', 's'], 'day': ['h'], 'week': ['day'], 'year': ['day', 'week'],
    'psi': ['bar', 'kpa'], 'bar': ['psi'], 'gb': ['gib', 'mb'], 'tb': ['tib', 'gb'],
}
USAGE = ('Usage: /convert <amount> <unit> to <unit>\n'
         'Examples: /convert 72 fahrenheit to celsius · /convert 5 km to miles · /convert 2 cups to ml\n'
         '/convert 1/2 cup to tbsp · /convert 30 mpg to l/100km · /convert 500 GB to GiB\n'
         'Leave out the target to see common conversions: /convert 10 kg\n'
         'Categories: temperature, length, weight, volume & cooking (US cups), area, speed, time, '
         'data, energy, pressure, fuel economy.\n'
         'Note: cups ↔ grams depends on the ingredient, so it is not supported.')


def _build_index():
    index = {}

    def add(alias, entry):
        alias = alias.lower().strip()
        index.setdefault(alias, entry)
        if len(alias) > 2 and not alias.endswith('s') and not alias.startswith(('°', 'sq ', 'square ')):
            index.setdefault(alias + 's', entry)          # plurals: miles, cups, pounds
        elif alias.startswith(('square ', 'cubic ')) and not alias.endswith('s'):
            index.setdefault(alias + 's', entry)          # square meters, cubic feet

    for category, units in UNITS.items():
        for key, (_, symbol, aliases) in units.items():
            for alias in [key, symbol, *aliases]:
                add(alias, (category, key))
    for key, (symbol, aliases) in TEMPERATURE.items():
        for alias in [key, symbol, *aliases]:
            add(alias, ('temperature', key))
    for key, (symbol, aliases) in FUEL.items():
        for alias in [key, symbol, *aliases]:
            add(alias, ('fuel', key))
    return index


INDEX = _build_index()


def _unit(text):
    text = re.sub(r'\s+', ' ', text.lower().strip().rstrip('.?!'))
    text = re.sub(r'^(?:an?|the)\s+', '', text)
    text = re.sub(r'^degrees?\s+|^deg\s+', '', text)
    entry = INDEX.get(text) or INDEX.get(text.replace(' ', ''))
    if not entry:
        raise CalcError(f'Unknown unit: "{text}". Send /convert for supported units.')
    return entry


PLURAL_WORDS = {'cup', 'acre', 'knot', 'day', 'week', 'year', 'US ton'}


def _symbol(category, key, value=1):
    if category == 'temperature':
        return TEMPERATURE[key][0]
    if category == 'fuel':
        return FUEL[key][0]
    symbol = UNITS[category][key][1]
    return symbol + 's' if symbol in PLURAL_WORDS and value != 1 else symbol


def _to_celsius(value, key):
    return value if key == 'c' else (value - 32) * 5 / 9 if key == 'f' else value - 273.15


def _from_celsius(value, key):
    return value if key == 'c' else value * 9 / 5 + 32 if key == 'f' else value + 273.15


def _fuel(value, source, target):
    # Convert everything through litres per 100 km; mpg is inversely proportional.
    us = 235.214583, 282.480936  # L/100km = constant / mpg
    if source == target:
        return value
    if value == 0:
        raise CalcError('Fuel economy of 0 cannot be converted.')
    l100 = value if source == 'l100km' else (us[0] if source == 'mpg' else us[1]) / value
    return l100 if target == 'l100km' else (us[0] if target == 'mpg' else us[1]) / l100


def _convert(value, source, target):
    category, from_key = source
    to_category, to_key = target
    if category != to_category:
        raise CalcError(f'Cannot convert {category} to {to_category}.'
                        + (' Cups ↔ grams depends on the ingredient.' if {category, to_category} == {'volume', 'mass'} else ''))
    if category == 'temperature':
        celsius = _to_celsius(value, from_key)
        if celsius < -273.15 - 1e-9:
            raise CalcError('That is below absolute zero.')
        return _from_celsius(celsius, to_key)
    if category == 'fuel':
        return _fuel(value, from_key, to_key)
    return value * UNITS[category][from_key][0] / UNITS[category][to_key][0]


def _fmt(value):
    if value == 0:
        return '0'
    if abs(value) >= 1e15 or abs(value) < 1e-4:
        return f'{value:.4g}'
    decimals = 2 if abs(value) >= 100 else 4 if abs(value) < 1 else 3
    text = f'{value:,.{decimals}f}'.rstrip('0').rstrip('.')
    return text


def is_conversion(query: str) -> bool:
    """True if the text names an amount and two known, compatible units (for natural-language routing)."""
    match = re.match(r"""^([-+($]*\d[\d\s.,/*+\-()]*?)\s*([a-z°µ"'].*?)\s+(?:to|in|into|as)\s+(.+?)\s*\??$""",
                     (query or '').strip(), re.I)
    if not match:
        return False
    try:
        evaluate(match.group(1))
        return _unit(match.group(2))[0] == _unit(match.group(3))[0]
    except CalcError:
        return False


def convert(query: str) -> str:
    query = re.sub(r'\s+', ' ', (query or '').strip())
    if not query or query.lower() in ('help', '?', 'units'):
        return USAGE
    if len(query) > 120:
        return 'Please keep conversions under 120 characters.'
    # Amount (digits and math such as 1,200 or 1/2) runs until the first letter of the unit.
    match = re.match(r"""^([-+($]*\d[\d\s.,/*+\-()]*?)\s*([a-z°µ"'].*?)(?:\s+(?:to|in|into|as|->|=)\s+(.+?))?\s*\??$""",
                     query, re.I)
    if not match:
        return f'🔁 Could not read that conversion.\n\n{USAGE}'
    amount_text, unit_text, target_text = match.groups()
    try:
        value = evaluate(amount_text)
        source = _unit(unit_text)
        targets = [_unit(target_text)] if target_text else \
            [(source[0], key) for key in DEFAULT_TARGETS.get(source[1], [])]
        if not targets:
            return f'🔁 Add a target unit, e.g. /convert {amount_text.strip()} {unit_text} to <unit>'
        lines = []
        for target in targets:
            result = _convert(value, source, target)
            lines.append(f'🔁 {_fmt(value)} {_symbol(*source, value)} = {_fmt(result)} {_symbol(*target, round(result, 6))}')
    except CalcError as exc:
        return f'🔁 {exc}'
    if source[0] == 'volume' and any(t[1] in ('cup', 'pt', 'qt', 'gal', 'floz') for t in [source, *targets]):
        lines.append('(US measures)')
    return '\n'.join(lines)
