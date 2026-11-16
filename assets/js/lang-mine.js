/* Your language, in its own words (author 2026-11-13, site clean-up).

   One button, first on the home page and the book page, for a visitor whose language
   this book is in. It says the edition's OWN title and its own word for the Opening
   -- «Klänge · Auftakt →», «صداها · سرآغاز ←» -- taken from the book (editions.js),
   so a German screen is never offered English words.

   Which language: the one the visitor last opened (remembered by reader.js on any
   Opening page), else the first of the browser's languages this site has. English
   stays the default: a browser that prefers English gets nothing here, since the
   page already is English. It never redirects -- a shared link opens what was
   shared, and search engines see the same page everyone does. The × forgets the
   language and stops offering it.

   The home page's "Read free in your language" button follows a remembered choice;
   the Books tab does the same on every other page (sync_head.py). */
(function () {
  var data = window.EDITIONS || [];
  var bySlug = {};
  data.forEach(function (L) { bySlug[L.slug] = L; });
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function drop(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  var remembered = bySlug[get('sedaha-lang')] || null;
  var mine = remembered;
  if (!mine && get('sedaha-lang-offer') !== 'off') {
    var wanted = (navigator.languages || [navigator.language || '']).slice(0, 4);
    for (var i = 0; i < wanted.length && !mine; i++) {
      var tag = String(wanted[i]).toLowerCase().replace('_', '-');
      var base = tag.split('-')[0];
      if (base === 'en') break;              // English first: English is the default
      mine = bySlug[tag] || bySlug[base] || null;
    }
  }

  var read = document.getElementById('readMine');
  var box = document.getElementById('langMine');
  var show = !!(box && mine && mine.title && mine.opening &&
               !(mine.slug === 'en' && !remembered));
  // One filled button on the page (review 2026-11-14): with the your-language
  // button showing, "Read free in your language" stays the way to every other
  // language, as an outline button; without it, it follows a remembered choice.
  if (read && show) read.className = 'btn';
  else if (read && remembered) read.href = remembered.url;
  if (!show) return;

  var go = document.createElement('a');
  go.className = 'btn btn-primary lang-mine-go';
  go.href = mine.url;
  go.setAttribute('lang', mine.lang);
  if (mine.rtl) go.setAttribute('dir', 'rtl');
  go.textContent = mine.title + ' · ' + mine.opening + (mine.rtl ? ' ←' : ' →');
  if (mine.en !== mine.native) {
    // the English name, hidden, so a screen reader can say which language this is
    var also = document.createElement('span');
    also.className = 'visually-hidden';
    also.setAttribute('lang', 'en');
    also.textContent = ' — ' + mine.en;
    go.appendChild(also);
  }
  var close = document.createElement('button');
  close.type = 'button';
  close.className = 'lang-clear lang-mine-close';
  close.setAttribute('aria-label', 'Hide this suggestion');
  close.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  close.addEventListener('click', function () {
    box.hidden = true;
    drop('sedaha-lang');
    drop('sedaha-lang-url');
    put('sedaha-lang-offer', 'off');
    if (read) { read.href = '/sedaha/'; read.className = 'btn btn-primary'; }
  });
  box.appendChild(go);
  box.appendChild(close);
  box.hidden = false;
})();
