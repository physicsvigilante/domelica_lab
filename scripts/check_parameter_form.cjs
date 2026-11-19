#!/usr/bin/env node
"use strict";
// Exercise the actual parameter page in Chromium; native HTTP integration is
// separately tested in the compiler-free Python container.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const repo = path.resolve(__dirname, "..");
  const app = fs.readFileSync(path.join(repo, "viewer/parameter-lab.html"), "utf8");
  const js = fs.readFileSync(path.join(repo, "viewer/parameter-lab.js"), "utf8");
  const definitions = JSON.parse(fs.readFileSync(path.join(repo, "viewer/compiled-experiments.json"), "utf8"));
  const url = "http://127.0.0.1:8765/";
  const requests = [];
  const errors = [];
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
    page.on("pageerror", error => errors.push(String(error)));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    await page.route("**/*", async route => {
      const req = route.request(), target = new URL(req.url());
      if (target.pathname === "/") return route.fulfill({ status: 200, contentType: "text/html", body: app });
      if (target.pathname === "/app.js") return route.fulfill({ status: 200, contentType: "text/javascript", body: js });
      if (target.pathname === "/favicon.ico") return route.fulfill({ status: 204 });
      if (target.pathname === "/api/config") return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ model: definitions.model, parameters: definitions.parameters }) });
      if (target.pathname === "/api/run") {
        requests.push({ headers: req.headers(), data: req.postDataJSON() });
        return route.fulfill({ status: 200, contentType: "application/json",
          body: JSON.stringify({ runId: "rfake", url: "/runs/rfake/viewer.html", parameters: req.postDataJSON().parameters,
            samples: 1202, simulatedSeconds: 6, runtimeCompilerInvocations: 0 }) });
      }
      if (target.pathname === "/runs/rfake/viewer.html") return route.fulfill({ status: 200,
        contentType: "text/html", body: "<!doctype html><title>Fresh recorded motion</title>" });
      throw new Error("Unexpected browser request: " + req.url());
    });
    await page.goto(url, { waitUntil: "load" });
    await page.waitForFunction(() => document.getElementById("param-cartMass") !== null);
    assert.equal(await page.locator("#inputs input").count(), 4);
    await page.getByLabel("Cart mass (kg)").fill("3.37");
    await page.getByLabel("Pendulum mass (kg)").fill("0.76");
    await page.getByLabel("Spring stiffness (N/m)").fill("18");
    await page.getByLabel("Release angle (degrees)").fill("45");
    await page.getByRole("button", { name: "Run fresh simulation" }).click();
    await page.waitForFunction(() => document.getElementById("result").getAttribute("src") === "/runs/rfake/viewer.html");
    assert.equal(requests.length, 1);
    const posted = requests[0];
    assert.equal(posted.headers["x-domelica-request"], "1");
    assert.equal(posted.data.parameters.cartMass, 3.37);
    assert.equal(posted.data.parameters.bobMass, 0.76);
    assert.equal(posted.data.parameters.springStiffness, 18);
    assert.ok(Math.abs(posted.data.parameters.initialAngle - Math.PI / 4) < 1e-12);
    assert.equal(await page.locator("#result").isVisible(), true);
    assert.equal(await page.locator("#download").getAttribute("href"), "/runs/rfake/viewer.html");
    assert.match(await page.locator("#status").textContent(), /0 runtime compiler calls/);
    await page.getByLabel("Cart mass (kg)").fill("0");
    await page.getByRole("button", { name: "Run fresh simulation" }).click();
    assert.equal(requests.length, 1, "Invalid value must not launch another run");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: true, browser: browser.version(),
      parameters: posted.data.parameters, runRequestCount: requests.length,
      checks: ["actual form inputs", "unit conversion", "same-origin request header",
        "new recording iframe and download", "native-run status", "invalid value refused", "no browser errors"] }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
