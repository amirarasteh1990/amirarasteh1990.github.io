/* Account-free intake for the arasteh.art guestbook, and for the native-speaker
   check pages (/sedaha/check/<slug>/).

   POST /       one public guestbook note -> a `guestbook` issue the publishing
                workflow turns into an entry.
   POST /check  a native speaker's answers -> one `native-check` issue for Amir.
                It never carries the guestbook marker or label, so the
                guestbook workflow leaves it alone.
   GET  /dl/<release>/<file>
                a book or painting download: records one event in the
                DOWNLOADS store (time, file, country, network owner, kind of
                client, referring site) and redirects to the GitHub release
                asset, which GitHub still counts. No IP address is stored.
   GET  /dl-stats?day=YYYY-MM-DD
                that day's events, for download_log.py; needs the STATS_KEY
                secret as a Bearer token.

   Both validate, rate-limit a salted hash of the source address, and create a
   GitHub issue. The issue-only credential never reaches the browser. Raw IP
   addresses and email addresses are not stored or logged by this code. A
   download event keeps the client's own self-description (its user agent, cut
   to 160 characters) only so robots can be told from readers. */

const MAX_BODY_BYTES = 8192;
// A full check: up to 40 answers with 600-character notes, which in a three-byte
// script (Devanagari, Bengali, Thai...) is about 72 KB of UTF-8.
const MAX_CHECK_BYTES = 98304;
const GITHUB_API_VERSION = '2026-03-10';
const CONTROL_CHARACTERS = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/;
const LANGUAGE = /^(?:[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*|mul|und)$/;
const CHECK_MARKER = '<!-- native-check:v1 -->';
const CHECK_SLUG = /^[a-z]{2,3}(?:-[a-z]{2,4})?$/;
const CHECK_VERSION = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,39}$/;
const CHECK_ID = /^[A-Za-z0-9][A-Za-z0-9_./#-]{0,79}$/;
const VERDICTS = {ok: 'Correct', change: 'Needs change', unsure: 'Not sure'};

// Downloads: only these releases, only plain file names, so /dl/ can never be
// turned into a redirect to somewhere else.
const DL_RELEASES = new Set(['books', 'paintings', 'first-edition-1.0']);
const DL_FILE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.(?:pdf|epub|jpg|jpeg|zip)$/;
const DL_PATH = /^\/dl\/([^/]+)\/([^/]+)$/;
const DL_KEEP_SECONDS = 400 * 86400;
const STATS_DAY = /^\d{4}-\d{2}-\d{2}$/;
const BOT_AGENT = /bot|crawl|spider|slurp|archiv|preview|fetch|scan|monitor|curl|wget|python|httpclient|okhttp|go-http|java\/|libwww|headless|lighthouse|facebookexternalhit|whatsapp|telegram|discord|slack|embedly|validator|checker|scrap/i;

function clientKind(agent) {
  if (!agent) return 'none';
  if (BOT_AGENT.test(agent)) return 'bot';
  if (/^Mozilla\/|^Opera\//.test(agent)) return 'browser';
  return 'other';
}

function plain(value, maximum) {
  return String(value || '').replace(/[\u0000-\u001f\u007f]/g, ' ').slice(0, maximum);
}

function referringSite(referer) {
  if (!referer) return '';
  try {
    return plain(new URL(referer).host, 80);
  } catch {
    return '?';
  }
}

function sameSecret(given, expected) {
  // constant time over the expected length, so the key cannot be guessed byte by byte
  const a = String(given || '');
  const b = String(expected || '').trim();
  if (!b) return false;
  let diff = a.length ^ b.length;
  for (let i = 0; i < b.length; i += 1) diff |= (a.charCodeAt(i) || 0) ^ b.charCodeAt(i);
  return diff === 0;
}

async function recordDownload(request, env, release, file) {
  if (!env.DOWNLOADS || typeof env.DOWNLOADS.put !== 'function') return;
  const cf = request.cf || {};
  const agent = request.headers.get('User-Agent') || '';
  const metadata = {
    r: release,
    a: file,
    m: request.method,
    c: plain(cf.country, 4),
    o: plain(cf.asOrganization, 60),
    n: Number.isInteger(cf.asn) ? cf.asn : 0,
    k: clientKind(agent),
    u: plain(agent, 160),
    f: referringSite(request.headers.get('Referer'))
  };
  const random = crypto.getRandomValues(new Uint8Array(4));
  const tag = Array.from(random, b => b.toString(16).padStart(2, '0')).join('');
  await env.DOWNLOADS.put('ev:' + new Date().toISOString() + ':' + tag, '',
    {metadata, expirationTtl: DL_KEEP_SECONDS});
}

async function download(request, env, ctx, url) {
  const text = {'Cache-Control': 'no-store', 'Content-Type': 'text/plain; charset=utf-8',
    'X-Content-Type-Options': 'nosniff', 'X-Robots-Tag': 'noindex, nofollow'};
  const match = url.pathname.match(DL_PATH);
  if (!match || !DL_RELEASES.has(match[1]) || !DL_FILE.test(match[2])) {
    return new Response('Not found.', {status: 404, headers: text});
  }
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return new Response('Method not allowed.', {status: 405, headers: text});
  }
  const owner = env.GITHUB_OWNER || 'amirarasteh1990';
  const repo = env.GITHUB_REPO || 'amirarasteh1990.github.io';
  const target = 'https://github.com/' + encodeURIComponent(owner) + '/' +
    encodeURIComponent(repo) + '/releases/download/' + match[1] + '/' + match[2];
  // the redirect never waits for, or fails because of, the record
  const record = recordDownload(request, env, match[1], match[2]).catch(error => {
    console.error('Download record failed', {name: error && error.name ? error.name : 'Error'});
  });
  if (ctx && typeof ctx.waitUntil === 'function') ctx.waitUntil(record);
  else await record;
  return new Response(null, {status: 302, headers: Object.assign({}, text,
    {'Location': target})});
}

async function downloadStats(request, env, url) {
  const headers = responseHeaders('', false);
  headers['X-Robots-Tag'] = 'noindex, nofollow';
  if (request.method !== 'GET') return json({ok: false, error: 'Method not allowed.'}, 405, headers);
  if (!env.STATS_KEY || !env.DOWNLOADS) {
    return json({ok: false, error: 'Download statistics are not configured.'}, 503, headers);
  }
  const auth = request.headers.get('Authorization') || '';
  if (!sameSecret(auth.replace(/^Bearer\s+/i, ''), env.STATS_KEY)) {
    return json({ok: false, error: 'Not allowed.'}, 401, headers);
  }
  const day = url.searchParams.get('day') || '';
  if (!STATS_DAY.test(day)) return json({ok: false, error: 'day must be YYYY-MM-DD'}, 400, headers);
  const events = [];
  let cursor;
  for (let page = 0; page < 10; page += 1) {
    const listed = await env.DOWNLOADS.list({prefix: 'ev:' + day, cursor});
    for (const key of listed.keys) {
      events.push(Object.assign({t: key.name.slice(3, 27)}, key.metadata || {}));
    }
    if (listed.list_complete || !listed.cursor) break;
    cursor = listed.cursor;
  }
  return json({ok: true, day, events}, 200, headers);
}

class PublicError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.name = 'PublicError';
    this.status = status;
  }
}

