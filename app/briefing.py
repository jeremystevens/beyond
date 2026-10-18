"""/morning: a daily morning briefing at your chosen time: the weather for your city, today's reminders, a few
headlines, and a quote or a joke. Ported from PromptetheusBot (one user; the voice version comes with the speech
phase). No AI needed.

The server checks every 30 seconds and posts a due briefing in the chat where you set it up, with a Windows popup
(app/server.py), so it arrives with the browser closed. If BEYOND was off at briefing time, the briefing still comes
within GRACE_MINUTES; otherwise that day is skipped. Settings are one row in BEYOND's database.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import chats, reminders

GRACE_MINUTES = 120
SECTIONS = {'weather': '🌤 Weather', 'reminders': '⏰ Reminders', 'headlines': '📰 Headlines', 'closer': '💬 Quote/joke'}
NEWS_CHOICES = ('top', 'world', 'us', 'tech', 'science', 'business', 'health', 'sports', 'entertainment', 'politics')
TIME_CHOICES = ('06:00', '06:30', '07:00', '07:30', '08:00', '08:30', '09:00', '09:30', '10:00')
DEFAULTS = {'enabled': 0, 'weekday_time': '07:30', 'weekend_time': '09:00', 'sections': list(SECTIONS),
            'news': 'top', 'closer': 'quote', 'city': None, 'place': None, 'timezone': None,
            'latitude': None, 'longitude': None, 'country': None, 'name': None, 'chat_id': None, 'last_sent': None}
HELP = ("☀️ /morning — a daily briefing at your chosen time: weather for your city, today's reminders, top "
        'headlines, and a quote or joke. It arrives in the chat where you set it up, with a popup, even with the '
        'browser closed.\n/morning opens the menu · /morning city San Carlos, CA · /morning 7:30 · '
        '/morning weekends 9am · /morning news tech · /morning name Sam · /morning on · /morning off · '
        '/morning now')


# ---------- settings storage ----------

def initialize():
    with chats.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS briefing_settings (id INTEGER PRIMARY KEY CHECK (id = 1), '
                   'data TEXT NOT NULL)')


def get_settings():
    settings = dict(DEFAULTS)
    with chats.connect() as db:
        row = db.execute('SELECT data FROM briefing_settings WHERE id = 1').fetchone()
    if row:
        try:
            settings.update(json.loads(row[0]))
        except ValueError:
            pass
    return settings


def save_settings(settings):
    data = {key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS}
    with chats.connect() as db:
        db.execute('INSERT INTO briefing_settings (id, data) VALUES (1, ?) '
                   'ON CONFLICT(id) DO UPDATE SET data = excluded.data', (json.dumps(data),))
    return settings


# ---------- scheduling (pure functions, easy to test) ----------

def parse_time(text):
    """'7:30', '07:30', '7am', '7:30 pm', 'off' -> 'HH:MM' or 'off'; raise ValueError."""
    text = text.strip().lower().replace('.', '')
    if text in ('off', 'none', 'no'):
        return 'off'
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
    if not match:
        raise ValueError('Use a time like 7:30, 07:30, or 7am.')
    hour, minute, ampm = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if ampm:
        if not 1 <= hour <= 12:
            raise ValueError('With am/pm the hour must be 1–12.')
        hour = hour % 12 + (12 if ampm == 'pm' else 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError('That is not a valid time.')
    return f'{hour:02d}:{minute:02d}'


def display_time(value):
    if value == 'off':
        return 'off'
    return datetime.strptime(value, '%H:%M').strftime('%I:%M %p').lstrip('0')


def scheduled_for(settings, local_now):
    """The local datetime today's briefing is scheduled for, or None if today is 'off'."""
    value = settings['weekday_time'] if local_now.weekday() < 5 else settings['weekend_time']
    if value == 'off':
        return None
    hour, minute = map(int, value.split(':'))
    return local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def is_due(settings, now_utc=None):
    """True if the briefing should be sent now (on time, or late but within the grace period)."""
    if not settings['enabled'] or not settings['timezone']:
        return False
    local_now = (now_utc or datetime.now(timezone.utc)).astimezone(ZoneInfo(settings['timezone']))
    target = scheduled_for(settings, local_now)
    if target is None or settings['last_sent'] == local_now.date().isoformat():
        return False
    return target <= local_now <= target + timedelta(minutes=GRACE_MINUTES)


def mark_sent(settings, now_utc=None):
    local_now = (now_utc or datetime.now(timezone.utc)).astimezone(ZoneInfo(settings['timezone']))
    settings['last_sent'] = local_now.date().isoformat()
    return save_settings(settings)


def skip_today_if_passed(settings, now_utc=None):
    """After turning it on or changing times: if today's time already passed, start tomorrow instead of sending a
    'good morning' right away. If today's time is still ahead, today's briefing is allowed again."""
    if settings['timezone']:
        local_now = (now_utc or datetime.now(timezone.utc)).astimezone(ZoneInfo(settings['timezone']))
        target = scheduled_for(settings, local_now)
        if target is not None and local_now >= target:
            settings['last_sent'] = local_now.date().isoformat()
        elif settings['last_sent'] == local_now.date().isoformat():
            settings['last_sent'] = None
    return settings


