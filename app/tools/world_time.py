"""World clock and time-zone converter.

Uses Python's zoneinfo with the tzdata package (exact, offline, daylight-saving aware).
Places are resolved offline first (IANA zone names, ~400 zone cities, common cities,
countries, and abbreviations); anything else (e.g. "San Jose, CA") is looked up with the
free Open-Meteo geocoder (app/tools/places.py; only the place name is sent).
Copied from PromptetheusBot (requests replaced by httpx).
"""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

import httpx

from app.tools import places

MAX_PLACES = 6
ABBREVIATIONS = {
    'utc': 'UTC', 'gmt': 'Etc/GMT', 'z': 'UTC',
    'est': 'America/New_York', 'edt': 'America/New_York', 'et': 'America/New_York', 'eastern': 'America/New_York',
    'cst': 'America/Chicago', 'cdt': 'America/Chicago', 'ct': 'America/Chicago', 'central': 'America/Chicago',
    'mst': 'America/Denver', 'mdt': 'America/Denver', 'mt': 'America/Denver', 'mountain': 'America/Denver',
    'pst': 'America/Los_Angeles', 'pdt': 'America/Los_Angeles', 'pt': 'America/Los_Angeles',
    'pacific': 'America/Los_Angeles', 'akst': 'America/Anchorage', 'hst': 'Pacific/Honolulu',
    'bst': 'Europe/London', 'cet': 'Europe/Paris', 'cest': 'Europe/Paris', 'eet': 'Europe/Athens',
    'ist': 'Asia/Kolkata', 'jst': 'Asia/Tokyo', 'kst': 'Asia/Seoul', 'sgt': 'Asia/Singapore',
    'aest': 'Australia/Sydney', 'aedt': 'Australia/Sydney', 'awst': 'Australia/Perth', 'nzst': 'Pacific/Auckland',
}
ALIASES = {  # common places that are not IANA zone names
    'san francisco': 'America/Los_Angeles', 'sf': 'America/Los_Angeles', 'seattle': 'America/Los_Angeles',
    'san jose': 'America/Los_Angeles', 'san diego': 'America/Los_Angeles', 'las vegas': 'America/Los_Angeles',
    'portland': 'America/Los_Angeles', 'sacramento': 'America/Los_Angeles', 'silicon valley': 'America/Los_Angeles',
    'nyc': 'America/New_York', 'new york city': 'America/New_York', 'boston': 'America/New_York',
    'washington': 'America/New_York', 'washington dc': 'America/New_York', 'dc': 'America/New_York',
    'miami': 'America/New_York', 'atlanta': 'America/New_York', 'philadelphia': 'America/New_York',
    'orlando': 'America/New_York', 'pittsburgh': 'America/New_York', 'charlotte': 'America/New_York',
    'houston': 'America/Chicago', 'dallas': 'America/Chicago', 'austin': 'America/Chicago',
    'san antonio': 'America/Chicago', 'minneapolis': 'America/Chicago', 'new orleans': 'America/Chicago',
    'nashville': 'America/Chicago', 'st louis': 'America/Chicago', 'kansas city': 'America/Chicago',
    'salt lake city': 'America/Denver', 'albuquerque': 'America/Denver', 'hawaii': 'Pacific/Honolulu',
    'alaska': 'America/Anchorage', 'montreal': 'America/Toronto', 'ottawa': 'America/Toronto',
    'calgary': 'America/Edmonton', 'rio': 'America/Sao_Paulo', 'rio de janeiro': 'America/Sao_Paulo',
    'manchester': 'Europe/London', 'edinburgh': 'Europe/London', 'liverpool': 'Europe/London',
    'barcelona': 'Europe/Madrid', 'milan': 'Europe/Rome', 'venice': 'Europe/Rome', 'florence': 'Europe/Rome',
    'munich': 'Europe/Berlin', 'frankfurt': 'Europe/Berlin', 'hamburg': 'Europe/Berlin',
    'geneva': 'Europe/Zurich', 'st petersburg': 'Europe/Moscow', 'saint petersburg': 'Europe/Moscow',
    'mumbai': 'Asia/Kolkata', 'bombay': 'Asia/Kolkata', 'delhi': 'Asia/Kolkata', 'new delhi': 'Asia/Kolkata',
    'bangalore': 'Asia/Kolkata', 'bengaluru': 'Asia/Kolkata', 'chennai': 'Asia/Kolkata',
    'beijing': 'Asia/Shanghai', 'shenzhen': 'Asia/Shanghai', 'guangzhou': 'Asia/Shanghai',
    'osaka': 'Asia/Tokyo', 'kyoto': 'Asia/Tokyo', 'abu dhabi': 'Asia/Dubai', 'tel aviv': 'Asia/Jerusalem',
    'hanoi': 'Asia/Bangkok', 'canberra': 'Australia/Sydney', 'wellington': 'Pacific/Auckland',
    # countries with a single (or main) time zone
    'japan': 'Asia/Tokyo', 'china': 'Asia/Shanghai', 'india': 'Asia/Kolkata', 'korea': 'Asia/Seoul',
    'south korea': 'Asia/Seoul', 'uk': 'Europe/London', 'united kingdom': 'Europe/London',
    'england': 'Europe/London', 'scotland': 'Europe/London', 'ireland': 'Europe/Dublin',
    'france': 'Europe/Paris', 'germany': 'Europe/Berlin', 'italy': 'Europe/Rome', 'spain': 'Europe/Madrid',
    'netherlands': 'Europe/Amsterdam', 'switzerland': 'Europe/Zurich', 'sweden': 'Europe/Stockholm',
    'norway': 'Europe/Oslo', 'poland': 'Europe/Warsaw', 'greece': 'Europe/Athens', 'turkey': 'Europe/Istanbul',
    'egypt': 'Africa/Cairo', 'south africa': 'Africa/Johannesburg', 'nigeria': 'Africa/Lagos',
    'kenya': 'Africa/Nairobi', 'israel': 'Asia/Jerusalem', 'uae': 'Asia/Dubai', 'thailand': 'Asia/Bangkok',
    'vietnam': 'Asia/Ho_Chi_Minh', 'philippines': 'Asia/Manila', 'singapore': 'Asia/Singapore',
    'new zealand': 'Pacific/Auckland', 'argentina': 'America/Argentina/Buenos_Aires', 'peru': 'America/Lima',
    'colombia': 'America/Bogota', 'iceland': 'Atlantic/Reykjavik',
}
USAGE = ('🕒 Usage:\n'
         '/time Tokyo — current time in a city\n'
         '/time Tokyo, London, New York — several places (up to 6)\n'
         '/time 3pm London to Tokyo — convert a time (also 15:30, noon, midnight)\n'
         'Cities, countries, US states like "San Jose, CA", or zones like EST / UTC / Asia/Tokyo.')


