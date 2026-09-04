#!/usr/bin/env node
/**
 * Prism 桌面端 PM2 Controller —— 替代原 supervisor.py。
 *
 * 职责：
 *  1. 用 PM2 托管全部服务（backend/worker/celery/hermes-dashboard/hermes-webui/
 *     deepseek-harness/redis/frontend），进程生命周期（启停/重启/监控/日志/重启次数）由 PM2 负责。
 *  2. 提供与原 supervisor 完全一致的 HTTP API 契约（:7002 → GET /api/status|health|diagnostics|
 *     restart-status；POST /api/start|stop|restart|restart/<name>），使 Electron 主进程、preload、
 *     renderer 及后端 /api/v1/system/supervisor/* 代理无需改动。
 *  3. 把发现信息写入状态文件（PRISM_SUPERVISOR_STATE_PATH 或默认路径），供主进程连接。
 *
 * 跨平台：macOS / Windows。PM2 由本机 node 或 Electron 主进程的 ELECTRON_RUN_AS_NODE 运行。
 */
'use strict';

const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

let pm2;
try {
  pm2 = require('pm2');
} catch (err) {
  // 退回到从仓库根解析 pm2（dev / 未打包场景）
  const repoRoot = path.resolve(__dirname, '..', '..', '..');
  pm2 = require(path.join(repoRoot, 'node_modules', 'pm2'));
}

const ECO_PATH = path.join(__dirname, 'ecosystem.desktop.config.js');
const eco = require(ECO_PATH);
const { servicePorts, serviceKeys } = eco._prism;

// ── supervisor 服务 key → PM2 进程名 ──
const SERVICE_TO_PM2 = {
  backend: 'prism-backend',
  'automation-worker': 'prism-worker',
  'celery-worker': 'prism-celery',
  // hermes-gateway 由外部/未配置，通常不启动
  'hermes-dashboard': 'hermes-dashboard',
  'hermes-webui': 'hermes-webui',
  'deepseek-harness': 'deepseek-harness',
};

const pm2NameFor = (service) => SERVICE_TO_PM2[service];

// ── 只由 supervisor 上报/控制的“服务型”进程（不含 redis/frontend，除非显式加入）──
const MANAGED_PM2_SERVICES = ['prism-backend', 'prism-worker', 'prism-celery', 'hermes-dashboard', 'hermes-webui', 'deepseek-harness'];

const LAUNCH_TOKEN = crypto.randomBytes(16).toString('hex');
const STARTED_AT = Date.now();
const CONTROLLER_PID = process.pid;

const statePath =
  process.env.PRISM_SUPERVISOR_STATE_PATH ||
  path.join(os.homedir(), '.prism-supervisor', 'state.json');

// ── API 端口：默认 7002，被占用时回退到可用端口并写入状态文件 ──
const preferredApiPort = Number.parseInt(process.env.SUPERVISOR_API_PORT || process.env.PRISM_SUPERVISOR_PORT || '7002', 10);

function canBind(port) {
  return new Promise((resolve) => {
    const srv = http.createServer();
    srv.once('error', () => resolve(false));
    srv.once('listening', () => {
      srv.close(() => resolve(true));
    });
    srv.listen(port, '127.0.0.1');
  });
}

async function findApiPort() {
  for (let p = preferredApiPort; p < preferredApiPort + 200; p += 1) {
    if (await canBind(p)) return p;
  }
  return preferredApiPort;
}

function writeStateFile(apiPort) {
  try {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    const payload = {
      pid: CONTROLLER_PID,
      startedAt: Math.floor(STARTED_AT / 1000),
      launchToken: LAUNCH_TOKEN,
      apiPort,
      servicePorts,
    };
    const tmp = statePath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(payload), 'utf8');
    fs.renameSync(tmp, statePath);
  } catch (_) { /* ignore */ }
}

// ── 端口探测（用于 deepseek-harness 外部形态、以及告警）──
function portOpen(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const client = require('net').connect({ host, port });
    client.once('connect', () => { client.destroy(); resolve(true); });
    client.once('error', () => resolve(false));
    setTimeout(() => { client.destroy(); resolve(false); }, 400);
  });
}

