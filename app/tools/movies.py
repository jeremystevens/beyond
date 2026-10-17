"""/movie and /tv: film and TV information from free public sources (no API key or account). Ported from
PromptetheusBot.

Films: Wikidata (year, runtime, director, IMDb / Rotten Tomatoes / Metacritic scores)
plus Wikipedia (summary and billed cast from the infobox). TV shows: TVmaze.
If Wikidata is slow or down, films fall back to a Wikipedia-only answer.
All results are third-party data, not instructions.
"""
import html
import re
from datetime import datetime
from urllib.parse import quote, unquote

import httpx

from app.tools.web import Unavailable, get

WIKIDATA_SPARQL = 'https://query.wikidata.org/sparql'
WIKIPEDIA_API = 'https://en.wikipedia.org/w/api.php'
WIKIPEDIA_SUMMARY = 'https://en.wikipedia.org/api/rest_v1/page/summary/'
TVMAZE_SEARCH = 'https://api.tvmaze.com/search/shows'
SECONDS, HOURS = 'http://www.wikidata.org/entity/Q11574', 'http://www.wikidata.org/entity/Q25235'
SCORE_SOURCES = ('IMDb', 'Rotten Tomatoes', 'Metacritic')
MAX_CAST, MAX_SUMMARY = 6, 700


