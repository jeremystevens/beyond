(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const cards = new Map();
  let view = null, working = false, refreshing = false, canAdd = false, disconnected = false, epoch = 0;

  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function bytes(size) {
    if (size === 0) return '0 bytes';
    const units = ['bytes', 'KiB', 'MiB', 'GiB', 'TiB'];
    const power = Math.min(4, Math.floor(Math.log(size) / Math.log(1024)));
    return (size / Math.pow(1024, power)).toLocaleString(undefined, { maximumFractionDigits: power ? 2 : 0 }) + ' ' + units[power];
  }
  function notice(text, bad = false) {
    const el = $('notice');
    el.hidden = !text; el.className = 'notice ' + (bad ? 'bad' : 'ok'); el.textContent = text;
  }
  async function api(url, body) {
    const r = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(20000),
      ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || (r.status === 422 ? 'Check the model settings and try again.' : 'The request could not be completed.'));
    return data;
  }

  function makeCard(model) {
    const el = node('article');
    const top = node('div', 'card-head'), name = node('h2', '', model.name), badge = node('span', 'badge');
    top.append(name, badge);
    const info = node('div'), size = node('p', 'spec'), location = node('p', 'muted location', model.location);
    info.append(size, location);
    const problem = node('p', 'muted'), actions = node('div', 'actions'), load = node('button', '', 'Load model');
    load.type = 'button'; load.onclick = () => act('/api/models/load', { id: model.id }, 'Loading ' + model.name + '…');
    actions.append(load);
    const details = node('details'), summary = node('summary', '', 'Model settings'), form = node('form');
    const fields = node('div', 'fields'), inputs = {};
    function number(key, label, min, max) {
      const row = node('label', '', label), input = node('input');
      input.type = 'number'; input.min = min; input.max = max; input.step = '1'; input.required = true;
      input.name = key; input.ariaLabel = label + ' for ' + model.name;
      row.append(input); fields.append(row); inputs[key] = input;
    }
    number('engine_threads', 'CPU threads', 1, 64);
    number('engine_context', 'Context size', 1024, 131072);
    const cacheLabel = node('label', '', 'Cache'), cache = node('select');
    cache.name = 'engine_cache'; cache.ariaLabel = 'Cache for ' + model.name;
    for (const [value, label] of [['f16', 'f16 · fastest'], ['q8_0', 'q8_0 · less memory'], ['q4_0', 'q4_0 · least memory']]) {
      const option = node('option', '', label); option.value = value; cache.append(option);
    }
    inputs.engine_cache = cache; cacheLabel.append(cache); fields.append(cacheLabel);
    const thinkingLabel = node('label', 'check'), thinking = node('input');
    thinking.type = 'checkbox'; thinking.name = 'engine_thinking';
    thinkingLabel.append(thinking, 'Let thinking models think first'); inputs.engine_thinking = thinking;
    const tip = node('p', 'muted', 'Thinking can be much slower on a CPU. Saving settings for the loaded model reloads it.');
    const foot = node('div', 'actions'), save = node('button', 'ghost', 'Save settings'), note = node('p', 'form-note');
    save.type = 'submit'; foot.append(save);
    form.append(fields, thinkingLabel, tip, foot, note);
    const card = { el, name, badge, size, location, problem, load, save, inputs, note, dirty: false, model };
    form.oninput = () => { card.dirty = true; note.textContent = 'Unsaved changes'; };
    form.onsubmit = event => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const changes = { engine_threads: Number(inputs.engine_threads.value), engine_context: Number(inputs.engine_context.value),
        engine_cache: cache.value, engine_thinking: thinking.checked };
      act('/api/models/profile', { id: model.id, changes }, 'Settings saved for ' + model.name + '.', () => {
        card.dirty = false; note.textContent = 'Saved';
      });
    };
    details.append(summary, form); el.append(top, info, problem, actions, details);
    return card;
  }

  function fillCard(card, model) {
    card.model = model;
    card.name.textContent = model.name; card.location.textContent = model.location;
    card.size.textContent = bytes(model.bytes) + (model.parts > 1 ? ' · ' + model.parts + ' parts' : '') + ' · ' + model.origin;
    card.problem.textContent = model.problem; card.problem.hidden = !model.problem;
    if (!card.dirty) for (const [key, input] of Object.entries(card.inputs)) {
      if (input.type === 'checkbox') input.checked = model.settings[key];
      else input.value = model.settings[key];
    }
    const selected = view.mode === 'builtin' && view.enabled && view.selected === model.id;
    const loaded = selected && view.active === model.id && view.engine.state === 'ok';
    const loading = selected && ['starting', 'stopping'].includes(view.engine.state);
    card.el.classList.toggle('loaded', loaded);
    let label = 'Available', kind = '';
    if (!model.available) { label = 'Missing file'; kind = 'bad'; }
    else if (loaded) { label = 'Loaded'; kind = 'ok'; }
    else if (loading) { label = 'Loading…'; kind = 'warn'; }
    else if (selected && view.engine.state === 'error') { label = 'Load failed'; kind = 'bad'; }
    else if (!view.enabled && view.selected === model.id) label = 'Unloaded';
    card.badge.textContent = label; card.badge.className = 'badge ' + kind;
    card.load.textContent = loaded ? 'Loaded' : loading ? 'Loading…' : selected && view.engine.state === 'error' ? 'Try loading again'
      : view.mode === 'server' ? 'Use built-in and load' : view.enabled && view.selected && view.selected !== model.id ? 'Switch model' : 'Load model';
    card.load.disabled = working || disconnected || view.busy || !model.available || !view.engine_configured || loaded || loading;
    card.save.disabled = working || disconnected || (view.busy && selected);
    for (const input of Object.values(card.inputs)) input.disabled = working;
  }

  function render(data) {
    view = data;
    if (data.can_add !== undefined) canAdd = data.can_add;
    $('folder').textContent = data.folder;
    $('count').textContent = '(' + data.models.length + ')';
    $('empty').hidden = data.models.length > 0;
    $('addForm').hidden = !canAdd; $('addLocal').hidden = canAdd;
    $('setupNote').hidden = data.engine_configured;
    $('busyNote').hidden = !data.busy;
    const state = data.engine.state;
    const selected = data.models.find(m => m.id === data.selected);
    const title = data.mode === 'server' ? 'Using an existing AI server'
      : state === 'ok' ? 'Ready to chat'
      : state === 'starting' ? 'Loading model…'
      : state === 'stopping' ? 'Unloading model…'
      : state === 'error' ? 'The model could not be loaded'
      : !data.enabled ? 'No model loaded' : 'Choose a model to get started';
    const message = data.mode === 'server' ? 'Load a model below to use BEYOND’s built-in engine, or manage your server in Settings.'
      : state === 'ok' ? (selected ? selected.name : data.engine.model)
      : state === 'starting' ? (selected ? selected.name + ' · ' : '') + 'This may take a few minutes. The page will update when it is ready.'
      : data.engine.message || '';
    if ($('engineTitle').textContent !== title) $('engineTitle').textContent = title;
    if ($('engineMessage').textContent !== message) $('engineMessage').textContent = message;
    $('engineDot').className = 'dot ' + (state === 'ok' && data.mode === 'builtin' ? 'ok' : state === 'error' ? 'bad' : 'warn');
    $('unload').hidden = data.mode !== 'builtin' || !data.enabled || !data.selected;
    $('unload').disabled = working || disconnected || data.busy;
    $('refresh').disabled = working;
    $('modelPath').disabled = working;
    for (const button of $('addForm').querySelectorAll('button')) button.disabled = working || disconnected;
    const ids = new Set(data.models.map(m => m.id));
    for (const [id, card] of cards) if (!ids.has(id)) { card.el.remove(); cards.delete(id); }
    for (const model of data.models) {
      let card = cards.get(model.id);
      if (!card) { card = makeCard(model); cards.set(model.id, card); $('models').append(card.el); }
      fillCard(card, model);
    }
  }

  async function act(url, body, success, onSuccess) {
    if (working) return;
    epoch += 1; working = true; if (view) render(view);
    try {
      const data = await api(url, body);
      if (onSuccess) onSuccess();
      disconnected = false; render(data); notice(success);
    } catch (error) {
      notice(error.name === 'TimeoutError' || error.name === 'TypeError'
        ? 'BEYOND did not respond. Refresh the list to check whether the change went through.' : error.message, true);
    } finally {
      working = false;
      if (view) render(view);
    }
  }

  async function refresh(manual = false) {
    if (working || refreshing || (!manual && document.hidden)) return;
    refreshing = true;
    const started = epoch;
    try {
      const data = await api('/api/models');
      if (!working && started === epoch) {
        const wasDisconnected = disconnected;
        disconnected = false; render(data);
        if (manual || wasDisconnected) notice(manual ? 'Model list refreshed.' : '');
      }
    } catch {
      if (started !== epoch || working) return;
      disconnected = true;
      notice('BEYOND is not responding. Check that the app is running, then refresh the list.', true);
      if (view) render(view);
    } finally { refreshing = false; }
  }
  $('refresh').onclick = () => refresh(true);
  $('unload').onclick = () => act('/api/models/unload', {}, 'Unloading the model. Its settings stay saved.');
  $('addForm').onsubmit = event => {
    event.preventDefault();
    if (!$('addForm').reportValidity()) return;
    act('/api/models/register', { path: $('modelPath').value.trim() }, 'Model added. Choose Load model when you are ready.', () => { $('modelPath').value = ''; });
  };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  refresh();
  setInterval(refresh, 3000);
})();
