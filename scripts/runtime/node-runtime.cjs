// A private Node/npm distribution for desktop component builds; no system installer.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
async function ensureNode(data, helpers) {
  const npmFor = node => [path.join(path.dirname(node), 'node_modules/npm/bin/npm-cli.js'),
    path.resolve(path.dirname(node), '../lib/node_modules/npm/bin/npm-cli.js')].find(file => fs.existsSync(file));
  if (!process.versions.electron && Number(process.versions.node.split('.')[0]) >= 22 && npmFor(process.execPath)) return { node: process.execPath, npm: npmFor(process.execPath) };
  const store = path.join(data, 'node'); fs.mkdirSync(store, { recursive: true });
  const manifestPath = path.join(store, 'runtime.json');
  try { const saved = JSON.parse(fs.readFileSync(manifestPath)); if (fs.existsSync(saved.node) && fs.existsSync(saved.npm)) return saved; } catch {}
  const suffix = `${process.platform}-${process.arch}.${process.platform === 'win32' ? 'zip' : 'tar.gz'}`;
  let failure;
  for (const base of ['https://nodejs.org/dist/latest-v22.x', 'https://npmmirror.com/mirrors/node/latest-v22.x']) {
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-node-'));
    try {
      const response = await fetch(`${base}/SHASUMS256.txt`, { signal: AbortSignal.timeout(30000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const line = (await response.text()).split('\n').find(line => line.trim().endsWith(suffix));
      if (!line) throw new Error(`Unsupported Node platform: ${suffix}`);
      const [hash, filename] = line.trim().split(/\s+/);
      const archive = path.join(temp, filename);
      await helpers.download([`${base}/${filename}`], archive, hash);
      await helpers.run('tar', ['-xf', archive, '-C', temp]);
      const folder = filename.replace(/\.(zip|tar.gz)$/, '');
      const destination = path.join(store, folder);
      fs.cpSync(path.join(temp, folder), destination, { recursive: true });
      const node = path.join(destination, process.platform === 'win32' ? 'node.exe' : 'bin/node');
      const result = { node, npm: npmFor(node) };
      if (!result.npm) throw new Error('Node archive has no npm');
      fs.writeFileSync(manifestPath, JSON.stringify(result));
      return result;
    } catch (error) { failure = error; }
    finally { fs.rmSync(temp, { recursive: true, force: true }); }
  }
  throw failure;
}
module.exports = { ensureNode };
