#!/usr/bin/env node
"use strict";
// Browser acceptance against delivered native data, never a replacement solver.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createHash } = require("node:crypto");
const { chromium } = require("playwright");
const input = path.resolve(process.argv[2] || "artifacts/motion-preview.html");
const output = path.join(path.dirname(input), "motion-checks");
fs.mkdirSync(output, { recursive: true });
const sha = value => createHash("sha256").update(value).digest("hex");
const report = { passed: false, artifact: path.basename(input), artifactSha256: null,
  browser: null, steps: [], screenshots: [], pageErrors: [], unexpectedRequests: [] };
const record = (name, detail = {}) => { report.steps.push({ name, passed: true, ...detail }); console.log("PASS", name); };
const close = (a, b, tolerance = 1e-10) => assert.ok(Number.isFinite(a) && Math.abs(a - b) <= tolerance, `${a} differs from ${b}`);
const frameAt = (object, i) => object.frames[object.frames.length === 1 ? 0 : i];
const point = (frame, v) => [0, 1, 2].map(k => frame[9 + k] + v[0] * frame[k] + v[1] * frame[k + 3] + v[2] * frame[k + 6]);

function inspectSpring(object, sample, snapshot) {
  const spec = object.spring[object.spring.length === 1 ? 0 : sample];
  const [length, radius, wire, turns] = spec;
  assert.deepEqual(snapshot.spring.nativeSpring, spec);
  const { segments, radial, centers } = snapshot.spring;
  assert.equal(centers.length, 3 * (segments + 1));
  const positions = snapshot.geometryPositions;
  assert.ok(positions.length > (segments + 1) * (radial + 1) * 3);
  let radiusError = 0, centerError = 0;
  for (let i = 0; i <= segments; i++) {
    const u = i / segments, phase = 2 * Math.PI * turns * u;
    const expected = [length * u, radius * Math.sin(phase), radius * Math.cos(phase)];
    centers.slice(3 * i, 3 * i + 3).forEach((value, k) => { close(value, expected[k]); centerError = Math.max(centerError, Math.abs(value - expected[k])); });
    for (let j = 0; j <= radial; j++) {
      const offset = ((radial + 1) * i + j) * 3;
      const delta = positions.slice(offset, offset + 3).map((v, k) => v - expected[k]);
      radiusError = Math.max(radiusError, Math.abs(Math.hypot(...delta) - wire));
      close(Math.hypot(...delta), wire, 2e-7);
    }
  }
  return { centerError, wireRadiusError: radiusError, length, radius, wire, turns };
}

async function inspectMeshes(page, scene) {
  const indices = [...new Set([0, Math.floor(scene.times.length / 4), Math.floor(scene.times.length / 2), scene.times.length - 1])];
  let matrixError = 0, springChecks = 0, wireError = 0;
  for (const index of indices) {
    await page.evaluate(i => window.__domelica.seek(i), index);
    const snapshots = await page.evaluate(ids => ids.map(id => window.__domelica.getObjectTransform(id, true)), scene.objects.map(o => o.id));
    scene.objects.forEach((object, j) => {
      const frame = frameAt(object, index), snapshot = snapshots[j];
      assert.equal(snapshot.type, object.type);
      const expected = [...frame.slice(0, 3), 0, ...frame.slice(3, 6), 0, ...frame.slice(6, 9), 0, ...frame.slice(9, 12), 1];
      snapshot.matrixWorld.forEach((v, k) => { close(v, expected[k]); matrixError = Math.max(matrixError, Math.abs(v - expected[k])); });
      assert.ok(snapshot.geometryPositions.every(Number.isFinite));
      if (object.type === "spring") {
        const result = inspectSpring(object, index, snapshot);
        wireError = Math.max(wireError, result.wireRadiusError); springChecks++;
      }
    });
    const renderedValues = await page.locator(".plot-value > span:first-child").allTextContents();
    scene.series.forEach((series, k) => {
      const native = series.values[index], displayed = Number(renderedValues[k]);
      assert.ok(Math.abs(native - displayed) <= Math.max(0.0051, Math.abs(native) * 0.006), `Displayed signal disagrees with native sample: ${series.name}`);
    });
    const state = await page.evaluate(() => window.__domelica.getState());
    assert.equal(state.index, index); assert.equal(state.time, scene.times[index]);
    assert.equal(Number(await page.locator("#scrub").inputValue()), index);
  }
  return { nativeSamplesChecked: indices, meshTransformsChecked: indices.length * scene.objects.length, matrixError, springChecks, maximumWireRadiusError: wireError };
}

