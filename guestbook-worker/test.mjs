import {handle} from './worker.mjs';

function assert(value, message) {
  if (!value) throw new Error(message);
}

function decodeMarker(body) {
  const match = body.match(/<!-- guestbook-submission:v2 ([A-Za-z0-9_-]+) -->/);
  assert(match, 'v2 marker missing');
  return JSON.parse(Buffer.from(match[1], 'base64url').toString('utf8'));
}

function environment(limit = true) {
  return {
    ALLOWED_ORIGINS: 'https://arasteh.art',
    GITHUB_TOKEN: 'test-token',
    GITHUB_OWNER: 'owner',
    GITHUB_REPO: 'site',
    RATE_LIMIT_SALT: 'test-salt',
    SUBMIT_RATE_LIMITER: {
      async limit({key}) {
        assert(/^[a-f0-9]{64}$/.test(key), 'rate-limit key is not a digest');
        assert(!key.includes('203.0.113.8'), 'raw address reached the limiter');
        return {success: limit};
      }
    }
  };
}

function payload(overrides = {}) {
  return Object.assign({
    name: 'Reader',
    message: 'The thread reached me. <script> stays text.',
    language: 'en',
    language_name: 'English',
    website: ''
  }, overrides);
}

function post(body = payload(), origin = 'https://arasteh.art') {
  return new Request('https://worker.example/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Origin': origin,
      'CF-Connecting-IP': '203.0.113.8'
    },
    body: JSON.stringify(body)
  });
}

let createdIssue;
let outgoingHeaders;
let githubCalls = 0;
async function githubSuccess(url, options) {
  githubCalls += 1;
  assert(url === 'https://api.github.com/repos/owner/site/issues', 'wrong GitHub endpoint');
  createdIssue = JSON.parse(options.body);
  outgoingHeaders = options.headers;
  return new Response(JSON.stringify({
    number: 42,
    created_at: '2026-08-09T10:30:00Z'
  }), {status: 201, headers: {'Content-Type': 'application/json'}});
}

const health = await handle(new Request('https://worker.example/'), environment(), githubSuccess);
assert(health.status === 200 && (await health.json()).ok === true, 'health check failed');

const preflight = await handle(new Request('https://worker.example/', {
  method: 'OPTIONS',
  headers: {'Origin': 'https://arasteh.art'}
}), environment(), githubSuccess);
assert(preflight.status === 204, 'preflight failed');
assert(preflight.headers.get('Access-Control-Allow-Origin') === 'https://arasteh.art',
  'allowed origin missing from preflight');

const response = await handle(post(), environment(), githubSuccess);
const receipt = await response.json();
assert(response.status === 201, 'valid post did not return 201');
assert(receipt.ok === true && receipt.posted === true, 'valid post lacked confirmation');
assert(receipt.entry.id === '2026-08-09-issue-42', 'canonical issue ID missing');
assert(receipt.entry.message === payload().message, 'returned note changed');
assert(response.headers.get('Access-Control-Allow-Origin') === 'https://arasteh.art',
  'successful response lacked exact CORS origin');
assert(response.headers.get('Cache-Control') === 'no-store', 'receipt could be cached');
assert(createdIssue.labels.join(',') === 'guestbook,pending,shareable', 'safe labels changed');
assert(createdIssue.body.includes('&lt;script&gt;'), 'visible issue body did not escape HTML');
const marker = decodeMarker(createdIssue.body);
assert(marker.audience === 'public', 'marker is not public');
assert(marker.message === undefined && marker.name === undefined,
  'visible text was duplicated inside the marker');
assert(outgoingHeaders.Authorization === 'Bearer test-token', 'GitHub token was not used upstream');
assert(outgoingHeaders['X-GitHub-Api-Version'] === '2026-03-10', 'API version changed');
assert(!JSON.stringify(receipt).includes('test-token'), 'credential leaked into the receipt');

const callsAfterSuccess = githubCalls;
const foreign = await handle(post(payload(), 'https://attacker.example'), environment(), githubSuccess);
assert(foreign.status === 403, 'foreign origin was accepted');
assert(!foreign.headers.has('Access-Control-Allow-Origin'), 'foreign origin received CORS access');
assert(githubCalls === callsAfterSuccess, 'foreign origin reached GitHub');

const trap = await handle(post(payload({website: 'spam.example'})), environment(), githubSuccess);
assert(trap.status === 400, 'honeypot submission was accepted');
assert(githubCalls === callsAfterSuccess, 'honeypot submission reached GitHub');

const long = await handle(post(payload({message: 'x'.repeat(501)})), environment(), githubSuccess);
assert(long.status === 400, 'oversized note was accepted');

const limited = await handle(post(), environment(false), githubSuccess);
assert(limited.status === 429, 'rate limit was not enforced');
assert(githubCalls === callsAfterSuccess, 'rate-limited submission reached GitHub');

const oldError = console.error;
console.error = () => {};
let upstream;
try {
  upstream = await handle(post(), environment(), async () => new Response('{}', {status: 403}));
} finally {
  console.error = oldError;
}
assert(upstream.status === 502 && (await upstream.json()).posted !== true,
  'GitHub failure produced a false receipt');

const missingSecret = environment();
delete missingSecret.GITHUB_TOKEN;
const unconfigured = await handle(post(), missingSecret, githubSuccess);
assert(unconfigured.status === 503, 'missing secret did not fail closed');

console.log('guestbook Worker contract passed');