async function serviceStatus(name) {
  const pm2Name = pm2NameFor(name);
  const port = servicePorts[name];
  const base = {
    running: false,
    pid: null,
    external: false,
    managed: false,
    source: 'stopped',
  };

  // deepseek-harness 可能由外部进程托管于规范端口 :3080
  if (name === 'deepseek-harness') {
    const canonical = servicePorts['deepseek-harness'] || 3080;
    const open = await portOpen(canonical);
    if (open) {
      base.running = true;
      base.external = true;
      base.source = 'external';
      base.port = canonical;
      base.url = `http://127.0.0.1:${canonical}`;
      base.cli = path.join(eco._prism.resourceRoot, 'tools', 'deepseek-harness', 'apps', 'cli', 'lib', 'bin.js');
      return base;
    }
  }

  const status = await pm2List();
  const proc = status.find((p) => p.pm2_env?.name === pm2Name);
  if (proc) {
    const online = proc.pm2_env?.status === 'online';
    base.running = online;
    base.managed = true;
    base.source = online ? 'managed' : 'stopped';
    base.pid = proc.pid || null;
  }

  if (name === 'backend') {
    base.port = port;
    base.url = `http://127.0.0.1:${port}`;
  } else if (name === 'automation-worker') {
    base.port = port;
    base.url = `http://127.0.0.1:${port}`;
  } else if (name === 'hermes-dashboard') {
    base.port = port;
    base.url = `http://127.0.0.1:${port}`;
    base.dashboard_url = base.url;
  } else if (name === 'hermes-webui') {
    base.port = port;
    base.url = `http://127.0.0.1:${port}`;
    base.webui_url = base.url;
  } else if (name === 'deepseek-harness') {
    base.port = servicePorts['deepseek-harness'] || 3080;
    base.url = `http://127.0.0.1:${base.port}`;
  }
  return base;
}

let _pm2ListCache = [];
async function pm2List() {
  try {
    const list = await new Promise((resolve, reject) => {
      pm2.list((err, l) => (err ? reject(err) : resolve(l || [])));
    });
    _pm2ListCache = list;
    return list;
  } catch (_) {
    return _pm2ListCache;
  }
}

async function getStatus() {
  const services = {};
  for (const name of serviceKeys) {
    services[name.replace(/-/g, '_')] = await serviceStatus(name);
  }
  return services;
}

function getDiagnostics(services) {
  return {
    supervisor: {
      pid: CONTROLLER_PID,
      apiPort: apiPort,
      launchToken: LAUNCH_TOKEN,
      startedAt: Math.floor(STARTED_AT / 1000),
      isPackaged: Boolean(process.env.PRISM_RESOURCES_PATH),
    },
    services,
    environment: {
      resourcesPath: eco._prism.resourceRoot,
      backendDir: path.join(eco._prism.resourceRoot, 'prism_backend'),
      servicePorts,
    },
    logPaths: {
      supervisor: path.join('logs', 'supervisor.log'),
      backend: path.join('logs', 'backend.log'),
    },
  };
}

// ── PM2 生命周期操作 ──
function connectPM2() {
  return new Promise((resolve, reject) => {
    pm2.connect((err) => (err ? reject(err) : resolve()));
  });
}

function pm2Start(app) {
  // app 可为对象（单进程）或数组（ecosystem 多个）
  return new Promise((resolve, reject) => {
    pm2.start(app, (err, proc) => (err ? reject(err) : resolve(proc)));
  });
}

async function startAll() {
  // 先清掉旧进程，保证拿到干净的一套托管集合
  await new Promise((resolve, reject) => pm2.delete('all', (e) => (e ? reject(e) : resolve())));
  // 适配“端口已被外部进程占用”的情况：redis/frontend 若已在目标端口运行，则接管而非重复启动，
  // 避免 PM2 负责的进程因端口冲突而无限重启。
  const apps = [];
  for (const app of eco.apps) {
    if (app.name === 'prism-redis') {
      if (await portOpen(6379)) continue; // 已有 redis 在 6379，直接接管
    }
    if (app.name === 'deepseek-harness') {
      // 与原 supervisor 一致：deepseek-harness 由外部（DSH harness / 本套件）托管于规范端 :3080，
      // PM2 不主动启动，仅通过端口探测上报运行状态（见 serviceStatus 的 external 分支）。
      continue;
    }
    if (app.name === 'prism-frontend') {
      const fp = Number.parseInt((app.env || {}).PORT || '3000', 10) || 3000;
      if (await portOpen(fp)) continue; // 已有前端在靶端口，接管
    }
    apps.push(app);
  }
  return new Promise((resolve, reject) => {
    pm2.start(apps, (startErr, proc) => (startErr ? reject(startErr) : resolve(proc)));
  });
}

function stopAll() {
  return new Promise((resolve, reject) => {
    pm2.stop(MANAGED_PM2_SERVICES, (err) => (err ? reject(err) : resolve()));
  });
}

function restartAll() {
  return new Promise((resolve, reject) => {
    pm2.restart(MANAGED_PM2_SERVICES, (err) => (err ? reject(err) : resolve()));
  });
}

