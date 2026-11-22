/* The site in the visitor's language (author 2026-11-22).

   Which language: the head bootstrap (sync_head.py) has already decided and set
   window.__ui -- the visitor's own choice if they made one (localStorage
   "arasteh-ui"), else the browser's FIRST language when the site has it, else
   English. When unsure, English. It has also loaded that language's dictionary
   (assets/i18n/<code>.js -> window.__I18N), synchronously, so it is here before
   this deferred script runs.

   What is translated: the site's own English words, found by matching their text
   against the dictionary -- never by position. Only text whose nearest lang is
   English is looked at, so book text (lang="de", lang="fa", ...) is never touched,
   and anything under translate="no" is skipped (the language names, the guestbook's
   notes, the native-check questions). A paragraph with links or bold inside is one
   entry, its inline elements written as numbered markers -- "Read <0>the
   licence</0> first." -- so a translation can put them where its grammar needs.
   The Persian pages carry a Persian shell (author 2026-11-16); its words map back
   to the English ones through window.__I18N_ALIAS, so they translate too.
   Text the scripts add later (search results, status lines) is caught by a
   MutationObserver and translated the same way.

   The language switch is in the nav on every page (sync_appnav.py), always shown
   (author 2026-11-22). Choosing a language stores it and reloads the page.

   ?ui=<code> previews a language for one page view without storing it;
   ?ui=x-extract makes this script collect every string it would look up and print
   them into the page, which is how build_i18n.py lists the site's words. */