def _city_index():
    index = {}
    for zone in available_timezones():
        if '/' in zone and not zone.startswith(('Etc/', 'SystemV/', 'US/')):
            city = zone.rsplit('/', 1)[1].replace('_', ' ').lower()
            index.setdefault(city, zone)
    return index


CITIES = _city_index()


def _offline(name):
    """Return (label, zone) from built-in data, or None."""
    key = re.sub(r'\s+', ' ', name.lower().replace('.', '').strip())
    key = re.sub(r'\s+(?:time|timezone|time zone)$', '', key)
    for table in (ALIASES, CITIES, ABBREVIATIONS):
        if key in table:
            zone = table[key]
            label = key.upper() if table is ABBREVIATIONS else name.strip().title()
            return label, zone
    exact = next((z for z in available_timezones() if z.lower() == key.replace(' ', '_')), None)
    return (exact, exact) if exact else None


def _online(name):
    """Return (label, zone) using the Open-Meteo geocoder, or None."""
    place = places.geocode(name)
    if place and place.get('timezone'):
        return places.label(place), place['timezone']
    return None


def resolve(name):
    """Return (label, ZoneInfo) or raise LookupError."""
    name = name.strip(' ?.!')
    if not name:
        raise LookupError('empty')
    found = None if ',' in name else _offline(name)  # "San Jose, CA" goes online for the state
    if not found:
        try:
            found = _online(name)
        except (httpx.HTTPError, ValueError):
            # Offline: "City, ST" can still fall back to the city name. A list such as
            # "Tokyo, London" must not, so the caller splits it into separate places.
            city, region = name.split(',', 1) if name.count(',') == 1 else (name, '')
            if region and not _offline(region):  # "Tokyo, London" is a list, not City, Region
                found = _offline(city)
    if not found:
        raise LookupError(name)
    return found[0], ZoneInfo(found[1])


