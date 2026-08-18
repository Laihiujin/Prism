#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { JSDOM } = require("jsdom");

const ROOT = __dirname;
const SDK_GLUE = fs.readFileSync(path.join(ROOT, "vendor", "sdk-glue-1.0.0.62.js"), "utf8");
const BDMS = fs.readFileSync(path.join(ROOT, "vendor", "bdms-1.0.1.16.js"), "utf8");

function runtime(userAgent) {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://creator.douyin.com/creator-micro/login?enter_from=qr",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const window = dom.window;
  Object.defineProperty(window.navigator, "userAgent", { value: userAgent });
  window.HTMLCanvasElement.prototype.getContext = () => ({
    fillRect() {}, fillText() {}, measureText() { return { width: 1 }; },
    getImageData() { return { data: new Uint8ClampedArray(4) }; },
  });
  window.HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,";
  window.fetch = async (url) => { window.__signedUrl = String(url); return {}; };
  window._sdkGlueVersionMap = {
    sdkGlueVersion: "1.0.0.62", bdmsVersion: "1.0.1.16", captchaVersion: "4.0.26",
  };
  window.eval(SDK_GLUE);
  window.eval(BDMS);
  window._SdkGlueInit({ bdms: { paths: ["/passport/"], boe: false }, aid: 2906 });
  return window;
}

async function sign(input) {
  const window = runtime(input.userAgent);
  await new Promise((resolve) => setTimeout(resolve, 25));
  await window.fetch(
    `https://creator.douyin.com/passport/web/check_qrconnect/?${input.query}`,
    { method: "POST", body: input.body },
  );
  const signature = new URL(window.__signedUrl).searchParams.get("a_bogus");
  window.close();
  if (!signature) throw new Error("web signer did not append a_bogus");
  return signature;
}

console.error = () => {};
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
lines.on("line", async (line) => {
  try {
    const input = JSON.parse(line);
    const aBogus = await sign(input);
    process.stdout.write(JSON.stringify({ ok: true, a_bogus: aBogus }) + "\n");
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: String(error) }) + "\n");
  }
});
