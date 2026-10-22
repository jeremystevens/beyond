/* Existing configured users keep opening chat; fresh installs get the optional guide. */
'use strict';
fetch('/api/welcome').then(response => response.ok ? response.json() : null).then(state => {
  if (state?.can_manage && state.offer) location.replace('/welcome');
}).catch(() => {}); // Chat remains usable if the welcome check is temporarily unavailable.
