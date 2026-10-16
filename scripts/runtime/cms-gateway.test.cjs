const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const { createGateway, setPassword, runtimeMode } = require('./cms-gateway.cjs');
async function fixture(t, mode = 'development', initialized = true) {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-cms-test-'));
  const backend = http.createServer(async (req, res) => {
    let bytes = 0; for await (const chunk of req) bytes += chunk.length;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ success: true, path: req.url, method: req.method, cookie: req.headers.cookie || '', bytes }));
  });
  backend.on('upgrade', (req, socket) => {
    socket.write('HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n');
    socket.on('data', data => socket.write(data));
    socket.on('end', () => socket.destroy());
  });
  await new Promise(resolve => backend.listen(0, '127.0.0.1', resolve));
  if (initialized) await setPassword(path.join(data, 'cms'), 'cms-test-password');
  const calls = [];
  const server = createGateway({ env: { PRISM_RUNTIME_DATA_DIR: data, PRISM_RUNTIME_MODE: mode },
    backend: `http://127.0.0.1:${backend.address().port}`, frontend: `http://127.0.0.1:${backend.address().port}`, tunnel: async enabled => calls.push(enabled) });
  const sockets = new Set();
  for (const listener of [server, backend]) listener.on('connection', socket => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { for (const socket of sockets) socket.destroy(); await Promise.all([new Promise(resolve => server.close(resolve)), new Promise(resolve => backend.close(resolve))]); fs.rmSync(data, { recursive: true, force: true }); });
  const base = `http://127.0.0.1:${server.address().port}`;
  const request = (url, method = 'GET', body, headers = {}) => fetch(base + url, { method, redirect: 'manual', headers: {
    Origin: base, 'Content-Type': 'application/json', ...headers }, ...(body ? { body: JSON.stringify(body) } : {}) });
  const login = async () => {
    const response = await request('/auth/login', 'POST', { password: 'cms-test-password' }, { 'X-Forwarded-Proto': 'https' });
    assert.equal(response.status, 200);
    assert.match(response.headers.get('set-cookie'), /HttpOnly; SameSite=Strict/);
    assert.match(response.headers.get('set-cookie'), /Secure/);
    const cookie = response.headers.get('set-cookie').split(';')[0];
    const status = await (await request('/api/cms/status', 'GET', undefined, { Cookie: cookie })).json();
    return { Cookie: cookie, 'X-CMS-CSRF': status.csrf };
  };
  return { data, base, request, login, calls };
}
test('login protects the entire application and forwards authenticated pages and APIs', async t => {
  const f = await fixture(t);
  assert.equal((await f.request('/cms')).status, 303);
  assert.equal((await f.request('/api/cms/headless')).status, 401);
  assert.equal((await f.request('/auth/login', 'POST', { password: 'wrong-password' })).status, 401);
  const auth = await f.login();
  assert.equal((await f.request('/cms', 'GET', undefined, auth)).status, 200);
  assert.equal((await f.request('/api/cms/headless', 'GET', undefined, auth)).status, 200);
  assert.equal((await f.request('/api/v1/accounts')).status, 401);
  const accounts = await (await f.request('/api/v1/accounts?limit=1', 'GET', undefined, auth)).json();
  assert.equal(accounts.path, '/api/v1/accounts?limit=1');
  assert.equal(accounts.cookie.includes('prism_cms_session'), false);
  assert.equal((await f.request('/', 'GET', undefined, auth)).status, 200);
  assert.equal((await f.request('/_next/static/app.js', 'GET', undefined, auth)).status, 200);
  assert.equal((await f.request('/api/v1/files/example', 'DELETE', undefined, { Cookie: auth.Cookie })).status, 200);
  assert.equal((await f.request('/api/v1/files/example', 'DELETE', undefined, { ...auth, Origin: 'https://attacker.invalid' })).status, 403);
  const upload = await (await f.request('/api/v1/files/upload', 'POST', { content: 'x'.repeat(20000) }, { Cookie: auth.Cookie })).json();
  assert.ok(upload.bytes > 8192);
  assert.equal((await f.request('/api/cms/security', 'PUT', { securityReminder: false }, { Cookie: auth.Cookie })).status, 403);
  assert.equal((await f.request('/api/cms/security', 'PUT', { securityReminder: false }, { ...auth, Origin: 'https://attacker.invalid' })).status, 403);
  assert.equal((await f.request('/api/cms/security', 'PUT', { publicEnabled: true, securityReminder: false }, auth)).status, 200);
  assert.deepEqual(f.calls, [true]);
  assert.equal((await f.request('/api/cms/password', 'PUT', { currentPassword: 'cms-test-password', newPassword: 'new-test-password' }, auth)).status, 200);
  assert.equal((await f.request('/api/cms/status', 'GET', undefined, auth)).status, 401);
  const stored = fs.readFileSync(path.join(f.data, 'cms/auth.json'), 'utf8');
  assert.equal(stored.includes('new-test-password'), false);
});
test('parallel bad logins cannot bypass the attempt limit', async t => {
  const f = await fixture(t);
  const results = await Promise.all(Array.from({ length: 9 }, () => f.request('/auth/login', 'POST', { password: 'bad-password' })));
  assert.equal(results.filter(response => response.status === 401).length, 5);
  assert.equal(results.filter(response => response.status === 429).length, 4);
});
test('packaged production mode rejects HTTP reverse login', async t => {
  const f = await fixture(t, 'production'); const auth = await f.login();
  assert.equal((await f.request('/api/cms/login-mode', 'PUT', { mode: 'http' }, auth)).status, 403);
  assert.equal((await f.request('/api/v1/system/douyin-login-mode', 'PUT', { mode: 'http' }, { Cookie: auth.Cookie })).status, 403);
  assert.equal((await f.request('/api/cms/login-mode', 'PUT', { mode: 'browser' }, auth)).status, 200);
  assert.equal(runtimeMode({ NODE_ENV: 'production' }), 'development');
  assert.equal(runtimeMode({ PRISM_RUNTIME_MODE: 'production' }), 'production');
});
test('first setup is local only, and cannot replace an existing password', async t => {
  const f = await fixture(t, 'production', false);
  assert.equal((await (await f.request('/login')).text()).includes('/auth/setup'), true);
  assert.equal((await f.request('/auth/setup', 'POST', { password: 'cms-test-password' }, { 'CF-Connecting-IP': 'test-remote' })).status, 403);
  assert.equal((await f.request('/auth/setup', 'POST', { password: 'cms-test-password' })).status, 200);
  assert.equal((await f.request('/auth/setup', 'POST', { password: 'replacement-password' })).status, 403);
  await f.login();
});

test('websocket upgrades require authentication and the correct origin', async t => {
  const f = await fixture(t); const auth = await f.login();
  const connect = headers => new Promise((resolve, reject) => {
    const req = http.request(f.base + '/_next/webpack-hmr', { headers: { Origin: f.base, Connection: 'Upgrade', Upgrade: 'websocket', ...headers } });
    req.on('error', reject);
    req.on('response', response => { response.resume(); resolve(response.statusCode); });
    req.on('upgrade', (response, socket) => { socket.destroy(); resolve(response.statusCode); });
    req.end();
  });
  assert.equal(await connect({}), 401);
  assert.equal(await connect({ Cookie: auth.Cookie, Origin: 'https://attacker.invalid' }), 401);
  assert.equal(await connect({ Cookie: auth.Cookie }), 101);
});
