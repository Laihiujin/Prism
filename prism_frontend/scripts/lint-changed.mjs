import { execSync, spawnSync } from "node:child_process";

function sh(cmd, opts = {}) {
  return execSync(cmd, { stdio: ["ignore", "pipe", "pipe"], encoding: "utf8", ...opts }).trim();
}

function trySh(cmd) {
  try {
    return sh(cmd);
  } catch {
    return "";
  }
}

function refExists(ref) {
  return !!trySh(`git rev-parse --verify ${ref}`);
}

function pickBaseRef() {
  const envBase = process.env.LINT_BASE_REF || process.env.GITHUB_BASE_REF || process.env.CI_MERGE_REQUEST_TARGET_BRANCH_NAME;
  if (envBase) {
    if (refExists(envBase)) return envBase;
    if (refExists(`origin/${envBase}`)) return `origin/${envBase}`;
  }
  if (refExists("origin/main")) return "origin/main";
  if (refExists("origin/master")) return "origin/master";
  if (refExists("HEAD~1")) return "HEAD~1";
  return "HEAD";
}

const baseRef = pickBaseRef();
const diff = sh(`git diff --name-only --diff-filter=ACMR ${baseRef}...HEAD`);
const files = diff
  .split("\n")
  .map((s) => s.trim())
  .filter(Boolean)
  .filter((p) => p.match(/\.(js|jsx|ts|tsx)$/i))
  .map((p) => (p.startsWith("syn_frontend_react/") ? p.replace(/^syn_frontend_react\//, "") : p))
  .filter((p) => !p.startsWith("node_modules/"));

if (files.length === 0) {
  process.stdout.write("[lint:changed] no changed JS/TS files\n");
  process.exit(0);
}

process.stdout.write(`[lint:changed] base=${baseRef} files=${files.length}\n`);

const result = spawnSync(
  process.platform === "win32" ? "npx.cmd" : "npx",
  ["eslint", ...files],
  { stdio: "inherit" }
);

process.exit(result.status ?? 1);

