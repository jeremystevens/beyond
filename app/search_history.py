"""Bounded snapshots of lookup results, independent of chats; no AI or network work for recalling them."""
import calendar
import html
import json
import logging
import re
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from app import chats, memory, reminders

TOOLS = {'web': 'Web', 'wiki': 'Wikipedia', 'weather': 'Weather', 'news': 'News',
         'so': 'Stack Overflow', 'define': 'Dictionary', 'movie': 'Movies', 'tv': 'TV'}
PROVIDERS = {'web': 'https://duckduckgo.com', 'wiki': 'https://en.wikipedia.org',
             'weather': 'https://open-meteo.com', 'news': 'https://news.google.com',
             'so': 'https://stackoverflow.com', 'define': 'https://en.wiktionary.org',
             'movie': 'https://www.wikidata.org', 'tv': 'https://www.tvmaze.com'}
URL = re.compile(r'https?://[^\s<>"]+', re.I)
WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
MONTHS = '|'.join([calendar.month_name[i] for i in range(1,13)] + [calendar.month_abbr[i] for i in range(1,13)])
DATE_PHRASE = re.compile(r'\b(?:today|yesterday|(?:last|this)\s+(?:week|month)|(?:last\s+)?(?:' +
    '|'.join(WEEKDAYS) + r')|\d{4}-\d{2}-\d{2}|(?:' + MONTHS +
    r')\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)\b', re.I)
STOP = set('search searches searched searching lookup lookups history recent previous past show list find recall remind '
           'did done do was were what which web wiki weather news so define movie tv last on for about please hey '
           'again look looked up searchhistory important me my i we our the from that it this'.split())
HELP = ('Search history is separate from chats and starts with this update.\n'
        '/searchhistory shows recent lookups. Add a date, tool or words, for example:\n'
        '/searchhistory last Thursday\n/searchhistory web Oct 18\n/searchhistory python\n'
        'Or ask “What did I search for last Thursday?”\n'
        'Browse, filter or bulk-delete in Settings → Search history. Search again fetches fresh results.')


