#!/usr/bin/env node
/* Browser checks against the actual generated native artifact, never fixture data.
 * Usage: node scripts/check_viewer.cjs artifacts/browser-preview.html
 * Requires Playwright and its Chromium browser (installed separately by CI).
 */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createHash } = require("node:crypto");
const { chromium } = require("playwright");

const input = path.resolve(process.argv[2] || "artifacts/browser-preview.html");
const output = path.join(path.dirname(input), "browser-checks");
fs.mkdirSync(output, { recursive: true });
const report = {
  passed: false,
  artifact: path.basename(input),
  artifactSha256: null,
  browser: null,
  steps: [],
  scenes: [],
  screenshots: [],
  pageErrors: [],
  consoleErrors: [],
  unexpectedRequests: [],
};
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
const record = (name, detail = {}) => {
  report.steps.push({ name, passed: true, ...detail });
  console.log("PASS", name);
};
const closestIndex = (times, target) => {
  let index = 0;
  for (let i = 1; i < times.length; i++) {
    if (Math.abs(times[i] - target) < Math.abs(times[index] - target)) index = i;
  }
  return index;
};

// Independently project conservative envelopes for every exported object frame.
// This verifies camera fit over the whole run, including the old clipping case.
// It does not establish that the exporter matches the Modelica mechanics.
function checkFraming(scene, camera, viewport) {
  const { yaw, pitch, center, radius, zoom } = camera;
  const right = [Math.cos(yaw), 0, -Math.sin(yaw)];
  const up = [-Math.sin(yaw) * Math.sin(pitch), Math.cos(pitch), -Math.cos(yaw) * Math.sin(pitch)];
  const scale = Math.min(viewport.width, viewport.height) * 0.405 / radius * zoom;
  const dot = (a, b) => a.reduce((sum, v, i) => sum + v * b[i], 0);
  let margin = Infinity;
  let cornerCount = 0;
  for (const object of scene.objects) {
    for (const frame of object.frames) {
      for (const x of [0, 1]) for (const y of [-0.5, 0.5]) for (const z of [-0.5, 0.5]) {
        const v = [0, 1, 2].map(k => frame[9 + k] + x * frame[k] + y * frame[3 + k] + z * frame[6 + k] - center[k]);
        const screenX = viewport.width / 2 + dot(v, right) * scale;
        const screenY = viewport.height / 2 - dot(v, up) * scale;
        const distance = Math.min(screenX, screenY, viewport.width - screenX, viewport.height - screenY);
        assert.ok(Number.isFinite(distance), `Nonfinite projected position: ${scene.id}/${object.id}`);
        assert.ok(distance >= -0.01, `Clipped native envelope: ${scene.id}/${object.id}, margin ${distance}px`);
        margin = Math.min(margin, distance);
        cornerCount++;
      }
    }
  }
  return { checkedCorners: cornerCount, minimumMarginPx: Number(margin.toFixed(3)) };
}

