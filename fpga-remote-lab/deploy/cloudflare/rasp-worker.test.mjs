import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import worker from './rasp-worker.mjs';

const actualFetch = globalThis.fetch;
const env = { RASP_ORIGIN: 'https://rasp-origin.aminbagheri.com' };
afterEach(() => { globalThis.fetch = actualFetch; });

test('redirects to /rasp/ and preserves the query', async () => {
  const response = await worker.fetch(new Request('https://aminbagheri.com/rasp?a=1'), env);
  assert.equal(response.status, 307);
  assert.equal(response.headers.get('Location'), 'https://aminbagheri.com/rasp/?a=1');
});

test('forwards an upload body, method, path, and query', async () => {
  globalThis.fetch = async request => {
    assert.equal(request.url, 'https://rasp-origin.aminbagheri.com/rasp/api/upload?test=1');
    assert.equal(request.method, 'POST');
    assert.equal(await request.text(), 'bitstream-test-payload');
    assert.equal(request.headers.get('X-Forwarded-Host'), 'aminbagheri.com');
    assert.equal(request.redirect, 'manual');
    return new Response('{"id":"example"}', { status: 202 });
  };
  const response = await worker.fetch(new Request('https://aminbagheri.com/rasp/api/upload?test=1', {
    method: 'POST', body: 'bitstream-test-payload',
  }), env);
  assert.equal(response.status, 202);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
});

test('returns WebSocket upgrade responses intact', async () => {
  const upgrade = { status: 101, webSocket: {} };
  globalThis.fetch = async request => {
    assert.equal(request.url, 'https://rasp-origin.aminbagheri.com/rasp/ws');
    assert.equal(request.headers.get('Upgrade'), 'websocket');
    assert.equal(request.headers.get('Origin'), 'https://rasp-origin.aminbagheri.com');
    return upgrade;
  };
  const response = await worker.fetch(new Request('https://aminbagheri.com/rasp/ws', {
    headers: { Upgrade: 'websocket', Origin: 'https://aminbagheri.com' },
  }), env);
  assert.equal(response, upgrade);
});

test('rewrites origin redirects to the public hostname', async () => {
  globalThis.fetch = async () => new Response(null, {
    status: 307, headers: { Location: 'https://rasp-origin.aminbagheri.com/rasp/static/?a=1' },
  });
  const response = await worker.fetch(new Request('https://aminbagheri.com/rasp/static'), env);
  assert.equal(response.headers.get('Location'), 'https://aminbagheri.com/rasp/static/?a=1');
});

test('keeps other website paths on their original origin', async () => {
  const response = new Response('converter');
  globalThis.fetch = async request => {
    assert.equal(request.url, 'https://aminbagheri.com/fpga/');
    return response;
  };
  assert.equal(await worker.fetch(new Request('https://aminbagheri.com/fpga/'), env), response);
});

test('blocks public hardware agent connections, including encoded paths', async () => {
  globalThis.fetch = async () => { throw new Error('Must not reach origin'); };
  for (const path of ['/rasp/agent', '/rasp/%61gent', '/rasp/agent/']) {
    const response = await worker.fetch(new Request('https://aminbagheri.com' + path), env);
    assert.equal(response.status, 404);
  }
});

test('invalid origin cannot loop back through the public route', async () => {
  const response = await worker.fetch(new Request('https://aminbagheri.com/rasp/'), {
    RASP_ORIGIN: 'https://aminbagheri.com',
  });
  assert.equal(response.status, 503);
});

test('rejects foreign browser origins before opening an upstream connection', async () => {
  globalThis.fetch = async () => { throw new Error('Must not connect upstream'); };
  for (const origin of ['https://example.com', 'null', 'https://aminbagheri.com.evil.example']) {
    const response = await worker.fetch(new Request('https://aminbagheri.com/rasp/ws', {
      headers: { Upgrade: 'websocket', Origin: origin },
    }), env);
    assert.equal(response.status, 403);
  }
});

test('keeps non-browser clients without an Origin header working', async () => {
  globalThis.fetch = async request => {
    assert.equal(request.headers.has('Origin'), false);
    return new Response('ok');
  };
  assert.equal((await worker.fetch(new Request('https://aminbagheri.com/rasp/'), env)).status, 200);
});
