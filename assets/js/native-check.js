/* Native-speaker check pages (/sedaha/check/<slug>/, build_check_pages.py).

   One Send button posts the answered lines to the guestbook Worker's /check
   route, which files them for Amir in a private repository. No credential is in
   the browser. If sending fails for any reason (no connection, a refusal, a
   timeout, a Worker not yet redeployed), the page offers the same answers as a
   prefilled email instead, so an answer is never lost. Visitor text is never
   rendered as HTML.

   Two page formats (2026-11-25):
   - format 2 (data-format="2"): the simplified pages, all in the reader's language
     (the strings come from #ncStrings). Rows are grouped under numbered
     questions; a row's note box opens only on the answer that asks for it
     (data-note-on). After page 1 a pop-up invites the reader on; pages 2..n-1
     go straight to the next page, which says the answers arrived (?sent=N).
   - format 1: the older English pages, in rounds. */
(function () {
  'use strict';

  var form = document.getElementById('ncForm');
  if (!form) return;
  var send = document.getElementById('ncSend');
  var statusLine = document.getElementById('ncStatus');
  var thanks = document.getElementById('ncThanks');
  var fallback = document.getElementById('ncFallback');
  var mail = document.getElementById('ncMail');
  var shortened = document.getElementById('ncShort');
  var copy = document.getElementById('ncCopy');

  var V2 = form.getAttribute('data-format') === '2';
  var S = {};
  try {
    var blob = document.getElementById('ncStrings');
    if (blob) S = JSON.parse(blob.textContent) || {};
  } catch (error) { S = {}; }
  // the page's own text, or the English of the older pages
  function t(key, english, n) {
    var value = S[key] || english;
    return n === undefined ? value : value.replace('{n}', n);
  }

  var meta = document.querySelector('meta[name="native-check-endpoint"]');
  var endpoint = meta ? meta.content.trim() : '';
  // the same local arrangement as the guestbook: guestbook-worker/dev-server.mjs
  if (/^(?:localhost|127\.0\.0\.1)$/.test(location.hostname)) {
    endpoint = 'http://127.0.0.1:8787/check';
  }
  var EMAIL = (mail.getAttribute('href') || '').replace(/^mailto:/, '').split('?')[0];
  // Mail apps and browsers cut or refuse long mailto: links; about 2,000
  // characters is the length every one of them accepts.
  var MAILTO_LIMIT = 1900;
  var LANG = form.getAttribute('data-lang');
  var LANGUAGE = form.getAttribute('data-language');
  var VERSION = form.getAttribute('data-version');
  var VERDICT = {ok: t('correct', 'Correct'), change: t('needs_change', 'Needs change'),
                 unsure: t('not_sure', 'Not sure')};
  var ROUND = parseInt(form.getAttribute('data-round') || '1', 10) || 1;
  var PAGES = parseInt(form.getAttribute('data-pages') || '1', 10) || 1;
  var BASE = form.getAttribute('data-base') || '';
  var SEND_LABEL = send.textContent;

  // The rounds (pages) this browser has sent, per language: {"1": "<page version>", ...}.
  // Only on this device; storage may be blocked, and then nothing is remembered.
  // The simplified pages keep their own list, so an old round never ticks a new page.
  var SENT_KEY = (V2 ? 'nc-sent2:' : 'nc-sent:') + LANG;

  function readSent() {
    try {
      var value = JSON.parse(localStorage.getItem(SENT_KEY) || '{}');
      return value && typeof value === 'object' ? value : {};
    } catch (error) {
      return {};
    }
  }

  function markSent() {
    var sent = readSent();
    sent[ROUND] = VERSION;
    try { localStorage.setItem(SENT_KEY, JSON.stringify(sent)); } catch (error) { /* not kept */ }
  }

  // the first round not yet sent from here, after this one if there is one
  function nextUnsent(total) {
    var sent = readSent();
    for (var n = ROUND + 1; n <= total; n++) if (!sent[n]) return n;
    for (var m = 1; m < ROUND; m++) if (!sent[m]) return m;
    return 0;
  }

  function roundHref(base, n) {
    return base + (n > 1 ? n + '/' : '');
  }

  // Tick the sent rounds in the strip; on a round already sent (this version),
  // offer the next one instead of the same lines again. No automatic jump: a
  // link someone shared still opens the round it names.
  function showRounds() {
    var sent = readSent();
    var marks = document.querySelectorAll('#ncRounds [data-round]');
    for (var i = 0; i < marks.length; i++) {
      var n = marks[i].getAttribute('data-round');
      if (sent[n] && !marks[i].hasAttribute('data-sent')) {
        marks[i].setAttribute('data-sent', '');
        marks[i].textContent = n + ' ✓';
      }
    }
    var box = document.getElementById('ncResume');
    if (!box || sent[ROUND] !== VERSION) return;
    var total = parseInt(box.getAttribute('data-total'), 10) || 1;
    var next = nextUnsent(total);
    var text = document.getElementById('ncResumeText');
    var link = document.getElementById('ncResumeLink');
    if (next) {
      text.textContent = t('already_sent', 'You have already sent this round from this device. Thank you!');
      link.href = roundHref(box.getAttribute('data-base'), next);
      link.textContent = (V2 ? t('continue_with', '', next) : 'Continue with round ' + next) + ' →';
      link.hidden = false;
    } else {
      text.textContent = t('all_done', 'You have sent every round from this device. Thank you for all of them!');
      link.hidden = true;
    }
    box.hidden = false;
  }

  function say(message, kind) {
    statusLine.textContent = message;
    statusLine.className = 'guestbook-form-status' + (kind ? ' is-' + kind : '');
    statusLine.hidden = !message;
  }

  function validEndpoint(value) {
    try {
      var url = new URL(value);
      return /\/check$/.test(url.pathname) && (url.protocol === 'https:' ||
        (url.protocol === 'http:' && /^(?:localhost|127\.0\.0\.1)$/.test(url.hostname)));
    } catch (error) {
      return false;
    }
  }

  // A row's note counts only while its box is open (format 2 closes it when the
  // reader changes their answer).
  function noteOf(item) {
    var box = item.querySelector('textarea');
    if (!box) return '';
    var holder = item.querySelector('.nc-notebox');
    if (holder && holder.hidden) return '';
    return box.value.trim();
  }

  // The answered lines, in page order. A note on a line with no answer is not
  // dropped silently: the reader is asked to choose for it.
  function collect() {
    var items = form.querySelectorAll('.nc-item');
    var out = [];
    for (var i = 0; i < items.length; i++) {
      var picked = items[i].querySelector('input[type="radio"]:checked');
      var note = noteOf(items[i]);
      if (!picked) {
        if (note) {
          return {error: V2 ? t('note_no_answer', '') : 'Line ' + (i + 1) + ' has a note: please ' +
            'choose Correct, Needs change or Not sure for it too.', focus: items[i].querySelector('input')};
        }
        continue;
      }
      var answer = {id: items[i].getAttribute('data-id'), verdict: picked.value};
      if (note) answer.note = note;
      out.push(answer);
    }
    return {items: out};
  }

  // by code point, so an emoji is never cut in half (encodeURIComponent would throw)
  function clip(text, size) {
    var chars = Array.from(text);
    if (chars.length <= size) return text;
    return size > 0 ? chars.slice(0, size).join('') + '…' : '[shortened]';
  }

  function plainText(payload, size) {
    var lines = ['Native check: ' + LANGUAGE + ' (' + LANG + '), page version ' + VERSION];
    if (payload.name) lines.push('From: ' + payload.name);
    if (payload.thanks) lines.push('May be listed on the Thanks page: yes');
    lines.push('');
    payload.items.forEach(function (a) {
      lines.push(a.id + ': ' + a.verdict);
      if (a.note) lines.push('  Note: ' + clip(a.note, size).replace(/\s*\n\s*/g, ' / '));
    });
    return lines.join('\r\n');
  }

  // The longest mailto: link within MAILTO_LIMIT: every answer, with notes cut to
  // a common length only when they do not all fit.
  function mailtoFor(payload) {
    var head = 'mailto:' + EMAIL + '?subject=' +
      encodeURIComponent('Native check: ' + LANGUAGE + ' (' + payload.items.length +
        (payload.items.length === 1 ? ' answer)' : ' answers)')) + '&body=';
    var href = function (size) { return head + encodeURIComponent(plainText(payload, size)); };
    var full = href(Infinity);
    if (full.length <= MAILTO_LIMIT) return {href: full, cut: false};
    var low = 0, high = 600;
    while (low < high) {
      var mid = Math.ceil((low + high) / 2);
      if (href(mid).length <= MAILTO_LIMIT) low = mid; else high = mid - 1;
    }
    var best = href(low);
    if (best.length > MAILTO_LIMIT) {
      // too many answers even without notes: keep as many whole lines as fit
      var keep = payload.items.slice();
      while (keep.length > 1 && best.length > MAILTO_LIMIT) {
        keep.pop();
        best = head + encodeURIComponent(plainText({name: payload.name, thanks: payload.thanks,
          items: keep}, 0) +
          '\r\n(more answers: see the full text on the page)');
      }
    }
    return {href: best, cut: true};
  }

  function offerEmail(payload, message) {
    var link = mailtoFor(payload);
    mail.href = link.href;
    shortened.hidden = !link.cut;
    copy.hidden = !link.cut;
    copy.value = link.cut ? plainText(payload, Infinity) : '';
    fallback.hidden = false;
    say(message + ' ' + t('use_email', 'Please use the email button below.'), 'error');
  }

  // ---- format 2: after a page is sent ----------------------------------------------------
  var pop = document.getElementById('ncPop');
  var popGo = document.getElementById('ncPopGo');

  function closePop() {
    if (!pop || pop.hidden) return;
    pop.hidden = true;
    thanks.focus();
  }

  if (pop) {
    pop.addEventListener('click', function (event) { if (event.target === pop) closePop(); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closePop();
    });
  }

  function afterSendV2() {
    markSent();
    showRounds();
    var box = document.getElementById('ncResume');
    if (box) box.hidden = true;
    if (ROUND > 1 && ROUND < PAGES) {
      // straight on; the next page says the answers arrived
      location.href = roundHref(BASE, ROUND + 1) + '?sent=' + ROUND;
      return;
    }
    form.hidden = true;
    say('', '');
    var more = document.getElementById('ncThanksMore');
    var nextLink = document.getElementById('ncNext');
    var next = nextUnsent(PAGES);
    if (nextLink) {
      if (next) {
        nextLink.href = roundHref(BASE, next) + '?sent=' + ROUND;
        nextLink.textContent = t('continue_with', '', next) + ' →';
      } else {
        nextLink.parentNode.hidden = true;
      }
    } else if (next && more) {
      // the last page, with an earlier page not yet sent from here
      var a = document.createElement('a');
      a.href = roundHref(BASE, next);
      a.className = 'btn btn-primary';
      a.textContent = t('continue_with', '', next) + ' →';
      more.textContent = '';
      more.appendChild(a);
      more.hidden = false;
    }
    if (!next && more && PAGES > 1) {
      more.textContent = t('all_done', '');
      more.hidden = false;
    }
    thanks.hidden = false;
    if (ROUND === 1 && pop && next === 2) {
      pop.hidden = false;
      if (popGo) popGo.focus();
    } else {
      thanks.focus();
    }
  }

  // "Thank you, your answers from page N arrived." on the page that follows
  function showArrived() {
    var line = document.getElementById('ncArrived');
    var match = /[?&]sent=(\d+)/.exec(location.search);
    if (!line || !match) return;
    line.textContent = t('arrived', '', match[1]);
    line.hidden = false;
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (error) { /* stays */ }
  }

  function afterSendV1() {
    markSent();
    showRounds();
    var nextLink = document.getElementById('ncNext');
    var box = document.getElementById('ncResume');
    if (nextLink && box) {
      var next = nextUnsent(parseInt(box.getAttribute('data-total'), 10) || 1);
      if (next) {
        nextLink.href = roundHref(box.getAttribute('data-base'), next);
        nextLink.textContent = 'More lines: round ' + next + ' →';
      } else {
        nextLink.parentNode.textContent = 'You have sent every round. Thank you for all of them.';
      }
    }
    if (box) box.hidden = true;
    form.hidden = true;
    say('', '');
    thanks.hidden = false;
    thanks.focus();
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (send.disabled) return;
    var got = collect();
    if (got.error) {
      say(got.error, 'error');
      if (got.focus) got.focus.focus();
      return;
    }
    if (!got.items.length) {
      say(t('need_one', 'Choose Correct, Needs change or Not sure for at least one line.'), 'error');
      return;
    }
    var payload = {lang: LANG, page_version: VERSION, items: got.items,
                   website: form.elements.website.value};
    var nameField = form.elements.name;
    var name = nameField ? nameField.value.trim() : '';
    if (name) payload.name = name;
    // the Thanks-page tick needs a name to list
    var listMe = form.elements.thanks;
    if (listMe && listMe.checked) {
      if (!name) {
        say(t('name_needed', 'Add the name you would like listed, or untick the Thanks-page box.'), 'error');
        nameField.focus();
        return;
      }
      payload.thanks = true;
    }
    fallback.hidden = true;
    if (!validEndpoint(endpoint)) {
      offerEmail(payload, t('not_connected', 'Sending is not connected yet.'));
      return;
    }

    send.disabled = true;
    send.textContent = t('sending', 'Sending…');
    say(t('sending', 'Sending your answers…'), 'quiet');
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
          throw new Error(data.error || t('cannot_send', 'The answers could not be sent just now.'));
        }
        return data;
      });
    }).then(function () {
      if (V2) afterSendV2(); else afterSendV1();
    }).catch(function (error) {
      offerEmail(payload, timedOut ? t('too_long', 'Sending took too long.') :
        error instanceof TypeError ? t('cannot_send', 'The answers could not be sent from here.') :
        (error.message || t('cannot_send', 'The answers could not be sent just now.')));
    }).finally(function () {
      if (timer) clearTimeout(timer);
      send.disabled = false;
      send.textContent = SEND_LABEL;
    });
  });

  // Format 2: the note box opens on the answer that asks for the reader's words
  // (data-note-on: "change" for most rows, "ok" for the sayings: "I can guess it"
  // asks what it means). Format 1: "Needs change" lights the note box up.
  function onAnswer(radio) {
    var item = radio.closest('.nc-item');
    if (!item) return;
    if (V2) {
      var holder = item.querySelector('.nc-notebox');
      if (holder) holder.hidden = !(radio.checked && radio.value === item.getAttribute('data-note-on'));
      return;
    }
    var note = item.querySelector('textarea');
    if (!note) return;
    var on = radio.value === 'change' && radio.checked;
    var optional = item.querySelector('.nc-optional');
    note.style.borderColor = on ? 'var(--accent)' : '';
    note.style.boxShadow = on ? '0 0 0 2px var(--accent)' : '';
    note.placeholder = on ? 'How would you say it? Write it here.' : '';
    if (optional) optional.hidden = on;
  }
  form.addEventListener('change', function (event) {
    if (event.target.type === 'radio') onAnswer(event.target);
  });
  Array.prototype.forEach.call(form.querySelectorAll('.nc-verdict input:checked'), onAnswer);
  showRounds();
  if (V2) showArrived();

  // As on the guestbook: on a phone the tab bar steps aside while a field is in use.
  var settle;
  form.addEventListener('focusin', function (event) {
    if (!/^(INPUT|TEXTAREA)$/.test(event.target.tagName) || event.target.type === 'radio') return;
    clearTimeout(settle);
    document.body.classList.add('is-typing');
  });
  form.addEventListener('focusout', function () {
    clearTimeout(settle);
    settle = setTimeout(function () { document.body.classList.remove('is-typing'); }, 180);
  });
})();
