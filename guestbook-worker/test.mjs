import worker from './worker.mjs';

function assert(value, message) {
  if (!value) throw new Error(message);
}

var githubReply = {number: 42};
var createdIssue;
globalThis.fetch = async function (url, options) {
  assert(url.includes('api.github.com/repos/'), 'unexpected intake destination');
  createdIssue = JSON.parse(options.body);
  return new Response(JSON.stringify(githubReply), {
    status: 201,
    headers: {'Content-Type': 'application/json'}
  });
};

var env = {
  ALLOWED_ORIGIN: 'https://arasteh.art',
  GITHUB_TOKEN: 'test-token',
  GITHUB_OWNER: 'owner',
  GITHUB_REPO: 'private-queue'
};

function request(audience, origin) {
  return new Request('https://worker.example/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'Origin': origin || 'https://arasteh.art'},
    body: JSON.stringify({
      name: 'Reader',
      message: 'The thread reached me.',
      language: 'en',
      language_name: 'English',
      audience: audience,
      website: ''
    })
  });
}

async function delivered(audience) {
  var response = await worker.fetch(request(audience), env);
  var receipt = await response.json();
  assert(response.status === 201, audience + ' note did not return 201');
  assert(receipt.ok === true && receipt.received === true,
    audience + ' note did not return a verified receipt');
  assert(receipt.message.includes('Amir'), audience + ' receipt does not name Amir');
  assert(createdIssue.labels.includes(audience === 'public' ? 'shareable' : 'private'),
    audience + ' audience label missing');
  var marker = createdIssue.body.match(/<!-- guestbook-submission:v1 ([A-Za-z0-9_-]+) -->/);
  assert(marker, audience + ' durable payload marker missing');
  var payload = JSON.parse(Buffer.from(marker[1], 'base64url').toString('utf8'));
  assert(payload.audience === audience, audience + ' choice changed in transit');
  assert(payload.message === 'The thread reached me.', 'note changed in transit');
}

await delivered('private');
await delivered('public');

var blocked = await worker.fetch(request('public', 'https://attacker.example'), env);
assert(blocked.status === 403, 'unrelated origin was not rejected');

githubReply = {};
var oldError = console.error;
console.error = function () {};
var ambiguous;
try {
  ambiguous = await worker.fetch(request('public'), env);
} finally {
  console.error = oldError;
}
var falseReceipt = await ambiguous.json();
assert(ambiguous.status === 502, 'unverified GitHub response was accepted');
assert(falseReceipt.received !== true, 'unverified delivery produced a receipt');

console.log('guestbook verified-delivery pipeline passed');
