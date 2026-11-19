#!/usr/bin/env node
"use strict";
// Browser acceptance of sampled native geometry and observations, not a physics solver.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createHash } = require("node:crypto");
const { chromium } = require("playwright");

const input = path.resolve(process.argv[2] || "artifacts/domelica_observation_lab.html");
const output = path.resolve(process.argv[3] || path.join(path.dirname(input), "observation-checks"));
fs.mkdirSync(output, { recursive: true });
const inputURL = pathToFileURL(input).href;
const report = { passed: false, artifact: path.basename(input), artifactSHA256: null,
  browser: null, renderer: null, fallbackRenderer: null, steps: [], screenshots: [],
  pageErrors: [], consoleErrors: [], unexpectedRequests: [] };
const record = (name, detail = {}) => { report.steps.push({ name, passed: true, ...detail }); console.log("PASS", name); };
const close = (a, b, tolerance = 1e-9) => assert.ok(Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= tolerance, `${a} differs from ${b}`);
const row = (rows, i) => rows[rows.length === 1 ? 0 : i];
const indices = scene => [...new Set([0, Math.floor((scene.times.length - 1) * .37), scene.times.length - 1])];
const sourceLabels = { native: "Native result", "native-transform": "Native · world-resolved", derived: "Derived from native data" };
const scaleUnits = { force: "m/N", velocity: "s", acceleration: "s²", torque: "m/(N·m)" };
const sha = value => createHash("sha256").update(value).digest("hex");

function readPayload(html) {
  const marker = "\nconst D = ", start = html.lastIndexOf(marker);
  const end = html.indexOf(";\n(() => {", start);
  assert.ok(start >= 0 && end > start, "Delivered HTML must contain its own native payload");
  const payload = JSON.parse(html.slice(start + marker.length, end));
  assert.equal(payload.schema, "domelica.observation-lab/v1");
  assert.ok(payload.scenes.length >= 2, "The shared viewer must exercise multiple recordings");
  return payload;
}

function observe(page, label) {
  page.on("pageerror", error => report.pageErrors.push({ page: label, message: String(error) }));
  page.on("console", message => { if (message.type() === "error") report.consoleErrors.push({ page: label, message: message.text() }); });
  page.on("request", request => {
    const url = request.url();
    if (url !== inputURL && !/^(data|blob):/i.test(url)) report.unexpectedRequests.push({ page: label, url });
  });
}

async function ready(page) {
  await page.goto(inputURL, { waitUntil: "load" });
  await page.waitForFunction(() => window.__domelica !== undefined, null, { timeout: 20000 });
  const state = await page.evaluate(() => ({ available: window.__domelica.available, state: window.__domelica.getState() }));
  assert.equal(state.available, true, JSON.stringify(state));
  return state.state;
}

async function captureRenderedScene(page) {
  // Observe the actual scene submitted to the renderer without changing the file.
  // Restore the method immediately; the retained reference is read only below.
  await page.evaluate(() => {
    const owned = Object.prototype.hasOwnProperty.call(THREE.Scene.prototype, "updateMatrixWorld");
    const original = THREE.Scene.prototype.updateMatrixWorld;
    THREE.Scene.prototype.updateMatrixWorld = function(...args) {
      if (this.getObjectByName("Native observations")) window.__observationAcceptanceScene = this;
      return original.apply(this, args);
    };
    try { window.__domelica.draw(); }
    finally {
      if (owned) THREE.Scene.prototype.updateMatrixWorld = original;
      else delete THREE.Scene.prototype.updateMatrixWorld;
    }
    if (!window.__observationAcceptanceScene) throw new Error("Actual rendered observation scene was not observed");
  });
}

