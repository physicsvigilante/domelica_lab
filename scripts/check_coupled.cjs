#!/usr/bin/env node
"use strict";
// Observe native data and the unchanged browser renderer; never solve motion.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createHash } = require("node:crypto");
const { chromium } = require("playwright");
const input = path.resolve(process.argv[2] || "artifacts/coupled-preview.html");
const output = path.join(path.dirname(input), "coupled-checks");
fs.mkdirSync(output, { recursive: true });
const sha = value => createHash("sha256").update(value).digest("hex");
const report = { passed: false, artifact: path.basename(input), artifactSha256: null,
  browser: null, steps: [], screenshots: [], pageErrors: [], consoleErrors: [], unexpectedRequests: [] };
const record = (name, detail = {}) => { report.steps.push({ name, passed: true, ...detail }); console.log("PASS", name); };
const close = (a, b, tolerance = 1e-10) => assert.ok(Number.isFinite(a) && Math.abs(a - b) <= tolerance, `${a} differs from ${b}`);
const sampleAt = (samples, i) => samples[samples.length === 1 ? 0 : i];
const frameAt = (object, i) => sampleAt(object.frames, i);
const point = (frame, v) => [0, 1, 2].map(k => frame[9 + k] + v[0] * frame[k] + v[1] * frame[k + 3] + v[2] * frame[k + 6]);
const vectorAt = (scene, name, i) => [1, 2, 3].map(k => scene.probes[`${name}[${k}]`][i]);
const minus = (a, b) => a.map((v, k) => v - b[k]);
const maxDistance = positions => Math.max(...positions.map(p => Math.hypot(...minus(p, positions[0]))));
const nearestIndex = (scene, time) => scene.times.reduce((best, value, i) => Math.abs(value - time) < Math.abs(scene.times[best] - time) ? i : best, 0);

function inspectNativeCoupling(scene) {
  const definitions = scene.observations;
  assert.equal(definitions.bodies.length, 2, "This milestone must contain two physical moving bodies");
  const byId = new Map(scene.objects.map(object => [object.id, object]));
  let bodyError = 0, rigidError = 0, endpointError = 0, endpointPairs = 0;
  const positions = new Map();
  for (const body of definitions.bodies) {
    const object = byId.get(body.object);
    assert.ok(object && object.type === "box");
    const centers = scene.times.map((time, i) => {
      const native = vectorAt(scene, body.position, i);
      const rendered = point(frameAt(object, i), [.5, 0, 0]);
      native.forEach((v, k) => { close(rendered[k], v); bodyError = Math.max(bodyError, Math.abs(rendered[k] - v)); });
      return native;
    });
    assert.ok(maxDistance(centers) > body.minimumTravel, `${body.role} must actually move`);
    positions.set(body.role, centers);
  }
  const block = positions.get("block"), wedge = positions.get("wedge");
  assert.ok(block && wedge);
  const relative = block.map((p, i) => minus(p, wedge[i]));
  assert.ok(maxDistance(relative) > .4, "Block and wedge cannot be a single translated visual group");
  for (const id of definitions.rigidGroup) {
    const object = byId.get(id), initial = frameAt(object, 0);
    scene.times.forEach((time, i) => {
      const frame = frameAt(object, i), shift = minus(wedge[i], wedge[0]);
      frame.slice(0, 9).forEach((v, k) => close(v, initial[k]));
      for (let k = 0; k < 3; k++) {
        const error = Math.abs(frame[9 + k] - initial[9 + k] - shift[k]);
        assert.ok(error < 1e-10); rigidError = Math.max(rigidError, error);
      }
    });
  }
  for (const id of definitions.fixedObjects) {
    const object = byId.get(id), initial = frameAt(object, 0);
    scene.times.forEach((time, i) => frameAt(object, i).forEach((v, k) => close(v, initial[k])));
  }
  assert.equal(scene.objects.filter(o => o.type === "spring").length, definitions.springs.length);
  for (const spring of definitions.springs) {
    const object = byId.get(spring.object), lengths = [];
    const firstSpec = sampleAt(object.spring, 0);
    scene.times.forEach((time, i) => {
      const frame = frameAt(object, i), spec = sampleAt(object.spring, i);
      const a = vectorAt(scene, spring.frameA, i), b = vectorAt(scene, spring.frameB, i);
      const graphicsA = point(frame, [0, 0, 0]), graphicsB = point(frame, [spec[0], 0, 0]);
      for (let k = 0; k < 3; k++) {
        close(graphicsA[k], a[k]); close(graphicsB[k], b[k]);
        endpointError = Math.max(endpointError, Math.abs(graphicsA[k] - a[k]), Math.abs(graphicsB[k] - b[k]));
      }
      spec.slice(1).forEach((v, k) => close(v, firstSpec[k + 1]));
      close(spec[0], Math.hypot(...minus(a, b)));
      lengths.push(spec[0]); endpointPairs++;
    });
    assert.ok(Math.max(...lengths) - Math.min(...lengths) > spring.minimumLengthChange);
    const anchorTravel = scene.times.map((t, i) => vectorAt(scene, spring.frameA, i));
    assert.ok(maxDistance(anchorTravel) > .2, "The spring anchor must move with the wedge, not remain on the ground");
  }
  return { nativeSamples: scene.times.length, bodyPositionsChecked: scene.times.length * definitions.bodies.length,
    bodyCenterError_m: bodyError, rigidSupportError_m: rigidError,
    springEndpointPairsChecked: endpointPairs, springEndpointError_m: endpointError };
}

