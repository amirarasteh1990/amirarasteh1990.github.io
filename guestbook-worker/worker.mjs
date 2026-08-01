/* Intake endpoint for the arasteh.art guestbook.

   It validates a public, account-free form and creates a human-readable issue in
   a private GitHub repository. The GitHub token is a Worker secret and is never
   sent to the browser. The endpoint stores no email address and does not persist
   an IP address or user-agent string. */

function cors(origin, allowed) {
  return {
    'Access-Control-Allow-Origin': origin === allowed ? origin : allowed,
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin'
  };
}

function json(value, status, headers) {
  return new Response(JSON.stringify(value), {
    status: status,
    headers: Object.assign({'Content-Type': 'application/json; charset=utf-8'}, headers)
  });
}

function text(value, field, minimum, maximum) {
  if (typeof value !== 'string') throw new Error(field + ' is required.');
  value = value.replace(/\r\n?/g, '\n').trim();
  if (value.length < minimum || value.length > maximum || value.indexOf('\0') !== -1) {
    throw new Error(field + ' must be between ' + minimum + ' and ' + maximum + ' characters.');
  }
  return value;
}

function line(value, field, minimum, maximum) {
  value = text(value, field, minimum, maximum);
  if (value.indexOf('\n') !== -1) throw new Error(field + ' must stay on one line.');
  return value;
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

function submission(raw) {
  var language = text(raw.language, 'Language', 2, 35);
  if (!/^(?:[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*|mul|und)$/.test(language)) {
    throw new Error('The note language could not be recognized.');
  }
  if (raw.website) throw new Error('The note could not be accepted.');
  var audience = text(raw.audience, 'Audience', 6, 7);
  if (audience !== 'private' && audience !== 'public') {
    throw new Error('Choose who the note is for.');
  }
  var now = new Date();
  return {
    id: now.toISOString().slice(0, 10) + '-' + crypto.randomUUID().slice(0, 8),
    name: line(raw.name, 'Name or pen name', 1, 80),
    message: text(raw.message, 'Note', 1, 3000),
    language: language,
    language_name: line(raw.language_name, 'Language name', 1, 80),
    audience: audience,
    submitted_at: now.toISOString()
  };
}

function issueBody(note) {
  var marker = base64url(JSON.stringify(note));
  var moderation = note.audience === 'public'
    ? 'Add the `approved` label to publish it on the next local guestbook sync. ' +
      'Add `featured` as well to place it in the curated group.'
    : 'This note is private. The sync script blocks it from publication even if ' +
      'an approval label is added accidentally.';
  return '<!-- guestbook-submission:v1 ' + marker + ' -->\n\n' +
    '## Name or pen name\n\n<pre>' + escapeHtml(note.name) + '</pre>\n\n' +
    '## Language (automatic)\n\n' + escapeHtml(note.language_name) + ' (`' + note.language + '`)\n\n' +
    '## Audience\n\n' + (note.audience === 'public'
      ? 'May be shared with readers after approval.'
      : '**For Amir only. Never publish this note.**') + '\n\n' +
    '## Reader note\n\n<pre>' + escapeHtml(note.message) + '</pre>\n\n' +
    '---\nSubmitted ' + note.submitted_at + '. ' + moderation;
}

export default {
  async fetch(request, env) {
    var origin = request.headers.get('Origin') || '';
    var allowed = env.ALLOWED_ORIGIN || 'https://arasteh.art';
    var headers = cors(origin, allowed);
    if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers: headers});
    if (request.method !== 'POST') return json({ok:false, error:'Method not allowed.'}, 405, headers);
    if (origin !== allowed) return json({ok:false, error:'Origin not allowed.'}, 403, headers);
    if (!env.GITHUB_TOKEN || !env.GITHUB_OWNER || !env.GITHUB_REPO) {
      return json({ok:false, error:'The private review queue is not configured.'}, 503, headers);
    }
    var raw;
    try {
      if (!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) {
        throw new Error('The form format was not recognized.');
      }
      var length = Number(request.headers.get('Content-Length') || 0);
      if (length > 16384) throw new Error('The note was larger than the form allows.');
      raw = await request.json();
      if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
        throw new Error('The form format was not recognized.');
      }
      var note = submission(raw);
      var response = await fetch('https://api.github.com/repos/' +
        encodeURIComponent(env.GITHUB_OWNER) + '/' + encodeURIComponent(env.GITHUB_REPO) + '/issues', {
        method: 'POST',
        headers: {
          'Accept': 'application/vnd.github+json',
          'Authorization': 'Bearer ' + env.GITHUB_TOKEN,
          'Content-Type': 'application/json',
          'User-Agent': 'arasteh-guestbook',
          'X-GitHub-Api-Version': '2022-11-28'
        },
        body: JSON.stringify({
          title: 'Guestbook · ' + note.language_name + ' · ' + note.submitted_at.slice(0, 10),
          body: issueBody(note),
          labels: ['guestbook', 'pending', note.audience === 'public' ? 'shareable' : 'private']
        })
      });
      if (!response.ok) {
        console.error('GitHub issue creation failed:', response.status);
        return json({ok:false, error:'The private review queue could not accept the note.'}, 502, headers);
      }
      var created = await response.json().catch(function () { return {}; });
      if (!created || !Number.isInteger(created.number)) {
        console.error('GitHub issue creation returned no issue number.');
        return json({ok:false, error:'Delivery could not be confirmed.'}, 502, headers);
      }
      return json({
        ok: true,
        received: true,
        message: note.audience === 'public'
          ? 'Amir has received it. After a read-through, it may join the public archive.'
          : 'It is with Amir only and will not be published.'
      }, 201, headers);
    } catch (error) {
      return json({ok:false, error:error && error.message ? error.message : 'The note could not be accepted.'}, 400, headers);
    }
  }
};
