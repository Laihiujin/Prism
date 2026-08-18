#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { webcrypto } = require("crypto");
const { JSDOM } = require("jsdom");
const NODE_STDOUT = process.stdout;

const ROOT = __dirname;
const SDK_GLUE = fs.readFileSync(path.join(ROOT, "vendor", "sdk-glue-1.0.0.62.js"), "utf8");
const BDMS = fs.readFileSync(path.join(ROOT, "vendor", "bdms-1.0.1.16.js"), "utf8");
const DTRAIT = fs.readFileSync(path.join(ROOT, "vendor", "dtrait-1.0.0.16.js"), "utf8");
const ZERO_TRUST = fs.readFileSync(path.join(ROOT, "vendor", "zero-trust-1.0.0.381.js"), "utf8");
const ZERO_TRUST_RSA = fs.readFileSync(
  path.join(ROOT, "vendor", "zero-trust-rsa-414.330fdc91.js"), "utf8",
);
const VERIFY_CENTER = fs.readFileSync(path.join(ROOT, "vendor", "verifycenter-1.0.0.399.js"), "utf8");

let abogusCache = null;
function runtime(userAgent) {
  if (abogusCache && abogusCache.userAgent === userAgent) return abogusCache.window;
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://creator.douyin.com/creator-micro/login?enter_from=qr",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const window = dom.window;
  window.console = { log() {}, error() {}, warn() {}, info() {}, debug() {} };
  Object.defineProperty(window.navigator, "userAgent", { value: userAgent });
  // Match the actual Chromium login collector, not jsdom defaults.  Passport
  // binds account_sdk_source_info to the same environment that emits D-Trait.
  Object.defineProperty(window.navigator, "hardwareConcurrency", { value: 15 });
  Object.defineProperty(window.navigator, "webdriver", { value: true });
  Object.defineProperty(window.navigator, "plugins", { value: { length: 5 } });
  for (const [key, value] of Object.entries({ innerWidth: 1280, innerHeight: 800, outerWidth: 1280, outerHeight: 800 })) {
    Object.defineProperty(window, key, { value });
  }
  Object.defineProperty(window, "crypto", { value: webcrypto });
  window.HTMLCanvasElement.prototype.getContext = () => ({
    fillRect() {}, fillText() {}, measureText() { return { width: 1 }; },
    getImageData() { return { data: new Uint8ClampedArray(4) }; },
  });
  window.HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,";
  window.TextEncoder = TextEncoder;
  window.TextDecoder = TextDecoder;
  window.BroadcastChannel = class {};
  window.Worker = class {};
  window.fetch = async (url, options = {}) => {
    if (String(url).startsWith("https://mssdk.bytedance.com/")) {
      const response = await globalThis.fetch(String(url), options);
      const token = response.headers.get("x-ms-token");
      if (token) {
        window.__msToken = token;
        window.localStorage.setItem("xmst", token);
      }
      return response;
    }
    window.__signedUrl = String(url);
    window.__signedHeaders = Object.fromEntries(new window.Headers(options.headers || {}).entries());
    return {
      clone() { return this; },
      headers: new window.Headers(),
      json: async () => ({}),
      text: async () => "",
    };
  };
  window._sdkGlueVersionMap = {
    sdkGlueVersion: "1.0.0.62", bdmsVersion: "1.0.1.16", captchaVersion: "4.0.26",
  };
  window.eval(DTRAIT);
  window.eval(ZERO_TRUST_RSA);
  window.eval(ZERO_TRUST);
  // Passport obtains fp/verifyFp from this SDK.  Keep it in the same window as
  // MSSDK, D-Trait and BDMS so every anti-abuse field describes one device.
  window.eval(VERIFY_CENTER);
  window.eval(SDK_GLUE);
  window.eval(BDMS);
  window._SdkGlueInit({ bdms: { paths: ["/passport/"], boe: false }, aid: 2906 });
  abogusCache = { userAgent, window };
  return window;
}

