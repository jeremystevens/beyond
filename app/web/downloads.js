// Model downloads on the Models page (Phase 35): recommended models, any GGUF model on Hugging Face, and the
// progress of each download with Pause, Resume, Cancel and Load now.
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let data = null, working = false, canDownload = false, browsed = null, timer = null;
  const finished = new Set(), accepted = new Set();
  const rows = new Map(), cards = new Map();   // rebuilt only when something besides the progress changes

  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function size(bytes) {
    return bytes >= 1024 ** 3 ? (bytes / 1024 ** 3).toFixed(1) + ' GB' : Math.round(bytes / 1024 ** 2) + ' MB';
  }
  function duration(seconds) {
    if (seconds < 60) return 'less than a minute';
    const minutes = Math.round(seconds / 60);
    return minutes < 60 ? `about ${minutes} min` : `about ${Math.floor(minutes / 60)} h ${minutes % 60} min`;
  }
  function say(text, bad = false) {
    const el = $('dlNotice');
    el.hidden = !text; el.className = 'notice ' + (bad ? 'bad' : 'ok'); el.textContent = text;
    if (text) $('dlBox').hidden = false;
  }
  async function api(url, body) {
    const r = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(30000),
      ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
    const answer = await r.json();
    if (!r.ok) throw new Error(answer.error || 'The request could not be completed.');
    return answer;
  }
  async function act(url, body, success) {
    if (working) return;
    working = true; render();
    try { show(await api(url, body)); if (success) say(success); }
    catch (error) { say(error.name === 'TimeoutError' ? 'BEYOND did not respond. Check the list in a moment.' : error.message, true); }
    finally { working = false; render(); }
  }
  function licence(item, onAccept, remember = '') {
    const box = node('div', 'licence');
    const link = node('a', '', item.licence); link.href = item.licence_url; link.target = '_blank'; link.rel = 'noopener';
    if (!item.accept) { box.append('Licence: ', link); return { box, accepted: () => true }; }
    const label = node('label', 'check'), tick = node('input');
    tick.type = 'checkbox'; tick.checked = accepted.has(remember);
    tick.onchange = () => { if (remember) tick.checked ? accepted.add(remember) : accepted.delete(remember); onAccept(); };
    label.append(tick, 'I have read and accept the ', link);
    box.append(label);
    return { box, accepted: () => tick.checked };
  }

  // ---------- downloads in progress ----------
  function jobRow(job) {
    const row = node('div', 'job'), head = node('div', 'card-head');
    const title = node('div'); title.append(node('h3', '', job.name), node('p', 'muted location', job.repo));
    const labels = { queued: ['Waiting', 'warn'], downloading: ['Downloading', 'warn'], verifying: ['Checking fingerprint', 'warn'],
      paused: ['Paused', ''], failed: ['Failed', 'bad'], done: ['Ready', 'ok'] };
    const [label, kind] = labels[job.state] || [job.state, ''];
    head.append(title, node('span', 'badge ' + kind, label));
    const bar = node('div', 'progress'), fill = node('span'), text = node('p', 'muted');
    bar.setAttribute('role', 'progressbar'); bar.ariaLabel = 'Download progress for ' + job.name;
    bar.append(fill);
    row.append(head, bar, text);
    row.progress = latest => {   // called every poll; the rest of the row only changes with the state
      const percent = latest.total ? Math.floor(latest.received / latest.total * 100) : 0;
      bar.ariaValueNow = percent; fill.style.width = percent + '%';
      let line = `${size(latest.received)} of ${size(latest.total)} (${percent}%)`;
      if (latest.state === 'downloading' && latest.speed) line += ` · ${size(latest.speed)}/s · ${duration(latest.remaining)} left`;
      if (latest.files.length > 1) line += ` · ${latest.files.length} parts`;
      text.textContent = line;
    };
    row.progress(job);
    if (job.error) row.append(node('p', job.state === 'failed' ? 'notice bad' : 'muted', job.error));
    const buttons = node('div', 'actions');
    const button = (label, url, success, ghost = true) => {
      const b = node('button', ghost ? 'ghost' : '', label); b.type = 'button';
      b.disabled = working || !canDownload; b.onclick = () => act(url, { id: job.id }, success); buttons.append(b);
    };
    if (job.state === 'done') {
      const load = node('button', '', 'Load now'); load.type = 'button'; load.disabled = working || !job.model_id;
      load.onclick = async () => {
        working = true; render();
        try {
          await api('/api/models/load', { id: job.model_id });
          say(`Loading ${job.name}. It's ready to chat when Your models shows it as Loaded.`);
          document.dispatchEvent(new Event('models:changed'));
        } catch (error) { say(error.message, true); }
        finally { working = false; render(); }
      };
      buttons.append(load);
    } else if (canDownload) {
      if (['downloading', 'queued'].includes(job.state)) button('Pause', '/api/downloads/pause', 'Paused. Resume continues where it stopped.');
      if (['paused', 'failed'].includes(job.state)) button('Resume', '/api/downloads/resume', 'Resuming ' + job.name + '.', false);
      button('Cancel', '/api/downloads/cancel', 'Cancelled. The unfinished file was deleted.');
    }
    if (buttons.children.length) row.append(buttons);
    return row;
  }

  // ---------- recommended models ----------
  function recommendedCard(item) {
    const el = node('article'), head = node('div', 'card-head');
    head.append(node('h2', '', item.name), node('span', 'badge', size(item.size)));
    const about = node('p', '', item.about);
    const spec = node('p', 'spec', `${item.file} · needs about ${size(item.size + 1024 ** 3)} of memory`);
    const job = data.jobs.find(j => j.id === item.job);
    const actions = node('div', 'actions'), go = node('button', '', 'Download');
    go.type = 'button';
    const terms = licence(item, () => { go.disabled = !ready(); }, item.key);
    const ready = () => canDownload && !working && terms.accepted();
    if (item.have) { go.textContent = 'In Your models'; go.disabled = true; }
    else if (job && job.state !== 'done') { go.textContent = 'In Downloads'; go.disabled = true; }
    else go.disabled = !ready();
    go.onclick = () => act('/api/downloads/recommended', { key: item.key, accept: terms.accepted() },
      `Downloading ${item.name}. You can keep using BEYOND meanwhile.`);
    actions.append(go);
    el.append(head, about, spec, terms.box);
    if (item.tight) el.append(node('p', 'muted', 'This may be too large for the memory in this PC.'));
    if (canDownload) el.append(actions);
    return el;
  }

  // ---------- any model on Hugging Face ----------
  function browseResult() {
    const box = $('browseResult');
    box.replaceChildren();
    if (!browsed) return;
    if (browsed.gated) {
      const p = node('p', 'notice'), link = node('a', '', 'its Hugging Face page');
      link.href = browsed.page; link.target = '_blank'; link.rel = 'noopener';
      p.append('This model needs you to sign in to Hugging Face and accept its terms, which BEYOND does not support. ' +
        'See ', link, ', or look for a community GGUF copy.');
      box.append(p); return;
    }
    if (!browsed.files.length) { box.append(node('p', 'muted', 'No downloadable .gguf model files were found in ' + browsed.repo + '.')); return; }
    const terms = licence(browsed, () => box.querySelectorAll('button').forEach(b => { b.disabled = working || !terms.accepted(); }),
      'repo:' + browsed.repo);
    box.append(terms.box);
    for (const file of browsed.files) {
      const row = node('div', 'file'), text = node('div');
      text.append(node('strong', '', file.name), node('div', 'muted',
        size(file.size) + (file.parts ? ` · ${file.parts} parts` : '')));
      const go = node('button', 'ghost', 'Download'); go.type = 'button'; go.disabled = working || !terms.accepted();
      go.onclick = () => act('/api/downloads/custom', { repo: browsed.repo, name: file.name, accept: terms.accepted() },
        `Downloading ${file.name}.`);
      row.append(text, go); box.append(row);
    }
  }

  function render() {
    if (!data) return;
    $('dlLocal').hidden = canDownload;
    $('browseBox').hidden = !canDownload;
    $('dlSpace').textContent = `Free space: ${size(data.free)}.`;
    $('dlBox').hidden = !data.jobs.length && $('dlNotice').hidden;
    $('dlClear').hidden = !canDownload || !data.jobs.some(j => j.state === 'done');
    $('dlClear').disabled = working;
    const common = [working, canDownload].join();
    keyed($('jobs'), rows, data.jobs, job => job.id,
      job => [common, job.state, job.error, job.model_id].join('|'), jobRow, (el, job) => el.progress(job));
    keyed($('recommended'), cards, data.recommended, item => item.key, item => {
      const job = data.jobs.find(j => j.id === item.job);
      return [common, item.have, job ? job.state : ''].join('|');
    }, recommendedCard);
  }

  // Keeps each element until its signature changes, so ticked boxes and half-pressed buttons survive a poll.
  function keyed(parent, store, items, key, signature, build, update) {
    const seen = new Set();
    let index = 0;
    for (const item of items) {
      const id = key(item), sig = signature(item);
      seen.add(id);
      let entry = store.get(id);
      if (!entry || entry.sig !== sig) {
        const el = build(item);
        if (entry) entry.el.replaceWith(el);
        entry = { el, sig }; store.set(id, entry);
      } else if (update) update(entry.el, item);
      // keeps the server's order, moving an element only when it's out of place (a move would drop focus)
      if (parent.children[index] !== entry.el) parent.insertBefore(entry.el, parent.children[index] || null);
      index += 1;
    }
    for (const [id, entry] of store) if (!seen.has(id)) { entry.el.remove(); store.delete(id); }
  }

  function show(answer) {
    data = answer;
    if (answer.can_download !== undefined) canDownload = answer.can_download;
    for (const job of answer.jobs) {
      if (job.state === 'done' && !finished.has(job.id)) {
        if (finished.size || timer) {   // finished while this page was open
          say(`${job.name} is downloaded and verified. Press Load now to use it.`);
          document.dispatchEvent(new Event('models:changed'));
        }
        finished.add(job.id);
      }
    }
    render();
    if (!timer) for (const job of answer.jobs) if (job.state === 'done') finished.add(job.id);
  }

  async function poll() {
    try { if (!working && !document.hidden) show(await api('/api/downloads')); }
    catch { /* the Models list already says when BEYOND isn't responding */ }
    const active = data && data.jobs.some(j => ['queued', 'downloading', 'verifying'].includes(j.state));
    timer = setTimeout(poll, active ? 1000 : 5000);
  }

  $('browseForm').onsubmit = async event => {
    event.preventDefault();
    if (working || !$('browseForm').reportValidity()) return;
    working = true; render();
    $('browseResult').replaceChildren(node('p', 'muted', 'Looking it up on Hugging Face…'));
    try { browsed = await api('/api/downloads/browse?repo=' + encodeURIComponent($('repo').value.trim())); }
    catch (error) { browsed = null; say(error.message, true); }
    finally { working = false; render(); browseResult(); }
  };
  $('dlClear').onclick = () => act('/api/downloads/clear', {}, '');
  poll();
})();
