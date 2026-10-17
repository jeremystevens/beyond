"""/weather: current weather and a 3-day forecast from the free Open-Meteo API (no API key or account).
Ported from PromptetheusBot; the place lookup is shared with /time (app/tools/places.py)."""
from datetime import date

from app.tools import places
from app.tools.web import get

FORECAST_API = 'https://api.open-meteo.com/v1/forecast'

# WMO weather interpretation codes used by Open-Meteo.
WMO_CODES = {
    0: ('☀️', 'Clear sky'), 1: ('🌤', 'Mainly clear'), 2: ('⛅', 'Partly cloudy'), 3: ('☁️', 'Overcast'),
    45: ('🌫', 'Fog'), 48: ('🌫', 'Freezing fog'),
    51: ('🌦', 'Light drizzle'), 53: ('🌦', 'Drizzle'), 55: ('🌧', 'Heavy drizzle'),
    56: ('🌧', 'Freezing drizzle'), 57: ('🌧', 'Heavy freezing drizzle'),
    61: ('🌦', 'Light rain'), 63: ('🌧', 'Rain'), 65: ('🌧', 'Heavy rain'),
    66: ('🌧', 'Freezing rain'), 67: ('🌧', 'Heavy freezing rain'),
    71: ('🌨', 'Light snow'), 73: ('🌨', 'Snow'), 75: ('❄️', 'Heavy snow'), 77: ('🌨', 'Snow grains'),
    80: ('🌦', 'Light showers'), 81: ('🌧', 'Showers'), 82: ('⛈', 'Violent showers'),
    85: ('🌨', 'Snow showers'), 86: ('❄️', 'Heavy snow showers'),
    95: ('⛈', 'Thunderstorm'), 96: ('⛈', 'Thunderstorm with hail'), 99: ('⛈', 'Severe thunderstorm with hail'),
}
COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']


def _describe(code):
    return WMO_CODES.get(code, ('🌡', 'Unknown conditions'))


def _compass(degrees):
    try:
        return COMPASS[round(float(degrees) / 45) % 8]
    except (TypeError, ValueError):
        return '?'


def get_weather(location: str) -> str:
    location = location.strip()[:120]
    if not location:
        return 'Tell me where, for example: /weather San Jose, CA  or  /weather London'
    try:
        place = places.geocode(location)
    except ValueError:
        return 'That place name is too short. Example: /weather Paris'
    if not place:
        return f'I couldn\'t find a place called: {location}\nTry adding a state or country, for example: /weather San Jose, CA'
    imperial = place.get('country_code') in ('US', 'LR', 'MM')
    temp_unit, wind_unit, rain_unit = ('°F', 'mph', 'in') if imperial else ('°C', 'km/h', 'mm')
    data = get(FORECAST_API, params={
        'latitude': place['latitude'], 'longitude': place['longitude'],
        'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,'
                   'wind_speed_10m,wind_direction_10m,precipitation',
        'hourly': 'temperature_2m,precipitation_probability,weather_code',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
        'timezone': 'auto', 'forecast_days': 3,
        'temperature_unit': 'fahrenheit' if imperial else 'celsius',
        'wind_speed_unit': 'mph' if imperial else 'kmh',
        'precipitation_unit': 'inch' if imperial else 'mm',
    }).json()
    current, hourly, daily = data.get('current') or {}, data.get('hourly') or {}, data.get('daily') or {}
    if not current:
        raise ValueError('Open-Meteo returned no current conditions')

    icon, text = _describe(current.get('weather_code'))
    lines = [
        f'Weather for {places.label(place)}',
        f'Local time: {str(current.get("time", "")).replace("T", " ")}',
        '',
        f'{icon} Now: {text}, {current.get("temperature_2m")}{temp_unit} '
        f'(feels like {current.get("apparent_temperature")}{temp_unit})',
        f'💧 Humidity {current.get("relative_humidity_2m")}%  |  '
        f'💨 Wind {current.get("wind_speed_10m")} {wind_unit} {_compass(current.get("wind_direction_10m"))}  |  '
        f'Precip {current.get("precipitation")} {rain_unit}',
    ]

    # Next 6 hours, starting at the current local hour.
    times = hourly.get('time') or []
    now_hour = str(current.get('time', ''))[:13]
    start = next((i for i, stamp in enumerate(times) if str(stamp)[:13] >= now_hour), None)
    if start is not None:
        lines += ['', 'Next hours:']
        for i in range(start, min(start + 6, len(times))):
            hour_icon, _ = _describe(hourly['weather_code'][i])
            rain = hourly['precipitation_probability'][i]
            lines.append(f'{str(times[i])[11:16]}  {hour_icon} {hourly["temperature_2m"][i]}{temp_unit}'
                         + (f'  ☔ {rain}%' if rain is not None else ''))

    days = daily.get('time') or []
    if days:
        lines += ['', '3-day forecast:']
        for i, day in enumerate(days[:3]):
            day_icon, day_text = _describe(daily['weather_code'][i])
            label = 'Today' if i == 0 else ('Tomorrow' if i == 1 else date.fromisoformat(str(day)).strftime('%A'))
            rain = daily['precipitation_probability_max'][i]
            lines.append(f'{label}: {day_icon} {day_text}, '
                         f'{daily["temperature_2m_min"][i]}–{daily["temperature_2m_max"][i]}{temp_unit}'
                         + (f', ☔ {rain}%' if rain is not None else ''))

    lines += ['', 'Source: Open-Meteo.com']
    return '\n'.join(lines)
