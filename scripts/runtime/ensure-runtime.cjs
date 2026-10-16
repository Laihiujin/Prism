// First-run runtime installer, shared by source launchers and Electron.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawn } = require('node:child_process');
const { createHash } = require('node:crypto');

function run(exe, args, options = {}) {
  return new Promise((resolve, reject) => {
    const log = process.env.PRISM_INSTALL_LOG;
    const fd = log ? fs.openSync(log, 'a') : null;
    const child = spawn(exe, args, { stdio: fd === null ? 'inherit' : ['ignore', fd, fd], windowsHide: true, timeout: 1800000, ...options });
    const close = () => { if (fd !== null) fs.closeSync(fd); };
    child.once('error', error => { close(); reject(error); });
    child.once('exit', code => { close(); code === 0 ? resolve() : reject(new Error(`${path.basename(exe)} exited ${code}`)); });
  });
}
async function download(urls, destination, sha256) {
  const failures = [];
  for (const url of urls) {
    try {
      const response = await fetch(url, { headers: { Accept: 'application/octet-stream' }, signal: AbortSignal.timeout(120000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = Buffer.from(await response.arrayBuffer());
      if (data.length < 1024) throw new Error('Truncated download');
      if (sha256 && createHash('sha256').update(data).digest('hex') !== sha256) throw new Error('Checksum mismatch');
      fs.writeFileSync(destination, data);
      return;
    } catch (error) { failures.push(`${new URL(url).hostname}: ${error.message}`); }
  }
  throw new Error(`All download sources failed: ${failures.join('; ')}`);
}
async function ensureComponents(root, data, python, env) {
  const registry = require('./components.json');
  const tools = path.join(data, 'tools');
  for (const [name, component] of Object.entries(registry)) {
    const packaged = path.join(root, 'tools', component.directory);
    const sourceCheckout = fs.existsSync(path.join(root, 'bootstrap.py'));
    const destination = sourceCheckout && fs.existsSync(path.join(packaged, component.entry)) ? packaged : path.join(tools, component.directory);
    if (destination !== packaged && !fs.existsSync(destination) && fs.existsSync(path.join(packaged, component.entry))) {
      fs.mkdirSync(path.dirname(destination), { recursive: true });
      fs.cpSync(packaged, destination, { recursive: true });
    }
    if (!fs.existsSync(path.join(destination, component.entry))) {
      const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-component-'));
      try {
        const archive = path.join(temp, 'source.tar.gz');
        const canonical = `https://github.com/${component.repository}/archive/${component.revision}.tar.gz`;
        const mirrors = (env.PRISM_GITHUB_MIRRORS || '').split('|').filter(Boolean).map(prefix => prefix + canonical);
        await download([...mirrors, `https://codeload.github.com/${component.repository}/tar.gz/${component.revision}`, canonical,
          `https://api.github.com/repos/${component.repository}/tarball/${component.revision}`], archive);
        const extracted = path.join(temp, 'extracted'); fs.mkdirSync(extracted);
        await run('tar', ['-xzf', archive, '-C', extracted, '--strip-components=1']);
        if (!fs.existsSync(path.join(extracted, component.entry))) throw new Error(`Incomplete component archive: ${name}`);
        fs.mkdirSync(path.dirname(destination), { recursive: true });
        // Never replace an existing component source tree or local edits.
        if (fs.existsSync(destination) && fs.readdirSync(destination).length) throw new Error(`Incomplete component directory requires review: ${name}`);
        fs.cpSync(extracted, destination, { recursive: true });
      } finally { fs.rmSync(temp, { recursive: true, force: true }); }
    }
    env[`PRISM_${name.replaceAll('-', '_').toUpperCase()}_SOURCE`] = destination;
    if (name !== 'hermes-webui') {
      await run(python, [path.join(root, 'scripts/packaging/provision/provision.py'), '--component', name, '--component-env-dir', env.PRISM_COMPONENT_ENV_DIR], { cwd: root, env });
    }
  }
  const hermesPython = path.join(env.PRISM_COMPONENT_ENV_DIR, 'hermes', process.platform === 'win32' ? 'python.exe' : 'bin/python');
  env.PRISM_HERMES_PYTHON = hermesPython;
  const hermesWeb = path.join(env.PRISM_HERMES_SOURCE, 'hermes_cli/web_dist/index.html');
  const personaDashboard = path.join(env.PRISM_PERSONA_SOURCE, 'dashboard');
  const needsHermes = !fs.existsSync(hermesWeb);
  const needsPersona = !fs.existsSync(path.join(personaDashboard, 'node_modules/vite/bin/vite.js'));
  if (needsHermes || needsPersona) {
    const node = await require('./node-runtime.cjs').ensureNode(data, { run, download });
    env.PRISM_NODE = node.node;
    env.PATH = path.dirname(node.node) + path.delimiter + (env.PATH || '');
    const npm = async (args, cwd) => {
      let failure;
      for (const registry of ['https://registry.npmmirror.com', 'https://registry.npmjs.org']) {
        try { await run(node.node, [node.npm, ...args], { cwd, env: { ...env, npm_config_registry: registry, npm_config_fetch_timeout: '60000', npm_config_fetch_retries: '2' } }); failure = null; break; }
        catch (error) { failure = error; }
      }
      if (failure) throw failure;
    };
    if (needsHermes) {
      if (!fs.existsSync(path.join(env.PRISM_HERMES_SOURCE, 'web/package.json'))) throw new Error('Hermes web sources missing; rebuild package with web_dist');
      await npm(['install', '--workspace', 'web'], env.PRISM_HERMES_SOURCE);
      await npm(['run', 'build', '-w', 'web'], env.PRISM_HERMES_SOURCE);
    }
    if (needsPersona) await npm(['install'], personaDashboard);
  }
  const webRequirements = path.join(env.PRISM_HERMES_WEBUI_SOURCE, 'requirements.txt');
  if (fs.existsSync(webRequirements)) {
    const digest = createHash('sha256').update(fs.readFileSync(webRequirements)).digest('hex');
    const stamp = path.join(env.PRISM_COMPONENT_ENV_DIR, 'hermes', '.webui-requirements');
    if (!fs.existsSync(stamp) || fs.readFileSync(stamp, 'utf8') !== digest) {
      let failure;
      for (const index of ['https://pypi.tuna.tsinghua.edu.cn/simple', 'https://mirrors.aliyun.com/pypi/simple', 'https://pypi.org/simple']) {
        try { await run(hermesPython, ['-m', 'pip', 'install', '--timeout', '30', '--retries', '2', '-i', index, '-r', webRequirements], { env }); failure = null; break; }
        catch (error) { failure = error; }
      }
      if (failure) throw failure;
      fs.writeFileSync(stamp, digest);
    }
  }
}
function target(platform = process.platform, arch = process.arch) {
  const value = { 'win32-x64': 'win-64', 'darwin-x64': 'osx-64', 'darwin-arm64': 'osx-arm64', 'linux-x64': 'linux-64', 'linux-arm64': 'linux-aarch64' }[`${platform}-${arch}`];
  if (!value) throw new Error(`Unsupported runtime platform: ${platform}/${arch}`);
  return value;
}
async function ensureRuntime(root, data, options = {}) {
  fs.mkdirSync(data, { recursive: true });
  process.env.PRISM_INSTALL_LOG = path.join(data, 'installation.log');
  const existingSourceEnv = fs.existsSync(path.join(root, 'bootstrap.py')) && fs.existsSync(path.join(root, 'prismenv/conda-meta'));
  const envDir = options.envDir || (existingSourceEnv ? path.join(root, 'prismenv') : path.join(data, 'envs', 'shared'));
  const python = path.join(envDir, process.platform === 'win32' ? 'python.exe' : 'bin/python');
  const bin = path.join(data, 'bin');
  fs.mkdirSync(bin, { recursive: true });
  const embedded = path.join(root, 'scripts/packaging/provision/micromamba', target(), process.platform === 'win32' ? 'micromamba.exe' : 'micromamba');
  const mm = process.env.PRISM_MICROMAMBA || (fs.existsSync(embedded) ? embedded : path.join(bin, process.platform === 'win32' ? 'micromamba.exe' : 'micromamba'));
  const env = { ...process.env, PRISM_ENV_DIR: envDir, PRISM_COMPONENT_ENV_DIR: path.join(data, 'envs', 'components'), PRISM_RUNTIME_DATA_DIR: data,
    PRISM_HERMES_HOME: process.env.PRISM_HERMES_HOME || path.join(data, 'hermes-home'), HERMES_HOME: process.env.PRISM_HERMES_HOME || path.join(data, 'hermes-home'),
    PRISM_MICROMAMBA: mm, MAMBA_ROOT_PREFIX: path.join(data, 'mamba'), PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' };
  const lock = path.join(data, '.provision-lock');
  try { fs.mkdirSync(lock); } catch {
    let owner;
    try { owner = JSON.parse(fs.readFileSync(path.join(lock, 'owner.json'), 'utf8')); } catch {}
    let active = true;
    if (owner?.pid) { try { process.kill(owner.pid, 0); } catch (error) { if (error.code === 'ESRCH') active = false; } }
    if (active) throw new Error('Runtime installation already active; see installation.log');
    fs.unlinkSync(path.join(lock, 'owner.json')); fs.rmdirSync(lock); fs.mkdirSync(lock);
  }
  fs.writeFileSync(path.join(lock, 'owner.json'), JSON.stringify({ pid: process.pid }));
  try {
    if (!fs.existsSync(mm)) {
      const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-mamba-'));
      try {
        const archive = path.join(temp, 'micromamba.tar.bz2');
        const sources = (process.env.PRISM_MAMBA_DOWNLOAD_URLS || '').split('|').filter(Boolean).map(url => url.replaceAll('{target}', target()));
        sources.push(`https://micro.mamba.pm/api/micromamba/${target()}/latest`,
          `https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-${target()}.tar.bz2`);
        await download(sources, archive);
        const member = process.platform === 'win32' ? 'Library/bin/micromamba.exe' : 'bin/micromamba';
        await run('tar', ['-xjf', archive, '-C', temp, member]);
        fs.copyFileSync(path.join(temp, member), mm);
        fs.chmodSync(mm, 0o755);
      } finally { fs.rmSync(temp, { recursive: true, force: true }); }
    }
    await run(mm, ['--version'], { env });
    if (!fs.existsSync(python)) {
      let failure;
      for (const channel of ['https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge', 'https://mirrors.ustc.edu.cn/anaconda/cloud/conda-forge', 'conda-forge']) {
        try { await run(mm, ['create', '-y', '-p', envDir, '--override-channels', '-c', channel, 'python=3.11', 'pip'], { env }); failure = null; break; }
        catch (error) { failure = error; }
      }
      if (failure) throw failure;
    }
    await run(python, [path.join(root, 'scripts/packaging/provision/provision.py'), '--env-dir', envDir, '--component-env-dir', env.PRISM_COMPONENT_ENV_DIR, '--skip-inject', ...(options.force ? ['--force'] : [])], { cwd: root, env });
    // Redis is managed by PM2, not installed as a system service.
    const redis = path.join(envDir, process.platform === 'win32' ? 'Library/bin/redis-server.exe' : 'bin/redis-server');
    const bundledRedis = path.join(root, 'desktop-electron/resources/redis/redis-server.exe');
    if (process.platform === 'win32' && !fs.existsSync(redis) && !fs.existsSync(bundledRedis)) {
      const destination = path.join(data, 'components', 'redis');
      const executable = path.join(destination, 'redis-server.exe');
      if (!fs.existsSync(executable)) {
        const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-redis-'));
        try {
          const archive = path.join(temp, 'redis.zip');
          const canonical = 'https://github.com/redis-windows/redis-windows/releases/download/8.10.2/Redis-8.10.2-Windows-x64-msys2.zip';
          await download([...(env.PRISM_GITHUB_MIRRORS || '').split('|').filter(Boolean).map(prefix => prefix + canonical), canonical,
            'https://api.github.com/repos/redis-windows/redis-windows/releases/assets/571541296'], archive,
            '7c8cebd50347eaa1d9e784da842ed47a4f33394637835531d6614777b950ee85');
          await run(python, ['-c', 'import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])', archive, path.join(temp, 'out')], { env });
          const find = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? find(path.join(dir, entry.name)) : entry.name === 'redis-server.exe' ? [dir] : []);
          const source = find(path.join(temp, 'out'))[0];
          if (!source) throw new Error('Redis executable missing from archive');
          fs.mkdirSync(destination, { recursive: true }); fs.cpSync(source, destination, { recursive: true });
        } finally { fs.rmSync(temp, { recursive: true, force: true }); }
      }
      env.PRISM_REDIS_SERVER = executable;
    } else if (!fs.existsSync(redis) && !fs.existsSync(bundledRedis)) {
      let failure;
      for (const channel of ['https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge', 'conda-forge']) {
        try { await run(mm, ['install', '-y', '-p', envDir, '--override-channels', '-c', channel, 'redis-server'], { env }); failure = null; break; }
        catch (error) { failure = error; }
      }
      if (failure) throw failure;
    }
    await ensureComponents(root, data, python, env);
    const browserStamp = path.join(data, '.chromium-ready');
    env.PLAYWRIGHT_BROWSERS_PATH = path.join(data, 'components/browsers/patchright/versions/current');
    if (!fs.existsSync(browserStamp) || !fs.existsSync(env.PLAYWRIGHT_BROWSERS_PATH)) {
      let failure;
      for (const host of ['https://npmmirror.com/mirrors/playwright', '']) {
        try { await run(python, ['-m', 'patchright', 'install', 'chromium'], { env: { ...env, PLAYWRIGHT_DOWNLOAD_HOST: host, PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT: '30000' } }); failure = null; break; }
        catch (error) { failure = error; }
      }
      if (failure) throw failure;
      fs.writeFileSync(browserStamp, 'ready');
    }
    const manifest = { manager: 'micromamba', envDir, python, componentRoot: env.PRISM_COMPONENT_ENV_DIR,
      environment: Object.fromEntries(Object.entries(env).filter(([key]) => /^PRISM_(ENV_DIR|COMPONENT_ENV_DIR|RUNTIME_DATA_DIR|MICROMAMBA|HERMES_SOURCE|HERMES_WEBUI_SOURCE|PERSONA_SOURCE|HERMES_PYTHON|HERMES_HOME|REDIS_SERVER)$/.test(key) || key === 'HERMES_HOME' || key === 'PLAYWRIGHT_BROWSERS_PATH' || key === 'MAMBA_ROOT_PREFIX')) };
    fs.writeFileSync(path.join(data, 'runtime-manifest.json.tmp'), JSON.stringify(manifest, null, 2));
    fs.renameSync(path.join(data, 'runtime-manifest.json.tmp'), path.join(data, 'runtime-manifest.json'));
    Object.assign(process.env, env);
    return manifest;
  } finally { fs.unlinkSync(path.join(lock, 'owner.json')); fs.rmdirSync(lock); }
}
module.exports = { ensureRuntime, ensureComponents, download, run, target };
if (require.main === module) {
  const root = path.resolve(__dirname, '../..');
  const existing = path.join(root, 'prismenv');
  const data = process.env.PRISM_RUNTIME_DATA_DIR || path.join(root, 'runtime-data');
  const command = process.argv[2] || 'start';
  const prepare = ['stop', 'status'].includes(command)
    ? Promise.resolve().then(() => { const manifest = JSON.parse(fs.readFileSync(path.join(data, 'runtime-manifest.json'), 'utf8')); Object.assign(process.env, manifest.environment || {}, { PRISM_ENV_DIR: manifest.envDir }); return manifest; })
    : ensureRuntime(root, data, { envDir: process.env.PRISM_ENV_DIR || (fs.existsSync(path.join(existing, 'conda-meta')) ? existing : undefined) });
  prepare
    .then(manifest => run(manifest.python, [path.join(root, 'bootstrap.py'), ...(process.argv.slice(2).length ? process.argv.slice(2) : ['start'])], { cwd: root, env: process.env }))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}
