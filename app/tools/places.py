"""Find a place by name with the free Open-Meteo geocoder (no API key or account). Only the place name is sent.

Copied from PromptetheusBot's weather plugin (its "City, ST" handling); used by /time now and by /weather later.
"""
import unicodedata

import httpx

GEOCODE_API = 'https://geocoding-api.open-meteo.com/v1/search'
HEADERS = {'User-Agent': 'BEYOND/1.0 (personal local AI assistant; place lookup)'}

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia',
}


def _matches(place, qualifier):
    """True if a geocoding result matches a 'City, State/Country' qualifier."""
    qualifier = qualifier.strip().lower()
    if not qualifier:
        return True
    state = US_STATES.get(qualifier.upper())
    candidates = [str(place.get(key, '')).lower() for key in ('admin1', 'admin2', 'country', 'country_code')]
    if state and place.get('country_code') == 'US':
        return str(place.get('admin1', '')).lower() == state.lower()
    return qualifier in candidates or any(qualifier in value for value in candidates if len(qualifier) > 2)


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c)).strip()


def geocode(location):
    """The best match for 'City' or 'City, State/Country', as Open-Meteo's place dict, or None.
    Raises httpx.HTTPError when offline and ValueError for a too-short name."""
    name, _, qualifier = location.partition(',')
    name = name.strip()
    if len(name) < 2:
        raise ValueError('Location name is too short')
    params = {'name': name, 'count': 10, 'language': 'en', 'format': 'json'}
    qualifier_key = qualifier.strip().upper()
    if qualifier_key:
        # Common names (e.g. San Carlos) exist in many countries, so the right one may not be in the
        # top 10: search the US only for a US state, otherwise look through the top 100 matches.
        params['count'] = 100
        if qualifier_key in US_STATES or qualifier_key.title() in US_STATES.values() or qualifier_key in ('US', 'USA'):
            params['countryCode'] = 'US'
    response = httpx.get(GEOCODE_API, params=params, headers=HEADERS, timeout=10)
    response.raise_for_status()
    results = response.json().get('results') or []
    results = [place for place in results if isinstance(place, dict) and _matches(place, qualifier)]
    # Prefer a place actually named what the user typed (accents ignored: San Jose = San José) over
    # one that only lists it as an alternative name (e.g. "Úrsulo Galván" for San Carlos, Mexico).
    exact = [place for place in results if plain(place.get('name', '')) == plain(name)]
    return (exact or results or [None])[0]


def label(place):
    """'San Jose, California, United States' from a place dict."""
    parts = [place.get('name'), place.get('admin1'), place.get('country')]
    seen = []
    for part in parts:
        if part and part not in seen:
            seen.append(str(part))
    return ', '.join(seen)