async function actualGlyphs(page, ids) {
  return page.evaluate(names => names.map(id => {
    const group = window.__observationAcceptanceScene.getObjectByName("Observation: " + id);
    if (!group) throw new Error("Missing actual arrow group: " + id);
    group.updateWorldMatrix(true, true);
    return { id, visible: group.visible, arrows: group.children.map(arrow => ({
      origin: arrow.getWorldPosition(new THREE.Vector3()).toArray(),
      tip: arrow.cone.getWorldPosition(new THREE.Vector3()).toArray(),
      lineScale: arrow.line.scale.toArray(), coneScale: arrow.cone.scale.toArray()
    })) };
  }), ids);
}

async function checkSample(page, scene, sample, kind, three) {
  await page.evaluate(i => window.__domelica.seek(i), sample);
  const expected = scene.overlays.filter(o => o.kind === kind && o.defaultVisible !== false);
  const snapshot = await page.evaluate(() => ({ state: window.__domelica.getState(),
    vectors: window.__domelicaObservations.getActiveSamples(), settings: window.__domelicaObservations.getState() }));
  assert.equal(snapshot.state.index, sample); assert.equal(snapshot.state.time, scene.times[sample]);
  assert.equal(snapshot.settings.kind, kind); assert.equal(snapshot.settings.scaleUnit, scaleUnits[kind]);
  assert.deepEqual(snapshot.vectors.map(v => v.id), expected.map(o => o.id));
  let zeros = 0, nativePoints = 0;
  const actual = three ? await actualGlyphs(page, scene.overlays.map(o => o.id)) : [];
  const actualById = new Map(actual.map(v => [v.id, v]));
  for (const [i, definition] of expected.entries()) {
    const value = snapshot.vectors[i], point = row(definition.positions, sample), vector = row(definition.vectors, sample);
    assert.deepEqual(value.point, point); assert.deepEqual(value.vector, vector);
    assert.equal(value.body, definition.body); assert.equal(value.unit, definition.unit);
    assert.equal(value.source.mode, definition.source.mode); assert.equal(value.scale, snapshot.settings.scale);
    const magnitude = Math.hypot(...vector); close(value.magnitude, magnitude);
    for (let k = 0; k < 3; k++) close(value.end[k], point[k] + vector[k] * value.scale);
    if (three) {
      const glyph = actualById.get(definition.id);
      assert.equal(glyph.visible, magnitude !== 0, "Only exact zero may hide an enabled glyph");
      assert.equal(glyph.arrows.length, kind === "torque" ? 2 : 1);
      if (magnitude !== 0) {
        glyph.arrows[0].origin.forEach((v, k) => close(v, point[k]));
        glyph.arrows[0].tip.forEach((v, k) => close(v, value.end[k]));
        if (kind === "torque") {
          glyph.arrows[1].tip.forEach((v, k) => close(v, point[k] + .78 * vector[k] * value.scale));
        }
      }
    }
    if (magnitude === 0) zeros++;
    nativePoints++;
  }
  if (three) for (const glyph of actual) if (!expected.some(o => o.id === glyph.id)) assert.equal(glyph.visible, false, "Filtered glyph still visible");
  return { nativePoints, zeroVectors: zeros, actualGlyphs: three ? expected.length : 0 };
}

async function checkNativeMatrices(page, scene, sample) {
  await page.evaluate(i => window.__domelica.seek(i), sample);
  const snapshots = await page.evaluate(ids => ids.map(id => window.__domelica.getObjectTransform(id)), scene.objects.map(o => o.id));
  scene.objects.forEach((object, i) => {
    const frame = row(object.frames, sample), expected = [...frame.slice(0, 3), 0, ...frame.slice(3, 6), 0, ...frame.slice(6, 9), 0, ...frame.slice(9, 12), 1];
    assert.equal(snapshots[i].type, object.type);
    snapshots[i].matrixWorld.forEach((v, k) => close(v, expected[k]));
  });
  return snapshots.length;
}