function inspectSpring(object, sample, snapshot) {
  const spec = sampleAt(object.spring, sample), [length, radius, wire, turns] = spec;
  assert.deepEqual(snapshot.spring.nativeSpring, spec);
  const { segments, radial, centers } = snapshot.spring;
  assert.equal(centers.length, 3 * (segments + 1));
  const positions = snapshot.geometryPositions;
  let radiusError = 0;
  for (let i = 0; i <= segments; i++) {
    const u = i / segments, phase = 2 * Math.PI * turns * u;
    const expected = [length * u, radius * Math.sin(phase), radius * Math.cos(phase)];
    centers.slice(3 * i, 3 * i + 3).forEach((v, k) => close(v, expected[k]));
    for (let j = 0; j <= radial; j++) {
      const offset = ((radial + 1) * i + j) * 3;
      const delta = positions.slice(offset, offset + 3).map((v, k) => v - expected[k]);
      radiusError = Math.max(radiusError, Math.abs(Math.hypot(...delta) - wire));
      close(Math.hypot(...delta), wire, 3e-7);
    }
  }
  return radiusError;
}

async function inspectMeshes(page, scene) {
  const indices = [...new Set([0, nearestIndex(scene, scene.observations.screenshotTime), Math.floor(scene.times.length / 2), scene.times.length - 1])];
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
      if (object.type === "spring") { wireError = Math.max(wireError, inspectSpring(object, index, snapshot)); springChecks++; }
    });
    const renderedValues = await page.locator(".plot-value > span:first-child").allTextContents();
    scene.series.forEach((series, k) => {
      const native = series.values[index], displayed = Number(renderedValues[k]);
      assert.ok(Math.abs(native - displayed) <= Math.max(.0051, Math.abs(native) * .006), `Displayed signal differs from native sample: ${series.name}`);
    });
    const state = await page.evaluate(() => window.__domelica.getState());
    assert.equal(state.index, index); assert.equal(state.time, scene.times[index]);
    assert.equal(Number(await page.locator("#scrub").inputValue()), index);
  }
  return { nativeSamplesChecked: indices, meshTransformsChecked: indices.length * scene.objects.length,
    matrixError, springCrossSectionsChecked: springChecks, maximumWireRadiusError_m: wireError };
}

