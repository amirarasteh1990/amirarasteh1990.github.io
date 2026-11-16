/* Accessible dialog viewer for any painting gallery.
   Click / tap a thumbnail to open; arrow keys, on-screen arrows, a swipe on
   touch screens, or a tap on the painting itself move between works.
   Each painting also has its own address (/paintings/sounds/#picture-4), so a
   single work can be linked to and shared, and the share button hands that
   address to the system share sheet through share.js. The download control
   offers the painting's data-download: its badged 3000 px copy, a release asset
   on GitHub, so each download is counted (make_painting_downloads.py). */
(function () {
  'use strict';

  var dialog = document.getElementById('galleryLightbox');
  // Found by class, not by the id the Sounds page used to be alone in having.
  // One gallery per page, so the first .gallery is the gallery; a second one
  // ships nothing but its own markup and this file already knows what to do.
  var gallery = document.querySelector('.gallery');
  if (!dialog || !gallery || typeof dialog.showModal !== 'function') return;

  var shots = Array.prototype.slice.call(gallery.querySelectorAll('.shot'));
  var image = document.getElementById('lightboxImage');
  var source = document.getElementById('lightboxSource');
  var caption = document.getElementById('lightboxCaption');
  var counter = document.getElementById('lightboxCounter');
  var shell = document.getElementById('lightboxShell');
  var closeButton = document.getElementById('lightboxClose');
  var previousButton = document.getElementById('lightboxPrev');
  var nextButton = document.getElementById('lightboxNext');
  var shareButton = document.getElementById('lightboxShare');
  var downloadLink = document.getElementById('lightboxDownload');
  var current = 0;
  var trigger;
  // the series this page shows, for the share title (it said "Sedaha (Sounds)" on
  // every gallery); the page states it on its .gallery
  var series = gallery.getAttribute('data-series') || 'Sedaha (Sounds)';
  var loadToken = 0;
  var themeMeta = document.querySelector('meta[name="theme-color"]:not([media])');
  // A right-to-left page hangs its paintings right to left (style.css, .gallery), so
  // there the next painting is to the left: arrow keys and swipes follow the wall.
  var rtl = window.getComputedStyle(gallery).direction === 'rtl';
  var themeBefore = themeMeta ? themeMeta.content : '';

  // A painting's address comes from its caption, so links stay readable and
  // survive a file being renamed: "Picture 4" -> #picture-4, the cover -> #cover.
  // A generated gallery states the address instead, because its caption is a full
  // museum line -- "Iran II - 2026 - 40 x 40 cm" would slug to a mouthful nobody
  // would paste anywhere. data-slug lets that page keep #iran-ii.
  function slugOf(shot) {
    var stated = shot.getAttribute('data-slug');
    if (stated) return stated;
    var text = (shot.getAttribute('data-caption') || '').toLowerCase();
    var numbered = text.match(/picture\s+(\d+)/);
    if (numbered) return 'picture-' + numbered[1];
    if (text.indexOf('cover') === 0) return 'cover';
    return text.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'painting';
  }

  var slugs = shots.map(slugOf);

  function setUrl(hash) {
    if (!window.history || !history.replaceState) return;
    history.replaceState(null, '', hash ? '#' + hash : location.pathname + location.search);
  }

  function show(index) {
    current = (index + shots.length) % shots.length;
    var shot = shots[current];
    var thumbnail = shot.querySelector('img');
    // The thumbnail the reader tapped is already downloaded: show it at once, then
    // swap in the full painting in the same format the page is showing (review
    // 2026-11-14 -- on a slow line the viewer sat dark for seconds, and the JPG
    // neighbours it prefetched were never shown, since the browser uses WebP).
    var thumbSrc = thumbnail.currentSrc || thumbnail.src;
    var useWebp = /\.webp(\?|$)/i.test(thumbSrc);
    var full = useWebp ? shot.href.replace(/\.jpg$/i, '.webp') : shot.href;
    var token = ++loadToken;
    if (source) source.removeAttribute('srcset');
    image.src = thumbSrc;
    image.classList.add('is-loading');
    var loader = new Image();
    loader.onload = function () {
      if (token !== loadToken) return;
      image.src = full;
      image.classList.remove('is-loading');
      preload(current + 1, useWebp);
      preload(current - 1, useWebp);
    };
    loader.onerror = function () {
      if (token === loadToken) image.classList.remove('is-loading');
    };
    loader.src = full;
    image.alt = thumbnail.alt;
    caption.textContent = shot.getAttribute('data-caption') || thumbnail.alt;
    if (counter) counter.textContent = (current + 1) + ' / ' + shots.length;
    setUrl(slugs[current]);
    if (shareButton) {
      shareButton.setAttribute('data-share-url',
        location.origin + location.pathname + '#' + slugs[current]);
      shareButton.setAttribute('data-share-title',
        caption.textContent + ' \u2014 ' + series + ', Amir Arasteh');
    }
    // A painting without a download keeps the control hidden rather than dead.
    if (downloadLink) {
      var file = shot.getAttribute('data-download');
      if (file) downloadLink.href = file;
      else downloadLink.removeAttribute('href');
      downloadLink.hidden = !file;
    }
  }

  // The neighbours are fetched ahead so arrows/swipes feel instant -- after the
  // painting being looked at has arrived, and in the format that will be shown.
  function preload(index, webp) {
    var href = shots[(index + shots.length) % shots.length].href;
    var img = new Image();
    img.src = webp ? href.replace(/\.jpg$/i, '.webp') : href;
  }

  function open(index, openedBy) {
    trigger = openedBy;
    show(index);
    dialog.showModal();
    // the phone's status bar goes dark with the viewer, not cream above it
    if (themeMeta) themeMeta.content = '#14120f';
    closeButton.focus();
  }

  shots.forEach(function (shot, index) {
    shot.addEventListener('click', function (event) {
      event.preventDefault();
      open(index, shot);
    });
  });

  previousButton.addEventListener('click', function () { show(current - 1); });
  nextButton.addEventListener('click', function () { show(current + 1); });
  closeButton.addEventListener('click', function () { dialog.close(); });
  shell.addEventListener('click', function (event) {
    if (event.target === shell) dialog.close();
  });

  // Tapping the painting does nothing, deliberately. It used to advance, but a
  // tap on a painting means "let me look", not "next" -- an accidental skip is
  // the worst interruption an art viewer has. Arrows, swipe and keys all still
  // move; the backdrop still closes. The painting itself is for looking at.

  // Horizontal swipe on touch screens moves between paintings.
  var startX = null, startY = null;
  shell.addEventListener('touchstart', function (event) {
    if (event.touches.length !== 1) { startX = null; return; }
    startX = event.touches[0].clientX;
    startY = event.touches[0].clientY;
  }, { passive: true });
  shell.addEventListener('touchend', function (event) {
    if (startX === null) return;
    var touch = event.changedTouches[0];
    var dx = touch.clientX - startX;
    var dy = touch.clientY - startY;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) {
      show((dx < 0) !== rtl ? current + 1 : current - 1);
    }
    startX = null;
  }, { passive: true });

  dialog.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      show(rtl ? current + 1 : current - 1);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      show(rtl ? current - 1 : current + 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      show(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      show(shots.length - 1);
    }
  });

  dialog.addEventListener('close', function () {
    loadToken++;
    if (themeMeta) themeMeta.content = themeBefore;
    image.removeAttribute('src');
    if (source) source.removeAttribute('srcset');
    setUrl('');
    if (trigger) trigger.focus();
  });

  // Arriving on /paintings/sounds/#picture-4 opens that painting straight away.
  function openFromHash() {
    var index = slugs.indexOf(decodeURIComponent(location.hash.slice(1)).toLowerCase());
    if (index < 0) return;
    if (dialog.open) show(index);
    else open(index, shots[index]);
  }
  openFromHash();
  window.addEventListener('hashchange', openFromHash);
})();