function allowedOrigins(env) {
  return String(env.ALLOWED_ORIGINS || 'https://arasteh.art')
    .split(',').map(value => value.trim()).filter(Boolean);
}

function responseHeaders(origin, allowed) {
  const headers = {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
    'Vary': 'Origin',
    'X-Content-Type-Options': 'nosniff'
  };
  if (allowed) {
    headers['Access-Control-Allow-Origin'] = origin;
    headers['Access-Control-Allow-Headers'] = 'Content-Type';
    headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS';
    headers['Access-Control-Max-Age'] = '86400';
  }
  return headers;
}

function json(value, status, headers) {
  return new Response(JSON.stringify(value), {status, headers});
}

function cleanText(value, field, minimum, maximum) {
  if (typeof value !== 'string') throw new PublicError(field + ' is required.');
  value = value.replace(/\r\n?/g, '\n').trim();
  if (value.length < minimum || value.length > maximum || CONTROL_CHARACTERS.test(value)) {
    throw new PublicError(
      field + ' must be between ' + minimum + ' and ' + maximum + ' characters.'
    );
  }
  return value;
}

function cleanLine(value, field, minimum, maximum) {
  value = cleanText(value, field, minimum, maximum);
  if (value.includes('\n')) throw new PublicError(field + ' must stay on one line.');
  return value;
}

