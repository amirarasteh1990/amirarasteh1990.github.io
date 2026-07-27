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
   v2: the complete-editions list, the search result card, the reading strip. */
var VERSION = 'arasteh-v2';

/* The shell: enough to render any page offline, kept deliberately small. */
var SHELL = [
  '/',
  '/sedaha/',
  '/assets/css/style.css',
  '/assets/js/reader.js',
  '/assets/js/editions.js',
  '/assets/js/finder.js',
  '/assets/js/lang-alias.js',
  '/assets/js/share.js',
  '/assets/js/backtotop.js',
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
  if (url.origin !== self.location.origin) return;   // book files, embeds: untouched

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
