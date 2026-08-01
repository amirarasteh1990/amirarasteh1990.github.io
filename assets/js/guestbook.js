/* Native guestbook for /comments/.

   Approved notes are read from the repository-owned JSON index. New notes are
   handed to GitHub as pre-filled public issues; no write credential is present in
   the browser. Approved issue data is copied into the index by GitHub Actions.
   Visitor text is never rendered as HTML on this page. */
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
  var repositoryMeta = document.querySelector('meta[name="guestbook-repository"]');
  var repository = repositoryMeta ? repositoryMeta.content.trim() : '';
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

  function escapeHtml(value) {
    return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function base64url(value) {
    var bytes = new TextEncoder().encode(value);
    var binary = '';
    for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function submissionId(now) {
    var random = window.crypto && typeof window.crypto.randomUUID === 'function'
      ? window.crypto.randomUUID().slice(0, 8)
      : Math.random().toString(36).slice(2, 10).padEnd(8, '0');
    return now.toISOString().slice(0, 10) + '-' + random;
  }

  function issueUrl(note) {
    var metadata = {
      id: note.id,
      language: note.language,
      language_name: note.language_name,
      audience: 'public',
      submitted_at: note.submitted_at
    };
    var marker = base64url(JSON.stringify(metadata));
    var body = '<!-- guestbook-submission:v2 ' + marker + ' -->\n\n' +
      '## Name or pen name\n\n<pre>' + escapeHtml(note.name) + '</pre>\n\n' +
      '## Language (automatic)\n\n' + escapeHtml(note.language_name) +
      ' (`' + note.language + '`)\n\n' +
      '## Reader note\n\n<pre>' + escapeHtml(note.message) + '</pre>\n\n' +
      '---\nSubmitted through https://arasteh.art/comments/. ' +
      'Amir can add the `approved` label to publish this note.';
    var url = new URL('https://github.com/' + repository + '/issues/new');
    url.searchParams.set('title', 'Reader note from ' + note.name);
    url.searchParams.set('body', body);
    url.searchParams.set('labels', 'guestbook,pending,shareable');
    return url.toString();
  }

  function configureForm() {
    if (!form || !submit) return;
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
      submit.disabled = true;
      status('The GitHub guestbook repository is not configured.', 'error');
      return;
    }
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (submit.disabled) return;
      if (form.elements.website.value) {
        status('The note could not be prepared.', 'error');
        return;
      }
      var L = preferredLanguage();
      var now = new Date();
      var note = {
        id: submissionId(now),
        name: form.elements.name.value.trim(),
        message: form.elements.message.value.trim(),
        language: L.lang,
        language_name: L.en,
        submitted_at: now.toISOString()
      };
      if (!note.name || !note.message) {
        status('Add your name and note before continuing.', 'error');
        return;
      }
      var target = issueUrl(note);
      if (target.length > 7500) {
        status('This note is too long for GitHub\'s handoff. Please shorten it slightly.', 'error');
        return;
      }
      status('Opening GitHub so you can review and submit this public note.', 'quiet');
      location.assign(target);
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
        allEntries = Array.isArray(data.entries) ? data.entries : [];
        populateFilter(allEntries);
        renderFeatured();
        tools.hidden = !allEntries.length;
        render();
      }).catch(function () {
        allEntries = [];
        tools.hidden = true;
        empty.hidden = false;
        empty.textContent = 'The reader notes could not be opened just now. Please try again later.';
        count.textContent = '';
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
