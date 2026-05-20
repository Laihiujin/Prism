const path = require("path");

const { _electron: electron } = require(path.join(
  __dirname,
  "..",
  "..",
  "syn_frontend_react",
  "node_modules",
  "playwright"
));
const electronBinary = require(path.join(
  __dirname,
  "..",
  "node_modules",
  "electron"
));

const repoRoot = path.resolve(__dirname, "..", "..");
const desktopDir = path.join(repoRoot, "desktop-electron");

async function waitForHttp(url, attempts = 40, delayMs = 2000) {
  let lastError = null;
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(url);
      const text = await response.text();
      let data = null;
      try {
        data = JSON.parse(text);
      } catch {
        data = null;
      }

      if (response.ok) {
        return { ok: true, status: response.status, data, text };
      }
      lastError = `HTTP ${response.status}: ${text}`;
    } catch (error) {
      lastError = error.message;
    }

    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }

  return { ok: false, error: lastError };
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function main() {
  const app = await electron.launch({
    executablePath: electronBinary,
    args: ["."],
    cwd: desktopDir,
    env: {
      ...process.env,
      SYNAPSE_START_SERVICES: "1",
      SYNAPSE_START_FRONTEND: "1",
      PLAYWRIGHT_AUTO_INSTALL: "0",
    },
    timeout: 120000,
  });

  try {
    const page = await app.firstWindow();
    const consoleTail = [];
    page.on("console", (msg) => {
      consoleTail.push(`${msg.type()}: ${msg.text()}`);
    });

    await page.waitForLoadState("domcontentloaded", { timeout: 180000 });
    await page.waitForTimeout(5000);

    const electronState = await page.evaluate(async () => {
      const api = globalThis.electronAPI;
      const payload = {
        hasElectronAPI: !!api,
        apiKeys: api ? Object.keys(api) : [],
      };

      if (!api) {
        return payload;
      }

      payload.appInfo = await api.app.getInfo();
      payload.browserRuntime = await api.browserRuntime.getStatus();
      payload.systemStatus = await api.system.getStatus();
      payload.uninstallPatchright = await api.browserRuntime.uninstall("patchright");
      payload.afterUninstall = await api.browserRuntime.getStatus();
      payload.installPatchright = await api.browserRuntime.install("patchright");
      payload.afterInstall = await api.browserRuntime.getStatus();

      return payload;
    });

    assert(electronState.hasElectronAPI, "electronAPI is not available in the renderer");
    assert(
      Array.isArray(electronState.apiKeys) &&
        electronState.apiKeys.includes("browserRuntime") &&
        electronState.apiKeys.includes("system"),
      `electronAPI is missing required namespaces: ${JSON.stringify(electronState.apiKeys)}`
    );

    const appInfo = electronState.appInfo || {};
    const runtimeInfo = electronState.browserRuntime || {};
    const browserRuntimeInfo = runtimeInfo.browserRuntimeInfo || {};
    const pythonRuntime = browserRuntimeInfo.pythonRuntime || {};

    assert(runtimeInfo.success === true, `browserRuntime.getStatus failed: ${runtimeInfo.error || "unknown_error"}`);
    assert(
      pythonRuntime.source === "synenv",
      `Expected Python runtime source=synenv, received ${pythonRuntime.source || "missing"}`
    );
    assert(
      browserRuntimeInfo.runtimes?.patchright?.installed === true,
      "Patchright should be installed before uninstall/install smoke test"
    );

    assert(
      electronState.uninstallPatchright?.success === true,
      `Patchright uninstall failed: ${electronState.uninstallPatchright?.error || "unknown_error"}`
    );
    assert(
      electronState.afterUninstall?.browserRuntimeInfo?.runtimes?.patchright?.installed === false,
      "Patchright should be absent after uninstall"
    );
    assert(
      electronState.installPatchright?.success === true,
      `Patchright install failed: ${electronState.installPatchright?.error || "unknown_error"}`
    );
    assert(
      electronState.afterInstall?.browserRuntimeInfo?.runtimes?.patchright?.installed === true,
      "Patchright should be restored after install"
    );

    const backendPort = appInfo.backendPort || 7000;
    const frontendPort = appInfo.frontendPort || 3000;
    const health = await waitForHttp(`http://127.0.0.1:${backendPort}/health`, 40, 2000);
    const browserRuntimeStatus = await waitForHttp(
      `http://127.0.0.1:${backendPort}/api/v1/system/browser-runtime/status`,
      20,
      2000
    );
    const frontendRoot = await waitForHttp(`http://127.0.0.1:${frontendPort}/`, 20, 1000);

    assert(health.ok, `Backend /health is unavailable: ${health.error || health.text}`);
    assert(
      String(health.data?.status || "").toLowerCase() === "healthy",
      `Backend /health returned unexpected payload: ${JSON.stringify(health.data)}`
    );
    assert(
      browserRuntimeStatus.ok && browserRuntimeStatus.data?.success === true,
      `Backend browser-runtime status endpoint failed: ${browserRuntimeStatus.error || browserRuntimeStatus.text}`
    );
    assert(frontendRoot.ok, `Frontend root is unavailable: ${frontendRoot.error || frontendRoot.text}`);

    console.log(
      JSON.stringify(
        {
          electronWindowUrl: page.url(),
          pythonRuntimeSource: pythonRuntime.source,
          pythonPath: browserRuntimeInfo.pythonPath,
          activeRuntime: browserRuntimeInfo.activeRuntime,
          backendPort,
          frontendPort,
          consoleTail: consoleTail.slice(-20),
        },
        null,
        2
      )
    );
  } finally {
    await app.close();
  }
}

main().catch((error) => {
  console.error("ELECTRON_RUNTIME_SMOKE_FAILED");
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
