const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { download, target } = require('./ensure-runtime.cjs');
const { decision } = require('./pm2-recovery.cjs');

test('download fails over and rejects a bad checksum', async t => {
  const server = http.createServer((req, res) => {
    if (req.url === '/missing') { res.writeHead(503); res.end(); }
    else res.end(Buffer.alloc(2048, 42));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => server.close());
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-download-test-'));
  t.after(() => fs.rmSync(folder, { recursive: true, force: true }));
  const base = `http://127.0.0.1:${server.address().port}`;
  const file = path.join(folder, 'artifact');
  await download([base + '/missing', base + '/ok'], file);
  assert.equal(fs.statSync(file).size, 2048);
  await assert.rejects(download([base + '/ok'], file, 'bad'), /Checksum mismatch/);
});
test('recovery escalates once, then opens the circuit across controller restarts', () => {
  const proc = { name: 'prism-backend', pm2_env: { status: 'errored', restart_time: 5 } };
  const first = decision({}, proc, 1000);
  assert.equal(first.action, 'restart');
  assert.equal(decision(first, proc, 2000), null);
  const second = decision(JSON.parse(JSON.stringify(first)), proc, 62000);
  assert.equal(second.action, 'repair-dependencies');
  assert.equal(decision(second, proc, 183000).action, 'circuit-open');
  assert.equal(decision({}, { ...proc, pm2_env: { status: 'stopped' } }), null);
});
test('runtime platform is independent of the build machine', () => {
  assert.equal(target('darwin', 'arm64'), 'osx-arm64');
  assert.equal(target('darwin', 'x64'), 'osx-64');
  assert.equal(target('win32', 'x64'), 'win-64');
  assert.throws(() => target('win32', 'ia32'), /Unsupported/);
});
