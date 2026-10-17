"""/news: headlines from public RSS feeds (no API key or account). Ported from PromptetheusBot.

Known categories use curated BBC / NPR / Ars Technica feeds; any other topic uses the public Google News RSS
search. Headlines are untrusted third-party text.
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

import httpx

from app.tools.web import Unavailable, get_limited

MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_HEADLINES = 6

CATEGORIES = {
    'top': ('Top stories', ['https://feeds.bbci.co.uk/news/rss.xml', 'https://feeds.npr.org/1001/rss.xml']),
    'world': ('World', ['https://feeds.bbci.co.uk/news/world/rss.xml', 'https://feeds.npr.org/1004/rss.xml']),
    'us': ('U.S.', ['https://feeds.npr.org/1003/rss.xml']),
    'politics': ('Politics', ['https://feeds.npr.org/1014/rss.xml']),
    'technology': ('Technology', ['https://feeds.bbci.co.uk/news/technology/rss.xml',
                                  'https://feeds.arstechnica.com/arstechnica/index']),
    'science': ('Science', ['https://feeds.bbci.co.uk/news/science_and_environment/rss.xml',
                            'https://feeds.npr.org/1007/rss.xml']),
    'business': ('Business', ['https://feeds.bbci.co.uk/news/business/rss.xml', 'https://feeds.npr.org/1006/rss.xml']),
    'health': ('Health', ['https://feeds.bbci.co.uk/news/health/rss.xml', 'https://feeds.npr.org/1128/rss.xml']),
    'entertainment': ('Entertainment', ['https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml']),
    'sports': ('Sports', ['https://feeds.bbci.co.uk/sport/rss.xml']),
}
ALIASES = {
    '': 'top', 'top': 'top', 'headlines': 'top', 'latest': 'top', 'general': 'top',
    'world': 'world', 'international': 'world', 'global': 'world',
    'us': 'us', 'u.s.': 'us', 'usa': 'us', 'national': 'us', 'america': 'us',
    'politics': 'politics', 'political': 'politics',
    'tech': 'technology', 'technology': 'technology',
    'science': 'science', 'environment': 'science',
    'business': 'business', 'economy': 'business', 'finance': 'business', 'money': 'business',
    'health': 'health', 'medicine': 'health',
    'entertainment': 'entertainment', 'arts': 'entertainment', 'movies': 'entertainment', 'music': 'entertainment',
    'sport': 'sports', 'sports': 'sports',
}
SOURCE_NAMES = {'feeds.bbci.co.uk': 'BBC', 'feeds.npr.org': 'NPR', 'feeds.arstechnica.com': 'Ars Technica'}


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _child_text(element, name):
    for child in element:
        if _local(child.tag) == name:
            return (child.text or '').strip()
    return ''


def _parse_date(text):
    if not text:
        return None
    try:
        stamp = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            stamp = datetime.fromisoformat(text.replace('Z', '+00:00'))
        except ValueError:
            return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _fetch(url, fallback_source):
    """[(published, title, source, link)] from an RSS or Atom feed."""
    root = ET.fromstring(get_limited(url, MAX_FEED_BYTES))
    items = []
    for entry in root.iter():
        if _local(entry.tag) not in ('item', 'entry'):
            continue
        title = re.sub(r'\s+', ' ', _child_text(entry, 'title'))
        link = _child_text(entry, 'link')
        if not link:  # Atom: <link href="..."/>
            link = next((child.get('href') for child in entry if _local(child.tag) == 'link' and child.get('href')), '')
        if not title or urlparse(link).scheme not in ('http', 'https'):
            continue
        source = _child_text(entry, 'source') or fallback_source
        if source != fallback_source and title.endswith(' - ' + source):
            title = title[:-len(' - ' + source)]  # Google News appends " - Source"
        published = _parse_date(_child_text(entry, 'pubDate') or _child_text(entry, 'published')
                                or _child_text(entry, 'updated'))
        items.append((published, title[:200], source[:60], link))
    return items


def _clean_link(link):
    """Drop RSS tracking parameters such as BBC's at_medium / at_campaign."""
    parts = urlparse(link)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith(('at_', 'utm_'))]
    return urlunparse(parts._replace(query=urlencode(query)))


def _age(published):
    if not published:
        return ''
    minutes = int((datetime.now(timezone.utc) - published).total_seconds() // 60)
    if minutes < 1:
        return 'just now'
    if minutes < 60:
        return f'{minutes}m ago'
    if minutes < 48 * 60:
        return f'{minutes // 60}h ago'
    return f'{minutes // 1440}d ago'


def _gather(feeds):
    """Fetch the feeds; return (items, failed feed count). Items are newest first within each feed, then
    alternate between feeds so one source can't fill the list."""
    per_feed, failures = [], 0
    for url, source in feeds:
        try:
            per_feed.append(_fetch(url, source))
        except (httpx.HTTPError, ET.ParseError, ValueError):
            failures += 1
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    for feed_items in per_feed:
        feed_items.sort(key=lambda item: item[0] or oldest, reverse=True)
    items = []
    for position in range(max((len(f) for f in per_feed), default=0)):
        items.extend(f[position] for f in per_feed if position < len(f))
    return items, failures


def get_news(topic: str = '') -> str:
    topic = re.sub(r'\s+', ' ', topic.strip())[:100]
    category = ALIASES.get(topic.lower())
    if category:
        label, urls = CATEGORIES[category]
        feeds = [(url, SOURCE_NAMES.get(urlparse(url).hostname, 'News')) for url in urls]
        heading = f'📰 {label} headlines'
    else:
        query = quote_plus(f'{topic} when:7d')
        feeds = [(f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en', 'Google News')]
        heading = f'📰 News about: {topic}'

    items, failures = _gather(feeds)
    if not items:
        if failures:
            raise Unavailable('the news feeds')
        return f'No recent headlines found for: {topic}'

    seen, lines = set(), [heading]
    for published, title, source, link in items:
        key = re.sub(r'\W+', '', title.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        meta = ' · '.join(part for part in (source, _age(published)) if part)
        lines.append(f'\n{len(seen)}. {title}\n{meta}\n{_clean_link(link)}')
        if len(seen) >= MAX_HEADLINES:
            break
    if not category:
        lines.append('\nCategories: top, world, us, politics, tech, science, business, health, entertainment, sports')
    return '\n'.join(lines)