function restartService(service) {
  // 允许直接传 PM2 进程名（如 prism-frontend），也接受 supervisor 服务名（如 backend）。
  const pm2Name = pm2NameFor(service) || service;
  if (!pm2Name) return Promise.reject(new Error(`Invalid service: ${service}`));
  return new Promise((resolve, reject) => {
    pm2.restart(pm2Name, (err, proc) => (err ? reject(err) : resolve(proc)));
  });
}

function deleteAll() {
  return new Promise((resolve, reject) => {
    pm2.delete('all', (err) => (err ? reject(err) : resolve()));
  });
}

function pm2KillDaemon() {
  return new Promise((resolve) => {
    pm2.killDaemon(() => resolve());
  });
}

// ── HTTP server（与原 supervisor :7002 契约一致）──
let apiPort = 7002;
let restartInProgress = false;

function sendJson(res, data, status = 200) {
  const body = JSON.stringify(data);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(body);
}

async function handle(req, res) {
  const url = new URL(req.url, 'http://127.0.0.1');
  const p = url.pathname;
  const method = req.method;

  if (method === 'OPTIONS') {
    res.writeHead(200, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  if (method === 'GET' && p === '/api/health') {
    return sendJson(res, { status: 'ok', message: 'Supervisor is running', pid: CONTROLLER_PID, launchToken: LAUNCH_TOKEN, apiPort });
  }

  if (method === 'GET' && p === '/api/status') {
    const status = await getStatus();
    return sendJson(res, { status: 'success', data: status });
  }

  if (method === 'GET' && p === '/api/diagnostics') {
    const services = await getStatus();
    return sendJson(res, { status: 'success', data: getDiagnostics(services) });
  }

  if (method === 'GET' && p === '/api/restart-status') {
    return sendJson(res, { status: 'success', data: { restart_in_progress: restartInProgress } });
  }

  if (method === 'POST') {
    if (p === '/api/start') {
      try { await startAll(); return sendJson(res, { status: 'success', message: 'All services started' }); }
      catch (e) { return sendJson(res, { status: 'error', message: String(e.message || e) }, 500); }
    }
    if (p === '/api/stop') {
      try { await stopAll(); return sendJson(res, { status: 'success', message: 'All services stopped' }); }
      catch (e) { return sendJson(res, { status: 'error', message: String(e.message || e) }, 500); }
    }
    if (p === '/api/restart') {
      if (restartInProgress) return sendJson(res, { status: 'accepted', message: 'Restart already in progress' });
      restartInProgress = true;
      (async () => {
        try {
          await stopAll();
          await startAll();
        } catch (e) {
          try { await startAll(); } catch (_) { /* ignore */ }
        } finally {
          restartInProgress = false;
        }
      })();
      return sendJson(res, { status: 'accepted', message: 'Restart scheduled' });
    }
    if (p.startsWith('/api/restart/')) {
      const service = p.split('/')[3];
      try {
        await restartService(service);
        const status = await serviceStatus(service);
        return sendJson(res, { status: 'success', message: `${service} restarted`, data: status });
      } catch (e) {
        return sendJson(res, { status: 'error', message: String(e.message || e) }, 500);
      }
    }
  }

  sendJson(res, { status: 'error', message: 'Not Found' }, 404);
}

async function main() {
  const autoStart = process.env.PRISM_SUPERVISOR_DISABLE_START !== '1';
  apiPort = await findApiPort();
  await connectPM2();
  if (autoStart) {
    // 优先复用已在 PM2 的进程集（重启 controller 时不重复杀），否则干净启动。
    const existing = await pm2List();
    if (existing.length === 0) {
      try { await startAll(); } catch (e) { /* PM2 daemon 已起但启动失败时继续提供状态/健康接口 */ }
    }
  }
  const server = http.createServer((req, res) => {
    handle(req, res).catch(() => sendJson(res, { status: 'error', message: 'Internal error' }, 500));
  });
  await new Promise((resolve) => server.listen(apiPort, '127.0.0.1', resolve));
  writeStateFile(apiPort);
  console.log(`[pm2-controller] listening on http://127.0.0.1:${apiPort} pid=${CONTROLLER_PID}`);

  const shutdown = () => {
    server.close(() => {
      // 退出时清掉托管进程集合并关闭 PM2 daemon，确保应用退出后不再有残留服务
      deleteAll()
        .catch(() => {})
        .then(() => pm2KillDaemon())
        .then(() => pm2.disconnect(() => process.exit(0)));
    });
  };
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
  process.on('SIGUSR2', shutdown);
}

main().catch((err) => {
  console.error('[pm2-controller] fatale:', err && err.message, err);
  process.exit(1);
});