def _offset(moment):
    minutes = int(moment.utcoffset().total_seconds() // 60)
    sign = '+' if minutes >= 0 else '-'
    hours, mins = divmod(abs(minutes), 60)
    return f'UTC{sign}{hours}' + (f':{mins:02d}' if mins else '')


def _clock(moment):
    return f"{moment.strftime('%a')} {moment.strftime('%I:%M %p').lstrip('0')}"


def _zone_name(moment):
    abbr = moment.strftime('%Z')
    return abbr if abbr and not abbr.startswith(('+', '-')) else ''


def _difference(a, b):
    """How far b's clock is from a's, e.g. '8h behind Tokyo'."""
    delta = (b.utcoffset() - a.utcoffset()).total_seconds() / 3600
    if delta == 0:
        return 'same time'
    hours = f'{abs(delta):g}h'
    return f'{hours} ahead' if delta > 0 else f'{hours} behind'


def _line(label, moment):
    zone = _zone_name(moment)
    return f"🕒 {label} — {_clock(moment)} ({zone + ', ' if zone else ''}{_offset(moment)})"


def _split_places(text):
    """Try the whole text as one place; otherwise split on commas / 'and' / ';'."""
    try:
        return [resolve(text)]
    except LookupError:
        pass
    parts = [p for p in re.split(r'\s*(?:,|;|\band\b|\bvs\.?\b|&)\s*', text) if p.strip()]
    if len(parts) > MAX_PLACES:
        raise ValueError(f'Please ask about at most {MAX_PLACES} places at once.')
    return [resolve(part) for part in parts]


TIME_RE = re.compile(r'^(?:(noon|midday|midnight)|(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?)\s+(.+?)\s+(?:to|in|into|->|=)\s+(.+)$', re.I)


def _convert(match):
    word, hour, minute, ampm, source_text, target_text = match.groups()
    if word:
        hour, minute = (0 if word.lower() == 'midnight' else 12), 0
    else:
        hour, minute = int(hour), int(minute or 0)
        if ampm:
            if not 1 <= hour <= 12:
                raise ValueError('With am/pm, the hour must be 1–12.')
            hour = hour % 12 + (12 if ampm.lower().startswith('p') else 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError('That is not a valid time.')
    source_text = re.sub(r'\s+time$', '', source_text, flags=re.I)
    source_label, source_zone = resolve(source_text)
    targets = _split_places(re.sub(r'\s+time$', '', target_text.strip(' ?.!'), flags=re.I))
    today = datetime.now(source_zone).date()
    start = datetime(today.year, today.month, today.day, hour, minute, tzinfo=source_zone)
    lines = [f'🕒 {_clock(start)} in {source_label} ({_zone_name(start) or _offset(start)}) is:']
    for label, zone in targets:
        moment = start.astimezone(zone)
        days = (moment.date() - start.date()).days
        note = ' (next day)' if days == 1 else ' (previous day)' if days == -1 else ''
        lines.append(f"→ {label}: {_clock(moment)}{note} ({_zone_name(moment) + ', ' if _zone_name(moment) else ''}{_offset(moment)})")
    return '\n'.join(lines)


def world_time(query: str = '') -> str:
    query = re.sub(r'\s+', ' ', (query or '').strip())
    if not query or query.lower() in ('help', '?'):
        now = datetime.now(timezone.utc)
        return f"{USAGE}\n\nRight now it is {now.strftime('%a %H:%M')} UTC."
    if len(query) > 150:
        return '🕒 Please keep time requests under 150 characters.'
    try:
        match = TIME_RE.match(query)
        if match:
            return _convert(match)
        places = _split_places(query)
    except LookupError as exc:
        return f'🕒 I could not find "{exc.args[0]}". Try a bigger nearby city, add a state or country, or use a zone like EST.'
    except ValueError as exc:
        return f'🕒 {exc}'
    now = datetime.now(timezone.utc)
    moments = [(label, now.astimezone(zone)) for label, zone in places]
    lines = [_line(label, moment) for label, moment in moments]
    if len(moments) > 1:
        first_label, first = moments[0]
        for i, (label, moment) in enumerate(moments[1:], 1):
            lines[i] += f' · {_difference(first, moment)} {first_label}' if _difference(first, moment) != 'same time' \
                else f' · same time as {first_label}'
    return '\n'.join(lines)