def _shorten(text, limit=MAX_SUMMARY):
    """Trim to the last full sentence within the limit."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    return cut[:end + 1] if end > limit // 2 else cut.rsplit(' ', 1)[0] + '…'


def _sparql(query):
    return get(WIKIDATA_SPARQL, timeout=15, params={'query': query, 'format': 'json'}).json()['results']['bindings']


def _escape(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


def _find_film(title, year):
    """Return (wikidata_uri, label, year, wikipedia_url) of the best-matching film, or None."""
    rows = _sparql('''SELECT ?film ?filmLabel ?num (MIN(YEAR(?date)) AS ?year) (SAMPLE(?article) AS ?wiki) WHERE {
      SERVICE wikibase:mwapi { bd:serviceParam wikibase:api "EntitySearch"; wikibase:endpoint "www.wikidata.org";
        mwapi:search "%s"; mwapi:language "en". ?film wikibase:apiOutputItem mwapi:item. ?num wikibase:apiOrdinal true. }
      ?film wdt:P31/wdt:P279* wd:Q11424 .
      OPTIONAL { ?film wdt:P577 ?date }
      OPTIONAL { ?article schema:about ?film ; schema:isPartOf <https://en.wikipedia.org/> }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    } GROUP BY ?film ?filmLabel ?num ORDER BY ?num LIMIT 15''' % _escape(title))
    films = [(r['film']['value'], r.get('filmLabel', {}).get('value', title),
              int(r['year']['value']) if 'year' in r else None, r.get('wiki', {}).get('value'))
             for r in rows]
    if year:
        films = [f for f in films if f[2] and abs(f[2] - year) <= 1] or []
    return films[0] if films else None


def _film_details(uri):
    entity = uri.rsplit('/', 1)[-1]
    rows = _sparql('''SELECT ?dirLabel ?amount ?unit ?score ?byLabel WHERE {
      OPTIONAL { wd:%(e)s wdt:P57 ?dir }
      OPTIONAL { wd:%(e)s p:P2047/psv:P2047 [ wikibase:quantityAmount ?amount; wikibase:quantityUnit ?unit ] }
      OPTIONAL { wd:%(e)s p:P444 ?s . ?s ps:P444 ?score . OPTIONAL { ?s pq:P447 ?by } }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    } LIMIT 100''' % {'e': entity})
    directors = list(dict.fromkeys(r['dirLabel']['value'] for r in rows if 'dirLabel' in r))
    runtime = None
    for r in rows:
        if 'amount' in r:
            amount = float(r['amount']['value'])
            unit = r.get('unit', {}).get('value')
            runtime = round(amount / 60 if unit == SECONDS else amount * 60 if unit == HOURS else amount)
            break
    scores = {}
    for r in rows:
        source, value = r.get('byLabel', {}).get('value'), r.get('score', {}).get('value', '')
        if source not in SCORE_SOURCES or source in scores:
            continue
        # Rotten Tomatoes lists both the Tomatometer (%) and an average (x/10); prefer the %.
        if source == 'Rotten Tomatoes' and not value.endswith('%'):
            if any(r2.get('byLabel', {}).get('value') == source and r2['score']['value'].endswith('%')
                   for r2 in rows if 'score' in r2):
                continue
        scores[source] = value.replace(',', '.')
    return directors, runtime, scores


def _article_title(url):
    return unquote(url.rsplit('/wiki/', 1)[-1]) if url else None


def _summary(article):
    data = get(WIKIPEDIA_SUMMARY + quote(article.replace(' ', '_'), safe=''), timeout=10).json()
    if data.get('type') == 'disambiguation':
        return '', ''
    return (data.get('extract') or '').strip(), data.get('content_urls', {}).get('desktop', {}).get('page', '')


def _starring(article):
    """Billed cast from the Wikipedia infobox 'starring' field, in order."""
    try:
        text = get(WIKIPEDIA_API, timeout=10, params={
            'action': 'query', 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main', 'rvsection': 0,
            'titles': article, 'format': 'json', 'formatversion': 2, 'redirects': 1,
        }).json()['query']['pages'][0]['revisions'][0]['slots']['main']['content']
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return []
    match = re.search(r'\|\s*starring\s*=(.*?)(?=\n\s*\|\s*[a-z_ ]+=|\n\}\})', text, re.S | re.I)
    if not match:
        return []
    block = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->', '', match.group(1), flags=re.S)
    block = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]', r'\1', block)  # [[Target|Name]] -> Name
    block = re.sub(r'\{\{\s*(?:plain\s*list|plainlist|unbulleted\s*list|ubl|flatlist|hlist)\s*\|?', '', block, flags=re.I)
    names = []
    for piece in re.split(r'\n\s*\*|\||<br\s*/?>|\n', block):
        name = re.sub(r'\{\{[^}]*\}\}|[{}\[\]*\']', '', piece).strip(' ,')
        if name and len(name) < 60 and name not in names:
            names.append(name)
    return names[:MAX_CAST]


def _wikipedia_only(title, year):
    """Fallback for films when Wikidata is unavailable: first Wikipedia search hit for the film."""
    search = f'{title} {year} film' if year else f'{title} film'
    hits = get(WIKIPEDIA_API, timeout=10, params={'action': 'query', 'list': 'search', 'srsearch': search,
                                                  'srlimit': 1, 'format': 'json'}).json().get('query', {}).get('search', [])
    if not hits:
        return None
    article = hits[0]['title']
    extract, url = _summary(article)
    if not extract or 'film' not in extract[:300].lower():
        return None
    lines = [f'🎬 {article}']
    cast = _starring(article)
    if cast:
        lines.append('Starring: ' + ', '.join(cast))
    lines += ['', _shorten(extract), '', '(Ratings unavailable right now.)', f'Source: Wikipedia — {url}']
    return '\n'.join(lines), re.sub(r'\s*\([^)]*\)$', '', article)  # "Dune (1984 film)" -> "Dune"


def _movie(title, year):
    try:
        film = _find_film(title, year)
    except (httpx.HTTPError, ValueError, KeyError):
        return _wikipedia_only(title, year)  # Wikidata slow or down
    if not film:
        return None
    uri, label, film_year, wiki_url = film
    try:
        directors, runtime, scores = _film_details(uri)
    except (httpx.HTTPError, ValueError, KeyError):
        directors, runtime, scores = [], None, {}
    article = _article_title(wiki_url)
    extract, page_url = _summary(article) if article else ('', '')
    lines = [f'🎬 {label}' + (f' ({film_year})' if film_year else '')]
    facts = []
    if directors:
        facts.append('Directed by ' + ', '.join(directors[:2]))
    if runtime:
        facts.append(f'{runtime} min')
    if facts:
        lines.append(' · '.join(facts))
    cast = _starring(article) if article else []
    if cast:
        lines.append('Starring: ' + ', '.join(cast))
    if scores:
        lines.append('⭐ ' + ' · '.join(f'{source} {scores[source]}' for source in SCORE_SOURCES if source in scores))
    if extract:
        lines += ['', _shorten(extract)]
    lines += ['', 'Sources: Wikidata, Wikipedia' + (f' — {page_url}' if page_url else '')]
    return '\n'.join(lines), label


def _tv(title, year):
    shows = [hit.get('show') or {} for hit in get(TVMAZE_SEARCH, timeout=10, params={'q': title}).json()
             if isinstance(hit, dict)]
    if year:
        shows = [s for s in shows if str(s.get('premiered') or '')[:4].isdigit()
                 and abs(int(str(s['premiered'])[:4]) - year) <= 1]
    if not shows:
        return None
    show = shows[0]
    cast = []
    try:
        people = get(f"https://api.tvmaze.com/shows/{int(show['id'])}/cast", timeout=10).json()
        cast = list(dict.fromkeys(c['person']['name'] for c in people
                                  if isinstance(c, dict) and c.get('person', {}).get('name')))[:MAX_CAST]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    start, end = str(show.get('premiered') or '')[:4], str(show.get('ended') or '')[:4]
    years = f'{start}–{end}' if start and end and end != start else (f'{start}–' if start and show.get('status') == 'Running' else start)
    channel = (show.get('network') or {}).get('name') or (show.get('webChannel') or {}).get('name')
    lines = [f"📺 {show.get('name', title)}" + (f' ({years})' if years else '')]
    facts = [part for part in (show.get('status'), channel, ', '.join(show.get('genres') or [])) if part]
    if facts:
        lines.append(' · '.join(facts))
    if cast:
        lines.append('Starring: ' + ', '.join(cast))
    rating = (show.get('rating') or {}).get('average')
    if rating:
        lines.append(f'⭐ TVmaze {rating}/10')
    summary = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', show.get('summary') or ''))).strip()
    if summary:
        lines += ['', _shorten(summary)]
    lines += ['', f"Source: TVmaze — {show.get('url', 'https://www.tvmaze.com')}"]
    return '\n'.join(lines), show.get('name', '')


def _normalize(title):
    title = re.sub(r'[^a-z0-9 ]', '', title.lower().replace('&', 'and'))
    return re.sub(r'^the ', '', re.sub(r'\s+', ' ', title).strip())


def _lookup(query, year, kind):
    """Return (text, failed_lookups). An exact title match wins over a fuzzy one,
    so '/movie Breaking Bad' finds the show rather than the spin-off film."""
    order = (_tv, _movie) if kind == 'tv' else (_movie, _tv)
    results, errors = [], 0
    for lookup in order:
        try:
            result = lookup(query, year)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            errors += 1
            continue
        if result:
            text, matched = result
            if _normalize(matched) == _normalize(query):
                return text, errors
            results.append(text)
    return (results[0] if results else None), errors


def get_movie(query: str, kind: str = 'movie') -> str:
    """kind='movie': films first, then TV. kind='tv': TV first, then films."""
    query = re.sub(r'\s+', ' ', query.strip())[:120]
    if not query:
        return f'Tell me a title, for example: /{kind} ' + ('Breaking Bad' if kind == 'tv' else 'Back to the Future')
    attempts = [(query, None)]
    # A trailing year narrows remakes ("Dune 1984"); titles like "Blade Runner 2049" still work
    # because the full title is tried again without a year if the year search finds nothing.
    match = re.match(r'^(.+?)\s*\(?((?:18|19|20)\d{2})\)?$', query)
    if match and 1880 <= int(match.group(2)) <= datetime.now().year + 3:
        attempts.insert(0, (match.group(1).strip(), int(match.group(2))))
    errors = total = 0
    for title, year in attempts:
        text, failed = _lookup(title, year, kind)
        errors, total = errors + failed, total + 2
        if text:
            return text
    if errors == total:
        raise Unavailable('the movie and TV services (Wikidata, Wikipedia, TVmaze)')
    return f'No movie or TV show found for: {query}\nTry the full title, or add a year, e.g. /movie Dune 1984'
