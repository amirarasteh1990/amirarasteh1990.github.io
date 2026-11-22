/* Service worker for arasteh.art.

   The point is one thing only: a reader who has opened the book should still be
   able to read it when the connection goes. Editions in Iran and Afghanistan are
   read on connections that come and go, so an opening already visited must not
   vanish with the signal.

   Pages are network-first, so a deploy is never hidden behind a stale copy; the
   cached page is used only when the network fails. Same-origin assets (the
   stylesheet, the fonts, the paintings) are served from the cache and refreshed
   in the background. Nothing cross-origin is touched, so the book files on the
   GitHub release always come from the network. */

/* Bump this whenever a deploy changes the stylesheet or a script. Pages are
   network-first so they always arrive fresh, but assets are served from the cache
   and refreshed afterwards -- so without a bump, a returning visitor gets the NEW
   pages painted with the OLD stylesheet for one visit. On activate, every cache
   whose name is not this one is deleted, so the whole shell is re-fetched.
   v2: the complete-editions list, the search result card, the reading strip.
   v3: the dark logo, the painting band behind the language boxes, and the
       vertical-rhythm pass.
   v4: the collection tiles on /paintings/, and the gallery CSS moved out of that
       page's inline <style> into the shared sheet -- so a cached stylesheet would
       now leave the Sounds gallery with no gallery rules at all.
   v5: the loose-end mark beside the excerpt on /sedaha/.
   v6: the logo panel stripped to one treatment at every width.
   v7: the excerpt painting, whole and centred against the text.
   v8: that painting turned 180 and the text moved to its foot. The filename did
       not change, only the pixels -- which is exactly the case a cache-first asset
       strategy gets wrong without a bump: the new CSS with the old picture.
   v9: /sedaha/languages/ retired to a redirect, and the download + share bar added
       to the head of every Opening page.
   v10: the "Arasteh" wordmark dropped from the nav -- Home was the same link -- and
        the tabs moved to the start of the bar.
   v11: the all-languages list uses the quick-start box, with names shrunk to fit.
   v12: the excerpt image is the author's own crop of the loose end, used unturned.
        Same filename, different pixels and a different shape -- so a cached copy
        would be both the wrong picture and the wrong width.
   v13: the excerpt image is now the author's own file, square, at two lines tall.
   v14: that image mirrored, so the loose end runs toward the sentence.
   v15: Paintings links go straight to the gallery, the lightbox no longer advances
        on tap, download buttons carry sizes, guestbook trust lines.
   v16: the native guestbook page, script and repository-owned note index.
   v17: the private-or-public note choice.
   v18: receipts require verified private-queue storage; no email fallback.
   v19: pin the guestbook form script to the page version, so a returning browser
        cannot combine new form markup with an older cached submission client.
   v20: replace the retired intake service with a GitHub-only public issue handoff.
   v21: publish valid notes automatically and notify Amir through issue assignment.
   v22: post through the account-free Worker and keep confirmed notes visible locally.
   v23: the Opening frontispiece layout; returning readers must not combine its new
        figure markup with the old stylesheet's browser-default figure margins.
   v24: justified long-form prose throughout the site, including every Opening.
   v25: version the stylesheet URL itself, so even the previous service worker
        cannot serve pre-justification CSS during its replacement visit.
   v26: connect the production account-free guestbook endpoint.
   v27: a second gallery, The World Through Boteh-Jegheh, so the Paintings tab lands
        on the collection index again rather than jumping past it into Sounds. The
        nav is baked into every cached page, and gallery.js now finds its grid by
        class instead of the id only the Sounds page had -- a returning browser must
        not combine the new pages with the old script.
   v28: the two remaining doors into the Sounds gallery -- the home page's Paintings
        card and the installed app's Paintings shortcut -- go to /paintings/ like
        everything else. The manifest is an ASSET here, so it is served cache-first:
        without this bump an installed app would keep the old shortcut, and the one
        route into the site that does not go through a page would still land past
        the new gallery. */
/* v29: generated language links work without scripts; pin the enhanced finder
   so a returning browser cannot append the old dynamic list to the new HTML. */
/* v30: the download terms line under the finder's buttons (finder.js?v=30). */
/* v31: site clean-up -- the home page leads with the book, the your-language button
   (lang-mine.js) replaces the offer line, the rotating line and hero count are gone,
   three quick starts instead of nine; stylesheet v27. */
/* v32: wording pass -- share previews, the finder's answers, the app shortcut to the
   language list (the manifest is an asset, served cache-first). */
