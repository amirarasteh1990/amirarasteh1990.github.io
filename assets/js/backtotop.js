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
  /* in Persian on the Persian page, whose shell is Persian (author 2026-11-16) */
  var label = document.documentElement.lang === 'fa' ? 'بازگشت به بالا' : 'Back to top';
  btn.setAttribute('aria-label', label);
  btn.setAttribute('title', label);
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>';
  document.body.appendChild(btn);

  /* Shown only while the reader scrolls back UP past the first screens (review
     2026-11-14): sitting over the text edge while someone reads down a phone, it
     covered words. Scrolling up is the moment a reader wants the top. */
  var shown = false, lastY = 0;
  function onScroll() {
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    var up = y < lastY - 2, down = y > lastY + 2;
    if (up || down) lastY = y;
    var show = y > 600 && (up || (shown && !down));
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
