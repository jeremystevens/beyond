"""/web: search the public web with DuckDuckGo (the ddgs package; no API key). Ported from PromptetheusBot."""
from urllib.parse import urlparse

from app.tools.web import Unavailable


def search_web(query: str) -> str:
    query = query.strip()[:300]
    if not query:
        return 'Tell me what to search for, for example: /web Python 3.14 features'
    try:
        from ddgs import DDGS
    except ImportError:
        return 'Web search needs the ddgs package: .\\.venv\\Scripts\\python.exe -m pip install ddgs'
    try:
        results = DDGS(timeout=12).text(query, max_results=5)
    except Exception as exc:   # ddgs raises its own exception types for timeouts, rate limits and outages
        raise Unavailable('DuckDuckGo search') from exc
    lines = [f'🔎 Web results for: {query}']
    for item in results or []:
        url = str(item.get('href') or item.get('url') or '').strip()
        if urlparse(url).scheme not in ('https', 'http'):
            continue
        title = str(item.get('title') or 'Untitled').strip()[:180]
        snippet = str(item.get('body') or item.get('description') or '').strip()[:350]
        lines.append(f'{len(lines)}. {title}\n{snippet}\n{url}')
    return '\n\n'.join(lines) if len(lines) > 1 else f'No web results found for: {query}'
