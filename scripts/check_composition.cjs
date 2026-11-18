#!/usr/bin/env node
"use strict";
// Observe native evidence and the unchanged renderer. No equation of motion is solved here.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createHash } = require("node:crypto");
const { chromium } = require("playwright");
const input = path.resolve(process.argv[2] || "artifacts/composition-preview.html");
const output = path.join(path.dirname(input), "composition-checks");
fs.mkdirSync(output, { recursive: true });
const sha = value => createHash("sha256").update(value).digest("hex");
const report = { passed: false, artifact: path.basename(input), artifactSha256: null,
  browser: null, steps: [], screenshots: [], pageErrors: [], consoleErrors: [], unexpectedRequests: [] };
const record = (name, detail = {}) => { report.steps.push({ name, passed: true, ...detail }); console.log("PASS", name); };
const close = (a, b, tolerance = 1e-10) => assert.ok(Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= tolerance, `${a} differs from ${b}`);
const sampleAt = (samples, i) => samples[samples.length === 1 ? 0 : i];
const frameAt = (object, i) => sampleAt(object.frames, i);
const point = (frame, v) => [0, 1, 2].map(k => frame[9 + k] + v[0] * frame[k] + v[1] * frame[k + 3] + v[2] * frame[k + 6]);
const vectorAt = (scene, name, i) => [1, 2, 3].map(k => scene.probes[`${name}[${k}]`][i]);
const minus = (a, b) => a.map((v, k) => v - b[k]);
const dot = (a, b) => a.reduce((s, v, k) => s + v * b[k], 0);
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = a => { const n = Math.hypot(...a); assert.ok(n > 0); return a.map(v => v / n); };
const maxDistance = positions => positions.reduce((max, p) => Math.max(max, Math.hypot(...minus(p, positions[0]))), 0);
const nearestIndex = (scene, time) => scene.times.reduce((best, value, i) => Math.abs(value - time) < Math.abs(scene.times[best] - time) ? i : best, 0);

function inspectNativeGeometry(scene) {
  const native = new Map(scene.nativeDimensions.map(item => [item.id, item]));
  assert.equal(native.size, scene.objects.length);
  let maximumDimensionError = 0, dimensionsChecked = 0, springRadiusSamples = 0;
  const primitiveCounts = {};
  for (const object of scene.objects) {
    assert.ok(["box", "cylinder", "cone", "sphere", "spring"].includes(object.type));
    primitiveCounts[object.type] = (primitiveCounts[object.type] || 0) + 1;
    const source = native.get(object.id); assert.equal(source.type, object.type);
    for (const rows of Object.values(source.fields)) assert.ok(rows.length === 1 || rows.length === scene.times.length);
    assert.ok(object.frames.length === 1 || object.frames.length === scene.times.length);
    scene.times.forEach((time, i) => {
      const fields = Object.fromEntries(Object.entries(source.fields).map(([name, rows]) => [name, sampleAt(rows, i)]));
      const kind = object.type, frame = frameAt(object, i);
      let sizes = [fields.length[0], fields.width[0], fields.height[0]];
      if (kind === "cylinder" || kind === "cone") sizes[2] = sizes[1];
      if (kind === "sphere") sizes = [sizes[0], sizes[0], sizes[0]];
      if (kind === "spring") {
        const spec = sampleAt(object.spring, i);
        ["length", "width", "height", "extra"].forEach((key, k) => close(spec[k], fields[key][0]));
        assert.ok(spec.every(v => v > 0) && spec[2] < spec[1]);
        sizes = [1, 1, 1]; springRadiusSamples++;
      }
      assert.equal(frame.length, 12); assert.ok(frame.every(Number.isFinite));
      const axes = [frame.slice(0, 3), frame.slice(3, 6), frame.slice(6, 9)];
      axes.forEach((axis, k) => {
        const size = Math.hypot(...axis); close(size, sizes[k]);
        maximumDimensionError = Math.max(maximumDimensionError, Math.abs(size - sizes[k]));
      });
      // Native geometry axes are orthogonal even while a joint rotates them.
      for (let a = 0; a < 3; a++) for (let b = a + 1; b < 3; b++) close(dot(axes[a], axes[b]), 0);
      if (sizes.every(v => v > 0)) close(dot(cross(unit(axes[0]), unit(axes[1])), unit(axes[2])), 1);
      dimensionsChecked++;
    });
  }
  return { primitiveCounts, allSampleShapeDimensionsChecked: dimensionsChecked,
    maximumNativeDimensionError_m: maximumDimensionError, springNativeRadiusSamplesChecked: springRadiusSamples };
}

