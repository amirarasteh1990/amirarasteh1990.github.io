/* The language finder on /sedaha/.

   One question, one answer, in one place. The page is a doorway: it holds no list
   languages until its disclosure is opened. The list is generated HTML; search
   reads window.EDITIONS from the same record and answers under the input.

   Three outcomes, all answered in the same place:
     one language   its name, what exists in it, and the buttons
     several        how many, and up to five to choose from
     none           said plainly, with a way to browse and a way to write

   (The cycling "Read it in ..." line it used to run was retired 2026-11-13.)
   Needs assets/js/lang-alias.js loaded first for the other names each language
   answers to. */
(function () {
  'use strict';
  var LANGS = window.EDITIONS || [];
  var ALIAS = window.LANG_ALIASES || {};
  var input = document.getElementById('langSearch');
  var result = document.getElementById('langResult');
  if (!input || !result || !LANGS.length) return;

  /* The catalogue page at /sedaha/languages/ is retired: the expandable list on
     THIS page holds the same languages, already grouped by whether the whole book
     exists or only the opening. Three places used to send the reader off to that
     page; they now open the list in place, which is both faster and one page fewer
     to keep in step. The href stays a real fragment so that with no scripting the
     browser still jumps to the disclosure and the reader can open it. */
  function toAllLangs(a) {
    a.href = '#allLangs';
    a.addEventListener('click', function () {
      var box = document.getElementById('allLangs');
      if (box) box.open = true;
    });
    return a;
  }
  // and so a link from another page, /sedaha/#allLangs, arrives with it open
  if (location.hash === '#allLangs') {
    var opened = document.getElementById('allLangs');
    if (opened) opened.open = true;
  }

  /* Fold a name to something a keyboard without that language can produce: the
     accents decompose away, and the letters that do not decompose (o with a
     stroke is one character, not o plus a mark) are mapped by hand. So turkce
     finds Türkçe, espanol finds Español, foroyskt finds Føroyskt. */
  var LETTERS = {'ø':'o','æ':'ae','ß':'ss','đ':'d','ð':'d',
                 'þ':'th','ł':'l','ı':'i','œ':'oe','’':"'"};
  function fold(s) {
    s = String(s).toLowerCase().replace(/[øæßđðþłıœ’]/g, function (c) { return LETTERS[c]; });
    return s.normalize ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '') : s;
  }

  /* What a language is searchable BY: its two names, the other names it answers
     to, and its code. Nothing else -- indexing everything printed beside it meant
     "pdf" matched every complete edition and "opening" matched all of them. */
  LANGS.forEach(function (L) {
    L.hay = fold([L.native, L.en, ALIAS[L.slug] || '', L.slug].join(' '));
    L.first = (ALIAS[L.slug] || '').split(' ')[0];
  });

  var bySlug = {};
  LANGS.forEach(function (L) { bySlug[L.slug] = L; });

  /* The book was published in these three, and they are what a reader whose own
     edition is still coming can have tonight. The same three the opening pages
     offer, for the same reason: an answer that says only "not yet" is not an
     answer. Read from the data, so a language that loses its files drops out. */
  var WHOLE = ['fa', 'en', 'da'].map(function (s) { return bySlug[s]; })
    .filter(function (L) {
      return L && (L.files || []).some(function (f) { return f[0] === 'epub'; });
    });

  /* Typed in full beats typed in part: "german" is German, though it also sits
     inside Low German, and "farsi" is Persian, though Dari answers to it too.
     The first alias in a language's list counts as one of its full names. */
  function exact(L, q) {
    return fold(L.en) === q || fold(L.native) === q || L.slug === q || L.first === q;
  }

  var STATE = {
    ready: 'The whole book is free to read.',
    review: 'The opening is here; the whole book is in final review.',
    translated: 'The opening is here; the whole book is in preparation.',
    revising: 'The opening is here; the whole book is being revised.'
  };

  /* Every door is the same size, so a name that does not fit gives up type size
     rather than making its box wider -- one wide box among a hundred is what turns
     a grid back into a list. Hindi, Armenian and Nederlands need a step or two;
     most names need none.

     The box clips its overflow, so scrollHeight past clientHeight is the test. It
     is measured, not guessed from character counts, because a name's width depends
     on its script: 中文 is two characters and wider than five Latin ones. Only ever
     shrinks, never grows, and stops at a floor where a name would stop being
     readable. The element must be laid out when this runs. */
  var FIT_FLOOR = 0.74;              // rem
  var FIT_STEPS = 7;
  function fitLabel(a) {
    var size = 1.18;                 // .lang-box's own font-size
    // height for a name that wraps, width for one long word that cannot wrap (the
    // box breaks between words only since 2026-11-14, not inside them)
    for (var i = 0; i < FIT_STEPS && (a.scrollHeight > a.clientHeight + 1 ||
         a.scrollWidth > a.clientWidth + 1); i++) {
      size -= 0.06;
      if (size < FIT_FLOOR) { size = FIT_FLOOR; }
      a.style.fontSize = size.toFixed(2) + 'rem';
      if (size === FIT_FLOOR) { break; }
    }
  }
  function fitAll(root) {
    var boxes = root.querySelectorAll('.lang-box');
    for (var i = 0; i < boxes.length; i++) { fitLabel(boxes[i]); }
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function nameInto(node, L) {
    var n = el('span', 'native', L.native);
    n.setAttribute('lang', L.lang);
    if (L.rtl) n.setAttribute('dir', 'rtl');
    node.appendChild(n);
    if (L.en !== L.native) {
      node.appendChild(document.createTextNode(' '));
      node.appendChild(el('span', 'en', L.en));
    }
    return node;
  }

  function shareButton(L) {
    var b = el('button', 'btn btn-icon btn-share');
    b.type = 'button';
    b.setAttribute('aria-label', 'Share the ' + L.en + ' opening');
    b.setAttribute('title', 'Share the ' + L.en + ' opening');
    b.setAttribute('data-share-url', 'https://arasteh.art' + L.url);
    b.setAttribute('data-share-title', 'Sedaha (Sounds) — Book One');
    b.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v13"/>' +
      '<path d="m16 6-4-4-4 4"/><path d="M20 10v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-9"/></svg>';
    return b;
  }

  /* An edition still on its way used to leave the panel almost empty: a name and
     one button. It can offer more than that without pretending: the whole book
     exists in the three it was published in, and that is what the reader wants
     tonight. Same offer the opening pages make, from the same data. */
  function meanwhile(L) {
    var others = WHOLE.filter(function (o) { return o.slug !== L.slug; });
    if (!others.length) return null;
    var wrap = el('div', 'lr-meanwhile');
    /* Naming only these three read as though only three existed; there are many more.
       The count comes from the data, so the sentence cannot go stale again. */
    var whole = LANGS.filter(function (L) { return L.files && L.files.length; }).length;
    var note = el('p', 'lr-meanwhile-note', 'Until it is ready, the whole book can be read in ');
    var all = toAllLangs(el('a', null, whole + ' other languages'));
    note.appendChild(all);
    note.appendChild(document.createTextNode(', among them'));
    wrap.appendChild(note);
    var acts = el('p', 'lr-actions');
    others.forEach(function (o) {
      var epub = (o.files || []).filter(function (f) { return f[0] === 'epub'; })[0];
      var a = el('a', 'btn');
      a.href = epub[2];
      a.setAttribute('aria-label', o.en + ', the complete book, EPUB');
      var n = el('span', null, o.native);
      n.setAttribute('lang', o.lang);
      if (o.rtl) n.setAttribute('dir', 'rtl');
      a.appendChild(n);
      a.appendChild(el('span', 'btn-fmt', 'EPUB'));
      acts.appendChild(a);
    });
    wrap.appendChild(acts);
    return wrap;
  }

  /* The panel is not a live region any more: it was read out whole on every
     keystroke, licence sentence included. One short line says what happened. */
  var status = document.getElementById('langStatus');
  function say(text) { if (status) status.textContent = text; }

  function one(L) {
    result.textContent = '';
    say(L.native + (L.en !== L.native ? ', ' + L.en : '') + ': ' +
      (STATE[L.state] || STATE.translated));
    result.appendChild(nameInto(el('p', 'lr-name'), L));
    result.appendChild(el('p', 'lr-state',
      STATE[L.state] || STATE.translated));

    var acts = el('p', 'lr-actions');
    var read = el('a', 'btn btn-primary', 'Read the opening');
    read.href = L.url;
    acts.appendChild(read);
    (L.files || []).forEach(function (f) {
      var a = el('a', 'btn', f[0].toUpperCase() + (f[1] ? ' · ' + f[1] : ''));
      a.href = f[2];
      a.setAttribute('aria-label', L.en + ', the complete book, ' + f[0].toUpperCase());
      acts.appendChild(a);
    });
    acts.appendChild(shareButton(L));
    result.appendChild(acts);

    var soon = (L.files && L.files.length) ? null : meanwhile(L);
    if (soon) result.appendChild(soon);

    /* The terms every file carries, in one line under the offer (author 2026-11-13).
       Each Opening page says the same in its own language, from the book's copyright
       page; the whole notice is inside every file and on the License page. */
    if ((L.files && L.files.length) || soon) {
      var terms = el('p', 'muted-note dl-terms', 'The complete file may be shared freely, ' +
        'unchanged. Short excerpts may be quoted if each names its source: the book’s ' +
        'title, the author’s name and arasteh.art. ');
      var lic = el('a', null, 'License');
      lic.href = '/license.html';
      terms.appendChild(lic);
      result.appendChild(terms);
    }

    /* Why a download leaves the site, and what to do if it cannot: shown to anyone
       who has just been offered files, whether their own or the three the book was
       published in. It matters most to readers in Iran and Afghanistan, so it must
       be findable there and invisible where no file has been offered at all. */
    if ((L.files && L.files.length) || soon) {
      var help = document.createElement('details');
      help.className = 'dl-help';
      help.appendChild(el('summary', null, 'Download help'));
      var p = el('p', null, 'EPUB adjusts to your screen. PDF keeps the printed page. ' +
        'The files are hosted on GitHub, so the download opens there. If that is blocked ' +
        'on your network, ');
      var mail = el('a', null, 'write to Amir');
      mail.href = 'mailto:amirarasteh.art@gmail.com?subject=' +
        encodeURIComponent('Sedaha in ' + L.en);
      p.appendChild(mail);
      p.appendChild(document.createTextNode(' and he will send them to you.'));
      help.appendChild(p);
      result.appendChild(help);
    }
    result.hidden = false;
  }

  var SHOW = 5;

  function several(list, q) {
    result.textContent = '';
    say(list.length + ' languages match');
    result.appendChild(el('p', 'lr-state', list.length + ' languages match “' + q + '”'));
    var matches = el('div', 'lr-matches');
    matches.id = 'langMatches';
    result.appendChild(matches);
    function addMatch(L) {
      var row = el('p', 'lr-match');
      nameInto(row, L);
      var go = el('a', 'btn', 'Read the opening');
      go.href = L.url;
      row.appendChild(go);
      matches.appendChild(row);
      return go;
    }
    list.slice(0, SHOW).forEach(addMatch);
    if (list.length > SHOW) {
      var all = el('p', 'lr-actions');
      var more = el('button', 'btn', 'View all matches');
      more.type = 'button';
      more.setAttribute('aria-controls', matches.id);
      more.addEventListener('click', function () {
        var added = list.slice(SHOW).map(addMatch);
        all.remove();
        added[0].focus();
      });
      all.appendChild(more);
      result.appendChild(all);
    }
    result.hidden = false;
  }

  function none(q) {
    result.textContent = '';
    say('No language matches');
    result.appendChild(el('p', 'lr-state', 'No language matches “' + q + '”.'));
    var acts = el('p', 'lr-actions');
    var browse = toAllLangs(el('a', 'btn', 'Browse all languages'));
    var write = el('a', 'btn', 'Write to Amir');
    write.href = 'mailto:amirarasteh.art@gmail.com?subject=' +
      encodeURIComponent('Sedaha in ' + q);
    acts.appendChild(browse);
    acts.appendChild(write);
    result.appendChild(acts);
    result.hidden = false;
  }

  var clearBtn = document.getElementById('langClear');

  function apply() {
    var typed = input.value.trim();
    var q = fold(typed);
    if (clearBtn) clearBtn.hidden = !typed;
    if (!q) { result.hidden = true; result.textContent = ''; say(''); return; }
    var hits = LANGS.filter(function (L) { return L.hay.indexOf(q) > -1; });
    var full = hits.filter(function (L) { return exact(L, q); });
    if (full.length === 1) one(full[0]);
    else if (hits.length === 1) one(hits[0]);
    else if (hits.length) several(hits, typed);
    else none(typed);
  }

  input.addEventListener('input', apply);
  input.addEventListener('keydown', function (e) {
    // Escape clears the field, as it does in any search box
    if (e.key === 'Escape' && input.value) { input.value = ''; apply(); }
  });
  if (clearBtn) clearBtn.addEventListener('click', function () {
    input.value = ''; apply(); input.focus();
  });

  /* arasteh.art/sedaha/#ja still answers, so old links keep working */
  function fromHash() {
    var L = bySlug[decodeURIComponent(location.hash.slice(1)).toLowerCase()];
    if (!L) return;
    input.value = L.en;
    apply();
    result.scrollIntoView({block: 'center'});
  }
  fromHash();
  window.addEventListener('hashchange', fromHash);

  /* The three above the search (the editions the book was published in) get the
     same fitting as the list. The visitor's own language now has its own button
     (lang-mine.js, 2026-11-13); the old fifth-slot swap, the offer line and the
     rotating 'Read it in' line are retired. */
  (function () {
    var row = document.querySelector('.quick-row');
    if (row) { fitAll(row); }
  })();

  /* Every language is already in the generated HTML, so the disclosure works even
     if scripts fail. JavaScript only adjusts long labels once they are visible;
     it must never append a second copy of the catalogue. */
  (function () {
    var box = document.getElementById('allLangs');
    if (!box) return;
    function fitOpenList() { if (box.open) fitAll(box); }
    box.addEventListener('toggle', fitOpenList);
    fitOpenList();
  })();
})();