async function main() {
  let browser, page;
  try {
    assert.ok(fs.existsSync(input), `Native HTML artifact is missing: ${input}`);
    report.artifactSha256 = sha256(fs.readFileSync(input));
    browser = await chromium.launch({ headless: true });
    report.browser = browser.version();
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1080 },
      deviceScaleFactor: 1,
      reducedMotion: "reduce",
    });
    page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on("pageerror", error => report.pageErrors.push(error.message));
    page.on("console", message => {
      if (message.type() === "error") report.consoleErrors.push(message.text());
    });
    const fileURL = pathToFileURL(input).href;
    page.on("request", request => {
      if (request.url() !== fileURL && !request.url().startsWith("data:")) {
        report.unexpectedRequests.push(request.url());
      }
    });
    page.on("websocket", socket => report.unexpectedRequests.push(socket.url()));
    // Enforce offline execution rather than allowing a CDN fallback to pass.
    await context.route(/^https?:\/\//, route => route.abort());
    await page.goto(fileURL, { waitUntil: "load" });
    await page.waitForFunction(() => Boolean(window.__domelica));
    assert.equal(await page.locator("#error").isVisible(), false);
    const payload = await page.evaluate(() => D);
    assert.equal(payload.schema, "domelica.native-scene.v1");
    assert.equal(payload.scenes.length, 3, "This milestone should contain three native scenes");
    assert.equal(new Set(payload.scenes.map(scene => scene.id)).size, 3);
    report.provenance = payload.provenance;
    report.scenes = payload.scenes.map(scene => ({
      id: scene.id,
      model: scene.model,
      samples: scene.times.length,
      objects: scene.objects.length,
      signals: scene.series.length,
      timeRange: [scene.times[0], scene.times.at(-1)],
    }));
    const state = () => page.evaluate(() => window.__domelica.getState());
    const screenshot = async name => {
      await page.screenshot({ path: path.join(output, name), fullPage: true, animations: "disabled" });
      report.screenshots.push(name);
    };
    const switchTo = async scene => {
      const tabIndex = payload.scenes.findIndex(item => item.id === scene.id);
      await page.locator(".scene-tab").nth(tabIndex).click();
      await page.waitForFunction(id => window.__domelica.getState().sceneId === id, scene.id);
      const current = await state();
      assert.equal(current.index, 0, "Switching scenes should reset the sample");
      assert.equal(current.playing, false, "Scene changes should preserve paused state");
      return current;
    };
    const seekTime = async (scene, time) => {
      const index = closestIndex(scene.times, time);
      await page.evaluate(i => window.__domelica.seek(i), index);
      const current = await state();
      assert.equal(current.index, index);
      assert.equal(current.time, scene.times[index]);
      assert.equal(current.playing, false);
      return current;
    };

    let current = await state();
    assert.equal(current.playing, false, "Reduced-motion preference must disable autoplay");
    assert.equal(current.index, 0);
    record("initial native payload and reduced-motion behavior", { state: current });

    // Every scene is opened with the visible tab controls, and its UI is compared
    // against the actual embedded native data rather than hardcoded object counts.
    for (const scene of payload.scenes) {
      current = await switchTo(scene);
      assert.ok(scene.times.length >= 50);
      assert.ok(scene.objects.length > 0);
      assert.equal(current.objectCount, scene.objects.length);
      assert.equal(await page.locator("#objectList button").count(), scene.objects.length);
      assert.equal(await page.locator("#plots canvas").count(), scene.series.length);
      assert.equal(await page.locator("#title").textContent(), scene.title);
      assert.equal(await page.locator("#scrub").getAttribute("max"), String(scene.times.length - 1));
      const canvasBox = await page.locator("#scene").boundingBox();
      const framing = checkFraming(scene, current.camera, canvasBox);
      const paintedPixels = await page.locator("#scene").evaluate(canvas => {
        const pixels = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
        let count = 0;
        for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) count++;
        return count;
      });
      assert.ok(paintedPixels > 500, "Scene canvas was not painted");
      record(`native scene controls and framing: ${scene.id}`, { objects: current.objectCount, plots: scene.series.length, paintedPixels, ...framing });
    }

    const arm = payload.scenes.find(scene => scene.model.endsWith(".ThermalGearedArm3D"));
    const pendulum = payload.scenes.find(scene => scene.model.endsWith(".MotorizedPendulum3D"));
    const baseline = payload.scenes.find(scene => scene.model.endsWith(".DoublePendulum"));
    assert.ok(arm && pendulum && baseline, "Expected authored spatial arm, pendulum, and MSL baseline");
    await switchTo(arm);
    const beforeMotion = sha256(await page.locator("#scene").screenshot());
    await page.locator("#play").click();
    await page.waitForFunction(() => window.__domelica.getState().time > 0.35, null, { timeout: 8000 });
    await page.locator("#play").click();
    current = await state();
    assert.equal(current.playing, false);
    const pausedIndex = current.index;
    await page.waitForTimeout(200);
    assert.equal((await state()).index, pausedIndex, "Pause must stop native time");
    const afterMotion = sha256(await page.locator("#scene").screenshot());
    assert.notEqual(afterMotion, beforeMotion, "Native playback must alter the rendered scene");
    record("Play advances native time and pixels; Pause stops time", { state: current });

    // Use a genuine range-input keyboard gesture to test the scrubbing handler.
    await page.locator("#scrub").focus();
    await page.locator("#scrub").press("End");
    current = await state();
    assert.equal(current.index, arm.times.length - 1);
    assert.equal(current.time, arm.times.at(-1));
    assert.equal(current.playing, false);
    assert.equal(await page.locator("#play").textContent(), "Replay");
    await page.locator("#play").click();
    await page.waitForFunction(() => window.__domelica.getState().time > 0.1, null, { timeout: 8000 });
    current = await state();
    assert.equal(current.playing, true);
    assert.ok(current.time < arm.times.at(-1));
    await page.locator("#play").click();
    await page.locator("#speed").selectOption("2");
    assert.equal(await page.locator("#speed").inputValue(), "2");
    await page.locator("#speed").selectOption("1");
    record("time scrub, end state, Replay, and speed selection", { state: await state() });

    current = await seekTime(arm, 1.8);
    // Displayed measurements must be synchronized with the recorded sample.
    const displayed = await page.locator(".plot-value > span:first-child").allTextContents();
    arm.series.forEach((series, i) => {
      const actual = Number(displayed[i]);
      const expected = series.values[current.index];
      const rounding = Math.abs(expected) >= 1e4 || (Math.abs(expected) > 0 && Math.abs(expected) < 1e-4)
        ? Math.abs(expected) * 0.006
        : Math.abs(expected) >= 100 ? 0.00501 : 0.000501;
      assert.ok(Math.abs(actual - expected) <= rounding, `Signal readout differs from native sample: ${series.name}`);
    });
    await page.locator("#view3d").click();
    await screenshot("01-thermal-arm.png");
    record("native signal readouts at selected time", { time: current.time, readouts: displayed });

    await page.locator("#viewxy").click();
    current = await state();
    assert.equal(current.camera.yaw, 0);
    assert.equal(current.camera.pitch, 0);
    let box = await page.locator("#scene").boundingBox();
    await page.mouse.move(box.x + box.width * 0.48, box.y + box.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.61, box.y + box.height * 0.44, { steps: 8 });
    await page.mouse.up();
    const orbit = await state();
    assert.ok(Math.abs(orbit.camera.yaw) > 0.1 && Math.abs(orbit.camera.pitch) > 0.05);
    await page.mouse.wheel(0, -250);
    await page.waitForFunction(() => window.__domelica.getState().camera.zoom > 1);
    await page.locator("#fit").click();
    current = await state();
    assert.equal(current.camera.zoom, 1);
    assert.equal(current.camera.yaw, orbit.camera.yaw, "Fit should preserve the chosen orientation");
    box = await page.locator("#scene").boundingBox();
    const orbitFraming = checkFraming(arm, current.camera, box);
    await screenshot("02-thermal-arm-orbit.png");
    record("XY, pointer orbit, wheel zoom, and Fit", { state: current, ...orbitFraming });

    await page.locator("#objects summary").click();
    await page.locator("#objectList button").first().click();
    current = await state();
    assert.equal(current.selected, arm.objects[0].id);
    assert.ok((await page.locator("#inspector").textContent()).includes(arm.objects[0].id));
    assert.ok((await page.locator("#inspector").textContent()).includes("origin ("));
    await page.locator("#objects summary").click();
    record("native object inspector", { selected: current.selected });

    await switchTo(pendulum);
    current = await seekTime(pendulum, 1.0);
    await page.locator("#viewxy").click();
    current = await state();
    box = await page.locator("#scene").boundingBox();
    const pendulumFraming = checkFraming(pendulum, current.camera, box);
    await screenshot("03-motorized-pendulum-xy.png");
    record("rotating pendulum clipping regression", { time: current.time, ...pendulumFraming });

    await switchTo(baseline);
    current = await seekTime(baseline, 0.5);
    await screenshot("04-msl-double-pendulum.png");
    record("unchanged MSL baseline in the same renderer", { state: current });

    await switchTo(arm);
    await seekTime(arm, 1.8);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(() => {
      const canvas = document.querySelector("#scene");
      return innerWidth === 390 && Math.abs(canvas.width - canvas.getBoundingClientRect().width) <= 1;
    });
    const dimensions = await page.evaluate(() => ({
      viewport: innerWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      canvas: document.querySelector("#scene").getBoundingClientRect().width,
    }));
    assert.ok(dimensions.document <= dimensions.viewport + 1, "Mobile page overflows horizontally");
    assert.ok(dimensions.body <= dimensions.viewport + 1, "Mobile body overflows horizontally");
    current = await state();
    box = await page.locator("#scene").boundingBox();
    const mobileFraming = checkFraming(arm, current.camera, box);
    await screenshot("05-mobile.png");
    record("390 px mobile layout and trajectory framing", { dimensions, ...mobileFraming });

    assert.deepEqual(report.pageErrors, [], "Unexpected browser exceptions");
    assert.deepEqual(report.consoleErrors, [], "Unexpected browser console errors");
    assert.deepEqual(report.unexpectedRequests, [], "Offline preview attempted external requests");
    record("offline execution without browser errors");
    report.passed = true;
  } catch (error) {
    report.error = { name: error.name, message: error.message, stack: error.stack };
    if (page) {
      try {
        await page.screenshot({ path: path.join(output, "failure.png"), fullPage: true });
        report.screenshots.push("failure.png");
      } catch (_) { /* Preserve the original failure if the browser has exited. */ }
    }
    console.error("FAIL native viewer checks:", error.message);
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
    if (browser) await browser.close();
  }
  if (report.passed) console.log(`PASS browser playback verification: ${report.steps.length} checks; ${report.screenshots.length} screenshots`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
