/* Local adapter for the exact Worker handler. Set MOCK_GITHUB=1 for a safe,
   network-free browser test, or provide the real environment variables. */
import http from 'node:http';
import {handle} from './worker.mjs';

const port = Number(process.env.PORT || 8787);
const mock = process.env.MOCK_GITHUB === '1';
let mockNumber = 9000;
const counters = new Map();

const env = {
  ALLOWED_ORIGINS: process.env.ALLOWED_ORIGINS ||
    'http://127.0.0.1:8000,http://localhost:8000',
  GITHUB_TOKEN: mock ? 'mock-token' : (process.env.GITHUB_TOKEN || ''),
  GITHUB_OWNER: process.env.GITHUB_OWNER || 'amirarasteh1990',
  GITHUB_REPO: process.env.GITHUB_REPO || 'amirarasteh1990.github.io',
  RATE_LIMIT_SALT: process.env.RATE_LIMIT_SALT || 'local-test-only',
  SUBMIT_RATE_LIMITER: {
    async limit({key}) {
      const now = Date.now();
      const recent = (counters.get(key) || []).filter(value => now - value < 60000);
      if (recent.length >= 3) return {success: false};
      recent.push(now);
      counters.set(key, recent);
      return {success: true};
    }
  }
};

if (!mock && !env.GITHUB_TOKEN) {
  console.error('Set GITHUB_TOKEN or use MOCK_GITHUB=1 before starting the local intake.');
  process.exit(1);
}

async function githubFetch(url, options) {
  if (!mock) return fetch(url, options);
  mockNumber += 1;
  return new Response(JSON.stringify({
    number: mockNumber,
    created_at: new Date().toISOString()
  }), {status: 201, headers: {'Content-Type': 'application/json'}});
}

const server = http.createServer(async (incoming, outgoing) => {
  try {
    const chunks = [];
    for await (const chunk of incoming) chunks.push(chunk);
    const headers = Object.assign({}, incoming.headers, {
      'CF-Connecting-IP': incoming.socket.remoteAddress || '127.0.0.1'
    });
    const request = new Request('http://' + incoming.headers.host + incoming.url, {
      method: incoming.method,
      headers,
      body: /^(GET|HEAD)$/i.test(incoming.method || '')
        ? undefined
        : Buffer.concat(chunks)
    });
    const response = await handle(request, env, githubFetch);
    outgoing.writeHead(response.status, Object.fromEntries(response.headers.entries()));
    outgoing.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) {
    console.error(error);
    outgoing.writeHead(500, {'Content-Type': 'application/json; charset=utf-8'});
    outgoing.end(JSON.stringify({ok: false, error: 'Local intake failed.'}));
  }
});

server.listen(port, '127.0.0.1', () => {
  console.log('Guestbook intake listening on http://127.0.0.1:' + port + '/');
  if (mock) console.log('GitHub is mocked. No issue or external write will be created.');
});
