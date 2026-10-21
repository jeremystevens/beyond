// The sign-in page other devices see (Phase 38). The PC running BEYOND never needs it.
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const next = new URLSearchParams(location.search).get('next') || '/';
  const target = next.startsWith('/') && !next.startsWith('//') && !next.includes('\\') ? next : '/';

  const admin = new URLSearchParams(location.search).get('admin') === '1';
  const otherMode = new URLSearchParams({ next: target, ...(admin ? {} : { admin: '1' }) });
  $('switchMode').href = '/login?' + otherMode;
  if (admin) {   // the administrator sign-in: lets this device change settings like the PC running BEYOND
    document.title = 'Administrator sign-in · BEYOND';
    $('title').textContent = 'Administrator sign-in';
    $('intro').textContent = "Enter the administrator password to change BEYOND's settings from this device.";
    $('switchMode').textContent = 'Use the normal sign-in';
    $('remember').parentElement.lastChild.textContent = 'Keep me signed in on this device (up to 7 days)';
  }

  function problem(text) { $('error').hidden = !text; $('error').textContent = text; }

  fetch('/api/auth/state', { cache: 'no-store' }).then(r => r.json()).then(state => {
    if (admin ? state.admin : state.signed_in) { location.replace(target); return; }
    const ready = admin ? state.admin_set : state.password_set;
    $('noPassword').hidden = ready;
    if (admin) $('noPassword').textContent = 'No administrator password is set yet. Set one on the PC running BEYOND, in Settings → Sign-in.';
    $('submit').disabled = !ready;
    $('switchMode').parentElement.hidden = !admin && !state.admin_set;
    if (state.secure_url) {
      $('insecure').hidden = false;
      $('secureLink').href = state.secure_url + '?next=' + encodeURIComponent(target);
    }
  }).catch(() => problem('BEYOND is not responding. Check that it is running on your PC.'));

  $('form').onsubmit = async event => {
    event.preventDefault();
    const password = $('password').value;
    if (!password) { problem('Enter the password.'); $('password').focus(); return; }
    $('submit').disabled = true; problem('');
    try {
      const r = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, remember: $('remember').checked, admin }) });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Signing in did not work.');
      location.replace(target);
    } catch (error) {
      problem(error.message === 'Failed to fetch' ? 'BEYOND is not responding. Check that it is running on your PC.' : error.message);
      $('password').select();
      $('submit').disabled = false;
    }
  };
})();
