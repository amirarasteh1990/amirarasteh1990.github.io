/* Per-language share button: native share sheet where available,
   clipboard copy as a fallback. Buttons opt in with class "btn-share"
   and carry data-share-url / data-share-title / data-share-text.
   Delegated from document, so it covers buttons on any page. */
(function () {
  'use strict';
  var toast;

  function showToast(msg) {
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'share-toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    void toast.offsetWidth;              /* reflow so the transition replays */
    toast.classList.add('show');
    window.clearTimeout(toast._hide);
    toast._hide = window.setTimeout(function () {
      toast.classList.remove('show');
    }, 2200);
  }

  function fallbackCopy(url) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        function () { showToast('Link copied'); },
        function () { window.prompt('Copy this link:', url); }
      );
    } else {
      window.prompt('Copy this link:', url);
    }
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.btn-share');
    if (!btn) return;
    e.preventDefault();
    var url = btn.getAttribute('data-share-url') || window.location.href;
    var data = {
      title: btn.getAttribute('data-share-title') || document.title,
      text: btn.getAttribute('data-share-text') || '',
      url: url
    };
    if (navigator.share) {
      navigator.share(data).catch(function () { /* user dismissed the sheet */ });
    } else {
      fallbackCopy(url);
    }
  });
})();