async function checkFraming(page, scene) {
  const checks = await page.evaluate(s => {
    let count = 0, minimumMargin = Infinity;
    const viewport = window.__domelica.getRenderDiagnostics().viewport;
    for (const object of s.objects) {
      for (let i = 0; i < s.times.length; i++) {
        const f = object.frames[object.frames.length === 1 ? 0 : i];
        let axes = [[0, 1], [-.5, .5], [-.5, .5]];
        if (object.type === "spring") {
          const p = object.spring[object.spring.length === 1 ? 0 : i];
          axes = [[-p[2], p[0] + p[2]], [-p[1] - p[2], p[1] + p[2]], [-p[1] - p[2], p[1] + p[2]]];
        }
        for (const x of axes[0]) for (const y of axes[1]) for (const z of axes[2]) {
          const world = [0, 1, 2].map(k => f[9 + k] + x * f[k] + y * f[3 + k] + z * f[6 + k]);
          const p = window.__domelica.projectWorld(world);
          if (![p.x, p.y, p.z].every(Number.isFinite) || Math.abs(p.z) > 1) throw new Error("Native geometry outside camera depth range");
          minimumMargin = Math.min(minimumMargin, p.x, p.y, viewport.width - p.x, viewport.height - p.y);
          count++;
        }
      }
    }
    return { cornersChecked: count, minimumMargin_px: minimumMargin };
  }, scene);
  assert.ok(checks.minimumMargin_px >= 2, `Native geometry clipped: ${checks.minimumMargin_px} px`);
  return checks;
}

async function noOverflow(page) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, "Horizontal overflow");
  const boxes = await page.locator("#scene,#play,#scrub,#speed").evaluateAll(items => items.map(n => {
    const r = n.getBoundingClientRect(); return { width: r.width, height: r.height, left: r.left, right: r.right };
  }));
  assert.ok(boxes.every(b => b.width > 20 && b.height > 20 && b.left >= 0));
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(output, name), fullPage: true }); report.screenshots.push(name);
}

