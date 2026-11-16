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

  /* ---- theme: every tap flips what is showing (review 2026-11-14) ----
     It used to cycle auto -> light -> dark, so on a light system the first tap
     (auto -> light) changed nothing a reader could see. Now each tap shows the
     other palette, and stores "auto" whenever that is the system's own, so the
     page goes back to following the system without a third state to pass through. */
  if (!theme) return;
  if (!window.__theme || !window.__theme.usable) { theme.remove(); return; }

  var sysQuery = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
  function sysDark() { return !!(sysQuery && sysQuery.matches); }
  function showing(mode) { return mode === 'auto' ? (sysDark() ? 'dark' : 'light') : mode; }
  // The Persian page has a Persian shell (author 2026-11-16): its toolbar says so
  // with lang="fa", and the button keeps speaking Persian as it is relabelled.
  var LABELS = {
    en: { light: 'Colours: light. Switch to dark.',
          dark: 'Colours: dark. Switch to light.',
          auto: ' (Following the system.)' },
    fa: { light: 'رنگ‌ها: روشن. تغییر به تیره.',
          dark: 'رنگ‌ها: تیره. تغییر به روشن.',
          auto: ' (مطابق دستگاه)' }
  };
  var LABEL = LABELS[bar.getAttribute('lang')] || LABELS.en;

  function paint(mode) {
    var label = LABEL[showing(mode)] + (mode === 'auto' ? LABEL.auto : '');
    theme.setAttribute('data-mode', mode);
    theme.setAttribute('aria-label', label);
    theme.setAttribute('title', label);
  }

  theme.addEventListener('click', function () {
    var want = showing(window.__theme.get()) === 'dark' ? 'light' : 'dark';
    var next = ((want === 'dark') === sysDark()) ? 'auto' : want;
    window.__theme.set(next);
    paint(next);
  });
  paint(window.__theme.get());
})();

/* Remember the edition a reader opened (author 2026-11-13): the your-language button
   (lang-mine.js), the home page's "Read free in your language" button and the Books
   tab (sync_head.py) then lead straight back to it. Its × forgets it again. */
(function () {
  var m = location.pathname.match(/^\/sedaha\/read\/(?:([a-z-]+)\/)?(?:index\.html)?$/);
  if (!m) return;
  try {
    localStorage.setItem('sedaha-lang', m[1] || 'en');
    localStorage.setItem('sedaha-lang-url', '/sedaha/read/' + (m[1] ? m[1] + '/' : ''));
    localStorage.removeItem('sedaha-lang-offer');
  } catch (e) {}
})();
