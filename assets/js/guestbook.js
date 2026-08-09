/* Native guestbook for /comments/.

   Published notes are read from the repository-owned JSON index. New notes are
   posted through a small Cloudflare intake endpoint; no write credential is
   present in the browser. Confirmed notes appear at once while GitHub Actions
   copies them into the permanent index. Visitor text is never rendered as HTML. */
(function () {
  'use strict';

  var LANGS = (window.EDITIONS || []).slice();
  var RTL = {ar:1, bal:1, ckb:1, fa:1, glk:1, he:1, lrc:1, mzn:1,
             prs:1, ps:1, sd:1, ug:1, ur:1, yi:1};
  var form = document.getElementById('guestbookForm');
  var formStatus = document.getElementById('guestbookFormStatus');
  var submit = document.getElementById('guestbookSubmit');
  var search = document.getElementById('guestbookSearch');
  var languageFilter = document.getElementById('guestbookLanguageFilter');
  var sort = document.getElementById('guestbookSort');
  var tools = document.getElementById('guestbookTools');
  var count = document.getElementById('guestbookCount');
  var list = document.getElementById('guestbookEntries');
  var empty = document.getElementById('guestbookEmpty');
  var loadMore = document.getElementById('guestbookMore');
  var featuredSection = document.getElementById('guestbookFeatured');
  var featuredList = document.getElementById('guestbookFeaturedEntries');
  var endpointMeta = document.querySelector('meta[name="guestbook-endpoint"]');
  var endpoint = endpointMeta ? endpointMeta.content.trim() : '';
  if (/^(?:localhost|127\.0\.0\.1)$/.test(location.hostname)) {
    endpoint = 'http://127.0.0.1:8787/';
  }
  var PENDING_KEY = 'arasteh-guestbook-pending-v1';
  var PENDING_TTL = 24 * 60 * 60 * 1000;
  var allEntries = [];
  var shown = 12;

  var LETTERS = {'ø':'o','æ':'ae','ß':'ss','đ':'d','ð':'d',
                 'þ':'th','ł':'l','ı':'i','œ':'oe','’':"'"};
  function fold(value) {
    var s = String(value || '').toLowerCase()
      .replace(/[øæßđðþłıœ’]/g, function (c) { return LETTERS[c]; });
    return s.normalize ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '') : s;
  }

  function languageRecord(code) {
    code = String(code || '').toLowerCase();
    if (code === 'mul') return {slug:'mul', lang:'mul', native:'Multilingual', en:'Multilingual'};
    if (code === 'und') return {slug:'und', lang:'und', native:'Other', en:'Other'};
    for (var i = 0; i < LANGS.length; i++) {
      if (LANGS[i].slug.toLowerCase() === code || LANGS[i].lang.toLowerCase() === code) return LANGS[i];
    }
    return {slug:code, lang:code || 'und', native:code || 'Other', en:code || 'Other', rtl:RTL[code]};
  }

  function preferredLanguage() {
    var wanted = (navigator.languages || [navigator.language || 'en']);
    for (var i = 0; i < wanted.length; i++) {
      var tag = String(wanted[i]).toLowerCase();
      var match = LANGS.filter(function (L) {
        return L.lang.toLowerCase() === tag || L.slug.toLowerCase() === tag ||
          L.lang.toLowerCase().split('-')[0] === tag.split('-')[0];
      })[0];
      if (match) return match;
    }
    return languageRecord('und');
  }

  function status(message, kind) {
    if (!formStatus) return;
    formStatus.textContent = message;
    formStatus.className = 'guestbook-form-status' + (kind ? ' is-' + kind : '');
    formStatus.hidden = !message;
  }

  function validEndpoint(value) {
    try {
      var url = new URL(value);
      return url.protocol === 'https:' || (url.protocol === 'http:' &&
        /^(?:localhost|127\.0\.0\.1)$/.test(url.hostname));
    } catch (error) {
      return false;
    }
  }

  function normalizedEntry(raw, pending) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    var values = ['id', 'name', 'message', 'language', 'language_name', 'published'];
    for (var i = 0; i < values.length; i++) {
      if (typeof raw[values[i]] !== 'string') return null;
    }
    if (!/^\d{4}-\d{2}-\d{2}-[a-z0-9-]{6,64}$/.test(raw.id) ||
        !/^\d{4}-\d{2}-\d{2}$/.test(raw.published) ||
        !/^(?:[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*|mul|und)$/.test(raw.language) ||
        !raw.name || raw.name.length > 80 || !raw.message || raw.message.length > 3000 ||
        !raw.language_name || raw.language_name.length > 80) return null;
    return {
      id: raw.id,
      name: raw.name,
      message: raw.message,
      language: raw.language,
      language_name: raw.language_name,
      published: raw.published,
      featured: raw.featured === true,
      _pending: pending === true
    };
  }

  function readPending() {
    try {
      var raw = JSON.parse(localStorage.getItem(PENDING_KEY) || '[]');
      if (!Array.isArray(raw)) return [];
      var cutoff = Date.now() - PENDING_TTL;
      return raw.map(function (record) {
        var entry = record && normalizedEntry(record.entry, true);
        return entry && Number(record.saved_at) >= cutoff
          ? {entry: entry, saved_at: Number(record.saved_at)} : null;
      }).filter(Boolean);
    } catch (error) {
      return [];
    }
  }

  function writePending(records) {
    try { localStorage.setItem(PENDING_KEY, JSON.stringify(records)); }
    catch (error) { /* The public archive still works when storage is unavailable. */ }
  }

  function rememberPending(entry) {
    var records = readPending().filter(function (record) {
      return record.entry.id !== entry.id;
    });
    records.unshift({entry: entry, saved_at: Date.now()});
    writePending(records.slice(0, 5));
  }

  function mergeEntries(published) {
    var clean = (Array.isArray(published) ? published : []).map(function (entry) {
      return normalizedEntry(entry, false);
    }).filter(Boolean);
    var ids = {};
    clean.forEach(function (entry) { ids[entry.id] = true; });
    var pending = readPending().filter(function (record) { return !ids[record.entry.id]; });
    writePending(pending);
    return pending.map(function (record) { return record.entry; }).concat(clean);
  }

  function addConfirmedEntry(raw) {
    var entry = normalizedEntry(raw, true);
    if (!entry) throw new Error('Posting was confirmed without a readable note.');
    rememberPending(entry);
    allEntries = [entry].concat(allEntries.filter(function (old) {
      return old.id !== entry.id;
    }));
    populateFilter(allEntries);
    renderFeatured();
    tools.hidden = false;
    shown = 12;
    render();
  }

  function configureForm() {
    if (!form || !submit) return;
    if (!validEndpoint(endpoint)) {
      submit.disabled = true;
      status('The comment box is not connected yet.', 'error');
      return;
    }
    submit.disabled = false;
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (submit.disabled) return;
      if (form.elements.website.value) {
        status('The note could not be posted.', 'error');
        return;
      }
      var L = preferredLanguage();
      var payload = {
        name: form.elements.name.value.trim(),
        message: form.elements.message.value.trim(),
        language: L.lang,
        language_name: L.en,
        website: form.elements.website.value
      };
      if (!payload.name || !payload.message) {
        status('Add your name and comment before posting.', 'error');
        return;
      }
      submit.disabled = true;
      submit.textContent = 'Posting\u2026';
      status('Posting your comment\u2026', 'quiet');
      var controller = typeof AbortController === 'function' ? new AbortController() : null;
      var timedOut = false;
      var timer = controller ? setTimeout(function () {
        timedOut = true;
        controller.abort();
      }, 20000) : null;
      fetch(endpoint, {
        method: 'POST',
        mode: 'cors',
        credentials: 'omit',
        cache: 'no-store',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
        signal: controller ? controller.signal : undefined
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (!response.ok || data.ok !== true || data.posted !== true) {
            throw new Error(data.error || 'The comment could not be posted just now.');
          }
          return data;
        });
      }).then(function (data) {
        addConfirmedEntry(data.entry);
        form.reset();
        status(data.message || 'Posted. Amir has been notified.', 'success');
      }).catch(function (error) {
        status(timedOut ? 'Posting took too long. Please try again.' :
          (error.message || 'The comment could not be posted just now.'), 'error');
      }).finally(function () {
        if (timer) clearTimeout(timer);
        submit.disabled = false;
        submit.textContent = 'Post';
      });
    });

    var settle;
    form.addEventListener('focusin', function (event) {
      if (!/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
      clearTimeout(settle);
      document.body.classList.add('is-typing');
    });
    form.addEventListener('focusout', function () {
      clearTimeout(settle);
      settle = setTimeout(function () { document.body.classList.remove('is-typing'); }, 180);
    });
  }

  function dateLabel(value) {
    var date = new Date(value + 'T12:00:00Z');
    if (isNaN(date.getTime())) return value;
    try { return new Intl.DateTimeFormat('en', {dateStyle:'medium', timeZone:'UTC'}).format(date); }
    catch (e) { return value; }
  }

  function card(entry, featured) {
    var L = languageRecord(entry.language);
    var article = document.createElement('article');
    article.className = 'guestbook-card' + (featured ? ' is-featured' : '');
    article.setAttribute('lang', entry.language === 'und' || entry.language === 'mul' ? 'en' : entry.language);
    article.setAttribute('dir', L.rtl || RTL[String(entry.language).split('-')[0]] ? 'rtl' : 'auto');

    var message = document.createElement('blockquote');
    message.className = 'guestbook-message';
    message.textContent = entry.message;
    article.appendChild(message);

    var footer = document.createElement('footer');
    footer.className = 'guestbook-card-meta';
    var name = document.createElement('cite');
    name.textContent = entry.name;
    footer.appendChild(name);
    var details = document.createElement('span');
    details.className = 'guestbook-card-details';
    details.lang = 'en';
    details.dir = 'ltr';
    var language = document.createElement('span');
    language.className = 'guestbook-card-language';
    language.textContent = entry.language_name || L.en;
    details.appendChild(language);
    details.appendChild(document.createTextNode(' · '));
    var time = document.createElement('time');
    time.dateTime = entry.published;
    time.textContent = dateLabel(entry.published);
    details.appendChild(time);
    if (entry._pending) {
      details.appendChild(document.createTextNode(' \u00b7 '));
      var pending = document.createElement('span');
      pending.className = 'guestbook-card-pending';
      pending.textContent = 'Publishing';
      details.appendChild(pending);
    }
    footer.appendChild(details);
    article.appendChild(footer);
    return article;
  }

  function populateFilter(entries) {
    if (!languageFilter) return;
    var old = languageFilter.value;
    var codes = {};
    entries.forEach(function (entry) { codes[entry.language] = entry.language_name; });
    languageFilter.textContent = '';
    var all = document.createElement('option');
    all.value = '';
    all.textContent = 'All languages';
    languageFilter.appendChild(all);
    Object.keys(codes).sort(function (a, b) {
      return String(codes[a]).localeCompare(String(codes[b]));
    }).forEach(function (code) {
      var option = document.createElement('option');
      option.value = code;
      option.textContent = codes[code] || languageRecord(code).en;
      languageFilter.appendChild(option);
    });
    languageFilter.value = codes[old] ? old : '';
  }

  function filtered() {
    var q = fold(search && search.value).trim();
    var lang = languageFilter ? languageFilter.value : '';
    var entries = allEntries.filter(function (entry) {
      var inLanguage = !lang || entry.language === lang;
      var hay = fold([entry.name, entry.message, entry.language_name, entry.language].join(' '));
      return inLanguage && (!q || hay.indexOf(q) !== -1);
    });
    entries.sort(function (a, b) {
      var order = (a.published + a.id).localeCompare(b.published + b.id);
      return sort && sort.value === 'oldest' ? order : -order;
    });
    return entries;
  }

  function renderFeatured() {
    var entries = allEntries.filter(function (entry) { return entry.featured; }).slice(0, 3);
    featuredList.textContent = '';
    entries.forEach(function (entry) { featuredList.appendChild(card(entry, true)); });
    featuredSection.hidden = !entries.length;
  }

  function render() {
    var entries = filtered();
    list.textContent = '';
    entries.slice(0, shown).forEach(function (entry) { list.appendChild(card(entry, false)); });
    empty.hidden = entries.length !== 0;
    count.textContent = entries.length === 1 ? 'One reader note' : entries.length + ' reader notes';
    loadMore.hidden = entries.length <= shown;
  }

  function load() {
    fetch('/assets/data/guestbook.json', {cache:'no-store'})
      .then(function (response) {
        if (!response.ok) throw new Error('The reader notes could not be opened.');
        return response.json();
      }).then(function (data) {
        allEntries = mergeEntries(data.entries);
        populateFilter(allEntries);
        renderFeatured();
        tools.hidden = !allEntries.length;
        render();
      }).catch(function () {
        allEntries = mergeEntries([]);
        if (allEntries.length) {
          populateFilter(allEntries);
          tools.hidden = false;
          render();
        } else {
          tools.hidden = true;
          empty.hidden = false;
          empty.textContent = 'The reader notes could not be opened just now. Please try again later.';
          count.textContent = '';
        }
      });
  }

  [search, languageFilter, sort].forEach(function (control) {
    if (!control) return;
    control.addEventListener(control === search ? 'input' : 'change', function () {
      shown = 12;
      render();
    });
  });
  if (loadMore) loadMore.addEventListener('click', function () { shown += 12; render(); });

  configureForm();
  load();
})();