def set_city(settings, city):
    """Look the city up (shared with /weather and /time) and store its coordinates and time zone."""
    from app.tools import places
    place = places.geocode(city)
    if not place or not place.get('timezone'):
        raise ValueError(f'I couldn\'t find "{city}". Add a state or country, e.g. San Carlos, CA')
    first_city = settings['city'] is None
    settings.update(city=city, place=places.label(place), timezone=place['timezone'],
                    latitude=place['latitude'], longitude=place['longitude'], country=place.get('country_code'))
    if first_city and settings['news'] == 'top' and settings['country'] == 'US':
        settings['news'] = 'us'   # "top" is mostly BBC (UK); US users get US national news by default
    return settings


# ---------- building the briefing ----------

def _weather(settings):
    from app.tools.weather import _describe
    from app.tools.web import get
    imperial = settings['country'] in ('US', 'LR', 'MM')
    unit = '°F' if imperial else '°C'
    data = get('https://api.open-meteo.com/v1/forecast', timeout=10, params={
        'latitude': settings['latitude'], 'longitude': settings['longitude'], 'timezone': 'auto', 'forecast_days': 1,
        'current': 'temperature_2m,weather_code',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
        'temperature_unit': 'fahrenheit' if imperial else 'celsius'}).json()
    now, daily = data['current'], data['daily']
    icon, text = _describe(daily['weather_code'][0])
    high, low = round(daily['temperature_2m_max'][0]), round(daily['temperature_2m_min'][0])
    rain = daily['precipitation_probability_max'][0] or 0
    tips = []
    if rain >= 50:
        tips.append('☂️ Take an umbrella.')
    elif rain >= 25:
        tips.append('🌦 Maybe pack an umbrella.')
    if low <= (50 if imperial else 10):
        tips.append('🧥 Grab a jacket.')
    if high >= (90 if imperial else 32):
        tips.append('🥤 Hot day: stay hydrated.')
    city = (settings['place'] or settings['city']).split(',')[0]
    return (f"{icon} {city}: {round(now['temperature_2m'])}{unit} now · high {high}{unit} / low {low}{unit} · "
            f"{text.lower()} · {rain}% chance of rain" + (f"\n{' '.join(tips)}" if tips else ''))


def _reminders(settings):
    tz = ZoneInfo(settings['timezone'])
    local_now = datetime.now(tz)
    end = local_now.replace(hour=23, minute=59, second=59)
    today = [(due_at.astimezone(tz).strftime('%I:%M %p').lstrip('0'), message[:80])
             for _, message, due_at, _, _ in reminders.active() if local_now <= due_at.astimezone(tz) <= end][:8]
    return ('⏰ Today: ' + ' · '.join(f'{when} — {what}' for when, what in today)) if today else None


def _headlines(settings):
    from app.tools.news import top_headlines
    items = top_headlines(settings['news'], 3)
    label = {'top': 'Top', 'us': 'U.S.', 'tech': 'Tech'}.get(settings['news'], settings['news'].title())
    return f'📰 {label} headlines\n' + '\n'.join(f'{i}. {title} ({source})' for i, (title, source) in enumerate(items, 1))


def _closer(settings):
    if settings['closer'] == 'joke':
        from app.tools.jokes import get_joke
        return '😄 ' + get_joke('').split('\n\n', 1)[-1].rsplit('\n\n—', 1)[0].strip()
    from app.tools.little_lookups import random_quote
    return random_quote().split('\n\nSource:')[0]


def build(settings, now_utc=None):
    """The briefing's text. A failing section (e.g. the news service is down) is left out instead of failing it."""
    local_now = (now_utc or datetime.now(timezone.utc)).astimezone(ZoneInfo(settings['timezone']))
    name = settings.get('name')
    text = [f'☀️ Good morning{", " + name if name else ""}! — {local_now:%A, %B} {local_now.day}']
    builders = {'weather': _weather, 'reminders': _reminders, 'headlines': _headlines, 'closer': _closer}
    for section in SECTIONS:
        if section not in settings['sections'] or (section == 'weather' and settings['latitude'] is None):
            continue
        try:
            line = builders[section](settings)
        except Exception:
            logging.warning('Morning briefing: the %s section failed', section, exc_info=True)
            continue
        if line:
            text.append(line)
    text.append('Have a great day! 🔥')
    return '\n\n'.join(text)


# ---------- the menu ----------

def menu_text(settings):
    status = '🟢 ON' if settings['enabled'] else '⚪ OFF'
    city = settings['place'] or 'not set — send /morning city <your city>'
    zone = f" ({settings['timezone']})" if settings['timezone'] else ''
    sections = ' · '.join(('✅ ' if key in settings['sections'] else '▫️ ') + label.split(' ', 1)[1]
                          for key, label in SECTIONS.items())
    return (f'☀️ Morning briefing — {status}\n\n'
            f"⏰ Weekdays {display_time(settings['weekday_time'])} · Weekends {display_time(settings['weekend_time'])}\n"
            f'📍 {city}{zone}\n'
            f'🧩 {sections}\n'
            f"📰 News: {settings['news']} · 💬 Ending: {settings['closer']}"
            + (f" · 👋 Name: {settings['name']}" if settings['name'] else '') + '\n\n'
            'Tap to change. Typing works too: /morning 7:30 · /morning weekends 9am · /morning city San Carlos, CA · '
            '/morning name Sam · /morning now')
