/* Native guestbook for /comments/.

   Approved notes are read from the repository-owned JSON index. New notes go to
   a small intake endpoint which creates a private moderation issue; the browser
   never receives a GitHub credential and never renders visitor text as HTML. */
(function () {
  'use strict';

  var LANGS = (window.EDITIONS || []).slice();
  var ALIASES = window.LANG_ALIASES || {};
  var RTL = {ar:1, bal:1, ckb:1, fa:1, glk:1, he:1, lrc:1, mzn:1,
             prs:1, ps:1, sd:1, ug:1, ur:1, yi:1};
  var form = document.getElementById('guestbookForm');
  var languageInput = document.getElementById('guestbookLanguage');
  var languageList = document.getElementById('guestbookLanguages');
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

  function languageFromText(value) {
    var q = fold(value).trim();
    if (!q) return null;
    if (q === 'multilingual' || q === 'multiple languages') return languageRecord('mul');
    if (q === 'other') return languageRecord('und');
    var exact = LANGS.filter(function (L) {
      var names = [L.slug, L.lang, L.native, L.en].concat(String(ALIASES[L.slug] || '').split(' '));
      return names.some(function (name) { return fold(name) === q; });
    });
    return exact.length === 1 ? exact[0] : null;
  }

  function populateLanguagePicker() {
    if (!languageList) return;
    LANGS.slice().sort(function (a, b) { return a.en.localeCompare(b.en); })
      .concat([languageRecord('mul'), languageRecord('und')])
      .forEach(function (L) {
        var option = document.createElement('option');
        option.value = L.en;
        option.label = L.native === L.en ? L.en : L.native + ' · ' + L.en;
        languageList.appendChild(option);
      });

    var wanted = (navigator.languages || [navigator.language || 'en']);
    for (var i = 0; i < wanted.length; i++) {
      var tag = String(wanted[i]).toLowerCase();
      var match = LANGS.filter(function (L) {
        return L.lang.toLowerCase() === tag || L.slug.toLowerCase() === tag ||
          L.lang.toLowerCase().split('-')[0] === tag.split('-')[0];
      })[0];
      if (match) { languageInput.value = match.en; break; }
    }
  }

  function status(message, kind) {
    if (!formStatus) return;
    formStatus.textContent = message;
    formStatus.className = 'guestbook-form-status' + (kind ? ' is-' + kind : '');
    formStatus.hidden = !message;
  }

  function configureForm() {
    if (!form || !submit) return;
    if (!endpoint) {
      submit.disabled = true;
      status('The new writing desk is ready locally and will open when its private moderation endpoint is connected.', 'quiet');
    }

    languageInput.addEventListener('input', function () { languageInput.setCustomValidity(''); });
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (!endpoint || submit.disabled) return;
      var L = languageFromText(languageInput.value);
      if (!L) {
        languageInput.setCustomValidity('Choose a language from the list, Multilingual, or Other.');
        languageInput.reportValidity();
        return;
      }
      languageInput.setCustomValidity('');
      var payload = {
        name: form.elements.name.value.trim(),
        message: form.elements.message.value.trim(),
        language: L.lang,
        language_name: L.en,
        consent: form.elements.consent.checked,
        website: form.elements.website.value
      };
      submit.disabled = true;
      submit.textContent = 'Sending…';
      status('Passing your note into the private review queue…');
      fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (!response.ok || !data.ok) throw new Error(data.error || 'The note could not be sent.');
          return data;
        });
      }).then(function (data) {
        form.reset();
        populateDefaultLanguage();
        status(data.message || 'Your note is waiting for a quiet read-through before it appears here.', 'success');
      }).catch(function (error) {
        status(error.message || 'The note could not be sent. Please try again.', 'error');
      }).finally(function () {
        submit.disabled = false;
        submit.textContent = 'Leave it here';
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

  function populateDefaultLanguage() {
    if (!languageInput) return;
    languageInput.value = '';
    var wanted = (navigator.languages || [navigator.language || 'en']);
    for (var i = 0; i < wanted.length; i++) {
      var tag = String(wanted[i]).toLowerCase();
      var match = LANGS.filter(function (L) {
        return L.lang.toLowerCase() === tag || L.slug.toLowerCase() === tag ||
          L.lang.toLowerCase().split('-')[0] === tag.split('-')[0];
      })[0];
      if (match) { languageInput.value = match.en; return; }
    }
    languageInput.value = 'English';
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

  populateLanguagePicker();
  configureForm();
  load();
})();
