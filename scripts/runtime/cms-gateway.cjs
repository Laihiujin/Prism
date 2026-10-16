// Dedicated CMS boundary. Only the explicit CMS settings API is forwarded.
const http = require('node:http');
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
    let text = ''; for await (const chunk of req) { text += chunk; if (Buffer.byteLength(text) > 8192) throw Object.assign(new Error('请求过大'), { status: 413 }); }
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
      if (!['GET', 'HEAD', 'POST', 'PUT'].includes(req.method)) return json(405, { error: 'Method not allowed' });
      const session = sessionFor(req);
      if (['POST', 'PUT'].includes(req.method)) {
        let origin; try { origin = new URL(req.headers.origin).host; } catch {}
        if (origin !== req.headers.host) return json(403, { error: '来源验证失败' });
        if (session && req.headers['x-cms-csrf'] !== session.csrf) return json(403, { error: '请求验证失败，请刷新页面' });
      }
      if (req.method === 'GET' && pathname === '/login') {
        if (session) return redirect('/cms');
        const localHost = /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(req.headers.host || '') && !req.headers['cf-connecting-ip'];
        const setup = !readJson(path.join(dirs.cms, 'auth.json')).hash && !config.publicEnabled && localHost;
        let html = fs.readFileSync(path.join(__dirname, 'cms-login.html'), 'utf8').replaceAll('__NONCE__', nonce).replaceAll('__MODE__', runtimeMode(env) === 'production' ? '生产模式' : '开发模式');
        if (setup) html = html.replace('/auth/login', '/auth/setup').replace('访问密码后继续。', '新的访问密码以完成初始化。').replace('登录后台</button>', '设置密码</button>');
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
      if ((pathname === '/' || pathname === '/cms') && req.method === 'GET') {
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
      if (!api.has(pathname) || !['GET', 'PUT'].includes(req.method)) return json(404, { error: 'Not found' });
      const payload = req.method === 'PUT' ? await body(req) : undefined;
      if (pathname === '/api/cms/login-mode' && payload && runtimeMode(env) === 'production' && payload.mode !== 'browser') return json(403, { error: '生产模式仅允许浏览器登录' });
      const backend = options.backend || env.PRISM_BACKEND_URL || 'http://127.0.0.1:7000';
      const response = await fetch(new URL(api.get(pathname), backend), { method: req.method, signal: AbortSignal.timeout(15000),
        headers: { 'Content-Type': 'application/json' }, ...(payload ? { body: JSON.stringify(payload) } : {}) });
      if (payload) audit('cms_setting_changed');
      return json(response.status, await response.json());
    } catch (error) { return json(error.status || 500, { error: error.status ? error.message : '操作失败，请查看本机 CMS 日志' }); }
  });
  server.requestTimeout = 20000; server.headersTimeout = 10000;
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
