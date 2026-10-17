"""/quote, /cat and /so: small lookups from free public services (no API key). Ported from PromptetheusBot.
The cat fact is adapted from Jeremy Stevens's MIT-licensed random_cat_fact.py (2023); the Stack Overflow search
from the original Stack Overflow module."""
import html

from app.tools.web import get

STACK_API = 'https://api.stackexchange.com/2.3/search/advanced'


def random_quote(_args='') -> str:
    data = get('https://zenquotes.io/api/random', timeout=8).json()
    if not isinstance(data, list) or not data or not isinstance(data[0], dict) or not str(data[0].get('q', '')).strip():
        raise ValueError('The quote service returned no quote')
    author = str(data[0].get('a') or '').strip() or 'Unknown'
    return f'💬 “{data[0]["q"].strip()}”\n— {author}\n\nSource: ZenQuotes.io'


def cat_fact(_args='') -> str:
    data = get('https://catfact.ninja/fact', timeout=6).json()
    fact = data.get('fact') if isinstance(data, dict) else None
    if not isinstance(fact, str) or not fact.strip():
        raise ValueError('The cat fact service returned no fact')
    return f'🐱 {fact.strip()[:2000]}\n\nSource: catfact.ninja'


def stack_overflow(query: str) -> str:
    query = query.strip()[:160]
    if not query:
        return 'Tell me what to search for, for example: /so python read a file line by line'
    data = get(STACK_API, params={'site': 'stackoverflow', 'q': query, 'sort': 'relevance', 'order': 'desc',
                                  'pagesize': 3, 'filter': 'default'}).json()
    if not isinstance(data, dict) or data.get('error_id'):
        raise ValueError('The Stack Exchange API returned an error')
    items = data.get('items', [])
    if not items:
        return f'No Stack Overflow questions found for: {query}'
    lines = [f'🧑‍💻 Stack Overflow results for: {query}']
    for item in items:
        answered = ('✅ accepted answer' if item.get('accepted_answer_id') else
                    'answered' if item.get('is_answered') else 'unanswered')
        lines.append(f'\n• {html.unescape(str(item.get("title", "Untitled")))}\n  Score: {item.get("score", 0)} | '
                     f'{answered}\n  {item.get("link", "")}')
    return '\n'.join(lines)
