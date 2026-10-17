"""/define: an English dictionary via Wiktionary's free public APIs (no API key or account). Ported from
PromptetheusBot.

Definitions and examples come from the Wiktionary REST definition endpoint; pronunciation (IPA) is read from the
entry's English section. Content is CC BY-SA licensed, so every reply links back to the Wiktionary page. If
Wiktionary fails (timeout, rate limit, outage) or has no entry, the Datamuse API is used as a backup (definitions
and pronunciation, no examples).
"""
import html
import re
from urllib.parse import quote

import httpx

from app.tools.web import HEADERS, Unavailable, get

DEFINITION_API = 'https://en.wiktionary.org/api/rest_v1/page/definition/'
WIKI_API = 'https://en.wiktionary.org/w/api.php'
WORD_RE = re.compile(r"^[A-Za-z][A-Za-z' .-]{0,59}$")
SKIP_PARTS = {'Symbol', 'Letter', 'Number', 'Han character'}
ACCENTS = {'UK': 'UK', 'RP': 'UK', 'GA': 'US', 'US': 'US', 'GenAm': 'US', 'AU': 'AU', 'CA': 'CA'}
MAX_PARTS, MAX_DEFINITIONS = 3, 2
DATAMUSE_API = 'https://api.datamuse.com/words'
DATAMUSE_PARTS = {'n': 'Noun', 'v': 'Verb', 'adj': 'Adjective', 'adv': 'Adverb', 'u': 'Other'}


def _clean(fragment):
    fragment = re.sub(r'<ol\b.*?</ol>', '', fragment or '', flags=re.S)  # drop nested sub-senses
    text = html.unescape(re.sub(r'<[^>]+>', '', fragment))
    return re.sub(r'\s+', ' ', text).strip()


def _title(word):
    return quote(word.replace(' ', '_'), safe='')


def _definitions(word):
    """Try the word as typed, then lowercase, then Title Case (Wiktionary titles are case-sensitive)."""
    for candidate in dict.fromkeys([word, word.lower(), word.title()]):
        # Uncached pages can take Wiktionary several seconds to render the first time.
        response = httpx.get(DEFINITION_API + _title(candidate), headers=HEADERS, timeout=15, follow_redirects=True)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        english = [part for part in response.json().get('en', []) if part.get('language') == 'English']
        if english:
            return candidate, english
    return None, []


def _pronunciation(title):
    try:
        text = get(WIKI_API, timeout=8, params={
            'action': 'query', 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main',
            'titles': title, 'format': 'json', 'formatversion': 2,
        }).json()['query']['pages'][0]['revisions'][0]['slots']['main']['content']
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return ''
    english = re.split(r'(?:^|\n)==English==\n', text, maxsplit=1)
    section = re.split(r'\n==[^=]', english[1], maxsplit=1)[0] if len(english) > 1 else ''
    found = {}  # IPA -> accent labels, in page order
    for template in re.findall(r'\{\{IPA\|en\|([^}]*)\}\}', section):
        params = template.split('|')
        ipa = next((p for p in params if p.startswith('/') and p.endswith('/')), None)
        if not ipa:
            continue
        labels = found.setdefault(ipa, [])
        for param in params:
            if param.startswith('a='):
                for accent in param[2:].split(','):
                    label = ACCENTS.get(accent.strip())
                    if label and label not in labels:
                        labels.append(label)
    # Prefer US and UK pronunciations; show at most two.
    ranked = sorted(found.items(), key=lambda item: 0 if {'US', 'UK'} & set(item[1]) else 1)[:2]
    return ' · '.join(f"{'/'.join(labels)} {ipa}".strip() for ipa, labels in ranked)