async function framing(page, scene, three = true) {
  const result = await page.evaluate(samples => {
    let count = 0, minimumMargin = Infinity;
    const viewport = window.__domelica.getRenderDiagnostics().viewport;
    for (const index of samples) {
      window.__domelica.seek(index);
      for (const value of window.__domelicaObservations.getActiveSamples()) for (const point of [value.point, value.end]) {
        const p = window.__domelica.projectWorld(point);
        if (![p.x, p.y, p.z].every(Number.isFinite)) throw new Error("Nonfinite arrow projection");
        minimumMargin = Math.min(minimumMargin, p.x, p.y, viewport.width - p.x, viewport.height - p.y);
        count++;
      }
    }
    return { endpoints: count, minimumMargin_px: minimumMargin, viewport };
  }, indices(scene));
  assert.ok(result.endpoints > 0 && result.minimumMargin_px >= 8, "Observation clipped: " + JSON.stringify(result));
  return { ...result, renderer: three ? "WebGL2" : "Canvas2D" };
}

async function noOverflow(page) {
  const result = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    controls: [...document.querySelectorAll('#scene,#play,#scrub,#speed,#observationControls select,#observationControls input[type="range"]')].map(node => {
      const r = node.getBoundingClientRect(); return { left: r.left, right: r.right, width: r.width, height: r.height };
    }) }));
  assert.ok(result.scrollWidth <= result.width + 1, JSON.stringify(result));
  assert.ok(result.controls.every(r => r.width >= 20 && r.height >= 20 && r.left >= 0 && r.right <= result.width + 1), JSON.stringify(result));
  return { viewportWidth: result.width, scrollWidth: result.scrollWidth };
}

async function screenshot(page, name) {
  assert.ok(report.screenshots.length < 4, "At most four focused screenshots");
  await page.screenshot({ path: path.join(output, name), fullPage: true });
  report.screenshots.push(name);
}