/* v33: the 2026-11-14 page-review fixes -- language boxes, right-to-left Opening
   pages, lightbox loading, guestbook, home on phones; stylesheet v28. */
/* v34: the 2026-11-16 batch -- galleries hang in rows, in series order; the
   cover and Opening painting come in smaller copies (srcset); share cards for the
   paintings pages; the Persian Opening's shell in Persian (reader.js, share.js and
   backtotop.js speak it there); stylesheet v29. */
/* v35: painting downloads -- the lightbox offers each painting's badged 3000 px
   copy from the `paintings` release (gallery.js?v=36); stylesheet v30. */
/* v36: downloads go through the guestbook Worker's /dl/ route, which records
   who fetched what (download_log.py) and redirects to the release; rel=nofollow
   on download links (finder.js?v=36); the native-check line in each page's own
   language, in a light box; question pages for 103 languages; stylesheet v31. */
/* lang-mine.js?v=37 (2026-11-20): on /sedaha/ the visitor's language takes the
   third quick start (Danish until known) instead of a separate button.
   style.css?v=32 (same day): the home page's whole book card is one link. A new
   script URL is enough -- assets are fetched by URL -- so VERSION stays. */
/* v37 (2026-11-22): the site in the visitor's language -- the language switch in
   every nav, assets/js/i18n.js and the dictionaries in assets/i18n/ (fetched by a
   hashed URL); finder.js and guestbook.js speak through it; the skip link and the
   guestbook honeypot no longer sit off the left edge (right-to-left pages);
   stylesheet v33. */
var VERSION = 'arasteh-v37';

/* The shell: enough to render any page offline, kept deliberately small. */
var SHELL = [
  '/',
  '/sedaha/',
  '/comments/',
  '/assets/css/style.css?v=33',
  '/assets/js/reader.js',
  '/assets/js/editions.js',
  '/assets/js/lang-mine.js?v=37',
  '/assets/js/finder.js?v=37',
  '/assets/js/lang-alias.js',
  '/assets/js/share.js',
  '/assets/js/backtotop.js',
  '/assets/js/guestbook.js?v=37',
  '/assets/data/guestbook.json',
  '/assets/fonts/ebgaramond-regular.woff2',
  '/assets/fonts/ebgaramond-italic.woff2',
  '/assets/fonts/ebgaramond-semibold.woff2',
  '/assets/fonts/vazirmatn-regular.woff2',
  '/assets/fonts/vazirmatn-semibold.woff2',
  '/404.html'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(VERSION)
      // one failed file must not fail the whole install
      .then(function (cache) {
        return Promise.all(SHELL.map(function (url) {
          return cache.add(url).catch(function () {});
        }));
      })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (key) {
          return key === VERSION ? null : caches.delete(key);
        }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') return;

  var url;
  try { url = new URL(request.url); } catch (e) { return; }
  if (url.origin !== self.location.origin) return;   // book files: untouched

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(function (response) {
          var copy = response.clone();
          caches.open(VERSION).then(function (cache) { cache.put(request, copy); });
          return response;
        })
        .catch(function () {
          return caches.match(request)
            .then(function (hit) { return hit || caches.match('/404.html'); })
            .then(function (hit) {
              return hit || new Response(
                '<!doctype html><meta charset="utf-8"><title>Offline</title>' +
                '<p style="font:16px/1.6 system-ui;padding:2rem">This page has not been ' +
                'opened before, so it is not stored on this device. It will be here again ' +
                'when the connection is.</p>',
                { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
              );
            });
        })
    );
    return;
  }

  /* Reader notes change independently of the shell. Ask for the live index first,
     then keep the last published set available when the connection disappears. */
  if (url.pathname === '/assets/data/guestbook.json') {
    event.respondWith(
      fetch(request).then(function (response) {
        if (response && response.ok) {
          var copy = response.clone();
          caches.open(VERSION).then(function (cache) { cache.put(request, copy); });
        }
        return response;
      }).catch(function () { return caches.match(request); })
    );
    return;
  }

  /* Assets: from the cache at once, refreshed quietly for next time. */
  event.respondWith(
    caches.match(request).then(function (hit) {
      var live = fetch(request).then(function (response) {
        if (response && response.ok) {
          var copy = response.clone();
          caches.open(VERSION).then(function (cache) { cache.put(request, copy); });
        }
        return response;
      }).catch(function () { return hit; });
      return hit || live;
    })
  );
});
