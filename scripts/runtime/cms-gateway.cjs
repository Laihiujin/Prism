// Password boundary for the entire application, with CMS access controls at /cms.
const http = require('node:http');
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { promisify } = require('node:util');
const scrypt = promisify(crypto.scrypt);
const SESSION_MS = 2 * 60 * 60 * 1000;
function runtimeMode(env = process.env) { return env.PRISM_RUNTIME_MODE === 'production' ? 'production' : 'development'; }
function locations(env = process.env) {
  const root = env.PRISM_APP_ROOT || path.resolve(__dirname, '../..');
  const data = env.PRISM_RUNTIME_DATA_DIR || path.join(root, 'runtime-data');
  return { root, data, cms: path.join(data, 'cms') };
}
async function passwordHash(password, salt = crypto.randomBytes(24).toString('hex')) {
  if (typeof password !== 'string' || password.length < 6 || password.length > 128) throw new Error('密码长度须为 6–128 个字符');
  return { salt, hash: (await scrypt(password, salt, 64)).toString('hex') };
}
async function passwordMatches(password, saved) {
  if (!saved?.hash || typeof password !== 'string' || password.length > 128) return false;
  const actual = await scrypt(password, saved.salt, 64);
  const expected = Buffer.from(saved.hash, 'hex');
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}
function readJson(file, fallback = {}) { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; } }
function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file + '.tmp', JSON.stringify(value, null, 2), { mode: 0o600 });
  fs.renameSync(file + '.tmp', file);
}
async function setPassword(cms, password) { writeJson(path.join(cms, 'auth.json'), await passwordHash(password)); }
function createGateway(options = {}) {
  const env = options.env || process.env;
  const dirs = locations(env);
  fs.mkdirSync(dirs.cms, { recursive: true });
  const configFile = path.join(dirs.cms, 'config.json');
  let config = { securityReminder: true, publicEnabled: false, ...readJson(configFile) };
  const sessions = new Map(); const attempts = new Map(); let globalAttempts = [];
  const frontend = new URL(options.frontend || env.PRISM_FRONTEND_URL || `http://127.0.0.1:${env.PRISM_FRONTEND_PORT || 3000}`);
  const proxyHeaders = req => {
    const headers = { ...req.headers, host: frontend.host };
    delete headers['x-cms-csrf'];
    if (headers.cookie) headers.cookie = headers.cookie.split(';').filter(value => !value.trim().startsWith('prism_cms_session=')).join(';');
    if (headers.origin) headers.origin = frontend.origin;
    if (headers.referer) { try { const url = new URL(headers.referer); headers.referer = frontend.origin + url.pathname + url.search; } catch { delete headers.referer; } }
    headers['x-forwarded-host'] = frontend.host;
    headers['x-forwarded-proto'] = frontend.protocol.slice(0, -1);
    return headers;
  };
  const proxy = (req, res) => {
    res.setHeader('X-Frame-Options', 'SAMEORIGIN');
    res.removeHeader('Content-Security-Policy'); // Next renders its own scripts and styles.
    const upstream = (frontend.protocol === 'https:' ? https : http).request({ protocol: frontend.protocol,
      hostname: frontend.hostname, port: frontend.port, path: req.url, method: req.method, headers: proxyHeaders(req) }, incoming => {
      for (const [key, value] of Object.entries(incoming.headers)) {
        if (!['connection', 'keep-alive', 'transfer-encoding', 'cache-control'].includes(key) && value !== undefined) res.setHeader(key, value);
      }
      const location = incoming.headers.location;
      if (location?.startsWith(frontend.origin)) res.setHeader('Location', location.slice(frontend.origin.length) || '/');
      res.statusCode = incoming.statusCode || 502;
      incoming.pipe(res);
    });
    upstream.on('error', () => { if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' }); res.end('应用暂时不可用，请稍后重试'); });
    res.once('close', () => upstream.destroy());
    req.pipe(upstream);
  };
  const audit = event => fs.appendFileSync(path.join(dirs.cms, 'security.jsonl'), JSON.stringify({ at: new Date().toISOString(), event }) + '\n');
  const sessionFor = req => {
    const cookie = String(req.headers.cookie || '').split(';').map(value => value.trim()).find(value => value.startsWith('prism_cms_session='));
    const token = cookie?.slice('prism_cms_session='.length);
    const session = token && sessions.get(token);
    if (session && session.expires > Date.now()) return session;
    if (token) sessions.delete(token);
    return null;
  };
  const body = async req => {
    let text = '';
    const timer = setTimeout(() => req.destroy(), 20000);
    try { for await (const chunk of req) { text += chunk; if (Buffer.byteLength(text) > 8192) throw Object.assign(new Error('请求过大'), { status: 413 }); } }
    finally { clearTimeout(timer); }
    return String(req.headers['content-type'] || '').includes('application/json') ? JSON.parse(text || '{}') : Object.fromEntries(new URLSearchParams(text));
  };
  const tunnel = options.tunnel || (async enabled => {
    let pm2; try { pm2 = require(path.join(dirs.root, 'node_modules/pm2')); } catch { pm2 = require(path.join(dirs.root, 'desktop-electron/resources/node_modules/pm2')); }
    const call = (method, ...args) => new Promise((resolve, reject) => pm2[method](...args, (error, result) => error ? reject(error) : resolve(result)));
    await call('connect');
    try {
      const apps = await call('list'); const existing = apps.find(app => app.name === 'prism-cms-tunnel');
      if (!enabled) { if (existing) await call('stop', existing.pm_id); return; }
      if (existing) await call('restart', existing.pm_id);
      else await call('start', { name: 'prism-cms-tunnel', script: process.execPath, args: [path.join(__dirname, 'cms-tunnel.cjs')],
        interpreter: 'none', windowsHide: true, min_uptime: '60s', max_restarts: 3, restart_delay: 10000, stop_exit_codes: [0, 78],
        env: { ...env, ELECTRON_RUN_AS_NODE: '1' } });
    } finally { pm2.disconnect(); }
  });
  const server = http.createServer(async (req, res) => {
    config = { ...config, ...readJson(configFile) };
    const nonce = crypto.randomBytes(18).toString('base64');
    res.setHeader('Cache-Control', 'no-store'); res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer'); res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    if (req.headers['x-forwarded-proto'] === 'https') res.setHeader('Strict-Transport-Security', 'max-age=31536000');
    res.setHeader('Content-Security-Policy', `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`);
    const json = (code, value) => { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(value)); };
    const redirect = target => { res.writeHead(303, { Location: target }); res.end(); };
    try {
      const pathname = new URL(req.url, 'http://localhost').pathname;
      if (!['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'].includes(req.method)) return json(405, { error: 'Method not allowed' });
      const session = sessionFor(req);
      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) {
        let origin; try { origin = new URL(req.headers.origin).host; } catch {}
        if (origin !== req.headers.host) return json(403, { error: '来源验证失败' });
        if (session && (pathname.startsWith('/api/cms/') || pathname.startsWith('/auth/')) && req.headers['x-cms-csrf'] !== session.csrf) return json(403, { error: '请求验证失败，请刷新页面' });
      }
      if (req.method === 'GET' && pathname === '/login') {
        if (session) return redirect('/');
        const localHost = /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(req.headers.host || '') && !req.headers['cf-connecting-ip'];
        const setup = !readJson(path.join(dirs.cms, 'auth.json')).hash && !config.publicEnabled && localHost;
        let html = fs.readFileSync(path.join(__dirname, 'cms-login.html'), 'utf8').replaceAll('__NONCE__', nonce).replaceAll('__MODE__', runtimeMode(env) === 'production' ? '生产模式' : '开发模式');
        if (setup) html = html.replace('/auth/login', '/auth/setup').replace('访问密码后继续。', '新的访问密码以完成初始化。').replace('进入工作台</button>', '设置密码</button>');
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); return res.end(html);
      }
      if (pathname === '/auth/setup' && req.method === 'POST') {
        const localHost = /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(req.headers.host || '') && !req.headers['cf-connecting-ip'];
        if (!localHost || config.publicEnabled || readJson(path.join(dirs.cms, 'auth.json')).hash) return json(403, { error: '仅允许在未初始化的本机入口设置密码' });
        await setPassword(dirs.cms, (await body(req)).password); audit('password_initialized');
        return json(200, { success: true });
      }
      if (pathname === '/auth/login' && req.method === 'POST') {
        const ip = String(req.headers['cf-connecting-ip'] || req.socket.remoteAddress || 'unknown');
        const now = Date.now(); const recent = (attempts.get(ip) || []).filter(time => now - time < 900000);
        globalAttempts = globalAttempts.filter(time => now - time < 900000);
        if (recent.length >= 5 || globalAttempts.length >= 100) { audit('login_rate_limited'); return json(429, { error: '尝试过多，请在 15 分钟后重试' }); }
        if (attempts.size >= 10000) attempts.clear();
        attempts.set(ip, [...recent, now]); globalAttempts.push(now);
        const data = await body(req);
        if (!await passwordMatches(data.password, readJson(path.join(dirs.cms, 'auth.json')))) {
          audit('login_failed');
          return json(401, { error: '密码错误或尚未在本机配置密码' });
        }
        attempts.delete(ip);
        for (const [key, value] of sessions) if (value.expires <= now) sessions.delete(key);
        if (sessions.size >= 1000) return json(503, { error: '会话数量已达上限' });
        const token = crypto.randomBytes(32).toString('base64url');
        sessions.set(token, { csrf: crypto.randomBytes(24).toString('hex'), expires: now + SESSION_MS });
        const secure = req.headers['x-forwarded-proto'] === 'https';
        res.setHeader('Set-Cookie', `prism_cms_session=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=7200${secure ? '; Secure' : ''}`);
        audit('login_success'); return json(200, { success: true });
      }
      if (!session) {
        if (pathname.startsWith('/api/') || pathname.startsWith('/auth/')) return json(401, { error: '请先登录 CMS' });
        return redirect('/login');
      }
      if (pathname === '/auth/logout' && req.method === 'POST') {
        for (const [token, value] of sessions) if (value === session) sessions.delete(token);
        res.setHeader('Set-Cookie', 'prism_cms_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0');
        return json(200, { success: true });
      }
      if (pathname === '/cms' && req.method === 'GET') {
        const html = fs.readFileSync(path.join(__dirname, 'cms-admin.html'), 'utf8').replaceAll('__NONCE__', nonce);
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); return res.end(html);
      }
      if (pathname === '/api/cms/status' && req.method === 'GET') {
        const publicState = readJson(path.join(dirs.cms, 'public.json'));
        return json(200, { mode: runtimeMode(env), csrf: session.csrf, securityReminder: config.securityReminder,
          publicEnabled: config.publicEnabled, publicUrl: config.publicEnabled ? publicState.url || null : null });
      }
      if (pathname === '/api/cms/security' && req.method === 'PUT') {
        const data = await body(req);
        if (typeof data.securityReminder === 'boolean') config.securityReminder = data.securityReminder;
        const changed = typeof data.publicEnabled === 'boolean' && data.publicEnabled !== config.publicEnabled;
        if (typeof data.publicEnabled === 'boolean') config.publicEnabled = data.publicEnabled;
        writeJson(configFile, config);
        if (changed && config.publicEnabled) await tunnel(true);
        if (changed && !config.publicEnabled) res.once('finish', () => { tunnel(false).catch(() => audit('tunnel_stop_failed')); });
        audit('security_settings_changed'); return json(200, { success: true });
      }
      if (pathname === '/api/cms/password' && req.method === 'PUT') {
        const data = await body(req);
        if (!await passwordMatches(data.currentPassword, readJson(path.join(dirs.cms, 'auth.json')))) return json(403, { error: '当前密码不正确' });
        await setPassword(dirs.cms, data.newPassword); sessions.clear(); audit('password_changed');
        return json(200, { success: true, loginRequired: true });
      }
      const api = new Map([
        ['/api/cms/login-mode', '/api/v1/system/douyin-login-mode'],
        ['/api/cms/headless', '/api/v1/system/browser-headless'],
        ['/api/cms/channels', '/api/v1/system/channels'],
        ['/api/cms/channels/visibility', '/api/v1/system/channels/visibility'],
      ]);
      if (/^\/api\/(?:v1\/)+system\/douyin-login-mode\/?$/.test(pathname)) api.set(pathname, '/api/v1/system/douyin-login-mode');
      if (!api.has(pathname)) {
        if (pathname.startsWith('/api/cms/') || pathname.startsWith('/auth/')) return json(404, { error: 'Not found' });
        return proxy(req, res);
      }
      if (!['GET', 'PUT'].includes(req.method)) return json(405, { error: 'Method not allowed' });
      const payload = req.method === 'PUT' ? await body(req) : undefined;
      if (api.get(pathname) === '/api/v1/system/douyin-login-mode' && payload && runtimeMode(env) === 'production' && payload.mode !== 'browser') return json(403, { error: '生产模式仅允许浏览器登录' });
      const backend = options.backend || env.PRISM_BACKEND_URL || 'http://127.0.0.1:7000';
      const response = await fetch(new URL(api.get(pathname), backend), { method: req.method, signal: AbortSignal.timeout(15000),
        headers: { 'Content-Type': 'application/json' }, ...(payload ? { body: JSON.stringify(payload) } : {}) });
      if (payload) audit('cms_setting_changed');
      return json(response.status, await response.json());
    } catch (error) { return json(error.status || 500, { error: error.status ? error.message : '操作失败，请查看本机 CMS 日志' }); }
  });
  server.on('upgrade', (req, socket, head) => {
    let origin; try { origin = new URL(req.headers.origin).host; } catch {}
    if (!sessionFor(req) || origin !== req.headers.host) { socket.end('HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n'); return; }
    const upstream = (frontend.protocol === 'https:' ? https : http).request({ protocol: frontend.protocol,
      hostname: frontend.hostname, port: frontend.port, path: req.url, method: 'GET', headers: proxyHeaders(req) });
    upstream.on('upgrade', (response, peer, upstreamHead) => {
      socket.write(`HTTP/1.1 ${response.statusCode} Switching Protocols\r\n` + Object.entries(response.headers).map(([key, value]) => `${key}: ${value}`).join('\r\n') + '\r\n\r\n');
      if (upstreamHead.length) socket.write(upstreamHead);
      if (head.length) peer.write(head);
      peer.pipe(socket); socket.pipe(peer);
      socket.on('end', () => peer.destroy()); peer.on('end', () => socket.destroy());
      peer.on('error', () => socket.destroy()); socket.on('error', () => peer.destroy()); socket.on('close', () => peer.destroy());
    });
    upstream.on('response', response => { response.resume(); socket.end('HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n'); });
    upstream.on('error', () => socket.destroy()); upstream.end();
  });
  server.requestTimeout = 900000; server.headersTimeout = 10000;
  return server;
}
module.exports = { createGateway, setPassword, passwordHash, passwordMatches, runtimeMode, locations, readJson, writeJson };
if (require.main === module) {
  const dirs = locations();
  if (process.argv.includes('--set-password-stdin')) {
    let input = ''; process.stdin.setEncoding('utf8'); process.stdin.on('data', chunk => { input += chunk; });
    process.stdin.on('end', () => setPassword(dirs.cms, input.trim()).then(() => console.log('CMS password configured')).catch(() => { console.error('Password setup failed'); process.exitCode = 1; }));
  } else createGateway().listen(Number(process.env.PRISM_CMS_PORT || 8441), '127.0.0.1', () => console.log(`CMS gateway ready (${runtimeMode()})`));
}