async function main() {
  let browser;
  try {
    const bytes = fs.readFileSync(input), html = bytes.toString("utf8"), payload = readPayload(html);
    report.artifactSHA256 = sha(bytes);
    report.recording = payload.provenance.recording;
    const buildPath = input.replace(/\.html$/i, "_build.json");
    const build = JSON.parse(fs.readFileSync(buildPath, "utf8"));
    assert.equal(build.htmlSHA256, report.artifactSHA256, "Browser must load the exact HTML recorded by the builder");
    const payloadPath = path.join(path.dirname(input), build.payload);
    const payloadBytes = fs.readFileSync(payloadPath);
    assert.equal(sha(payloadBytes), build.payloadSHA256); assert.deepEqual(JSON.parse(payloadBytes), payload);
    let sourceFiles = 0;
    if (process.env.GITHUB_SHA) {
      assert.equal(payload.provenance.revision, process.env.GITHUB_SHA, "Native source commit must match this CI checkout");
      assert.equal(report.recording.kind, "fresh-native-run", "CI acceptance requires this run's fresh native recording");
      const repo = path.resolve(__dirname, ".."), packageRoot = path.join(repo, "DomelicaLab");
      const frozenRoot = path.join(repo, "observation-run", "source", "DomelicaLab");
      assert.ok(Object.keys(report.recording.modelSourceSHA256 || {}).length > 0, "Native source hashes must be present");
      for (const [relative, expected] of Object.entries(report.recording.modelSourceSHA256)) {
        const current = path.resolve(packageRoot, relative), frozen = path.resolve(frozenRoot, relative);
        assert.ok(current.startsWith(packageRoot + path.sep) && frozen.startsWith(frozenRoot + path.sep), "Source binding escapes the package");
        assert.equal(sha(fs.readFileSync(current)), expected, "Checkout source hash mismatch: " + relative);
        assert.equal(sha(fs.readFileSync(frozen)), expected, "Frozen native source hash mismatch: " + relative);
        sourceFiles++;
      }
    }
    record("Build report, payload and native source identity bind the browser artifact", { sourceFiles, recordingKind: report.recording.kind, revision: payload.provenance.revision });
    browser = await chromium.launch({ headless: true, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
    report.browser = browser.version();
    const context = await browser.newContext({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 1, reducedMotion: "reduce", offline: true });
    const page = await context.newPage(); observe(page, "WebGL2");
    const initial = await ready(page);
    assert.equal(initial.playing, false); assert.equal(initial.rendererInfo.isWebGL2, true, "Default acceptance must exercise actual WebGL2, not the fallback");
    assert.equal(initial.rendererInfo.depthBuffer, true); assert.ok(initial.rendererInfo.triangles > 0);
    assert.deepEqual(await page.evaluate(() => D), payload);
    report.renderer = initial.rendererInfo;
    await captureRenderedScene(page);
    record("Exact delivered file and native payload render paused in WebGL2", { renderer: report.renderer });

    let totalZeros = 0;
    for (const scene of payload.scenes) {
      await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      assert.equal((await page.evaluate(() => window.__domelica.getState())).sceneId, scene.id);
      assert.equal(await page.locator("#title").textContent(), scene.title);
      const kinds = [...new Set(scene.overlays.map(o => o.kind))];
      let points = 0, glyphs = 0, matrices = 0;
      for (const kind of kinds) {
        await page.getByLabel("Observation quantity", { exact: true }).selectOption(kind);
        assert.deepEqual(await page.locator(".observation-select small").allTextContents(), scene.overlays.filter(o => o.kind === kind).map(o => sourceLabels[o.source.mode]));
        for (const sample of indices(scene)) {
          const checked = await checkSample(page, scene, sample, kind, true);
          points += checked.nativePoints; glyphs += checked.actualGlyphs; totalZeros += checked.zeroVectors;
        }
      }
      for (const sample of indices(scene)) matrices += await checkNativeMatrices(page, scene, sample);
      record(scene.id + ": native points, actual glyphs and geometry share sample indices", { indices: indices(scene), nativePoints: points, actualGlyphs: glyphs, nativeMatrices: matrices, quantities: kinds });

      await page.getByLabel("Observation quantity", { exact: true }).selectOption("force");
      const body = scene.bodies.find(b => scene.overlays.filter(o => o.kind === "force" && o.body === b.id).length > 1);
      assert.ok(body, "Need a body with multiple forces for filtering acceptance");
      await page.getByLabel("Receiving or observed body", { exact: true }).selectOption(body.id);
      const forces = scene.overlays.filter(o => o.kind === "force" && o.body === body.id && o.defaultVisible !== false);
      assert.deepEqual((await page.evaluate(() => window.__domelicaObservations.getActiveSamples())).map(o => o.id), forces.map(o => o.id));
      const checkbox = page.getByLabel("Show " + forces[0].label, { exact: true });
      await checkbox.uncheck();
      assert.equal((await actualGlyphs(page, [forces[0].id]))[0].visible, false);
      await page.getByLabel("Show " + forces[0].label, { exact: true }).check();
      await page.locator(".observation-select").first().click();
      assert.equal(await page.locator(".observation-source code").textContent(), forces[0].source.expression);
      await page.getByLabel("Receiving or observed body", { exact: true }).selectOption("all");
      const before = await page.evaluate(() => window.__domelicaObservations.getState().scale);
      await page.getByLabel("Common arrow scale for selected quantity", { exact: true }).evaluate(node => { node.value = "70"; node.dispatchEvent(new Event("input", { bubbles: true })); });
      close((await page.evaluate(() => window.__domelicaObservations.getState().scale)), before * 2);
      await checkSample(page, scene, indices(scene)[1], "force", true);
      record(scene.id + ": body, checkbox, source inspection and common linear scale controls work", { frame: await framing(page, scene) });
      await page.locator("#viewxy").click(); record(scene.id + ": force endpoints fit the XY camera", await framing(page, scene));
      await page.locator("#view3d").click();

      if (scene === payload.scenes[0]) {
        await page.evaluate(i => window.__domelica.seek(i), indices(scene)[1]);
        await screenshot(page, scene.id + "-forces-desktop.png");
        if (kinds.includes("torque")) {
          await page.getByLabel("Observation quantity", { exact: true }).selectOption("torque");
          await checkSample(page, scene, indices(scene)[1], "torque", true);
          await screenshot(page, scene.id + "-torque-desktop.png");
        }
      }
    }
    assert.ok(totalZeros > 0, "An initial zero-vector case must be exercised");
    record("Exact zero vectors hide their real glyph without discarding recorded values", { zeroSamples: totalZeros });

    const first = payload.scenes[0];
    await page.locator(`.scene-tab[data-id="${first.id}"]`).click();
    await page.locator("#speed").selectOption("0.25");
    await page.locator("#play").click();
    await page.waitForFunction(() => window.__domelica.getState().index > 0, null, { timeout: 10000 });
    await page.locator("#play").click();
    assert.equal((await page.evaluate(() => window.__domelica.getState())).playing, false);
    const scrubIndex = indices(first)[1];
    await page.locator("#scrub").evaluate((node, value) => { node.value = String(value); node.dispatchEvent(new Event("input", { bubbles: true })); }, scrubIndex);
    assert.equal((await page.evaluate(() => window.__domelica.getState())).index, scrubIndex);
    await page.evaluate(last => window.__domelica.seek(last - 2), first.times.length - 1);
    await page.locator("#speed").selectOption("4"); await page.locator("#play").click();
    await page.waitForFunction(() => document.getElementById("play").textContent === "Replay", null, { timeout: 10000 });
    assert.equal((await page.evaluate(() => window.__domelica.getState())).index, first.times.length - 1);
    record("Playback, pause, scrub and duplicate final timestamps retain the native clock");

    await page.setViewportSize({ width: 360, height: 900 });
    const last = payload.scenes.at(-1);
    for (const scene of payload.scenes) {
      await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      await page.locator("#viewxy").click();
      const fit = await framing(page, scene); const layout = await noOverflow(page);
      record(scene.id + ": 360 px controls and force framing", { ...layout, frame: fit });
    }
    await page.evaluate(i => window.__domelica.seek(i), indices(last)[1]);
    await screenshot(page, last.id + "-forces-mobile.png");

    const fallbackContext = await browser.newContext({ viewport: { width: 1000, height: 900 }, deviceScaleFactor: 1, reducedMotion: "reduce", offline: true });
    // Explicit feature fixture: exercise the shipped Canvas fallback independently.
    await fallbackContext.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type, ...args) { return type === "webgl2" ? null : original.call(this, type, ...args); };
    });
    const fallback = await fallbackContext.newPage(); observe(fallback, "Canvas fallback");
    const fallbackInitial = await ready(fallback); report.fallbackRenderer = fallbackInitial.rendererInfo;
    assert.equal(fallbackInitial.rendererInfo.isWebGL2, false); assert.equal(fallbackInitial.rendererInfo.projection, "XY");
    assert.equal(await fallback.locator("#view3d").isDisabled(), true); assert.equal(await fallback.locator("#graphicsNote").isVisible(), true);
    for (const scene of payload.scenes) {
      await fallback.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      const kind = scene.overlays.some(o => o.kind === "acceleration") ? "acceleration" : "force";
      await fallback.getByLabel("Observation quantity", { exact: true }).selectOption(kind);
      await checkSample(fallback, scene, indices(scene)[1], kind, false);
      await framing(fallback, scene, false); await noOverflow(fallback);
    }
    await fallback.evaluate(i => window.__domelica.seek(i), indices(last)[1]);
    await screenshot(fallback, last.id + "-acceleration-canvas.png");
    record("Explicit Canvas XY fallback preserves native vectors, controls and framing", { renderer: report.fallbackRenderer });
    await fallbackContext.close();
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.unexpectedRequests, []);
    record("No browser exceptions, console errors or external requests");
    report.passed = true;
  } catch (error) {
    report.failure = error.stack || String(error); process.exitCode = 1; console.error(error);
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
  }
}
main();
