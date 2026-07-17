/* Accessible dialog viewer for the Sounds painting gallery. */
(function () {
  'use strict';

  var dialog = document.getElementById('galleryLightbox');
  var gallery = document.getElementById('soundsGallery');
  if (!dialog || !gallery || typeof dialog.showModal !== 'function') return;

  var shots = Array.prototype.slice.call(gallery.querySelectorAll('.shot'));
  var image = document.getElementById('lightboxImage');
  var caption = document.getElementById('lightboxCaption');
  var shell = document.getElementById('lightboxShell');
  var closeButton = document.getElementById('lightboxClose');
  var previousButton = document.getElementById('lightboxPrev');
  var nextButton = document.getElementById('lightboxNext');
  var current = 0;
  var trigger;

  function show(index) {
    current = (index + shots.length) % shots.length;
    var shot = shots[current];
    var thumbnail = shot.querySelector('img');
    image.src = shot.href;
    image.alt = thumbnail.alt;
    caption.textContent = shot.getAttribute('data-caption') || thumbnail.alt;
  }

  function open(index, source) {
    trigger = source;
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
    if (trigger) trigger.focus();
  });
})();
