/* Account-free intake for the arasteh.art guestbook.

   The Worker validates one public note, rate-limits a salted hash of the source
   address, and creates a GitHub issue. Its issue-only credential never reaches
   the browser. Raw IP addresses, user agents, and email addresses are not stored
   or logged by this code. */

const MAX_BODY_BYTES = 8192;
const GITHUB_API_VERSION = '2026-03-10';
const CONTROL_CHARACTERS = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/;
const LANGUAGE = /^(?:[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*|mul|und)$/;

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

async function rateLimit(request, env) {
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
    throw new PublicError('Please wait a minute before posting another note.', 429);
  }
}

async function readPayload(request) {
  const contentType = (request.headers.get('Content-Type') || '').toLowerCase();
  if (!contentType.startsWith('application/json')) {
    throw new PublicError('The form format was not recognized.');
  }
  const declared = Number(request.headers.get('Content-Length') || 0);
  if (declared > MAX_BODY_BYTES) throw new PublicError('The note is too large.');
  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) {
    throw new PublicError('The note is too large.');
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

export async function handle(request, env, githubFetch = fetch) {
  const url = new URL(request.url);
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
  if (url.pathname !== '/') {
    return json({ok: false, error: 'Not found.'}, 404, headers);
  }
  if (request.method !== 'POST') {
    return json({ok: false, error: 'Method not allowed.'}, 405, headers);
  }
  if (!originAllowed) {
    return json({ok: false, error: 'Origin not allowed.'}, 403, headers);
  }
  if (!configured(env)) {
    return json({ok: false, error: 'The guestbook is not configured yet.'}, 503, headers);
  }

  try {
    const raw = await readPayload(request);
    const note = submission(raw);
    await rateLimit(request, env);

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
          body: JSON.stringify({
            title: 'Reader note from ' + note.name,
            body: issueBody(note),
            labels: ['guestbook', 'pending', 'shareable']
          })
        }
      );
    } catch {
      return json({ok: false, error: 'The note could not be posted just now.'}, 502, headers);
    }

    if (!response.ok) {
      console.error('GitHub issue creation failed', {
        status: response.status,
        request_id: response.headers.get('x-github-request-id') || undefined
      });
      return json({ok: false, error: 'The note could not be posted just now.'}, 502, headers);
    }

    const created = await response.json().catch(() => ({}));
    if (!Number.isInteger(created.number) || created.number < 1 ||
        typeof created.created_at !== 'string' ||
        !/^\d{4}-\d{2}-\d{2}T/.test(created.created_at)) {
      console.error('GitHub issue creation returned an incomplete receipt');
      return json({ok: false, error: 'Posting could not be confirmed.'}, 502, headers);
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
    return json({ok: false, error: 'The note could not be posted just now.'}, 500, headers);
  }
}

export default {
  fetch(request, env) {
    return handle(request, env);
  }
};
