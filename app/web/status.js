(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let refreshing = false, testing = false, diagnosing = false, managing = false, timer = null, stopped = false;
  const states = {ok:'Ready',error:'Problem',warning:'Review',skipped:'Skipped',disabled:'Off',off:'Unloaded',
    not_set:'Not configured',starting:'Preparing',stopping:'Unloading',external:'External'};
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const gib = n => (n / 1024 ** 3).toFixed(1) + ' GiB';
  const date = value => new Date(value).toLocaleString();
  const duration = n => n >= 60 ? Math.floor(n / 60) + 'm ' + Math.round(n % 60) + 's' : Math.round(n) + 's';
  async function api(path, post = false, timeoutMs = post ? 60000 : 12000) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(path, {method:typeof post === 'string' ? post : post ? 'POST' : 'GET', cache:'no-store', signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.summary || data.error || data.detail || 'The request could not be completed.');
      return data;
    } finally { clearTimeout(timeout); }
  }
  function item(name, detail, state) {
    const row = el('div', undefined, 'item'), copy = el('div');
    copy.append(el('p', name), el('p', detail, 'muted'));
    row.append(copy, el('span', states[state] || state, 'badge ' + state));
    return row;
  }
  function renderStatus(data) {
    const s = data.system;
    $('cpu').textContent = s.cpu_percent.toFixed(0) + '%';
    $('cpu-detail').textContent = (s.logical_cpus || 'Unknown') + ' logical processors';
    $('memory').textContent = s.memory_percent.toFixed(0) + '% used';
    const lowMemory = s.memory_warning ?? s.memory_available < 1024 ** 3;
    $('memory').classList.toggle('warning',lowMemory);
    $('memory-detail').classList.toggle('warning',lowMemory);
    $('memory-detail').textContent = (lowMemory ? 'Low memory · ' : '') + gib(s.memory_available) +
      ' free of ' + gib(s.memory_total) + (lowMemory ? '. Close unused apps or choose a smaller model.' : '');
    $('disk').textContent = gib(s.disk_free);
    $('disk-detail').textContent = 'Of ' + gib(s.disk_total) + ' on BEYOND’s drive';
    $('ai').textContent = states[data.ai.state] || data.ai.state;
    $('ai-detail').textContent = (data.ai.model || 'No model selected') + (data.ai.busy ? ' · In use' : '');
    $('updated').textContent = 'Updated ' + date(data.at) + ' · BEYOND ' + data.version + ' · Running ' + duration(s.app_uptime_seconds);
    $('services').replaceChildren(...data.services.map(service => item(service.name,
      (service.port ? service.host + ':' + service.port + ' · ' : '') + service.detail +
      (service.latency_ms !== undefined ? ' (' + service.latency_ms + ' ms)' : ''),service.state)));
  }
  function renderSpeed(data) {
    $('speeds').replaceChildren();
    for (const reply of data.items) {
      const row = el('tr');
      for (const [index, text] of [date(reply.at),reply.model,String(reply.tokens),duration(reply.seconds),reply.speed.toFixed(2) + ' t/s'].entries()) {
        row.append(el('td',text,index === 1 ? 'model' : ''));
      }
      $('speeds').append(row);
    }
    $('speed-empty').hidden = data.items.length > 0;
    $('averages').textContent = data.models.map(m => m.model + ': ' + m.average_speed.toFixed(2) + ' t/s average across ' + m.replies + ' replies').join(' · ');
    const svg = $('trend'); svg.replaceChildren(); svg.hidden = !data.items.length;
    const samples = [...data.items].reverse(), peak = Math.max(1,...samples.map(s => s.speed));
    const points = samples.map((s,i) => [samples.length === 1 ? 400 : 10 + i * 780 / (samples.length-1),110 - s.speed / peak * 100]);
    if (points.length > 1) {
      const line = document.createElementNS('http://www.w3.org/2000/svg','polyline');
      line.setAttribute('points',points.map(p => p.join(',')).join(' ')); svg.append(line);
    }
    points.forEach(([x,y],i) => {
      const dot = document.createElementNS('http://www.w3.org/2000/svg','circle');
      dot.setAttribute('cx',x); dot.setAttribute('cy',y); dot.setAttribute('r','3');
      const title = document.createElementNS('http://www.w3.org/2000/svg','title');
      title.textContent = samples[i].model + ' · ' + samples[i].speed + ' t/s · ' + date(samples[i].at);
      dot.append(title); svg.append(dot);
    });
    $('trend-caption').textContent = samples.length ? 'Oldest → newest · 0–' + peak.toFixed(1) + ' t/s · ' + samples.length + ' recent replies (models may differ)' : '';
  }
  function controls() {
    const busy = refreshing || testing || diagnosing || managing;
    for (const id of ['refresh','selftest','add-test-error','clear-test-errors']) $(id).disabled = busy;
    document.querySelectorAll('.diagnose-button,.report-button').forEach(button => { button.disabled = busy; });
  }
  function renderErrors(data) {
    $('errors').replaceChildren(...data.items.map(e => {
      const simulated = e.source === 'Diagnostic test';
      const row = item(e.source + ' · ' + date(e.created_at), e.summary, simulated ? 'warning' : 'error');
      if (simulated) row.querySelector('.badge').textContent = 'Test';
      const button = el('button','Diagnose','ghost diagnose-button');
      button.type = 'button';
      button.setAttribute('aria-label','Diagnose ' + e.source + ' error from ' + date(e.created_at));
      button.onclick = () => diagnose(e);
      const actions = el('div',undefined,'error-actions');
      const report = el('button','Report','ghost report-button');
      report.type='button';report.title='Preview and export a local error report';
      report.setAttribute('aria-label','Preview report for '+e.source+' error from '+date(e.created_at));
      report.onclick=()=>BeyondErrorReports.open(e.id,e.source);
      actions.append(row.lastChild,button,report); row.append(actions);
      return row;
    }));
    $('error-empty').hidden = data.items.length > 0;
    controls();
  }
  async function diagnose(entry) {
    if (refreshing || testing || diagnosing || managing) return;
    diagnosing = true; clearTimeout(timer); controls();
    const panel = $('diagnosis'); panel.hidden = false;
    $('diagnosis-title').textContent = 'Diagnosis · ' + entry.source + ' · ' + date(entry.created_at);
    $('diagnosis-note').textContent = 'Checking current health and asking the AI if it is ready. This may take up to 2 minutes…';
    $('diagnosis-answer').textContent = '';
    $('diagnosis-warning').hidden = true;
    $('diagnosis-evidence').replaceChildren();
    $('diagnosis-suggestions').replaceChildren();
    $('diagnosis-limit').textContent = '';
    panel.setAttribute('aria-busy','true');
    try {
      const result = await api('/api/status/errors/' + entry.id + '/diagnose',true,130000);
      $('diagnosis-note').textContent = (result.simulated ? 'SIMULATED ERROR · ' : '') +
        (result.mode === 'ai' ? 'AI-assisted' : 'Basic troubleshooting') + ' · ' + date(result.at) + '. ' + result.note;
      $('diagnosis-answer').textContent = result.explanation;
      $('diagnosis-warning').textContent = (result.warnings || []).join(' ');
      $('diagnosis-warning').hidden = !(result.warnings || []).length;
      $('diagnosis-evidence').replaceChildren(...result.evidence.map(text => el('li',text)));
      $('diagnosis-suggestions').replaceChildren(...result.suggestions.map(text => el('li',text)));
      $('diagnosis-limit').textContent = result.limitation;
    } catch (error) {
      $('diagnosis-note').textContent = error.name === 'AbortError' ?
        'The diagnosis took too long. Try again when the AI is idle.' : error.message || 'Diagnosis could not be completed.';
    } finally {
      panel.setAttribute('aria-busy','false'); diagnosing = false; controls(); schedule();
    }
  }
  async function manageTest(clear) {
    if (refreshing || testing || diagnosing || managing) return;
    managing = true; clearTimeout(timer); controls();
    try {
      renderErrors(await api('/api/status/errors/test',clear ? 'DELETE' : true));
      $('test-error-note').textContent = clear ? 'Test entries cleared. Real error history was kept.' :
        'Simulated timeout added. Press Diagnose beside its Test badge.';
      if (clear) $('diagnosis').hidden = true;
    } catch (error) { $('test-error-note').textContent = error.message || 'Could not update test errors.'; }
    finally { managing = false; controls(); schedule(); }
  }
  $('add-test-error').onclick = () => manageTest(false);
  $('clear-test-errors').onclick = () => manageTest(true);
  $('close-diagnosis').onclick = () => { $('diagnosis').hidden = true; };

  async function refresh() {
    if (refreshing || testing || diagnosing || managing || stopped || document.hidden) return;
    refreshing = true; controls();
    try {
      const results = await Promise.allSettled([api('/api/status'),api('/api/status/speed'),api('/api/status/errors')]);
      const renderers = [renderStatus,renderSpeed,renderErrors], failed = [];
      results.forEach((result,i) => {
        if (result.status === 'fulfilled') renderers[i](result.value);
        else failed.push(['Status','Speed history','Error history'][i]);
      });
      $('notice').hidden = !failed.length;
      $('notice').textContent = failed.join(', ') + ' could not be refreshed. Displayed readings may be old. Check the connection and try Refresh.';
    } finally { refreshing = false; controls(); schedule(); }
  }
  function schedule() {
    clearTimeout(timer);
    if (!stopped && !diagnosing && !managing && !testing && $('auto').checked && !document.hidden) timer = setTimeout(refresh,10000);
  }
  $('refresh').onclick = refresh;
  $('auto').onchange = schedule;
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); else clearTimeout(timer); });
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); });
  $('selftest').onclick = async () => {
    if (testing || refreshing || diagnosing || managing) return;
    testing = true; clearTimeout(timer); controls();
    $('test-summary').textContent = 'Checking…'; $('checks').replaceChildren();
    try {
      const result = await api('/api/status/selftest',true);
      $('test-summary').textContent = result.summary + ' · ' + date(result.at);
      $('checks').replaceChildren(...result.checks.map(c => item(c.name,c.detail,c.state)));
    } catch (error) { $('test-summary').textContent = error.message || 'The self-test could not be completed.'; }
    finally { testing = false; controls(); schedule(); }
  };
  refresh();
})();
