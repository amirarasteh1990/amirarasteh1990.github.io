import {readFileSync} from 'node:fs';
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

// ---------------------------------------------------------------- POST /check
function answers(overrides = {}) {
  return Object.assign({
    lang: 'hu',
    page_version: '2026-11-16',
    name: 'A reader',
    items: [
      {id: 'Opening/0007#1', verdict: 'change', note: 'Use "őket". <script> @someone `x`'},
      {id: '03/0585#3', verdict: 'ok'}
    ],
    website: ''
  }, overrides);
}

function postCheck(body = answers(), origin = 'https://arasteh.art') {
  return new Request('https://worker.example/check', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Origin': origin,
      'CF-Connecting-IP': '203.0.113.8'
    },
    body: JSON.stringify(body)
  });
}

const checkPreflight = await handle(new Request('https://worker.example/check', {
  method: 'OPTIONS',
  headers: {'Origin': 'https://arasteh.art'}
}), environment(), githubSuccess);
assert(checkPreflight.status === 204, '/check preflight failed');

const checkGet = await handle(new Request('https://worker.example/check'), environment(), githubSuccess);
assert(checkGet.status === 405, 'GET /check was not refused');

const unknown = await handle(new Request('https://worker.example/other', {
  method: 'POST', headers: {'Origin': 'https://arasteh.art'}
}), environment(), githubSuccess);
assert(unknown.status === 404, 'an unknown route was accepted');

const callsBeforeCheck = githubCalls;
const checked = await handle(postCheck(), environment(), githubSuccess);
const checkReceipt = await checked.json();
assert(checked.status === 201, 'valid check did not return 201');
assert(checkReceipt.ok === true && checkReceipt.posted === true &&
  checkReceipt.issue_number === 42, 'valid check lacked confirmation');
assert(githubCalls === callsBeforeCheck + 1, 'valid check did not create one issue');
assert(checked.headers.get('Access-Control-Allow-Origin') === 'https://arasteh.art',
  'check response lacked exact CORS origin');
assert(createdIssue.title === 'Native check: Hungarian (2 answers)',
  'check issue title changed: ' + createdIssue.title);
assert(createdIssue.labels.join(',') === 'native-check', 'check issue labels changed');
assert(createdIssue.body.startsWith('<!-- native-check:v1 -->'), 'check marker missing');
assert(createdIssue.body.includes('- `Opening/0007#1` **Needs change**: `` Use "őket". <script> @someone `x` ``'),
  'a note was not kept literally in inline code');
assert(createdIssue.body.includes('- `03/0585#3` Correct'), 'a Correct answer is missing');
assert(createdIssue.body.includes('` A reader `'), 'the optional name is missing');
assert(!/guestbook/i.test(createdIssue.body + createdIssue.title),
  'a check issue mentions the guestbook');
assert(!JSON.stringify(checkReceipt).includes('test-token'), 'credential leaked into the check receipt');

// The guestbook publishing workflow must ignore every check issue: read its own
// trigger conditions and hold the issue the Worker built against them.
const workflow = readFileSync(
  new URL('../.github/workflows/publish-guestbook.yml', import.meta.url), 'utf8');
const bodyMarkers = [...workflow.matchAll(/contains\(github\.event\.issue\.body, '([^']+)'\)/g)]
  .map(match => match[1]);
const labelNames = [...workflow.matchAll(/github\.event\.label\.name == '([^']+)'/g)]
  .map(match => match[1]);
const labelGates = [...workflow.matchAll(/contains\(github\.event\.issue\.labels\.\*\.name, '([^']+)'\)/g)]
  .map(match => match[1]);
assert(bodyMarkers.length && labelNames.length && labelGates.length,
  'the guestbook workflow conditions could not be read');
assert(!bodyMarkers.some(marker => createdIssue.body.includes(marker)),
  'a check issue would start the guestbook workflow (opened)');
assert(!createdIssue.labels.some(label => labelNames.includes(label) || labelGates.includes(label)),
  'a check issue would start the guestbook workflow (labeled/edited)');

const one = await handle(postCheck(answers({name: '', items: [{id: 'x#1', verdict: 'ok'}]})),
  environment(), githubSuccess);
assert(one.status === 201 && createdIssue.title === 'Native check: Hungarian (1 answer)',
  'a single unnamed answer was refused');
assert(createdIssue.body.includes('from an unnamed reader'), 'an unnamed reader was not stated');

// A full page in a three-byte script: 40 answers, each with a 600-character note.
const full = Array.from({length: 40}, (_, i) =>
  ({id: '04b/' + (1000 + i) + '#' + (i + 1), verdict: 'change', note: 'क'.repeat(600)}));
const big = await handle(postCheck(answers({lang: 'hi', items: full})), environment(), githubSuccess);
assert(big.status === 201, 'a full page of long Devanagari notes was refused');
assert(createdIssue.title === 'Native check: Hindi (40 answers)', 'Hindi title changed');

const callsBeforeRefusals = githubCalls;
async function refused(body, status, message) {
  const result = await handle(postCheck(body), environment(), githubSuccess);
  assert(result.status === status, message + ' (status ' + result.status + ')');
  assert(githubCalls === callsBeforeRefusals, message + ' reached GitHub');
}
await refused(answers({items: []}), 400, 'an empty check was accepted');
await refused(answers({items: full.concat([{id: 'extra#41', verdict: 'ok'}])}), 400,
  '41 answers were accepted');
await refused(answers({items: [{id: 'a#1', verdict: 'maybe'}]}), 400, 'an unknown verdict was accepted');
await refused(answers({items: [{id: 'a#1', verdict: 'ok'}, {id: 'a#1', verdict: 'ok'}]}), 400,
  'a duplicate answer was accepted');
await refused(answers({items: [{id: '<b>#1', verdict: 'ok'}]}), 400, 'a malformed id was accepted');
await refused(answers({items: [{id: 'a#1', verdict: 'ok', note: 'x'.repeat(601)}]}), 400,
  'a 601-character note was accepted');
await refused(answers({name: 'x'.repeat(61)}), 400, 'a 61-character name was accepted');
await refused(answers({lang: 'Hungarian'}), 400, 'a malformed language was accepted');
await refused(answers({page_version: ''}), 400, 'a missing page version was accepted');
await refused(answers({website: 'spam.example'}), 400, 'the check honeypot was ignored');
await refused(answers({items: [{id: 'a#1', verdict: 'ok',
  note: '<!-- guestbook-submission:v2 eyJ9 -->'}]}), 400, 'a smuggled guestbook marker was accepted');
await refused(answers({name: '<!-- guestbook-submission:v2 eyJ9 -->'}), 400,
  'a smuggled marker in the name was accepted');

const foreignCheck = await handle(postCheck(answers(), 'https://attacker.example'),
  environment(), githubSuccess);
assert(foreignCheck.status === 403, 'a foreign origin reached /check');
const limitedCheck = await handle(postCheck(), environment(false), githubSuccess);
assert(limitedCheck.status === 429, 'the rate limit did not cover /check');
assert(githubCalls === callsBeforeRefusals, 'a refused check reached GitHub');

console.error = () => {};
let checkUpstream;
try {
  checkUpstream = await handle(postCheck(), environment(), async () => new Response('{}', {status: 500}));
} finally {
  console.error = oldError;
}
assert(checkUpstream.status === 502 && (await checkUpstream.json()).posted !== true,
  'a GitHub failure produced a false check receipt');

console.log('native-check Worker contract passed');
