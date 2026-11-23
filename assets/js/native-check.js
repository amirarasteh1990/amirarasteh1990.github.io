/* Native-speaker check pages (/sedaha/check/<slug>/, build_check_pages.py).

   One Send button posts the answered lines to the guestbook Worker's /check
   route, which files them as one GitHub issue for Amir. No credential is in the
   browser. If sending fails for any reason (no connection, a refusal, a timeout,
   a Worker not yet redeployed), the page offers the same answers as a prefilled
   email instead, so an answer is never lost. Visitor text is never rendered as
   HTML. */
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
  var VERDICT = {ok: 'Correct', change: 'Needs change', unsure: 'Not sure'};

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

  // The answered lines, in page order. A note on a line with no answer is not
  // dropped silently: the reader is asked to choose for it.
  function collect() {
    var items = form.querySelectorAll('.nc-item');
    var out = [];
    for (var i = 0; i < items.length; i++) {
      var picked = items[i].querySelector('input[type="radio"]:checked');
      var box = items[i].querySelector('textarea');
      var note = box ? box.value.trim() : '';
      if (!picked) {
        if (note) {
          return {error: 'Line ' + (i + 1) + ' has a note: please choose Correct, ' +
            'Needs change or Not sure for it too.', focus: items[i].querySelector('input')};
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
      lines.push(a.id + ': ' + VERDICT[a.verdict]);
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
    say(message + ' Please use the email button below.', 'error');
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
      say('Choose Correct, Needs change or Not sure for at least one line.', 'error');
      return;
    }
    var payload = {lang: LANG, page_version: VERSION, items: got.items,
                   website: form.elements.website.value};
    var name = form.elements.name.value.trim();
    if (name) payload.name = name;
    // the Thanks-page tick needs a name to list
    var listMe = form.elements.thanks;
    if (listMe && listMe.checked) {
      if (!name) {
        say('Add the name you would like listed, or untick the Thanks-page box.', 'error');
        form.elements.name.focus();
        return;
      }
      payload.thanks = true;
    }
    fallback.hidden = true;
    if (!validEndpoint(endpoint)) {
      offerEmail(payload, 'Sending is not connected yet.');
      return;
    }

    send.disabled = true;
    send.textContent = 'Sending…';
    say('Sending your answers…', 'quiet');
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
          throw new Error(data.error || 'The answers could not be sent just now.');
        }
        return data;
      });
    }).then(function () {
      form.hidden = true;
      say('', '');
      thanks.hidden = false;
      thanks.focus();
    }).catch(function (error) {
      offerEmail(payload, timedOut ? 'Sending took too long.' :
        error instanceof TypeError ? 'The answers could not be sent from here.' :
        (error.message || 'The answers could not be sent just now.'));
    }).finally(function () {
      if (timer) clearTimeout(timer);
      send.disabled = false;
      send.textContent = 'Send';
    });
  });

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
