(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const selected = new Set();
  let data = null, busy = false, offset = 0;
  const limit = 25;
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function message(text, bad = false) {
    $('notice').hidden = !text; $('notice').className = 'notice' + (bad ? ' bad' : ''); $('notice').textContent = text;
  }
  function controls() {
    for (const node of $('filters').querySelectorAll('input, select, button')) node.disabled = busy;
    $('selectAll').disabled = busy || !data?.items.length;
    $('selectAll').checked = !!data?.items.length && selected.size === data.items.length;
    $('selectAll').indeterminate = selected.size > 0 && selected.size < (data?.items.length || 0);
    $('delete').disabled = busy || !selected.size;
    $('delete').textContent = selected.size ? 'Delete selected (' + selected.size + ')' : 'Delete selected';
    $('previous').disabled = busy || !offset;
    $('next').disabled = busy || !data || offset + limit >= data.total;
    for (const node of $('records').querySelectorAll('button,input')) node.disabled = busy;
    $('records').setAttribute('aria-busy', String(busy));
  }
  async function api(url, body) {
    const response = await fetch(url, { cache: 'no-store',
      ...(body === undefined ? {} : { method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body) }) });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'The request could not be completed. Refresh and try again.');
    return value;
  }
  function params() {
    const p = new URLSearchParams({ offset:String(offset),limit:String(limit) });
    for (const key of ['query','tool','start','end','origin']) if ($(key).value) p.set(key,$(key).value);
    return p;
  }
  function render() {
    selected.clear(); $('records').replaceChildren();
    if ($('tool').options.length === 1) for (const [key,name] of Object.entries(data.tools)) {
      const option = el('option','',name); option.value = key; $('tool').append(option);
    }
    $('zone').textContent = 'Date filters use the PC’s timezone: ' + data.time_zone + '. Each record shows the timezone used when it ran.';
    $('count').textContent = data.total + ' matching · ' + data.all_count + ' saved';
    $('page').textContent = data.total ? (offset + 1) + '–' + (offset + data.items.length) + ' of ' + data.total : '0 results';
    $('empty').hidden = data.items.length > 0;
    for (const item of data.items) {
      const article = el('article'), check = el('input','record-check'), copy = el('div','record-copy');
      check.type = 'checkbox'; check.ariaLabel = 'Select ' + item.command + ' from ' + item.when;
      check.onchange = () => { if (check.checked) selected.add(item.id); else selected.delete(item.id); controls(); };
      const when = el('p','muted',item.when + ' · ' + item.time_zone);
      const command = el('p','command',item.command);
      const tags = el('div','actions');
      tags.append(el('span','badge',item.origin === 'automatic' ? 'Automatic lookup' : 'Manual search'),
        el('span','badge',item.status.replaceAll('_',' ')));
      const details = el('details'), summary = el('summary','','Saved result and sources');
      details.append(summary, el('p','snapshot',item.summary));
      const sources = el('ul','sources');
      for (const url of item.sources) {
        try {
          const parsed = new URL(url);
          if (!['https:','http:'].includes(parsed.protocol)) continue;
          const row = el('li'), link = el('a','',url);
          link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
          row.append(link); sources.append(row);
        } catch {}
      }
      details.append(sources);
      const again = el('button','ghost','Search again');
      again.type = 'button'; again.onclick = () => repeat(item);
      copy.append(when,command,tags,details,again); article.append(check,copy); $('records').append(article);
    }
    controls();
  }
  async function load() {
    data = await api('/api/search-history?' + params());
    // A simultaneous deletion on another device can empty the last page.
    if (offset && !data.items.length && data.total) {
      offset = Math.floor((data.total-1)/limit)*limit;
      data = await api('/api/search-history?' + params());
    }
    render();
  }
  async function refresh(reset = false) {
    if (busy) return;
    if (reset) offset = 0;
    busy = true; controls();
    try { await load(); message(''); }
    catch (error) { message(error.message || 'BEYOND is not responding.',true); }
    finally { busy = false; controls(); }
  }
  async function repeat(item) {
    if (busy) return;
    busy = true; controls(); message('Searching again for “' + item.query + '”…');
    try {
      const result = await api('/api/search-history/' + item.id + '/repeat', {});
      location.href = '/#chat=' + result.chat_id;
    } catch (error) {
      message(error.message || 'BEYOND did not respond. Check recent history before retrying.',true);
      busy = false; controls();
    }
  }
  $('filters').onsubmit = event => { event.preventDefault(); refresh(true); };
  $('reset').onclick = () => { $('filters').reset(); refresh(true); };
  $('previous').onclick = () => { offset = Math.max(0,offset-limit); refresh(); };
  $('next').onclick = () => { offset += limit; refresh(); };
  $('selectAll').onchange = () => {
    for (const item of data.items) if ($('selectAll').checked) selected.add(item.id); else selected.delete(item.id);
    for (const check of $('records').querySelectorAll('input[type=checkbox]')) check.checked = $('selectAll').checked;
    controls();
  };
  $('delete').onclick = async () => {
    if (busy || !selected.size) return;
    const ids = [...selected];
    if (!confirm('Delete these ' + ids.length + ' saved search records? This cannot be undone. Your chats will stay saved.')) return;
    busy = true; controls();
    try {
      const result = await api('/api/search-history/delete',{ids});
      offset = 0; await load();
      message('Deleted ' + result.deleted + ' search record' + (result.deleted === 1 ? '.' : 's.'));
    } catch (error) { message(error.message || 'BEYOND is not responding.',true); }
    finally { busy = false; controls(); }
  };
  refresh();
})();