function escapeHtml(value) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function base64url(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function submission(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new PublicError('The form format was not recognized.');
  }
  if (raw.website) throw new PublicError('The note could not be accepted.');
  const language = cleanText(raw.language, 'Language', 2, 35);
  if (!LANGUAGE.test(language)) {
    throw new PublicError('The note language could not be recognized.');
  }
  const now = new Date();
  return {
    id: now.toISOString().slice(0, 10) + '-' + crypto.randomUUID().slice(0, 12),
    name: cleanLine(raw.name, 'Name or pen name', 1, 40),
    message: cleanText(raw.message, 'Note', 1, 500),
    language,
    language_name: cleanLine(raw.language_name, 'Language name', 1, 80),
    audience: 'public',
    submitted_at: now.toISOString()
  };
}

function issueBody(note) {
  const metadata = {
    id: note.id,
    language: note.language,
    language_name: note.language_name,
    audience: note.audience,
    submitted_at: note.submitted_at
  };
  return '<!-- guestbook-submission:v2 ' + base64url(JSON.stringify(metadata)) + ' -->\n\n' +
    '## Name or pen name\n\n<pre>' + escapeHtml(note.name) + '</pre>\n\n' +
    '## Language (automatic)\n\n' + escapeHtml(note.language_name) +
    ' (`' + note.language + '`)\n\n' +
    '## Reader note\n\n<pre>' + escapeHtml(note.message) + '</pre>\n\n' +
    '---\nSubmitted through https://arasteh.art/comments/. ' +
    'This note publishes automatically. Amir is notified and can remove it if needed.';
}

function optional(value) {
  return value === undefined || value === null ||
    (typeof value === 'string' && value.trim() === '');
}

// A native speaker's answers. Free text is refused if it holds an HTML comment
// opener, so no answer can smuggle the guestbook workflow's marker into the issue.
function checkSubmission(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new PublicError('The form format was not recognized.');
  }
  if (raw.website) throw new PublicError('The answers could not be accepted.');
  const lang = typeof raw.lang === 'string' ? raw.lang.trim() : '';
  if (!CHECK_SLUG.test(lang)) throw new PublicError('The language could not be recognized.');
  const pageVersion = cleanLine(raw.page_version, 'Page version', 1, 40);
  if (!CHECK_VERSION.test(pageVersion)) {
    throw new PublicError('The page version could not be recognized.');
  }
  const name = optional(raw.name) ? '' : cleanLine(raw.name, 'Name', 1, 60);
  if (!Array.isArray(raw.items) || raw.items.length < 1 || raw.items.length > 40) {
    throw new PublicError('Send between 1 and 40 answers.');
  }
  const seen = new Set();
  const items = raw.items.map(item => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new PublicError('An answer was not recognized.');
    }
    const id = typeof item.id === 'string' ? item.id.trim() : '';
    if (!CHECK_ID.test(id) || seen.has(id)) {
      throw new PublicError('An answer was not recognized.');
    }
    seen.add(id);
    if (!Object.prototype.hasOwnProperty.call(VERDICTS, item.verdict)) {
      throw new PublicError('Each answer must be Correct, Needs change or Not sure.');
    }
    const note = optional(item.note) ? '' : cleanText(item.note, 'Note', 1, 600);
    return {id, verdict: item.verdict, note};
  });
  if ([name].concat(items.map(item => item.note)).some(text => text.includes('<!--'))) {
    throw new PublicError('Notes cannot contain "<!--".');
  }
  return {lang, page_version: pageVersion, name, items};
}