let dtraitCache = null;
function dtraitRuntime(userAgent) {
  if (dtraitCache && dtraitCache.userAgent === userAgent) return dtraitCache.window;
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://creator.douyin.com/creator-micro/login?enter_from=qr",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const window = dom.window;
  window.console = { log() {}, error() {}, warn() {}, info() {}, debug() {} };
  Object.defineProperty(window.navigator, "userAgent", { value: userAgent });
  Object.defineProperty(window, "crypto", { value: webcrypto });
  window.TextEncoder = TextEncoder;
  window.TextDecoder = TextDecoder;
  window.BroadcastChannel = class {};
  window.Worker = class {};
  window.fetch = async (url, options = {}) => {
    window.__signedHeaders = Object.fromEntries(new window.Headers(options.headers || {}).entries());
    return {
      clone() { return this; }, headers: new window.Headers(),
      json: async () => ({}), text: async () => "",
    };
  };
  window.eval(DTRAIT);
  // The Zero Trust bundle lazy-loads this webpack chunk in browsers. Preload
  // it locally so the central RSA segment is generated without network/script tags.
  window.eval(ZERO_TRUST_RSA);
  window.eval(ZERO_TRUST);
  dtraitCache = { userAgent, window };
  return window;
}

async function sign(input) {
  const window = runtime(input.userAgent);
  const verifyFp = await window.getCaptchaWebId();
  if (!window.__signerWarm) {
    const deadline = Date.now() + 3000;
    while (!window.__msToken && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    window.__signerWarm = true;
  }
  await window.fetch(
    `${input.url || "https://creator.douyin.com/passport/web/check_qrconnect/"}?${input.query}`,
    { method: input.method || "POST", body: input.body || undefined, headers: input.headers || {} },
  );
  const signedUrl = new URL(window.__signedUrl);
  const signature = signedUrl.searchParams.get("a_bogus");
  const msToken = signedUrl.searchParams.get("msToken") || window.__msToken;
  const sourceInfo = {
    hardwareConcurrency: window.navigator.hardwareConcurrency,
    webdriver: Boolean(window.navigator.webdriver),
    chromedriver: false, shelldriver: false,
    plugins: window.navigator.plugins.length,
    innerHeight: window.innerHeight, innerWidth: window.innerWidth,
    outerHeight: window.outerHeight, outerWidth: window.outerWidth,
    webgl: { vendor: "Google Inc. (Apple)", renderer: "ANGLE (Apple, ANGLE Metal Renderer: Apple M5 Pro, Unspecified Version)" },
    automation: { s: "00000000", c: "0000", p: "1000000", s1: "10100000", c1: "0011", p1: "1" },
    performance: { timeOrigin: window.performance.timeOrigin, usedJSHeapSize: 44732153,
      navigationTiming: { decodedBodySize: 17221, entryType: "navigation", initiatorType: "navigation",
        name: "https://creator.douyin.com/creator-micro/login?enter_from=qr", renderBlockingStatus: "non-blocking",
        serverTiming: "inner,cdn-cache,edge,origin", guleStart: "none", guleDuration: "none" } },
    browser: { t: String(Math.trunc(window.performance.timeOrigin * 2.746)), bit_protocol: "false", bit_helper: false },
  };
  const sourceInfoHex = Buffer.from(JSON.stringify(sourceInfo), "utf8")
    .map((value) => value ^ 5).toString("hex");
  if (!signature) throw new Error("web signer did not append a_bogus");
  const dTrait = window.__signedHeaders && window.__signedHeaders["x-tt-session-dtrait"];
  if (!dTrait) throw new Error("web signer did not append x-tt-session-dtrait");
  return { a_bogus: signature, x_tt_session_dtrait: dTrait, ms_token: msToken || undefined,
    account_sdk_source_info: sourceInfoHex, verify_fp: verifyFp };
}

console.error = () => {};
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
lines.on("line", async (line) => {
  try {
    const input = JSON.parse(line);
    const signed = await sign(input);
    NODE_STDOUT.write(JSON.stringify({ ok: true, ...signed }) + "\n");
  } catch (error) {
    NODE_STDOUT.write(JSON.stringify({ ok: false, error: String(error) }) + "\n");
  }
});
