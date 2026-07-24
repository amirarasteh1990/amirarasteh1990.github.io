/* Back-to-top button for long pages. Self-gating: it appears only after the
   reader has scrolled a screenful or two, and stays clear of the mobile tab
   bar (its position is set in CSS). Include it anywhere; on short pages it
   simply never shows. */
(function () {
  'use strict';
  if (!('addEventListener' in window)) return;

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'to-top';
  btn.setAttribute('aria-label', 'Back to top');
  btn.setAttribute('title', 'Back to top');
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>';
  document.body.appendChild(btn);

  var shown = false;
  function onScroll() {
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    var show = y > 600;
    if (show !== shown) {
      shown = show;
      btn.classList.toggle('show', show);
    }
  }

  btn.addEventListener('click', function () {
    var reduce = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    // return focus to the top of the document for keyboard users
    var target = document.getElementById('main') || document.body;
    target.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: true });
  });

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();
