#!/usr/bin/env node
"use strict";
// Exercise the delivered comparison and its two unchanged native renderers.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createHash } = require("node:crypto");
const { chromium } = require("playwright");

const input = path.resolve(process.argv[2] || "artifacts/comparison.html");
const directory = path.dirname(input), output = path.join(directory, "comparison-checks");
fs.mkdirSync(output, { recursive: true });
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const report = { passed: false, artifact: path.basename(input), artifactSha256: null,
  browser: null, steps: [], screenshots: [], pageErrors: [], consoleErrors: [], unexpectedRequests: [] };
const record = (name, detail = {}) => { report.steps.push({ name, passed: true, ...detail }); console.log("PASS", name); };
// Deliberately use a linear scan, independent of the viewer's binary search.
function expectedIndex(times, target) {
  let answer = 0;
  for (let index = 0; index < times.length; index++) if (times[index] <= target) answer = index;
  return answer;
}
function transform(matrix, point) {
  const v = [...point, 1];
  const out = [0, 1, 2, 3].map(row => v.reduce((sum, value, column) => sum + matrix[4 * column + row] * value, 0));
  assert.ok(out.every(Number.isFinite) && Math.abs(out[3]) > 1e-12);
  return out.slice(0, 3).map(value => value / out[3]);
}
function framing(scene, diagnostics, viewport) {
  let minimumMargin = Infinity, count = 0;
  for (const object of scene.objects) for (const frame of object.frames) {
    for (const x of [0, 1]) for (const y of [-0.5, 0.5]) for (const z of [-0.5, 0.5]) {
      const world = [0, 1, 2].map(k => frame[9 + k] + x * frame[k] + y * frame[3 + k] + z * frame[6 + k]);
      const ndc = transform(diagnostics.projectionMatrix, transform(diagnostics.matrixWorldInverse, world));
      const px = (ndc[0] + 1) * viewport.width / 2, py = (1 - ndc[1]) * viewport.height / 2;
      const margin = Math.min(px, py, viewport.width - px, viewport.height - py);
      assert.ok(margin >= -0.01 && Math.abs(ndc[2]) <= 1.000001, `Clipped comparison geometry: ${scene.id}/${object.id}`);
      minimumMargin = Math.min(minimumMargin, margin); count++;
    }
  }
  return { nativeEnvelopeCorners: count, minimumMarginPx: minimumMargin };
}

