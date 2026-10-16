// The public connector is a separate PM2 process; it forwards only the CMS gateway.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { download, run } = require('./ensure-runtime.cjs');
const { locations, readJson, writeJson, runtimeMode } = require('./cms-gateway.cjs');
async function main() {
  const dirs = locations(); const config = readJson(path.join(dirs.cms, 'config.json'));
  if (!config.publicEnabled) return;
  if (!readJson(path.join(dirs.cms, 'auth.json')).hash) throw new Error('Configure a CMS password before enabling public access');
  const binary = path.join(dirs.data, 'bin', process.platform === 'win32' ? 'cloudflared.exe' : 'cloudflared');
  if (!fs.existsSync(binary)) {
    const assetName = { 'win32-x64': 'cloudflared-windows-amd64.exe', 'darwin-x64': 'cloudflared-darwin-amd64.tgz',
      'darwin-arm64': 'cloudflared-darwin-arm64.tgz', 'linux-x64': 'cloudflared-linux-amd64', 'linux-arm64': 'cloudflared-linux-arm64' }[`${process.platform}-${process.arch}`];
    if (!assetName) throw new Error('Unsupported Cloudflare connector platform');
    const response = await fetch('https://api.github.com/repos/cloudflare/cloudflared/releases/latest', { signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error(`Connector release lookup failed: ${response.status}`);
    const asset = (await response.json()).assets.find(asset => asset.name === assetName);
    if (!asset?.digest?.startsWith('sha256:')) throw new Error('Connector release has no verified SHA256 digest');
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-cms-tunnel-'));
    try {
      const file = path.join(temp, assetName);
      const mirrors = (process.env.PRISM_GITHUB_MIRRORS || '').split('|').filter(Boolean).map(prefix => prefix + asset.browser_download_url);
      await download([...mirrors, asset.browser_download_url, asset.url], file, asset.digest.slice(7));
      let executable = file;
      if (assetName.endsWith('.tgz')) { await run('tar', ['-xzf', file, '-C', temp, 'cloudflared']); executable = path.join(temp, 'cloudflared'); }
      fs.mkdirSync(path.dirname(binary), { recursive: true }); fs.copyFileSync(executable, binary); fs.chmodSync(binary, 0o755);
    } finally { fs.rmSync(temp, { recursive: true, force: true }); }
  }
  const stateFile = path.join(dirs.cms, 'public.json');
  writeJson(stateFile, { url: null, mode: runtimeMode(), pid: process.pid });
  // An empty dedicated config prevents an unrelated user's Cloudflare config from taking over.
  const emptyConfig = path.join(dirs.cms, 'cloudflared.yml'); fs.writeFileSync(emptyConfig, '{}\n');
  const child = spawn(binary, ['tunnel', '--config', emptyConfig, '--no-autoupdate', '--url', `http://127.0.0.1:${process.env.PRISM_CMS_PORT || 8441}`, '--protocol', 'http2'],
    { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  const report = chunk => {
    const text = chunk.toString(); const match = text.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com\b/);
    if (match) writeJson(stateFile, { url: match[0], mode: runtimeMode(), pid: process.pid, temporary: true, updatedAt: new Date().toISOString() });
    process.stdout.write(text);
  };
  child.stdout.on('data', report); child.stderr.on('data', report);
  const clear = () => { if (readJson(stateFile).pid === process.pid) writeJson(stateFile, { url: null, mode: runtimeMode() }); };
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => { clear(); child.kill(); setTimeout(() => process.exit(0), 500); });
  child.once('error', error => { clear(); console.error(error.message); process.exitCode = 1; });
  child.once('exit', code => { clear(); process.exitCode = code || 1; });
}
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