function inspectPhysicalObservations(scene) {
  const definitions = scene.observations, byId = new Map(scene.objects.map(object => [object.id, object]));
  let positionError = 0, segmentError = 0, endpointError = 0, endpointPairs = 0;
  const positions = new Map(), bodyTravel = {}, rotations = {}, springTravel = {};
  for (const body of definitions.bodies) {
    const object = byId.get(body.object); assert.ok(object && object.type !== "spring");
    const nativePositions = scene.times.map((time, i) => {
      const native = vectorAt(scene, body.position, i), rendered = point(frameAt(object, i), body.localPoint);
      native.forEach((v, k) => { close(rendered[k], v); positionError = Math.max(positionError, Math.abs(rendered[k] - v)); });
      return native;
    });
    const travel = maxDistance(nativePositions);
    assert.ok(travel > body.minimumTravel, `${body.role} must actually translate: ${travel}`);
    positions.set(body.role, nativePositions); bodyTravel[body.role] = travel;
  }
  for (const pair of definitions.relativeMotion || []) {
    assert.ok(positions.has(pair.a) && positions.has(pair.b));
    const relative = positions.get(pair.a).map((p, i) => minus(p, positions.get(pair.b)[i]));
    assert.ok(maxDistance(relative) > pair.minimumTravel, `${pair.a} and ${pair.b} need genuine relative motion`);
  }
  for (const segment of definitions.segments || []) {
    const object = byId.get(segment.object), starts = [], ends = [], directions = [];
    scene.times.forEach((time, i) => {
      const a = vectorAt(scene, segment.frameA, i), b = vectorAt(scene, segment.frameB, i);
      const graphicsA = point(frameAt(object, i), segment.localPointA), graphicsB = point(frameAt(object, i), segment.localPointB);
      for (let k = 0; k < 3; k++) {
        close(graphicsA[k], a[k]); close(graphicsB[k], b[k]);
        segmentError = Math.max(segmentError, Math.abs(graphicsA[k] - a[k]), Math.abs(graphicsB[k] - b[k]));
      }
      starts.push(a); ends.push(b); directions.push(unit(minus(b, a)));
    });
    const maxAngle = directions.reduce((max, v) => Math.max(max, Math.acos(Math.max(-1, Math.min(1, dot(v, directions[0]))))), 0);
    assert.ok(maxAngle > segment.minimumRotation, `Native segment must rotate: ${segment.object}`);
    assert.ok(maxDistance(starts) > segment.minimumStartTravel, "Native segment pivot must translate");
    assert.ok(maxDistance(ends) > segment.minimumEndTravel, "Native segment end must translate");
    rotations[segment.object] = { maximumAngleFromInitial_rad: maxAngle,
      startTravel_m: maxDistance(starts), endTravel_m: maxDistance(ends) };
  }
  for (const id of definitions.fixedObjects) {
    const object = byId.get(id), initial = frameAt(object, 0);
    scene.times.forEach((time, i) => frameAt(object, i).forEach((v, k) => close(v, initial[k])));
  }
  assert.equal(scene.objects.filter(o => o.type === "spring").length, definitions.springs.length);
  for (const spring of definitions.springs) {
    const object = byId.get(spring.object), lengths = [], aPositions = [], bPositions = [];
    scene.times.forEach((time, i) => {
      const frame = frameAt(object, i), spec = sampleAt(object.spring, i);
      const a = vectorAt(scene, spring.frameA, i), b = vectorAt(scene, spring.frameB, i);
      const graphicsA = point(frame, [0, 0, 0]), graphicsB = point(frame, [spec[0], 0, 0]);
      for (let k = 0; k < 3; k++) {
        close(graphicsA[k], a[k]); close(graphicsB[k], b[k]);
        endpointError = Math.max(endpointError, Math.abs(graphicsA[k] - a[k]), Math.abs(graphicsB[k] - b[k]));
      }
      close(spec[0], Math.hypot(...minus(a, b)));
      lengths.push(spec[0]); aPositions.push(a); bPositions.push(b); endpointPairs++;
    });
    const lengthChange = Math.max(...lengths) - Math.min(...lengths), aTravel = maxDistance(aPositions), bTravel = maxDistance(bPositions);
    assert.ok(lengthChange > spring.minimumLengthChange, `Native spring must change length: ${spring.object}`);
    if (spring.minimumFrameATravel !== undefined) assert.ok(aTravel > spring.minimumFrameATravel);
    if (spring.maximumFrameATravel !== undefined) assert.ok(aTravel <= spring.maximumFrameATravel);
    if (spring.minimumFrameBTravel !== undefined) assert.ok(bTravel > spring.minimumFrameBTravel);
    springTravel[spring.object] = { lengthChange_m: lengthChange, frameATravel_m: aTravel, frameBTravel_m: bTravel };
  }
  return { nativeSamples: scene.times.length, nativePositionsChecked: scene.times.length * definitions.bodies.length,
    maximumBodyPointError_m: positionError, bodyTravel_m: bodyTravel, rotatingSegments: rotations,
    maximumSegmentEndpointError_m: segmentError, springEndpointPairsChecked: endpointPairs,
    maximumSpringEndpointError_m: endpointError, springTravel };
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

function inspectCanonicalSolid(snapshot) {
  const vertices = snapshot.geometryPositions, tolerance = 1e-7;
  assert.ok(vertices.length > 0 && vertices.length % 3 === 0 && vertices.every(Number.isFinite));
  for (let i = 0; i < vertices.length; i += 3) {
    const [x, y, z] = vertices.slice(i, i + 3), radial = Math.hypot(y, z);
    assert.ok(x >= -tolerance && x <= 1 + tolerance && Math.abs(y) <= .5 + tolerance && Math.abs(z) <= .5 + tolerance);
    if (snapshot.type === "sphere") close(Math.hypot(x - .5, y, z), .5, tolerance);
    else if (snapshot.type === "cylinder") assert.ok(Math.abs(radial - .5) <= tolerance || Math.abs(x) <= tolerance || Math.abs(x - 1) <= tolerance);
    else if (snapshot.type === "cone") assert.ok(Math.abs(radial - .5 * (1 - x)) <= tolerance || Math.abs(x) <= tolerance);
    else if (snapshot.type === "box") assert.ok(Math.abs(x) <= tolerance || Math.abs(x - 1) <= tolerance || Math.abs(Math.abs(y) - .5) <= tolerance || Math.abs(Math.abs(z) - .5) <= tolerance);
    else assert.fail(`Unsupported canonical solid ${snapshot.type}`);
  }
  return vertices.length / 3;
}

async function inspectMeshes(page, scene) {
  const indices = scene.observations.checkTimes.map(time => nearestIndex(scene, time));
  assert.equal(new Set(indices).size, 4, "Four distinct native frames must be rendered");
  let matrixError = 0, springChecks = 0, wireError = 0, primitiveVertices = 0;
  for (const index of indices) {
    await page.evaluate(i => window.__domelica.seek(i), index);
    const snapshots = await page.evaluate(ids => ids.map(id => window.__domelica.getObjectTransform(id, true)), scene.objects.map(o => o.id));
    scene.objects.forEach((object, j) => {
      const frame = frameAt(object, index), snapshot = snapshots[j]; assert.equal(snapshot.type, object.type);
      const expected = [...frame.slice(0, 3), 0, ...frame.slice(3, 6), 0, ...frame.slice(6, 9), 0, ...frame.slice(9, 12), 1];
      snapshot.matrixWorld.forEach((v, k) => { close(v, expected[k]); matrixError = Math.max(matrixError, Math.abs(v - expected[k])); });
      assert.ok(snapshot.geometryPositions.every(Number.isFinite));
      if (object.type === "spring") { wireError = Math.max(wireError, inspectSpring(object, index, snapshot)); springChecks++; }
      else primitiveVertices += inspectCanonicalSolid(snapshot);
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
  return { nativeSamplesChecked: indices, nativeTimesChecked: indices.map(i => scene.times[i]),
    meshTransformsChecked: indices.length * scene.objects.length, maximumMatrixError: matrixError,
    canonicalSolidVerticesChecked: primitiveVertices, springCrossSectionsChecked: springChecks,
    maximumWireRadiusError_m: wireError };
}

async function checkFraming(page, scene) {
  const checks = await page.evaluate(s => {
    let count = 0, minimumMargin = Infinity;
    const viewport = window.__domelica.getRenderDiagnostics().viewport;
    for (const object of s.objects) for (let i = 0; i < s.times.length; i++) {
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
        minimumMargin = Math.min(minimumMargin, p.x, p.y, viewport.width - p.x, viewport.height - p.y); count++;
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
    const r = n.getBoundingClientRect(); return { width: r.width, height: r.height, left: r.left, right: r.right, viewport: innerWidth };
  }));
  assert.ok(boxes.every(b => b.width > 20 && b.height > 20 && b.left >= 0 && b.right <= b.viewport + 1));
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(output, name), fullPage: true }); report.screenshots.push(name);
}

async function main() {
  let browser;
  try {
    report.artifactSha256 = sha(fs.readFileSync(input));
    const manifest = JSON.parse(fs.readFileSync(path.join(path.dirname(input), "composition-provenance.json")));
    assert.equal(manifest.previewSHA256, report.artifactSha256);
    const expectedPayload = JSON.parse(fs.readFileSync(path.join(path.dirname(input), "composition-scenes.json")));
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
    assert.deepEqual(payload, expectedPayload); assert.equal(payload.schema, "domelica.motion-scene.v1");
    assert.deepEqual(payload.scenes.map(s => s.id), manifest.scenes.map(s => s.id));
    assert.equal(payload.metrics.passed, true);
    const info = await page.evaluate(() => window.__domelica.getState().rendererInfo);
    assert.equal(info.isWebGL2, true); assert.equal(info.depthBuffer, true); assert.ok(info.triangles > 0);
    assert.equal((await page.evaluate(() => window.__domelica.getState())).playing, false);
    record("Delivered HTML identity, native payload, physical acceptance and paused offline WebGL2", { renderer: info });

    for (const scene of payload.scenes) {
      record(`${scene.id}: all native shape dimensions, axis constraints and spring radii`, inspectNativeGeometry(scene));
      record(`${scene.id}: native body positions, joint rotation and spring attachments`, inspectPhysicalObservations(scene));
      await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
      assert.equal((await page.evaluate(() => window.__domelica.getState())).sceneId, scene.id);
      assert.equal(await page.locator("#title").textContent(), scene.title);
      record(`${scene.id}: four rendered native frames, primitive geometry and synchronized signals`, await inspectMeshes(page, scene));
      await noOverflow(page); const framing = await checkFraming(page, scene);
      await page.evaluate(() => window.__domelica.seek(0));
      const initialPixels = sha(await page.locator("#scene").screenshot());
      const capture = nearestIndex(scene, scene.observations.screenshotTime);
      await page.evaluate(i => window.__domelica.seek(i), capture);
      assert.notEqual(sha(await page.locator("#scene").screenshot()), initialPixels, "Native motion must change rendered pixels");
      await screenshot(page, `${scene.id}-desktop.png`);
      record(`${scene.id}: whole-trajectory framing and visible movement`, { ...framing, screenshotTime: scene.times[capture] });
      await page.locator("#viewxy").click();
      const flat = await page.evaluate(() => window.__domelica.getState()); close(flat.camera.yaw, 0); close(flat.camera.pitch, 0);
      const pick = scene.observations.pick, object = scene.objects.find(o => o.id === pick.object);
      const projected = await page.evaluate(p => window.__domelica.projectWorld(p), point(frameAt(object, capture), pick.localPoint));
      const box = await page.locator("#scene").boundingBox();
      await page.mouse.click(box.x + projected.x, box.y + projected.y);
      assert.equal((await page.evaluate(() => window.__domelica.getState())).selected, pick.object);
      assert.ok((await page.locator("#inspector").textContent()).includes(pick.object));
      record(`${scene.id}: XY camera and actual pointer selection`, { selectedObject: pick.object });
      await page.locator("#view3d").click();
      const canvas = await page.locator("#scene").boundingBox(), before = await page.evaluate(() => window.__domelica.getState().camera.yaw);
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
      assert.equal(replay.playing, false); assert.ok(replay.time < scene.times.at(-1));
      await page.locator("#scrub").evaluate((node, value) => { node.value = String(value); node.dispatchEvent(new Event("input", { bubbles: true })); }, capture);
      const scrubbed = await page.evaluate(() => window.__domelica.getState());
      assert.equal(scrubbed.index, capture); assert.equal(scrubbed.playing, false);
      record(`${scene.id}: orbit, bounded playback, replay, speed, pause and scrub`);
    }

    for (const width of [360, 390]) {
      await page.setViewportSize({ width, height: 844 });
      for (const scene of payload.scenes) {
        await page.locator(`.scene-tab[data-id="${scene.id}"]`).click();
        await page.evaluate(i => window.__domelica.seek(i), nearestIndex(scene, scene.observations.screenshotTime));
        await noOverflow(page); const framing = await checkFraming(page, scene);
        if (width === 390) await screenshot(page, `${scene.id}-mobile.png`);
        const selectedId = scene.observations.bodies[0].object;
        if (!(await page.locator("#objects").evaluate(node => node.open))) await page.locator("#objects summary").click();
        await page.locator(`.object-button[data-id="${selectedId}"]`).click();
        assert.equal((await page.evaluate(() => window.__domelica.getState())).selected, selectedId);
        record(`${scene.id}: ${width}px mobile controls, component inspection and whole-trajectory framing`, framing);
      }
    }
    const noGl = await browser.newContext({ viewport: { width: 800, height: 600 }, offline: true });
    await noGl.addInitScript(() => { const original = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(type, ...args) { return type === "webgl2" ? null : original.call(this, type, ...args); }; });
    const fallback = await noGl.newPage(); await fallback.goto(pathToFileURL(input).href);
    await fallback.waitForFunction(() => window.__domelica?.available === false);
    assert.ok((await fallback.locator("#error").textContent()).includes("WebGL2")); assert.equal(await fallback.locator("#play").isDisabled(), true);
    record("Explicit WebGL-unavailable state"); await noGl.close();
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.unexpectedRequests, []);
    record("No browser errors or network requests"); report.passed = true;
  } catch (error) {
    report.failure = String(error.stack || error); throw error;
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