def _from_datamuse(word):
    """Backup: Datamuse (free, no key; Wiktionary/WordNet definitions). No examples. None if unavailable."""
    try:
        results = get(DATAMUSE_API, timeout=8, params={'sp': word, 'md': 'dpr', 'ipa': 1, 'max': 1}).json()
    except (httpx.HTTPError, ValueError):
        return None
    entry = results[0] if isinstance(results, list) and results and isinstance(results[0], dict) else None
    # 'sp' can return a close spelling; only accept the exact word.
    if not entry or str(entry.get('word', '')).lower() != word.lower() or not entry.get('defs'):
        return None
    lines = [f'📖 {word}']
    ipa = next((tag[9:] for tag in entry.get('tags', []) if tag.startswith('ipa_pron:')), '')
    if ipa:
        lines.append(f'🗣 /{ipa}/')
    grouped = {}
    for item in entry['defs']:
        code, _, definition = str(item).partition('\t')
        name = DATAMUSE_PARTS.get(code, 'Meaning')
        if name not in grouped and len(grouped) >= MAX_PARTS:
            continue
        senses = grouped.setdefault(name, [])
        if len(senses) < MAX_DEFINITIONS and definition.strip():
            senses.append(definition.strip()[:400])
    for name, senses in grouped.items():
        lines += ['', name] + [f'{number}. {definition}' for number, definition in enumerate(senses, 1)]
    lines += ['', 'Source: Datamuse (backup dictionary)']
    return '\n'.join(lines)


def define_word(word: str) -> str:
    word = re.sub(r'\s+', ' ', word.strip().strip('"\'“”‘’?!.,'))
    if not word:
        return 'Tell me a word, for example: /define serendipity'
    if not WORD_RE.match(word) or len(word.split()) > 4:
        return 'Please send a single English word or short phrase, for example: /define serendipity'
    primary_error = None
    try:
        title, parts = _definitions(word)
    except (httpx.HTTPError, ValueError) as exc:  # timeout, rate limit (429), outage, bad JSON
        title, parts, primary_error = None, [], exc
    if not parts:
        fallback = _from_datamuse(word)
        if fallback:
            return fallback
        if primary_error is not None:
            response = getattr(primary_error, 'response', None)
            if response is not None and response.status_code == 429:
                return 'The dictionary is busy right now. Please try again in a minute.'
            raise Unavailable('the dictionary (Wiktionary and Datamuse)') from primary_error
        return (f'No dictionary entry found for: {word}\nCheck the spelling, or try the base form (e.g. "run" '
                'instead of "running").')

    lines = [f'📖 {title}']
    pronunciation = _pronunciation(title)
    if pronunciation:
        lines.append(f'🗣 {pronunciation}')
    # Words with several etymologies repeat a part of speech; group them under one heading.
    grouped, seen_definitions, seen_examples = {}, set(), set()
    for part in parts:
        name = part.get('partOfSpeech') or 'Meaning'
        if name in SKIP_PARTS or (name not in grouped and len(grouped) >= MAX_PARTS):
            continue
        senses = grouped.setdefault(name, [])
        candidates = []
        for sense in part.get('definitions', [])[:12]:
            examples = sense.get('parsedExamples') or [{'example': e} for e in sense.get('examples') or []]
            candidates.append([_clean(sense.get('definition')),
                               _clean(examples[0].get('example')) if examples else ''])
        # A parent sense can include its sub-senses' text; trim that so they aren't repeated.
        for i, current in enumerate(candidates):
            for later, _ in candidates[i + 1:]:
                if later and later != current[0] and later in current[0]:
                    current[0] = current[0].replace(later, '').strip()
        for definition, example in candidates:
            if len(senses) >= MAX_DEFINITIONS:
                break
            if not definition or definition in seen_definitions:
                continue
            seen_definitions.add(definition)
            if example in seen_examples or len(example.split()) < 3:  # skip repeats and stubs like "tomato:"
                example = ''
            seen_examples.add(example)
            senses.append((definition, example))
        if not senses:
            del grouped[name]
    if not grouped:
        return f'No English definitions found for: {word}'
    for name, senses in grouped.items():
        lines += ['', name]
        for number, (definition, example) in enumerate(senses, 1):
            lines.append(f'{number}. {definition[:400]}')
            if example:
                lines.append(f'   e.g. “{example[:250]}”')
    lines += ['', f'Source: Wiktionary (CC BY-SA) — https://en.wiktionary.org/wiki/{_title(title)}']
    return '\n'.join(lines)
