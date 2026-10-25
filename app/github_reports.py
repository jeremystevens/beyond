"""Explicit public issue lookup and browser handoff; never holds tokens or creates issues itself."""
import hashlib
import re
import threading
import time
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app import error_reports

REPO = 'jeremystevens/beyond'
SEARCH = 'https://api.github.com/search/issues'
NEW_ISSUE = f'https://github.com/{REPO}/issues/new'
_cache = {}
_lock = threading.Lock()


class ReviewedReport(BaseModel):
    model_config = {'extra': 'forbid'}
    text: str = Field(min_length=20, max_length=20000)


def reference(category, text):
    # Only user-described problem/reproduction content contributes; timestamps, readings and IDs never do.
    sections = []
    for title in ('What happened', 'Steps to reproduce'):
        match = re.search(r'^'+re.escape(title)+r'\n-+\n(.*?)(?=\n\n|\Z)', text, re.M|re.S)
        if match:
            sections.append(' '.join(match.group(1).casefold().split()))
    normalized = category + '\n' + '\n'.join(sections)
    return 'BEYOND-report-' + hashlib.sha256(normalized.encode()).hexdigest()[:24]


def draft(category, text, key):
    # A legacy Markdown template accepts title/body prefill. The user signs in and submits on GitHub.
    body = text.rstrip() + '\n\nReport reference: ' + key + '\n'
    query = {'template':'app-error-report.md','title':'BEYOND: '+category,'body':body}
    url = NEW_ISSUE+'?'+urlencode(query)
    needs_paste = len(url) > 7500
    if needs_paste:
        query['body'] = 'Report reference: '+key+'\n\nPaste the reviewed report copied from BEYOND below.\n'
        url = NEW_ISSUE+'?'+urlencode(query)
    return url, needs_paste


def clean_matches(items, exact):
    matches = []
    for item in items:
        number = item.get('number')
        url = item.get('html_url','')
        if (type(number) is not int or number <= 0 or item.get('pull_request')
                or url != f'https://github.com/{REPO}/issues/{number}'):
            continue
        matches.append({'number':number,'url':url,'title':str(item.get('title',''))[:180],
                        'state':'closed' if item.get('state')=='closed' else 'open',
                        'match':'Same report reference' if exact else 'Similar category'})
    return matches[:5]


async def check(error_id, body):
    from app import diagnostics
    entry = next((e for e in diagnostics.errors(200) if e['id']==error_id),None)
    if entry is None:
        raise HTTPException(404,'This error is no longer in recent history. Refresh and choose another.')
    if entry['source']=='Diagnostic test':
        raise HTTPException(409,'Simulated test errors cannot be reported to GitHub. Copy or save them locally instead.')
    category = error_reports.SOURCES.get(entry['source'],('App operation',''))[0]
    key = reference(category,body.text)
    url, needs_paste = draft(category,body.text,key)
    base = {'reference':key,'draft_url':url,'needs_paste':needs_paste}
    if key in _cache and time.monotonic()-_cache[key][0]<60:
        return {**base,**_cache[key][1],'cached':True}
    if not _lock.acquire(blocking=False):
        raise HTTPException(409,'Another GitHub check is running. Wait a moment, then try again.')
    result = {'checked':False,'matches':[],'note':'GitHub could not be checked. Check existing issues manually before submitting.'}
    try:
        async with httpx.AsyncClient(timeout=8,follow_redirects=False,trust_env=False,
                                     headers={'Accept':'application/vnd.github+json','User-Agent':'BEYOND-error-reports'}) as client:
            exact_query = f'repo:{REPO} is:issue in:body "{key}"'
            response = await client.get(SEARCH,params={'q':exact_query,'per_page':5,'sort':'updated'})
            response.raise_for_status();data=response.json()
            if not isinstance(data.get('items'),list) or data.get('incomplete_results'):
                raise ValueError('Incomplete search')
            matches = clean_matches(data['items'],True)
            if not matches:
                response = await client.get(SEARCH,params={'q':f'repo:{REPO} is:issue in:title "BEYOND: {category}"',
                                                          'per_page':5,'sort':'updated'})
                response.raise_for_status();data=response.json()
                if not isinstance(data.get('items'),list) or data.get('incomplete_results'):
                    raise ValueError('Incomplete search')
                matches = clean_matches(data['items'],False)
            result = {'checked':True,'matches':matches,'note':
                'Possible matches only: matching text or category does not prove the same cause. Review open and closed issues.' if matches else
                'No matching reports found in this search. This does not prove the problem is new; search indexing may lag.'}
    except (httpx.HTTPError,ValueError,TypeError,AttributeError):
        pass
    finally:
        _lock.release()
    if len(_cache)>=50:
        _cache.pop(next(iter(_cache)))
    _cache[key]=(time.monotonic(),result)
    return {**base,**result,'cached':False}