async function noOverflow(page) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, "Horizontal overflow");
  const boxes = await page.locator("#scene,#play,#scrub,#speed").evaluateAll(items => items.map(n => { const r = n.getBoundingClientRect(); return { width: r.width, height: r.height, left: r.left, right: r.right }; }));
  assert.ok(boxes.every(b => b.width > 20 && b.height > 20 && b.left >= 0));
}

async function screenshot(page, name) {
  const dest = path.join(output, name);
  await page.screenshot({ path: dest, fullPage: true }); report.screenshots.push(name);
}

async function main() {
  let browser;
  try {
    const html = fs.readFileSync(input);
    report.artifactSha256 = sha(html);
    const manifest = JSON.parse(fs.readFileSync(path.join(path.dirname(input), "motion-provenance.json")));
    assert.equal(manifest.previewSHA256, report.artifactSha256);
    const expectedPayload = JSON.parse(fs.readFileSync(path.join(path.dirname(input), "motion-scenes.json")));
    const launch = { headless: true, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] };
    if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) launch.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
    browser = await chromium.launch(launch); report.browser = browser.version();
    const context = await browser.newContext({ viewport: { width: 1440, height: 1060 }, reducedMotion: "reduce", offline: true });
    const page = await context.newPage();
    page.on("pageerror", error => report.pageErrors.push(String(error)));
    page.on("request", request => { if (/^https?:/i.test(request.url())) report.unexpectedRequests.push(request.url()); });
    await page.goto(pathToFileURL(input).href);
    await page.waitForFunction(() => window.__domelica?.available === true);
    const payload = await page.evaluate(() => D);
    assert.deepEqual(payload, expectedPayload);
    assert.equal(payload.schema, "domelica.motion-scene.v1");
    assert.deepEqual(payload.scenes.map(s => s.id), ["groove-slide", "two-spring"]);
    assert.equal(payload.metrics.passed, true);
    const info = await page.evaluate(() => window.__domelica.getState().rendererInfo);
    assert.equal(info.isWebGL2, true); assert.equal(info.depthBuffer, true); assert.ok(info.triangles > 0);
    record("Delivered HTML identity, native data, physical acceptance and offline WebGL2", { renderer: info });

    for (const scene of payload.scenes) {
      await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      assert.equal((await page.evaluate(() => window.__domelica.getState())).sceneId, scene.id);
      assert.equal(await page.locator("#title").textContent(), scene.title);
      const checks = await inspectMeshes(page, scene);
      record(`${scene.id}: native geometry, spring cross-sections and one sample clock`, checks);
      await noOverflow(page);
      await page.evaluate(() => window.__domelica.seek(0));
      await screenshot(page, `${scene.id}-desktop.png`);
      await page.locator("#viewxy").click();
      const flat = await page.evaluate(() => window.__domelica.getState());
      close(flat.camera.yaw, 0); close(flat.camera.pitch, 0);
      const block = scene.objects.find(o => o.id === "massBody.frameTranslation.shape");
      assert.ok(block, "Native block graphics must exist");
      const world = point(frameAt(block, 0), [0.5, 0, 0]);
      const projected = await page.evaluate(p => window.__domelica.projectWorld(p), world);
      const box = await page.locator("#scene").boundingBox();
      await page.mouse.click(box.x + projected.x, box.y + projected.y);
      assert.equal((await page.evaluate(() => window.__domelica.getState())).selected, block.id);
      assert.ok((await page.locator("#inspector").textContent()).includes(block.id));
      record(`${scene.id}: XY camera and actual pointer object picking`);
      await page.locator("#view3d").click();
      const canvas = await page.locator("#scene").boundingBox();
      const before = await page.evaluate(() => window.__domelica.getState().camera.yaw);
      await page.mouse.move(canvas.x + canvas.width * .5, canvas.y + canvas.height * .5);
      await page.mouse.down(); await page.mouse.move(canvas.x + canvas.width * .5 + 40, canvas.y + canvas.height * .5 + 20, { steps: 4 }); await page.mouse.up();
      assert.ok(Math.abs((await page.evaluate(() => window.__domelica.getState().camera.yaw)) - before) > .1);
      await page.locator("#view3d").click();
      const start = scene.times.length - 6;
      await page.evaluate(i => window.__domelica.seek(i), start);
      await page.locator("#speed").selectOption("4");
      await page.locator("#play").click();
      await page.waitForFunction(() => !window.__domelica.getState().playing && document.getElementById("play").textContent === "Replay");
      const ended = await page.evaluate(() => window.__domelica.getState());
      assert.equal(ended.index, scene.times.length - 1); assert.equal(ended.time, scene.times.at(-1));
      await page.locator("#speed").selectOption("0.25");
      await page.locator("#play").click();
      await page.waitForFunction(() => window.__domelica.getState().index > 0);
      await page.locator("#play").click();
      const replay = await page.evaluate(() => window.__domelica.getState());
      assert.equal(replay.playing, false); assert.ok(replay.time < 0.5);
      await page.locator("#scrub").evaluate((node, value) => { node.value = String(value); node.dispatchEvent(new Event("input", { bubbles: true })); }, Math.floor(scene.times.length / 2));
      const scrubbed = await page.evaluate(() => window.__domelica.getState());
      assert.equal(scrubbed.index, Math.floor(scene.times.length / 2)); assert.equal(scrubbed.playing, false);
      record(`${scene.id}: orbit, speed, bounded endpoint, replay, pause and scrub`);
    }

    const springScene = payload.scenes.find(s => s.id === "two-spring");
    assert.equal(springScene.objects.filter(o => o.type === "spring").length, 2);
    for (const object of springScene.objects.filter(o => o.type === "spring")) {
      assert.ok(object.spring.length > 1, "Spring length must follow native motion");
      const lengths = object.spring.map(p => p[0]);
      assert.ok(Math.max(...lengths) - Math.min(...lengths) > .19);
      const initial = object.spring[0];
      object.spring.forEach(p => p.slice(1).forEach((v, i) => close(v, initial[i + 1])));
    }
    record("Two physical springs change length while coil and wire radii remain native constants");

    await page.setViewportSize({ width: 390, height: 844 });
    for (const scene of payload.scenes) {
      await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      await page.evaluate(() => window.__domelica.seek(0));
      await noOverflow(page);
      await page.locator("#viewxy").click();
      await screenshot(page, `${scene.id}-mobile.png`);
      await page.locator("#view3d").click();
      const block = scene.objects.find(o => o.id === "massBody.frameTranslation.shape");
      if (!(await page.locator("#objects").evaluate(node => node.open))) await page.locator("#objects summary").click();
      await page.locator(`.object-button[data-id="${block.id}"]`).click();
      assert.equal((await page.evaluate(() => window.__domelica.getState())).selected, block.id);
      record(`${scene.id}: mobile layout, camera controls and component inspection`);
    }

    const noGl = await browser.newContext({ viewport: { width: 800, height: 600 } });
    await noGl.addInitScript(() => { const original = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(type, ...args) { return type === "webgl2" ? null : original.call(this, type, ...args); }; });
    const fallback = await noGl.newPage(); await fallback.goto(pathToFileURL(input).href);
    await fallback.waitForFunction(() => window.__domelica?.available === false);
    assert.ok((await fallback.locator("#error").textContent()).includes("WebGL2"));
    assert.equal(await fallback.locator("#play").isDisabled(), true);
    record("Clear WebGL-unavailable state");
    await noGl.close();
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.unexpectedRequests, []);
    record("No browser errors or network requests");
    report.passed = true;
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
