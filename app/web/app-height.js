// Keep BEYOND's page exactly on the part of the screen you can see.
//
// On phones the on-screen keyboard (and the browser's own bars) cover part of the page. Some browsers, iPhones
// especially, don't shrink the page for the keyboard; they slide the view down instead, which pushed the header off
// the top so you had to scroll back to reach it. The page (body) is pinned in place by style.css; here its height is
// set to the visible area and its top to where the visible area starts, every time either changes. So the header
// and the message box always stay on screen and only the conversation scrolls.
(function () {
  const vv = window.visualViewport;
  const root = document.documentElement.style;
  function fit() {
    if (vv) {
      root.setProperty('--app-height', Math.round(vv.height) + 'px');
      root.setProperty('--view-top', Math.round(vv.offsetTop) + 'px');
    }
    if (window.scrollY || window.scrollX) window.scrollTo(0, 0);
  }
  if (vv) {
    vv.addEventListener('resize', fit);
    vv.addEventListener('scroll', fit);
  }
  window.addEventListener('resize', fit);
  window.addEventListener('scroll', fit);
  window.addEventListener('orientationchange', fit);
  // Backup in case a browser misses a resize: the keyboard opens and closes when you tap into or out of a text box,
  // so fit again shortly after that (keyboards take a moment to slide in).
  for (const type of ['focusin', 'focusout']) {
    document.addEventListener(type, () => { setTimeout(fit, 100); setTimeout(fit, 400); });
  }
  fit();
})();
