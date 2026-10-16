// Bounded recovery controller. Run under the same project PM2_HOME as its services.
const fs = require('node:fs');
const path = require('node:path');
const { run } = require('./ensure-runtime.cjs');
function decision(state, proc, now = Date.now()) {
  if (proc.name === 'prism-recovery' || proc.pm2_env.status === 'stopped') return null;
  const failures = (state.failures || []).filter(time => now - time < 3600000);
  const restarts = proc.pm2_env.restart_time || 0;
  if (proc.pm2_env.status !== 'errored' && restarts - (state.baseline || 0) < 3) return null;
  if (now < (state.next || 0)) return null;
  if (failures.length >= 2) return { action: 'circuit-open', failures, baseline: restarts, next: now + 3600000 };
  return { action: failures.length ? 'repair-dependencies' : 'restart', failures: [...failures, now], baseline: restarts, next: now + 60000 * (failures.length + 1) };
}
async function start() {
  const root = process.env.PRISM_APP_ROOT || path.resolve(__dirname, '../..');
  let pm2;
  try { pm2 = require(path.join(root, 'node_modules/pm2')); }
  catch { pm2 = require(path.join(root, 'desktop-electron/resources/node_modules/pm2')); }
  const call = (method, ...args) => new Promise((resolve, reject) => pm2[method](...args, (error, result) => error ? reject(error) : resolve(result)));
  const file = path.join(process.env.PRISM_RUNTIME_DATA_DIR || path.join(root, 'runtime-data'), 'recovery-state.json');
  let state = {}; try { state = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {}
  await call('connect');
  let busy = false;
  setInterval(async () => {
    if (busy) return; busy = true;
    try {
      for (const proc of await call('list')) {
        if (proc.pm2_env.status === 'online' && Date.now() - proc.pm2_env.pm_uptime > 120000) {
          state[proc.name] = { ...(state[proc.name] || {}), baseline: proc.pm2_env.restart_time || 0 };
        }
        const next = decision(state[proc.name] || {}, proc);
        if (!next) continue;
        state[proc.name] = next;
        fs.mkdirSync(path.dirname(file), { recursive: true });
        fs.writeFileSync(file, JSON.stringify(state, null, 2));
        console.log(`${proc.name}: ${next.action}`);
        await call('stop', proc.pm_id);
        if (next.action === 'circuit-open') continue;
        try {
          if (next.action === 'repair-dependencies') {
            if (!['prism-backend', 'prism-worker', 'prism-celery', 'persona-api', 'hermes-dashboard', 'hermes-webui'].includes(proc.name)) continue;
            // Only repair known Python components; unknown/port/config errors stop safely.
            const errorFile = proc.pm2_env.pm_err_log_path;
            let text = ''; if (errorFile && fs.existsSync(errorFile)) {
              const fd = fs.openSync(errorFile, 'r');
              try { const size = fs.fstatSync(fd).size; const buffer = Buffer.alloc(Math.min(size, 16384)); fs.readSync(fd, buffer, 0, buffer.length, Math.max(0, size - buffer.length)); text = buffer.toString(); }
              finally { fs.closeSync(fd); }
            }
            if (!/ModuleNotFoundError|ImportError|DLL load failed|No module named/.test(text)) continue;
            const component = proc.name.startsWith('hermes-') ? 'hermes' : proc.name === 'persona-api' ? 'persona' : null;
            const related = component === 'hermes' ? ['hermes-dashboard', 'hermes-webui']
              : component === 'persona' ? ['persona-api'] : ['prism-backend', 'prism-worker', 'prism-celery'];
            const suspended = (await call('list')).filter(app => related.includes(app.name) && app.pm2_env.status === 'online').map(app => app.name);
            for (const name of suspended) await call('stop', name);
            const python = path.join(process.env.PRISM_ENV_DIR, process.platform === 'win32' ? 'python.exe' : 'bin/python');
            const command = [path.join(root, 'scripts/packaging/provision/provision.py'), '--force', ...(component ? ['--component', component] : ['--skip-inject'])];
            await run(python, command, { env: process.env, cwd: root });
            for (const name of suspended) await call('restart', name);
          }
          await call('restart', proc.pm_id);
        } catch { console.error(`${proc.name}: recovery failed; stopped for diagnosis`); }
      }
    } catch (error) { console.error(`Recovery controller: ${error.message}`); }
    finally { busy = false; }
  }, 10000);
}
module.exports = { decision };
if (require.main === module) start().catch(error => { console.error(error.message); process.exitCode = 1; });
