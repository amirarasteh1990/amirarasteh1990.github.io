/* Local HTTP adapter for worker.mjs. It keeps credentials in process memory and
   runs the exact same intake handler used by a deployed Worker. */
import http from 'node:http';
import worker from './worker.mjs';

var port = Number(process.env.PORT || 8787);
var env = {
  ALLOWED_ORIGIN: process.env.ALLOWED_ORIGIN || 'http://127.0.0.1:8000',
  GITHUB_TOKEN: process.env.GITHUB_TOKEN || '',
  GITHUB_OWNER: process.env.GITHUB_OWNER || '',
  GITHUB_REPO: process.env.GITHUB_REPO || ''
};

if (!env.GITHUB_TOKEN || !env.GITHUB_OWNER || !env.GITHUB_REPO) {
  console.error('Set GITHUB_TOKEN, GITHUB_OWNER, and GITHUB_REPO before starting the local intake.');
  process.exit(1);
}

var server = http.createServer(async function (incoming, outgoing) {
  try {
    var chunks = [];
    for await (var chunk of incoming) chunks.push(chunk);
    var body = chunks.length ? Buffer.concat(chunks) : undefined;
    var request = new Request('http://' + incoming.headers.host + incoming.url, {
      method: incoming.method,
      headers: incoming.headers,
      body: /^(GET|HEAD)$/i.test(incoming.method || '') ? undefined : body
    });
    var response = await worker.fetch(request, env);
    outgoing.writeHead(response.status, Object.fromEntries(response.headers.entries()));
    outgoing.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) {
    console.error(error);
    outgoing.writeHead(500, {'Content-Type': 'application/json; charset=utf-8'});
    outgoing.end(JSON.stringify({ok:false, error:'Local intake failed.'}));
  }
});

server.listen(port, '127.0.0.1', function () {
  console.log('Guestbook intake listening on http://127.0.0.1:' + port + '/');
});
