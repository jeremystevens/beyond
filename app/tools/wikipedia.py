# MIT License

# Copyright (c) 2023 - Jeremy Stevens

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""/wiki: a Wikipedia article's summary, from the public MediaWiki API (no API key or extra package).
Adapted from Jeremy Stevens's MIT-licensed wikipedia_search.py (2023), via PromptetheusBot."""
from app.tools.web import get

API = 'https://en.wikipedia.org/w/api.php'


def search_wikipedia(query: str) -> str:
    query = query.strip()[:160]
    if not query:
        return 'Tell me a topic, for example: /wiki Apollo 11'
    pages = get(API, params={
        'action': 'query', 'generator': 'search', 'gsrsearch': query,
        'gsrlimit': 1, 'prop': 'extracts|info', 'exintro': 1,
        'explaintext': 1, 'inprop': 'url', 'format': 'json',
        'redirects': 1,
    }).json().get('query', {}).get('pages', {})
    if not pages:
        return f'No Wikipedia article found for: {query}'
    page = next(iter(pages.values()))
    extract = (page.get('extract') or '').strip() or 'No introductory summary is available for this article.'
    return f'📚 {page.get("title", query)}\n\n{extract[:2600]}\n\nSource: {page.get("fullurl", "")}'.strip()