function languageName(lang) {
  try {
    const name = new Intl.DisplayNames(['en'], {type: 'language'}).of(lang);
    if (name && name.toLowerCase() !== lang) return name;
  } catch {
    // an unknown tag keeps its slug
  }
  return lang;
}

// Inline code renders visitor text literally: no HTML, no Markdown, and no
// @mention notifies anyone. Line breaks become " / " so each answer stays one row.
function literal(text) {
  text = text.replace(/\s*\n\s*/g, ' / ');
  const longest = Math.max(0, ...(text.match(/`+/g) || []).map(run => run.length));
  const fence = '`'.repeat(longest + 1);
  return fence + ' ' + text + ' ' + fence;
}

function checkIssue(answers) {
  const language = languageName(answers.lang);
  const n = answers.items.length;
  const count = verdict => answers.items.filter(item => item.verdict === verdict).length;
  const unsure = count('unsure');
  const rows = answers.items.map(item =>
    '- `' + item.id + '` ' +
    (item.verdict === 'change' ? '**' + VERDICTS.change + '**' : VERDICTS[item.verdict]) +
    (item.note ? ': ' + literal(item.note) : ''));
  return {
    title: 'Native check: ' + language + ' (' + n + (n === 1 ? ' answer)' : ' answers)'),
    body: CHECK_MARKER + '\n\n' +
      '**' + language + '** (`' + answers.lang + '`), page version `' +
      answers.page_version + '`, from ' +
      (answers.name ? literal(answers.name) : 'an unnamed reader') + '.\n' +
      n + (n === 1 ? ' answer' : ' answers') + ': ' + count('ok') + ' Correct, ' +
      count('change') + ' Needs change' + (unsure ? ', ' + unsure + ' Not sure' : '') +
      '.\n\n' + rows.join('\n') + '\n\n' +
      '---\nSent from https://arasteh.art/sedaha/check/' + answers.lang + '/.',
    labels: ['native-check']
  };
}

async function rateLimit(request, env, wait = 'Please wait a minute before posting another note.') {
  if (!env.RATE_LIMIT_SALT || !env.SUBMIT_RATE_LIMITER ||
      typeof env.SUBMIT_RATE_LIMITER.limit !== 'function') {
    throw new PublicError('The guestbook is not configured yet.', 503);
  }
  const address = request.headers.get('CF-Connecting-IP') || 'unknown';
  const material = new TextEncoder().encode(env.RATE_LIMIT_SALT + '\0' + address);
  const digest = await crypto.subtle.digest('SHA-256', material);
  const key = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0'))
    .join('');
  const result = await env.SUBMIT_RATE_LIMITER.limit({key});
  if (!result || result.success !== true) {
    throw new PublicError(wait, 429);
  }
}

async function readPayload(request, limit = MAX_BODY_BYTES, tooLarge = 'The note is too large.') {
  const contentType = (request.headers.get('Content-Type') || '').toLowerCase();
  if (!contentType.startsWith('application/json')) {
    throw new PublicError('The form format was not recognized.');
  }
  const declared = Number(request.headers.get('Content-Length') || 0);
  if (declared > limit) throw new PublicError(tooLarge);
  const body = await request.text();
  if (new TextEncoder().encode(body).length > limit) {
    throw new PublicError(tooLarge);
  }
  try {
    return JSON.parse(body);
  } catch {
    throw new PublicError('The form format was not recognized.');
  }
}

function configured(env) {
  return Boolean(env.GITHUB_TOKEN && env.GITHUB_OWNER && env.GITHUB_REPO);
}

export async function handle(request, env, githubFetch = fetch, ctx = null) {
  const url = new URL(request.url);
  if (url.pathname.startsWith('/dl/')) return download(request, env, ctx, url);
  if (url.pathname === '/dl-stats') return downloadStats(request, env, url);
  if (request.method === 'GET' && (url.pathname === '/' || url.pathname === '/health')) {
    return json({ok: true, service: 'arasteh-guestbook'}, 200,
      responseHeaders('', false));
  }

  const origin = request.headers.get('Origin') || '';
  const originAllowed = allowedOrigins(env).includes(origin);
  const headers = responseHeaders(origin, originAllowed);

  if (request.method === 'OPTIONS') {
    return originAllowed
      ? new Response(null, {status: 204, headers})
      : json({ok: false, error: 'Origin not allowed.'}, 403, headers);
  }
  if (url.pathname !== '/' && url.pathname !== '/check') {
    return json({ok: false, error: 'Not found.'}, 404, headers);
  }
  if (request.method !== 'POST') {
    return json({ok: false, error: 'Method not allowed.'}, 405, headers);
  }
  if (!originAllowed) {
    return json({ok: false, error: 'Origin not allowed.'}, 403, headers);
  }
  const check = url.pathname === '/check';
  const failed = check ? 'The answers could not be sent just now.'
    : 'The note could not be posted just now.';
  if (!configured(env)) {
    return json({ok: false, error: check ? 'The check form is not configured yet.'
      : 'The guestbook is not configured yet.'}, 503, headers);
  }

  try {
    let note;
    let issue;
    if (check) {
      const raw = await readPayload(request, MAX_CHECK_BYTES, 'The answers are too large.');
      issue = checkIssue(checkSubmission(raw));
      await rateLimit(request, env, 'Please wait a minute before sending again.');
    } else {
      const raw = await readPayload(request);
      note = submission(raw);
      issue = {
        title: 'Reader note from ' + note.name,
        body: issueBody(note),
        labels: ['guestbook', 'pending', 'shareable']
      };
      await rateLimit(request, env);
    }

    let response;
    try {
      response = await githubFetch(
        'https://api.github.com/repos/' + encodeURIComponent(env.GITHUB_OWNER) + '/' +
        encodeURIComponent(env.GITHUB_REPO) + '/issues',
        {
          method: 'POST',
          headers: {
            'Accept': 'application/vnd.github+json',
            'Authorization': 'Bearer ' + env.GITHUB_TOKEN,
            'Content-Type': 'application/json',
            'User-Agent': 'arasteh-guestbook',
            'X-GitHub-Api-Version': GITHUB_API_VERSION
          },
          body: JSON.stringify(issue)
        }
      );
    } catch {
      return json({ok: false, error: failed}, 502, headers);
    }

    if (!response.ok) {
      console.error('GitHub issue creation failed', {
        status: response.status,
        request_id: response.headers.get('x-github-request-id') || undefined
      });
      return json({ok: false, error: failed}, 502, headers);
    }

    const created = await response.json().catch(() => ({}));
    if (!Number.isInteger(created.number) || created.number < 1 ||
        typeof created.created_at !== 'string' ||
        !/^\d{4}-\d{2}-\d{2}T/.test(created.created_at)) {
      console.error('GitHub issue creation returned an incomplete receipt');
      return json({ok: false, error: check ? 'Sending could not be confirmed.'
        : 'Posting could not be confirmed.'}, 502, headers);
    }

    if (check) {
      return json({
        ok: true,
        posted: true,
        issue_number: created.number,
        message: 'Sent. Thank you: Amir has your answers.'
      }, 201, headers);
    }

    const published = created.created_at.slice(0, 10);
    return json({
      ok: true,
      posted: true,
      issue_number: created.number,
      message: 'Posted. Amir has been notified.',
      entry: {
        id: published + '-issue-' + created.number,
        name: note.name,
        message: note.message,
        language: note.language,
        language_name: note.language_name,
        published,
        featured: false
      }
    }, 201, headers);
  } catch (error) {
    if (error instanceof PublicError) {
      return json({ok: false, error: error.message}, error.status, headers);
    }
    console.error('Unexpected guestbook failure', {
      name: error && error.name ? error.name : 'Error'
    });
    return json({ok: false, error: failed}, 500, headers);
  }
}

export default {
  fetch(request, env, ctx) {
    return handle(request, env, fetch, ctx);
  }
};