def initialize():
    with closing(chats.connect()) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS lookup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tool TEXT NOT NULL, query TEXT NOT NULL,
            origin TEXT NOT NULL CHECK(origin IN ('manual','automatic')),
            created_at TEXT NOT NULL, local_at TEXT NOT NULL, time_zone TEXT NOT NULL,
            status TEXT NOT NULL, summary TEXT NOT NULL, sources TEXT NOT NULL)""")
        db.execute('CREATE INDEX IF NOT EXISTS idx_lookup_history_time ON lookup_history(created_at,id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_lookup_history_tool_time ON lookup_history(tool,created_at,id)')


def zone():
    return ZoneInfo(reminders.local_zone())


def result_status(text, ok=None):
    text = text.strip()
    if ok is False or text.startswith('🌐') or re.search(r'^(?:The dictionary is busy|Web search needs)', text, re.I):
        return 'error'
    if re.search(r"^(?:No (?:web results|Wikipedia article|recent headlines|Stack Overflow questions|dictionary entry|English definitions|movie or TV)|I couldn't find a place)", text, re.I):
        return 'no_results'
    return 'success'


def record(*args, **kwargs):
    try:
        return _record(*args, **kwargs)
    except Exception:
        logging.exception('Could not prepare search history')
        return None


def _record(tool, query, result, origin='manual', ok=None, now=None):
    """Call only after an actual lookup, never for help text. Failure to save must not lose its answer."""
    if tool not in TOOLS:
        return None
    query = ' '.join(str(query).split())[:300]
    result = str(result or '').strip()
    if not query or not result or re.match(r'^(Tell me|Please send|That place name is too short)', result, re.I):
        return None
    moment = now or datetime.now(timezone.utc)
    tz = zone()
    links = []
    for raw in URL.findall(result[:12000]):
        url = html.unescape(raw).rstrip(".,;!)]}'’")
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        if parsed.scheme.lower() in ('http','https') and parsed.hostname and len(url) <= 2000 and url not in links:
            links.append(url)
        if len(links) == 8:
            break
    status = result_status(result, ok)
    if not links and status == 'success':
        links = [PROVIDERS[tool]]
    summary = URL.sub('', result)
    summary = re.sub(r'\n{3,}', '\n\n', summary).strip()
    if len(summary) > 1800:
        summary = summary[:1799].rstrip() + '…'
    try:
        with closing(chats.connect()) as db, db:
            return db.execute('INSERT INTO lookup_history(tool,query,origin,created_at,local_at,time_zone,status,summary,sources) '
                              'VALUES (?,?,?,?,?,?,?,?,?)',
                              (tool,query,origin,moment.astimezone(timezone.utc).isoformat(timespec='microseconds'),
                               moment.astimezone(tz).isoformat(timespec='seconds'),str(tz),status,summary,json.dumps(links))).lastrowid
    except Exception:
        logging.exception('Could not save search history')
        return None


def _public(row):
    item = dict(row)
    item['sources'] = json.loads(item['sources'])
    when = datetime.fromisoformat(item['local_at']).astimezone(ZoneInfo(item['time_zone']))
    item['when'] = when.strftime('%a, %b %d, %Y · %I:%M %p %Z').replace(' 0',' ')
    item['command'] = '/' + item['tool'] + ' ' + item['query']
    return item


def get(identifier):
    with closing(chats.connect()) as db, db:
        row = db.execute('SELECT * FROM lookup_history WHERE id=?',(identifier,)).fetchone()
    return _public(row) if row else None


def browse(query='', tool='', start='', end='', origin='', offset=0, limit=25):
    if tool and tool not in TOOLS:
        raise ValueError('Choose a listed search tool.')
    if origin not in ('','manual','automatic'):
        raise ValueError('Choose manual, automatic or all lookups.')
    tz = zone()
    clauses, args = [], []
    if tool:
        clauses.append('tool=?'); args.append(tool)
    if origin:
        clauses.append('origin=?'); args.append(origin)
    if start:
        first = date.fromisoformat(start)
        clauses.append('created_at>=?')
        args.append(datetime.combine(first,time.min,tz).astimezone(timezone.utc).isoformat(timespec='microseconds'))
    if end:
        last = date.fromisoformat(end)
        if start and last < first:
            raise ValueError('The end date must be on or after the start date.')
        clauses.append('created_at<?')
        args.append(datetime.combine(last+timedelta(days=1),time.min,tz).astimezone(timezone.utc).isoformat(timespec='microseconds'))
    # Literal words, parameterized SQL; no user-provided FTS expression or wildcard expansion.
    for word in query.strip().split()[:8]:
        escaped = word.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        clauses.append("(query LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\')")
        args.extend(['%'+escaped+'%']*2)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    with closing(chats.connect()) as db, db:
        total = db.execute('SELECT count(*) FROM lookup_history'+where,args).fetchone()[0]
        all_count = db.execute('SELECT count(*) FROM lookup_history').fetchone()[0]
        rows = db.execute('SELECT * FROM lookup_history'+where+' ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
                          [*args,min(max(limit,1),50),max(offset,0)]).fetchall()
    return {'items': [_public(row) for row in rows], 'total':total,'all_count':all_count,'offset':offset,
            'limit':limit,'time_zone':str(tz),'tools':TOOLS}


def delete(identifiers):
    ids = list(dict.fromkeys(identifiers))
    if not ids or len(ids)>100 or any(isinstance(i,bool) or not isinstance(i,int) or i<1 for i in ids):
        raise ValueError('Select 1–100 valid history entries.')
    with closing(chats.connect()) as db, db:
        return db.execute('DELETE FROM lookup_history WHERE id IN ('+','.join('?' for _ in ids)+')',ids).rowcount


def date_range(phrase, now=None):
    today = (now or datetime.now(zone())).astimezone(zone()).date()
    value = phrase.lower().strip()
    if value in ('today','yesterday'):
        day=today-timedelta(days=value=='yesterday')
        return day,day
    if value in ('last week','this week'):
        first=today-timedelta(days=today.weekday()+(7 if value=='last week' else 0))
        return first,first+timedelta(days=6)
    if value in ('last month','this month'):
        first=today.replace(day=1)
        if value=='last month': first=(first-timedelta(days=1)).replace(day=1)
        return first,first.replace(day=calendar.monthrange(first.year,first.month)[1])
    weekday=value.removeprefix('last ')
    if weekday in WEEKDAYS:
        days=(today.weekday()-WEEKDAYS.index(weekday))%7
        day=today-timedelta(days=days or (7 if value.startswith('last ') else 0))
        return day,day
    try:
        day=date.fromisoformat(value)
        return day,day
    except ValueError:
        pass
    match=re.fullmatch(r'([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?',value)
    if not match: raise ValueError('Use a date like Oct 18, 2026 or 2026-10-18.')
    months={calendar.month_name[i].lower():i for i in range(1,13)}
    months.update({calendar.month_abbr[i].lower():i for i in range(1,13)})
    month=months.get(match[1])
    if not month: raise ValueError('That month was not recognized.')
    year=int(match[3]) if match[3] else today.year
    day=date(year,month,int(match[2]))
    if not match[3] and day>today:
        day=date(year-1,month,int(match[2]))
    return day,day


def filters(text):
    text=re.sub(r'^so\s+(?=(?:what|which|show|remind)\b)', '', text, flags=re.I)
    for phrase,canonical in (('stack overflow','so'),('stackoverflow','so'),('wikipedia','wiki'),('dictionary','define')):
        text=re.sub(r'\b'+phrase+r'\b',canonical,text,flags=re.I)
    match=DATE_PHRASE.search(text)
    start=end=''
    if match:
        first,last=date_range(match.group())
        start,end=first.isoformat(),last.isoformat()
        text=text[:match.start()]+' '+text[match.end():]
    selected=''
    for name in TOOLS:
        if re.search(r'(?<!\w)/?'+name+r'(?!\w)',text,re.I):
            selected=name
            text=re.sub(r'(?<!\w)/?'+name+r'(?!\w)',' ',text,flags=re.I)
            break
    query=' '.join(word for word in memory.keywords(text) if word not in STOP)
    return {'query':query,'tool':selected,'start':start,'end':end}


def recall_request(text):
    """Only explicit personal lookup-history questions; do not hijack a new request to search the web."""
    if len(text)>500: return None
    past = re.search(r'\b(?:search|lookup) history\b|\bmy (?:recent |previous |past |last )?(?:searches|lookups)\b',text,re.I)
    question = (re.search(r'\b(?:what|which|show|list|remind|recall)\b',text,re.I)
                and re.search(r'\b(?:search(?:es|ed)?|lookups?|look(?:ed)?\s+up)\b',text,re.I)
                and re.search(r'\b(?:i|my|me|we|our)\b',text,re.I)
                and re.search(r'\b(?:did|was|were|searched|last|previous|yesterday)\b',text,re.I))
    return text if past or question else None