(function () {
  'use strict';
  var ui = window.__ui || 'en';
  var D = window.__I18N || null;
  var ALIAS = window.__I18N_ALIAS || {};
  var EXTRACT = ui === 'x-extract';
  var seen = {};
  var KEY = 'arasteh-ui';
  var html = document.documentElement;

  var INLINE = /^(A|ABBR|B|BDI|BDO|BR|CITE|CODE|DFN|EM|I|IMG|KBD|MARK|Q|S|SAMP|SMALL|SPAN|STRONG|SUB|SUP|TIME|U|VAR|WBR)$/;
  var RICH = /^(P|LI|H[1-6]|FIGCAPTION|DD|DT|TD|TH|LABEL|LEGEND|SUMMARY|BLOCKQUOTE|CAPTION|BUTTON|A|OPTION)$/;
  var SKIP = /^(SCRIPT|STYLE|SVG|NOSCRIPT|TEXTAREA|PRE|TEMPLATE|INPUT|SELECT|IFRAME|CANVAS)$/;
  var VOID = /^(BR|WBR|IMG)$/;
  var ATTRS = ['aria-label', 'title', 'alt', 'placeholder'];
  var WS = /[ \t\n\r\f]+/g;
  // a site word has lowercase letters: PDF, EPUB, ISBN numbers and sizes stay as they are
  var WORDY = /[a-z]{2}|[؀-ۿ]{2}/;

  var DIR = window.__UI_RTL || {};
  var uiDir = DIR[ui] ? 'rtl' : 'ltr';

  function norm(s) { return s.replace(WS, ' ').replace(/^ | $/g, ''); }
  function tag(el) { return el.nodeName.toUpperCase(); }

  // The source a piece of text is written in, from the nearest lang: 'en', 'fa'
  // (the Persian shell, through ALIAS), or null (book text, other languages).
  function srcOf(lang) {
    lang = (lang || '').toLowerCase();
    if (lang === '' || lang.slice(0, 2) === 'en') return 'en';
    return lang === 'fa' ? 'fa' : null;
  }
  function langAt(el) {
    var l = el && el.closest ? el.closest('[lang]') : null;
    return l ? l.getAttribute('lang') : '';
  }
  // translate="no" (names that must stay in their own language; browsers honour it
  // too) or data-i18n-skip (left in English on purpose, e.g. the native-check
  // questions and the guestbook's notes, which a browser may still translate).
  var NOT = '[translate="no"],[data-i18n-skip],[data-i18n-name]';
  function off(el) {
    return el.getAttribute('translate') === 'no' || el.hasAttribute('data-i18n-skip') ||
      el.hasAttribute('data-i18n-name');
  }
  function blocked(el) {
    return !!(el && el.closest && el.closest(NOT));
  }

  // The translation of one msgid, or null to leave the text as it is. Text with
  // numbers in it ("12 reader notes", "Picture 4") is looked up with each number
  // as {n} ("{n} reader notes") and the numbers put back in order, so a count or a
  // year never multiplies the dictionary. "English" is never a site word: as a
  // label it is a language's own name, like "Deutsch" beside it.
  var MARK_OR_NUM = /(<\/?\d+\/?>)|\d+(?:[.,]\d+)*/g;
  function look(s, src, where) {
    if (!s || !WORDY.test(s) || s === 'English') return null;
    var key = src === 'fa' ? ALIAS[s] : s;
    if (!key) return null;
    var nums = null;
    if (/\d/.test(key)) {
      var got = [];
      // the markers' own digits (<0>, </1>, <2/>) are not numbers
      var k2 = key.replace(MARK_OR_NUM, function (m, mk) { if (mk) return mk; got.push(m); return '{n}'; });
      if (got.length) { key = k2; nums = got; }
    }
    if (EXTRACT) {
      if (src === 'en' && !seen[key]) seen[key] = where || '';
      return null;
    }
    var t;
    if (ui === 'en') { if (src !== 'fa') return null; t = key; }
    else {
      if (!D) return null;
      t = D[key];
      if (typeof t !== 'string' || t === '') return null;
    }
    if (nums) { var i = 0; t = t.replace(/\{n\}/g, function () { return i < nums.length ? nums[i++] : ''; }); }
    return t;
  }

  // For scripts that build a sentence around a value (finder.js): the template is
  // the msgid, {name} its slots. English when the site has no translation.
  window.__t = function (s, v) {
    if (EXTRACT && !seen[s]) seen[s] = 'js';
    var t = (ui !== 'en' && D && typeof D[s] === 'string' && D[s]) || s;
    return t.replace(/\{(\w+)\}/g, function (m, k) {
      return v && Object.prototype.hasOwnProperty.call(v, k) ? String(v[k]) : m;
    });
  };

  function where(el, attr) {
    var w = tag(el).toLowerCase();
    if (el.id) w += '#' + el.id;
    else if (typeof el.className === 'string' && el.className) w += '.' + el.className.split(/\s+/)[0];
    return w + (attr ? '@' + attr : '');
  }

  // On an English page the whole <html> takes the visitor's language at the end.
  // On a page in a book language only what was translated is marked, so a screen
  // reader and the fonts follow each part.
  var pageLang = html.getAttribute('lang') || 'en';
  // a page whose main text stays English on purpose (native-check pages) keeps its
  // <html lang>; only its shell is marked
  var pageEn = pageLang.slice(0, 2).toLowerCase() === 'en' &&
    !document.querySelector('main[data-i18n-skip]');
  var outLang = ui === 'en' ? 'en' : ui, outDir = ui === 'en' ? 'ltr' : uiDir;
  var changed = false;
  function mark(el) {
    changed = true;
    if (EXTRACT || pageEn || !el || el.nodeType !== 1) return;
    el.setAttribute('lang', outLang);
    if (el.hasAttribute('dir')) el.setAttribute('dir', outDir);
  }

  function attrs(el, src) {
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i], v = el.getAttribute(a);
      if (!v) continue;
      var k = norm(v), t = look(k, src, where(el, a));
      if (t !== null && t !== v) el.setAttribute(a, t);
    }
  }

  function opaque(el, src) {
    if (VOID.test(tag(el))) return true;
    if (off(el)) return true;
    var l = el.getAttribute('lang');
    return l !== null && srcOf(l) !== src;
  }
  function inlineOk(el, src) {
    if (!INLINE.test(tag(el))) return false;
    if (opaque(el, src)) return true;
    for (var n = el.firstChild; n; n = n.nextSibling)
      if (n.nodeType === 1 && !inlineOk(n, src)) return false;
    return true;
  }
  function isSegment(el, src) {
    if (!RICH.test(tag(el))) return false;
    var text = false;
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3) { if (/\S/.test(n.nodeValue)) text = true; }
      else if (n.nodeType === 1) { if (!inlineOk(n, src)) return false; }
    }
    return text;
  }
  function ser(el, src, list) {
    var out = '';
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3) out += n.nodeValue;
      else if (n.nodeType === 1) {
        var i = list.length;
        list.push(n);
        out += opaque(n, src) ? '<' + i + '/>' : '<' + i + '>' + ser(n, src, list) + '</' + i + '>';
      }
    }
    return out;
  }
  function rebuild(el, tr, list) {
    var frag = document.createDocumentFragment(), stack = [frag];
    var re = /<(\/?)(\d+)(\/?)>/g, last = 0, m;
    function put(node) { stack[stack.length - 1].appendChild(node); }
    while ((m = re.exec(tr))) {
      if (m.index > last) put(document.createTextNode(tr.slice(last, m.index)));
      var orig = list[+m[2]];
      if (!orig) return false;
      if (m[1]) { if (stack.length > 1) stack.pop(); }
      else if (m[3]) put(tag(orig) === 'BR' ? orig.cloneNode(false) : orig);
      else { var c = orig.cloneNode(false); put(c); stack.push(c); }
      last = re.lastIndex;
    }
    if (last < tr.length) put(document.createTextNode(tr.slice(last)));
    while (el.firstChild) el.removeChild(el.firstChild);
    el.appendChild(frag);
    return true;
  }
  function segment(el, src) {
    var list = [], k = norm(ser(el, src, list));
    var t = look(k, src, where(el));
    if (t !== null && t !== k && rebuild(el, t, list)) mark(el, src);
  }
  function textNode(n, src) {
    var v = n.nodeValue, k = norm(v);
    var t = look(k, src, n.parentNode ? where(n.parentNode) : '');
    if (t === null || t === k) return;
    n.nodeValue = /^[ \t\n\r\f]*/.exec(v)[0] + t + /[ \t\n\r\f]*$/.exec(v)[0];
    mark(n.parentNode, src);
  }

  function walk(el, lang) {
    if (el.nodeType !== 1 || SKIP.test(tag(el))) return;
    if (off(el)) return;
    var own = el.getAttribute('lang');
    if (own !== null && own !== '') lang = own;
    var src = srcOf(lang);
    if (src) attrs(el, src);
    if (src && isSegment(el, src)) { segment(el, src); return; }
    for (var n = el.firstChild, next; n; n = next) {
      next = n.nextSibling;
      if (n.nodeType === 3) { if (src && /\S/.test(n.nodeValue)) textNode(n, src); }
      else if (n.nodeType === 1) walk(n, lang);
    }
  }

  function run() {
    if (pageEn) {
      var t = look(norm(document.title), 'en', 'title');
      if (t !== null) document.title = t;
    }
    if (document.body) walk(document.body, pageLang);
    if (EXTRACT || !changed) return;
    // "the English text is the binding version" (license texts), only in translation
    if (ui !== 'en') {
      var only = document.querySelectorAll('[data-i18n-only]');
      for (var j = 0; j < only.length; j++) only[j].hidden = false;
    }
    if (pageEn) {
      html.setAttribute('lang', outLang);
      html.setAttribute('dir', outDir);
    } else {
      var shell = document.querySelectorAll('.appnav, .site-footer');
      for (var i = 0; i < shell.length; i++) {
        shell[i].setAttribute('lang', outLang);
        shell[i].setAttribute('dir', outDir);
      }
    }
  }

  // A language's name for screen readers beside its own name (/sedaha/ language
  // boxes: data-i18n-name) comes from the browser, which knows every language's name
  // in the visitor's language -- no dictionary needed for 113 names.
  function names() {
    if (EXTRACT || ui === 'en' || !window.Intl || !Intl.DisplayNames) return;
    var dn;
    try { dn = new Intl.DisplayNames([ui], {type: 'language'}); } catch (e) { return; }
    var spans = document.querySelectorAll('[data-i18n-name]');
    for (var i = 0; i < spans.length; i++) {
      var box = spans[i].closest('[lang]:not([data-i18n-name])');
      var code = box && box.getAttribute('lang');
      var n = null;
      try { n = code ? dn.of(code) : null; } catch (e) { n = null; }
      if (n && n.toLowerCase() !== code.toLowerCase()) {
        spans[i].textContent = ' — ' + n;
        spans[i].setAttribute('lang', ui);
      }
    }
  }

  function observe() {
    if (!window.MutationObserver || !document.body) return;
    new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        if (m.type === 'attributes') {
          var el = m.target;
          if (el.nodeType === 1 && !blocked(el)) { var s = srcOf(langAt(el)); if (s) attrs(el, s); }
          continue;
        }
        for (var j = 0; j < m.addedNodes.length; j++) {
          var n = m.addedNodes[j], p = n.parentNode;
          if (!p || blocked(p)) continue;
          if (n.nodeType === 3) {
            var src = srcOf(langAt(p));
            if (src && /\S/.test(n.nodeValue)) textNode(n, src);
          } else if (n.nodeType === 1) {
            walk(n, langAt(p));
          }
        }
      }
    }).observe(document.body, {childList: true, subtree: true, attributes: true,
                                attributeFilter: ATTRS});
  }

  // --- the language switch (markup: sync_appnav.py) ---------------------------
  function store(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function switcher() {
    var sw = document.querySelector('.langsw');
    if (!sw) return;
    var btn = sw.querySelector('.langsw-btn'), list = sw.querySelector('.langsw-list');
    var cur = sw.querySelector('.langsw-cur'), code = sw.querySelector('.langsw-code');
    var shown = EXTRACT ? 'en' : ui;
    var item = list.querySelector('[data-ui="' + shown + '"]');
    if (item) {
      item.setAttribute('aria-current', 'true');
      if (cur) {
        cur.textContent = item.textContent;
        cur.setAttribute('lang', item.getAttribute('lang'));
        cur.setAttribute('dir', item.getAttribute('dir'));
      }
      if (code) code.textContent = item.getAttribute('data-short') || shown.toUpperCase();
    }
    var word = look('Language', 'en', 'button.langsw-btn@aria-label') || 'Language';
    btn.setAttribute('aria-label', word + ': ' + (item ? item.textContent : 'English'));
    btn.setAttribute('title', word);
    function open(on) {
      list.hidden = !on;
      btn.setAttribute('aria-expanded', on ? 'true' : 'false');
      if (on) { var c = list.querySelector('[aria-current]') || list.querySelector('a'); if (c) c.focus(); }
    }
    btn.addEventListener('click', function (e) { e.stopPropagation(); open(list.hidden); });
    document.addEventListener('click', function (e) { if (!sw.contains(e.target)) open(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !list.hidden) { open(false); btn.focus(); }
    });
    list.addEventListener('click', function (e) {
      var a = e.target.closest('a[data-ui]');
      if (!a) return;
      e.preventDefault();
      store(a.getAttribute('data-ui'));
      // drop a preview ?ui= so the stored choice is what the reload shows
      var u = location.href.replace(/([?&])ui=[^&#]*&?/, '$1').replace(/[?&](#|$)/, '$1');
      if (u === location.href) location.reload(); else location.replace(u);
    });
  }

  function done() {
    html.classList.remove('i18n-wait');
    if (EXTRACT) {
      setTimeout(function () {
        var pre = document.createElement('pre');
        pre.id = 'i18n-extract';
        pre.hidden = true;
        pre.textContent = JSON.stringify(seen);
        document.body.appendChild(pre);
      }, 1500);
    }
  }

  try { run(); names(); } catch (e) { /* never leave a page hidden over a translation error */ }
  observe();
  try { switcher(); } catch (e) {}
  done();
})();
