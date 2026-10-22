'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let state, busy = false, pendingPreset = false, polling;
  const gib = bytes => (bytes / 1073741824).toFixed(1);
  async function api(path, data) {
    const response = await fetch('/api/welcome' + path, data === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Could not complete this step. Please try again.');
    return value;
  }
  function message(text, error = false) {
    $('message').textContent = text;
    $('message').classList.toggle('error', error);
  }
  function controls() {
    $('apply').disabled = busy;
    $('presets').disabled = busy;
    $('test').disabled = busy || pendingPreset || !state?.configured;
    $('finish').disabled = busy || pendingPreset || !state?.tested;
    $('skip').disabled = busy;
  }
  function render(value) {
    state = value;
    if (!state.can_manage) {
      $('restricted').hidden = false;
      message('Setup is managed by the PC owner.');
      return;
    }
    for (const id of ['configuration', 'verification', 'extras']) $(id).hidden = false;
    $('hardware').replaceChildren();
    for (const text of [gib(state.hardware.total_ram) + ' GB installed RAM',
                        gib(state.hardware.available_ram) + ' GB available now',
                        state.hardware.cores + ' CPU threads']) {
      const span = document.createElement('span');
      span.className = 'fact'; span.textContent = text; $('hardware').append(span);
    }
    $('memory').hidden = state.hardware.available_ram >= 2147483648;
    $('missing').hidden = state.configured;
    const local = state.mode === 'builtin';
    $('presets').hidden = !local || !state.configured;
    $('external').hidden = local;
    $('connection').textContent = local ? 'CPU · Built-in AI' : 'Your existing AI server';
    $('model').textContent = state.configured ? state.model : 'No model configured yet';
    $('current').textContent = state.current.engine_threads + ' threads · ' +
      state.current.engine_context.toLocaleString() + ' context';
    controls();
  }
  async function refreshStatus() {
    if (document.hidden || busy || !state?.can_manage) return;
    try {
      const response = await fetch('/api/ai-status');
      if (!response.ok) return;
      const value = await response.json();
      $('aiState').textContent = ['ok', 'ready'].includes(value.state) ? 'Your AI is ready for a test.' :
        value.state === 'starting' ? 'Your model is loading. Give it a moment, then test.' :
        'Your AI is not ready yet. Check Models or Settings, then retry.';
    } catch (_) { $('aiState').textContent = 'Could not check AI status. Check your connection and retry.'; }
  }
  async function action(work) {
    busy = true; controls();
    try { await work(); }
    catch (error) { message(error.message, true); $('message').focus(); }
    finally { busy = false; controls(); refreshStatus(); }
  }
  document.querySelectorAll('input[name="preset"]').forEach(input => {
    input.addEventListener('change', () => {
      pendingPreset = true; controls();
      message('Use the selected preset before testing. Your current settings have not changed yet.');
    });
  });
  $('apply').addEventListener('click', () => action(async () => {
    const preset = document.querySelector('input[name="preset"]:checked').value;
    await api('/preset', {preset});
    pendingPreset = false;
    render(await api(''));
    $('reply').hidden = true;
    message(preset === 'keep' ? 'Current settings kept. You can test your AI below.' :
      'CPU preset saved. The built-in model may reload; wait for it to be ready, then test.');
  }));
  $('test').addEventListener('click', () => action(async () => {
    state.tested = false; controls(); $('reply').hidden = true;
    $('progress').textContent = 'Waiting for a short reply… up to 90 seconds.';
    message('Testing your AI. Keep this page open until the result arrives.');
    try {
      const result = await api('/test', {});
      $('reply').textContent = result.reply; $('reply').hidden = false;
      state.tested = true;
      message('Your AI replied. You’re ready to open chat.');
    } finally { $('progress').textContent = ''; }
  }));
  $('finish').addEventListener('click', () => action(async () => {
    await api('/finish', {skip: false}); location.assign('/');
  }));
  $('skip').addEventListener('click', () => action(async () => {
    await api('/finish', {skip: true}); location.assign('/');
  }));
  api('').then(value => {
    render(value);
    if (value.can_manage) {
      message(value.tested ? 'This configuration has already passed its AI test. You can open chat or test again.' :
        'Your setup choices are ready to review.');
      refreshStatus(); polling = setInterval(refreshStatus, 4000);
    }
  }).catch(error => message(error.message, true));
  window.addEventListener('pagehide', () => clearInterval(polling));
})();