async function main() {
  let browser;
  try {
    report.artifactSha256 = sha(fs.readFileSync(input));
    const manifest = JSON.parse(fs.readFileSync(path.join(path.dirname(input), "coupled-provenance.json")));
    assert.equal(manifest.previewSHA256, report.artifactSha256);
    const expectedPayload = JSON.parse(fs.readFileSync(path.join(path.dirname(input), "coupled-scenes.json")));
    const launch = { headless: true, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] };
    if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) launch.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
    browser = await chromium.launch(launch); report.browser = browser.version();
    const context = await browser.newContext({ viewport: { width: 1440, height: 1060 }, reducedMotion: "reduce", offline: true });
    const page = await context.newPage();
    page.on("pageerror", error => report.pageErrors.push(String(error)));
    page.on("console", message => { if (message.type() === "error") report.consoleErrors.push(message.text()); });
    page.on("request", request => { if (/^https?:/i.test(request.url())) report.unexpectedRequests.push(request.url()); });
    await page.goto(pathToFileURL(input).href);
    await page.waitForFunction(() => window.__domelica?.available === true);
    const payload = await page.evaluate(() => D);
    assert.deepEqual(payload, expectedPayload);
    assert.equal(payload.schema, "domelica.motion-scene.v1");
    assert.deepEqual(payload.scenes.map(s => s.id), ["moving-wedge", "spring-wedge"]);
    assert.equal(payload.metrics.passed, true);
    const info = await page.evaluate(() => window.__domelica.getState().rendererInfo);
    assert.equal(info.isWebGL2, true); assert.equal(info.depthBuffer, true); assert.ok(info.triangles > 0);
    assert.equal((await page.evaluate(() => window.__domelica.getState())).playing, false);
    record("Delivered HTML identity, native data, physical acceptance and paused offline WebGL2", { renderer: info });

    for (const scene of payload.scenes) {
      record(`${scene.id}: two physical bodies, rigid support and native spring endpoints over the whole run`, inspectNativeCoupling(scene));
      await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      assert.equal((await page.evaluate(() => window.__domelica.getState())).sceneId, scene.id);
      assert.equal(await page.locator("#title").textContent(), scene.title);
      record(`${scene.id}: rendered native mesh transforms, spring cross-sections and synchronized signals`, await inspectMeshes(page, scene));
      await noOverflow(page);
      const framing = await checkFraming(page, scene);
      await page.evaluate(() => window.__domelica.seek(0));
      const initialPixels = sha(await page.locator("#scene").screenshot());
      const capture = nearestIndex(scene, scene.observations.screenshotTime);
      await page.evaluate(i => window.__domelica.seek(i), capture);
      assert.notEqual(sha(await page.locator("#scene").screenshot()), initialPixels, "Recorded native motion must change rendered pixels");
      await screenshot(page, `${scene.id}-desktop.png`);
      record(`${scene.id}: complete trajectory framing and visible movement`, { ...framing, screenshotTime: scene.times[capture] });
      await page.locator("#viewxy").click();
      const flat = await page.evaluate(() => window.__domelica.getState()); close(flat.camera.yaw, 0); close(flat.camera.pitch, 0);
      const blockId = scene.observations.bodies.find(b => b.role === "block").object;
      const block = scene.objects.find(o => o.id === blockId);
      const projected = await page.evaluate(p => window.__domelica.projectWorld(p), point(frameAt(block, capture), [.5, 0, 0]));
      const box = await page.locator("#scene").boundingBox();
      await page.mouse.click(box.x + projected.x, box.y + projected.y);
      assert.equal((await page.evaluate(() => window.__domelica.getState())).selected, blockId);
      assert.ok((await page.locator("#inspector").textContent()).includes(blockId));
      record(`${scene.id}: XY camera and actual pointer selection of the moving block`);
      await page.locator("#view3d").click();
      const canvas = await page.locator("#scene").boundingBox();
      const before = await page.evaluate(() => window.__domelica.getState().camera.yaw);
      await page.mouse.move(canvas.x + canvas.width * .5, canvas.y + canvas.height * .5);
      await page.mouse.down(); await page.mouse.move(canvas.x + canvas.width * .5 + 40, canvas.y + canvas.height * .5 + 20, { steps: 4 }); await page.mouse.up();
      assert.ok(Math.abs((await page.evaluate(() => window.__domelica.getState().camera.yaw)) - before) > .1);
      await page.locator("#view3d").click();
      await page.evaluate(i => window.__domelica.seek(i), scene.times.length - 6);
      await page.locator("#speed").selectOption("4"); await page.locator("#play").click();
      await page.waitForFunction(() => !window.__domelica.getState().playing && document.getElementById("play").textContent === "Replay");
      const ended = await page.evaluate(() => window.__domelica.getState());
      assert.equal(ended.index, scene.times.length - 1); assert.equal(ended.time, scene.times.at(-1));
      await page.locator("#speed").selectOption("0.25"); await page.locator("#play").click();
      await page.waitForFunction(() => window.__domelica.getState().index > 0); await page.locator("#play").click();
      const replay = await page.evaluate(() => window.__domelica.getState());
      assert.equal(replay.playing, false); assert.ok(replay.time < .5);
      await page.locator("#scrub").evaluate((node, value) => { node.value = String(value); node.dispatchEvent(new Event("input", { bubbles: true })); }, capture);
      const scrubbed = await page.evaluate(() => window.__domelica.getState());
      assert.equal(scrubbed.index, capture); assert.equal(scrubbed.playing, false);
      record(`${scene.id}: orbit, bounded playback, replay, speed, pause and scrub`);
    }

    await page.setViewportSize({ width: 390, height: 844 });
    for (const scene of payload.scenes) {
      await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      await page.evaluate(i => window.__domelica.seek(i), nearestIndex(scene, scene.observations.screenshotTime));
      await noOverflow(page);
      const framing = await checkFraming(page, scene);
      await screenshot(page, `${scene.id}-mobile.png`);
      const wedgeId = scene.observations.bodies.find(b => b.role === "wedge").object;
      if (!(await page.locator("#objects").evaluate(node => node.open))) await page.locator("#objects summary").click();
      await page.locator(`.object-button[data-id="${wedgeId}"]`).click();
      assert.equal((await page.evaluate(() => window.__domelica.getState())).selected, wedgeId);
      record(`${scene.id}: mobile controls, support inspection and whole-trajectory framing`, framing);
    }

    const noGl = await browser.newContext({ viewport: { width: 800, height: 600 }, offline: true });
    await noGl.addInitScript(() => { const original = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(type, ...args) { return type === "webgl2" ? null : original.call(this, type, ...args); }; });
    const fallback = await noGl.newPage(); await fallback.goto(pathToFileURL(input).href);
    await fallback.waitForFunction(() => window.__domelica?.available === false);
    assert.ok((await fallback.locator("#error").textContent()).includes("WebGL2"));
    assert.equal(await fallback.locator("#play").isDisabled(), true);
    record("Explicit WebGL-unavailable state"); await noGl.close();
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.unexpectedRequests, []);
    record("No browser errors or network requests"); report.passed = true;
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