async function main() {
  let browser, page;
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(directory, "comparison-provenance.json"), "utf8"));
    const nativeBytes = fs.readFileSync(path.join(directory, "native-scenes.json"));
    const metricsBytes = fs.readFileSync(path.join(directory, "m2-metrics.json"));
    const native = JSON.parse(nativeBytes), metrics = JSON.parse(metricsBytes);
    const scenes = new Map(native.scenes.map(scene => [scene.id, scene]));
    const cases = new Map(metrics.cases.map(item => [item.id, item]));
    report.artifactSha256 = sha(fs.readFileSync(input));
    assert.equal(report.artifactSha256, manifest.previewSHA256);
    assert.equal(sha(nativeBytes), manifest.nativeSceneSHA256);
    assert.equal(sha(metricsBytes), manifest.metricsSHA256);
    assert.equal(manifest.metricsSHA256, native.provenance.inputsSHA256["artifacts/m2-metrics.json"]);
    assert.equal(manifest.rendererTemplateSHA256, native.provenance.sourceSHA256["viewer/preview.template.html"]);
    assert.equal(manifest.nativeExporterSHA256, native.provenance.sourceSHA256["scripts/native_scene.py"]);
    assert.equal(manifest.rendererRuntimeSHA256, native.provenance.renderer.runtimeSHA256);
    assert.equal(manifest.revision, native.provenance.revision);
    report.provenance = manifest;
    record("comparison artifact, native results, metrics and unchanged renderer identities");

    browser = await chromium.launch({ headless: true,
      args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
    report.browser = browser.version();
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 },
      deviceScaleFactor: 1, reducedMotion: "reduce" });
    await context.route(/^https?:\/\//, route => route.abort());
    page = await context.newPage(); page.setDefaultTimeout(15000);
    page.on("pageerror", error => report.pageErrors.push(error.message));
    page.on("console", message => { if (message.type() === "error") report.consoleErrors.push(message.text()); });
    const fileURL = pathToFileURL(input).href;
    page.on("request", request => {
      const url = request.url();
      if (url !== fileURL && !/^(data:|about:)/.test(url)) report.unexpectedRequests.push(url);
    });
    page.on("websocket", socket => report.unexpectedRequests.push(socket.url()));
    await page.goto(fileURL, { waitUntil: "load" });
    await page.waitForFunction(() => window.__domelicaComparison?.getState().available === true);
    const state = () => page.evaluate(() => window.__domelicaComparison.getState());
    const childFrame = async slot => (await page.locator(slot === 0 ? "#frameA" : "#frameB").elementHandle()).contentFrame();
    const screenshot = async name => {
      await page.evaluate(() => { window.scrollTo(0, 0); });
      await page.evaluate(() => new Promise(requestAnimationFrame));
      await page.screenshot({ path: path.join(output, name), fullPage: true, animations: "disabled" });
      report.screenshots.push(name);
    };
    const currentData = await page.evaluate(() => {
      const data = window.__domelicaComparison.getData();
      return { schema: data.schema, config: data.config, provenance: data.provenance,
        metrics: data.metrics, scenes: data.native.scenes.map(scene => ({ id: scene.id, model: scene.model, samples: scene.times.length })) };
    });
    assert.equal(currentData.schema, "domelica.comparison.v1");
    assert.deepEqual(currentData.metrics, metrics);
    assert.equal(currentData.provenance.nativeSceneSHA256, manifest.nativeSceneSHA256);
    assert.deepEqual(currentData.config.sceneIds, manifest.sceneIds);
    assert.equal(currentData.config.sceneIds.length, 4);
    let current = await state();
    assert.equal(current.playing, false);
    assert.deepEqual(current.pair, manifest.defaultPair);
    assert.notEqual(current.pair[0], current.pair[1]);
    assert.equal(await page.locator("#error").isVisible(), false);
    assert.equal(await page.locator("#loading").isVisible(), false);
    report.renderers = current.frames.map(frame => frame.rendererInfo);
    for (const child of current.frames) {
      assert.equal(child.playing, false);
      assert.equal(child.rendererInfo.isWebGL2, true);
      assert.equal(child.rendererInfo.depthBuffer, true);
      assert.equal(child.rendererInfo.type, "Three.js WebGLRenderer");
      assert.ok(child.rendererInfo.drawCalls > 0);
    }
    record("two live native WebGL2 views with paused child clocks", { renderers: report.renderers });

    async function checkMapping() {
      // Snapshot state and rendered readouts in one browser task. During Play,
      // separate round-trips could compare an old time with a newer readout.
      const snapshot = await page.evaluate(() => ({
        ...window.__domelicaComparison.getState(),
        readouts: ["A", "B"].map(suffix => Object.fromEntries(
          Array.from(document.querySelectorAll("#readouts" + suffix + " output"),
            node => [node.dataset.signal, Number(node.dataset.value)]))),
      }));
      for (let slot = 0; slot < 2; slot++) {
        const scene = scenes.get(snapshot.pair[slot]), index = expectedIndex(scene.times, snapshot.time);
        const child = snapshot.frames[slot], sample = snapshot.samples[slot];
        assert.equal(child.sceneId, scene.id);
        assert.equal(child.index, index, `Wrong native index at shared time ${snapshot.time}: ${scene.id}`);
        assert.equal(child.time, scene.times[index]);
        assert.equal(child.playing, false, "Child clocks must never advance independently");
        assert.equal(sample.index, index);
        assert.equal(sample.time, scene.times[index]);
        assert.ok(sample.time <= snapshot.time);
        assert.ok(index === scene.times.length - 1 || scene.times[index + 1] > snapshot.time,
          "The last duplicate sample at an event must be selected");
        for (const series of scene.series) assert.equal(sample.values[series.name], series.values[index]);
        for (const name of ["shoulderAngle", "motorCurrent", "windingTemperature"]) {
          assert.equal(snapshot.readouts[slot][name], scene.series.find(series => series.name === name).values[index]);
        }
      }
      return snapshot;
    }
    await checkMapping();
    const pairScenes = current.pair.map(id => scenes.get(id));
    const repeated = pairScenes.flatMap(scene => scene.times.filter((t, i) => i > 0 && t === scene.times[i - 1]));
    const targetTimes = [...new Set([current.start, 0.37, 0.999, 1, 1.001, 9.999, 10, 20,
      current.end - 0.001, current.end, ...repeated.slice(0, 5)])].filter(t => t >= current.start && t <= current.end);
    for (const t of targetTimes) {
      await page.evaluate(value => window.__domelicaComparison.seek(value), t);
      current = await checkMapping(); assert.equal(current.time, t);
    }
    const unequalIndexTime = pairScenes.flatMap(scene => scene.times).find(t =>
      expectedIndex(pairScenes[0].times, t) !== expectedIndex(pairScenes[1].times, t));
    assert.notEqual(unequalIndexTime, undefined, "Native cases must exercise unequal event/sample grids for this comparison qualification");
    await page.evaluate(t => window.__domelicaComparison.seek(t), unequalIndexTime);
    current = await checkMapping();
    assert.notEqual(current.frames[0].index, current.frames[1].index);
    record("shared physical time maps independently through unequal grids and duplicate event samples", {
      checkedTimes: targetTimes, duplicateTimesObserved: repeated.length,
      unequalIndexTime, nativeIndexesAtThatTime: current.frames.map(frame => frame.index) });

    await page.locator("#scrub").evaluate(element => {
      element.value = "2.37"; element.dispatchEvent(new Event("input", { bubbles: true }));
    });
    current = await checkMapping(); assert.equal(current.time, 2.37);
    await page.locator("#play").click();
    await page.waitForFunction(() => window.__domelicaComparison.getState().time > 2.6);
    current = await checkMapping(); assert.equal(current.playing, true);
    await page.locator("#play").click(); current = await checkMapping();
    const pausedTime = current.time;
    await page.waitForTimeout(250);
    assert.equal((await state()).time, pausedTime);
    record("shared Play, Pause and scrub advance native samples without child clock drift");

    await page.frameLocator("#frameA").locator("#scene").focus();
    await page.keyboard.press("Space");
    await page.waitForFunction(() => window.__domelicaComparison.getState().playing);
    current = await checkMapping(); assert.equal(current.playing, true);
    await page.keyboard.press("Space");
    current = await checkMapping(); assert.equal(current.playing, false);
    record("Space inside a native canvas controls the shared clock");

    await page.locator("#speed").selectOption("4");
    await page.evaluate(() => { const api = window.__domelicaComparison; api.seek(api.getState().end - 0.05); });
    await page.locator("#play").click();
    await page.waitForFunction(() => { const s = window.__domelicaComparison.getState(); return !s.playing && s.time === s.end; });
    current = await checkMapping();
    assert.equal(await page.locator("#play").textContent(), "Replay");
    await page.locator("#play").click();
    await page.waitForFunction(() => { const s = window.__domelicaComparison.getState(); return s.playing && s.time < 1; });
    await page.locator("#play").click();
    record("shared end state, Replay and speed selection");
    await page.locator("#speed").selectOption("1");

    const seenCases = new Set();
    for (const id of currentData.config.sceneIds) {
      await page.locator("#caseB").selectOption(id);
      await page.evaluate(() => window.__domelicaComparison.seek(3.17));
      current = await checkMapping(); assert.equal(current.pair[1], id); seenCases.add(id);
      const metricsForCase = cases.get(id).metrics;
      for (const key of ["trackingRmseRad", "peakCurrentA", "peakTemperatureK", "electricalEnergyJ", "copperEnergyJ", "saturationDurationS"]) {
        const value = Number(await page.locator(`#metrics td[data-slot="1"][data-metric="${key}"]`).getAttribute("data-value"));
        assert.equal(value, metricsForCase[key]);
      }
      // Inspect a live box transform, not just the parent time label.
      const scene = scenes.get(id), object = scene.objects.find(item => item.type === "box");
      const frame = object.frames.length === 1 ? object.frames[0] : object.frames[current.frames[1].index];
      const actual = await (await childFrame(1)).evaluate(id => window.__domelica.getObjectTransform(id).matrixWorld, object.id);
      const expected = [...frame.slice(0, 3), 0, ...frame.slice(3, 6), 0, ...frame.slice(6, 9), 0, ...frame.slice(9, 12), 1];
      actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) <= 1e-10));
    }
    record("all four scenarios show native meshes and verified whole-run metrics", { cases: [...seenCases] });
    await page.locator("#play").click();
    await page.locator("#caseB").selectOption("m2-retuned");
    current = await checkMapping(); assert.equal(current.playing, false);
    assert.equal(current.pair[1], "m2-retuned");
    record("scenario switch pauses shared playback and commits one coherent case");

    await page.locator("#caseA").selectOption("m2-nominal");
    await page.locator("#caseB").selectOption("m2-heavy");
    await page.evaluate(() => window.__domelicaComparison.seek(1.8));
    current = await checkMapping();
    const desktopFrames = [];
    for (let slot = 0; slot < 2; slot++) {
      const frame = await childFrame(slot);
      const diagnostics = await frame.evaluate(() => window.__domelica.getRenderDiagnostics());
      const box = await frame.locator("#scene").boundingBox();
      desktopFrames.push(framing(scenes.get(current.pair[slot]), diagnostics, box));
    }
    await screenshot("01-controlled-comparison.png");
    record("desktop comparison keeps both complete native trajectories visible", { views: desktopFrames });
    await page.locator("#caseA").selectOption("m2-heavy");
    await page.locator("#caseB").selectOption("m2-retuned");
    await page.evaluate(() => window.__domelicaComparison.seek(12));
    await screenshot("02-retuned-comparison.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator("#caseA").selectOption("m2-nominal");
    await page.locator("#caseB").selectOption("m2-heavy");
    await page.evaluate(() => window.__domelicaComparison.seek(1.8));
    await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth + 1);
    current = await checkMapping();
    const mobileFrames = [];
    for (let slot = 0; slot < 2; slot++) {
      const frame = await childFrame(slot);
      await frame.waitForFunction(() => Math.abs(document.querySelector("#scene").width - document.querySelector("#scene").getBoundingClientRect().width) <= 1);
      const diagnostics = await frame.evaluate(() => window.__domelica.getRenderDiagnostics());
      const box = await frame.locator("#scene").boundingBox();
      mobileFrames.push(framing(scenes.get(current.pair[slot]), diagnostics, box));
      assert.ok(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    }
    await screenshot("03-mobile-comparison.png");
    record("390 px mobile comparison has no overflow or clipped native poses", { views: mobileFrames });

    // Test graphics failure on the actual delivered parent/iframe composition.
    // Keep this separate from the normal-path no-console-error assertion.
    const lossPage = await context.newPage();
    await lossPage.goto(fileURL, { waitUntil: "load" });
    await lossPage.waitForFunction(() => window.__domelicaComparison?.getState().available);
    await lossPage.locator("#play").click();
    const lossFrame = await (await lossPage.locator("#frameB").elementHandle()).contentFrame();
    assert.equal(await lossFrame.evaluate(() => {
      const extension = document.querySelector("#scene").getContext("webgl2").getExtension("WEBGL_lose_context");
      if (!extension) return false; extension.loseContext(); return true;
    }), true);
    await lossPage.locator("#error").waitFor({ state: "visible" });
    const lost = await lossPage.evaluate(() => window.__domelicaComparison.getState());
    assert.equal(lost.playing, false); assert.equal(lost.available, false);
    assert.equal(await lossPage.locator("#play").isDisabled(), true);
    assert.equal(await lossPage.locator("#scrub").isDisabled(), true);
    assert.match(await lossPage.locator("#error").textContent(), /graphics context/);
    await lossPage.close();
    record("a child graphics-context loss pauses and disables the shared comparison");

    const unavailable = await browser.newContext({ reducedMotion: "reduce" });
    await unavailable.route(/^https?:\/\//, route => route.abort());
    await unavailable.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
        if (this.id === "scene" && kind === "webgl2") return null;
        return original.call(this, kind, ...args);
      };
    });
    const unavailablePage = await unavailable.newPage();
    await unavailablePage.goto(fileURL, { waitUntil: "load" });
    await unavailablePage.locator("#error").waitFor({ state: "visible" });
    assert.match(await unavailablePage.locator("#error").textContent(), /WebGL2/);
    assert.equal(await unavailablePage.locator("#play").isDisabled(), true);
    assert.equal(await unavailablePage.evaluate(() => window.__domelicaComparison.getState().available), false);
    await unavailable.close();
    record("unavailable child WebGL2 is reported by the parent comparison");

    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []);
    assert.deepEqual(report.unexpectedRequests, []);
    record("comparison runs offline without unexpected browser errors or requests");
    report.passed = true;
  } catch (error) {
    report.error = { name: error.name, message: error.message, stack: error.stack };
    if (page) try {
      await page.screenshot({ path: path.join(output, "failure.png"), fullPage: true }); report.screenshots.push("failure.png");
    } catch (_) { /* Preserve the first failure. */ }
    console.error("FAIL native comparison:", error.message); process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
    if (browser) await browser.close();
  }
  if (report.passed) console.log(`PASS native comparison: ${report.steps.length} checks; ${report.screenshots.length} screenshots`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
