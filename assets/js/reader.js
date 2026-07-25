/* Reading settings for the Opening pages.

   The opening is set in 114 scripts, and a size that suits EB Garamond is small
   for Devanagari and smaller still for Khmer. The book is also read on phones
   held at arm's length and on laptops at a desk. So the reader gets the three
   controls a printed book cannot offer: how big the type is, how wide the
   measure runs, and whether the page is light or dark.

   The choice is kept in localStorage and applies to all 114 openings, so it is
   made once and then forgotten. The controls carry no words: an A and a larger
   A, a measure, a sun or a moon -- the chrome around the text stays quiet, and
   nothing needs translating into a hundred languages.

   The theme control drives window.__theme, defined in every <head> by
   sync_head.py. If that is missing (an old browser, or a stylesheet the page
   cannot read), the theme button removes itself and the other two still work. */
(function () {
  var bar = document.querySelector('.reader-tools');
  if (!bar) return;

  var root = document.documentElement;
  var SIZES = [0.88, 1, 1.14, 1.3, 1.48];   // 1 is the page's authored size
  var SIZE_KEY = 'arasteh-read-size';
  var WIDE_KEY = 'arasteh-read-wide';

  function stored(key, fallback) {
    try { var v = localStorage.getItem(key); return v === null ? fallback : v; }
    catch (e) { return fallback; }
  }
  function keep(key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
  }

  var step = parseInt(stored(SIZE_KEY, '1'), 10);
  if (isNaN(step) || step < 0 || step >= SIZES.length) step = 1;
  var wide = stored(WIDE_KEY, '0') === '1';

  var smaller = bar.querySelector('.rt-smaller');
  var larger = bar.querySelector('.rt-larger');
  var width = bar.querySelector('.rt-width');
  var theme = bar.querySelector('.rt-theme');

  function applyType() {
    root.style.setProperty('--read-scale', String(SIZES[step]));
    root.style.setProperty('--read-measure', wide ? '46em' : '34em');
    if (smaller) smaller.disabled = step === 0;
    if (larger) larger.disabled = step === SIZES.length - 1;
    if (width) width.setAttribute('aria-pressed', String(wide));
  }

  function resize(by) {
    step = Math.min(SIZES.length - 1, Math.max(0, step + by));
    keep(SIZE_KEY, String(step));
    applyType();
  }

  if (smaller) smaller.addEventListener('click', function () { resize(-1); });
  if (larger) larger.addEventListener('click', function () { resize(1); });
  if (width) width.addEventListener('click', function () {
    wide = !wide;
    keep(WIDE_KEY, wide ? '1' : '0');
    applyType();
  });
  applyType();

  /* ---- theme: auto -> light -> dark -> auto ---- */
  if (!theme) return;
  if (!window.__theme || !window.__theme.usable) { theme.remove(); return; }

  var ORDER = ['auto', 'light', 'dark'];
  var LABEL = {
    auto: 'Colours: following the system. Switch to light.',
    light: 'Colours: light. Switch to dark.',
    dark: 'Colours: dark. Follow the system again.'
  };

  function paint(mode) {
    theme.setAttribute('data-mode', mode);
    theme.setAttribute('aria-label', LABEL[mode]);
    theme.setAttribute('title', LABEL[mode]);
  }

  theme.addEventListener('click', function () {
    var next = ORDER[(ORDER.indexOf(window.__theme.get()) + 1) % ORDER.length];
    window.__theme.set(next);
    paint(next);
  });
  paint(window.__theme.get());
})();
