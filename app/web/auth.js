// On every page: if the sign-in on this device ends (signed out in Settings, password changed, or it expired),
// go to the sign-in page instead of showing errors. The PC running BEYOND never needs to sign in.
(() => {
  'use strict';
  const original = window.fetch.bind(window);
  let leaving = false;
  window.fetch = async (...args) => {
    const response = await original(...args);
    if (response.status === 401 && !leaving) {
      const data = await response.clone().json().catch(() => null);
      if (data && data.sign_in) {
        leaving = true;
        location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search + location.hash);
      }
    }
    return response;
  };
})();
