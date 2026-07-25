/* Accessible dialog viewer for the Sounds painting gallery.
   Click / tap a thumbnail to open; arrow keys, on-screen arrows, a swipe on
   touch screens, or a tap on the painting itself move between works.
   Each painting also has its own address (/paintings/sounds/#picture-4), so a
   single work can be linked to and shared, and the share button hands that
   address to the system share sheet through share.js. */
(function () {
  'use strict';

  var dialog = document.getElementById('galleryLightbox');
  var gallery = document.getElementById('soundsGallery');
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
  var current = 0;
  var trigger;

  // A painting's address comes from its caption, so links stay readable and
  // survive a file being renamed: "Picture 4" -> #picture-4, the cover -> #cover.
  function slugOf(shot) {
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
    image.classList.add('is-loading');
    if (source) source.srcset = shot.href.replace(/\.jpg$/i, '.webp');
    image.src = shot.href;
    image.alt = thumbnail.alt;
    caption.textContent = shot.getAttribute('data-caption') || thumbnail.alt;
    if (counter) counter.textContent = (current + 1) + ' / ' + shots.length;
    setUrl(slugs[current]);
    if (shareButton) {
      shareButton.setAttribute('data-share-url',
        location.origin + location.pathname + '#' + slugs[current]);
      shareButton.setAttribute('data-share-title',
        caption.textContent + ' — Sedaha (Sounds), Amir Arasteh');
    }
    preload(current + 1);
    preload(current - 1);
  }

  // The neighbours are fetched ahead so arrows/swipes feel instant.
  function preload(index) {
    var href = shots[(index + shots.length) % shots.length].href;
    var img = new Image();
    img.src = href;
  }

  image.addEventListener('load', function () { image.classList.remove('is-loading'); });

  function open(index, openedBy) {
    trigger = openedBy;
    show(index);
    dialog.showModal();
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

  // Tapping the painting advances to the next one (unless the tap was really a
  // swipe, handled below). The explicit close and arrow controls still stand.
  var swiped = false;
  image.addEventListener('click', function (event) {
    event.stopPropagation();
    if (!swiped) show(current + 1);
  });

  // Horizontal swipe on touch screens moves between paintings.
  var startX = null, startY = null;
  shell.addEventListener('touchstart', function (event) {
    if (event.touches.length !== 1) { startX = null; return; }
    startX = event.touches[0].clientX;
    startY = event.touches[0].clientY;
    swiped = false;
  }, { passive: true });
  shell.addEventListener('touchend', function (event) {
    if (startX === null) return;
    var touch = event.changedTouches[0];
    var dx = touch.clientX - startX;
    var dy = touch.clientY - startY;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) {
      swiped = true;                       // suppress the click that follows
      show(dx < 0 ? current + 1 : current - 1);
      window.setTimeout(function () { swiped = false; }, 300);
    }
    startX = null;
  }, { passive: true });

  dialog.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      show(current - 1);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      show(current + 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      show(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      show(shots.length - 1);
    }
  });

  dialog.addEventListener('close', function () {
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
