#!/usr/bin/env node
/* Browser checks against the generated native artifact, plus isolated and
 * explicitly labeled synthetic graphics fixtures for renderer edge cases.
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

// These checks use the actual Three camera matrices, not a duplicate of the
// application's camera-placement formula. Matrix elements are column-major.
function transformPoint(matrix, point) {
  const v = [...point, 1];
  const out = [0, 1, 2, 3].map(row => v.reduce((sum, x, col) => sum + matrix[4 * col + row] * x, 0));
  assert.ok(out.every(Number.isFinite) && Math.abs(out[3]) > 1e-14, "Invalid homogeneous projection");
  return out.slice(0, 3).map(x => x / out[3]);
}
function nativePoint(frame, point) {
  return [0, 1, 2].map(k => frame[9 + k] + point[0] * frame[k] + point[1] * frame[3 + k] + point[2] * frame[6 + k]);
}
function checkFraming(scene, diagnostics, viewport) {
  assert.equal(diagnostics.projectionMatrix.length, 16);
  assert.equal(diagnostics.matrixWorldInverse.length, 16);
  let margin = Infinity, depthMargin = Infinity, cornerCount = 0;
  for (const object of scene.objects) {
    for (const frame of object.frames) {
      for (const x of [0, 1]) for (const y of [-0.5, 0.5]) for (const z of [-0.5, 0.5]) {
        const world = nativePoint(frame, [x, y, z]);
        const view = transformPoint(diagnostics.matrixWorldInverse, world);
        const ndc = transformPoint(diagnostics.projectionMatrix, view);
        const screenX = (ndc[0] + 1) * viewport.width / 2;
        const screenY = (1 - ndc[1]) * viewport.height / 2;
        const distance = Math.min(screenX, screenY, viewport.width - screenX, viewport.height - screenY);
        assert.ok(distance >= -0.01, `Clipped native envelope: ${scene.id}/${object.id}, margin ${distance}px`);
        assert.ok(ndc[2] >= -1.000001 && ndc[2] <= 1.000001,
          `Near/far clipping: ${scene.id}/${object.id}, NDC depth ${ndc[2]}`);
        margin = Math.min(margin, distance);
        depthMargin = Math.min(depthMargin, 1 - Math.abs(ndc[2]));
        cornerCount++;
      }
    }
  }
  return { checkedCorners: cornerCount, minimumMarginPx: Number(margin.toFixed(3)),
    minimumClipDepthMargin: Number(depthMargin.toFixed(6)) };
}

function checkUnitGeometry(object, snapshot) {
  const epsilon = 2e-6;
  assert.ok(snapshot.boundingBox, `Missing actual geometry bounds: ${object.id}`);
  for (const [key, expected] of [["min", [0, -0.5, -0.5]], ["max", [1, 0.5, 0.5]]]) {
    snapshot.boundingBox[key].forEach((value, axis) => {
      assert.ok(Math.abs(value - expected[axis]) < epsilon,
        `Wrong unit ${object.type} extent ${key}[${axis}]: ${value}`);
    });
  }
  if (!snapshot.geometryPositions) return;
  const positions = snapshot.geometryPositions;
  assert.ok(positions.length >= 12 && positions.length % 3 === 0);
  assert.ok(positions.every(Number.isFinite));
  const points = [];
  for (let i = 0; i < positions.length; i += 3) points.push(positions.slice(i, i + 3));
  for (const [x, y, z] of points) {
    assert.ok(x >= -epsilon && x <= 1 + epsilon && Math.abs(y) <= 0.5 + epsilon && Math.abs(z) <= 0.5 + epsilon);
    if (object.type === "sphere") {
      assert.ok(Math.abs(Math.hypot(x - 0.5, y, z) - 0.5) < epsilon, "Sphere center/radius convention changed");
    }
  }
  if (object.type === "cone") {
    const tips = points.filter(p => p[0] >= 1 - epsilon);
    const base = points.filter(p => Math.abs(p[0]) <= epsilon);
    assert.ok(tips.length && tips.every(p => Math.hypot(p[1], p[2]) < epsilon), "Cone tip must face +X");
    assert.ok(base.some(p => Math.abs(Math.hypot(p[1], p[2]) - 0.5) < epsilon), "Cone base must lie at X=0");
  }
  if (object.type === "cylinder") {
    for (const x of [0, 1]) {
      assert.ok(points.some(p => Math.abs(p[0] - x) < epsilon && Math.abs(Math.hypot(p[1], p[2]) - 0.5) < epsilon),
        "Cylinder must span the X-axis with radius 0.5");
    }
  }
}

async function checkLiveMeshes(page, scene) {
  const indices = [...new Set([0, Math.floor(scene.times.length / 3),
    Math.floor(2 * scene.times.length / 3), scene.times.length - 1])];
  const inspectedTypes = new Set();
  let maxMatrixError = 0;
  for (const index of indices) {
    await page.evaluate(i => window.__domelica.seek(i), index);
    const requests = scene.objects.map(object => {
      const includeGeometry = !inspectedTypes.has(object.type);
      inspectedTypes.add(object.type);
      return { id: object.id, includeGeometry };
    });
    const snapshots = await page.evaluate(items => items.map(item =>
      window.__domelica.getObjectTransform(item.id, item.includeGeometry)), requests);
    scene.objects.forEach((object, i) => {
      const snapshot = snapshots[i], frame = object.frames[object.frames.length === 1 ? 0 : index];
      assert.equal(snapshot.id, object.id);
      assert.equal(snapshot.type, object.type);
      assert.equal(snapshot.matrixWorld.length, 16);
      const expected = [...frame.slice(0, 3), 0, ...frame.slice(3, 6), 0,
        ...frame.slice(6, 9), 0, ...frame.slice(9, 12), 1];
      snapshot.matrixWorld.forEach((value, j) => {
        const error = Math.abs(value - expected[j]);
        maxMatrixError = Math.max(maxMatrixError, error);
        assert.ok(Number.isFinite(value) && error <= 1e-10,
          `Actual Three mesh differs from native frame: ${scene.id}/${object.id}, sample ${index}, entry ${j}`);
      });
      checkUnitGeometry(object, snapshot);
    });
  }
  return { sampledFrames: indices, checkedMeshTransforms: indices.length * scene.objects.length,
    actualPrimitiveTypes: [...inspectedTypes], maxMatrixError };
}

async function main() {
  let browser, page;
  try {
    assert.ok(fs.existsSync(input), `Native HTML artifact is missing: ${input}`);
    report.artifactSha256 = sha256(fs.readFileSync(input));
    // This exercises real WebGL rendering on CI without claiming a hardware GPU.
    // Chromium documents SwANGLE for supported GPU-less browser testing.
    browser = await chromium.launch({ headless: true, args: [
      "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    ] });
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
    assert.equal(payload.scenes.length, 7, "M2 retains three baseline scenes and adds four controlled scenarios");
    assert.equal(new Set(payload.scenes.map(scene => scene.id)).size, 7);
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
    const renderDiagnostics = () => page.evaluate(() => window.__domelica.getRenderDiagnostics());
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
    const glState = await page.evaluate(() => {
      const gl = document.querySelector("#scene").getContext("webgl2");
      const debug = gl && gl.getExtension("WEBGL_debug_renderer_info");
      return { isWebGL2: gl instanceof WebGL2RenderingContext,
        depth: gl?.getContextAttributes()?.depth,
        depthBits: gl?.getParameter(gl.DEPTH_BITS),
        renderer: gl && debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl?.getParameter(gl.RENDERER),
        threeRevision: THREE.REVISION };
    });
    assert.equal(glState.isWebGL2, true, "Native scene must use an actual WebGL2 context");
    assert.equal(glState.depth, true);
    assert.ok(glState.depthBits >= 16, "A real depth buffer is required");
    assert.equal(current.rendererInfo.type, "Three.js WebGLRenderer");
    assert.equal(current.rendererInfo.isWebGL2, true);
    assert.equal(current.rendererInfo.contextLost, false);
    assert.equal(current.rendererInfo.revision, glState.threeRevision);
    assert.equal(glState.threeRevision, String(payload.provenance.renderer.revision));
    report.renderer = { ...glState, ...current.rendererInfo, testMode: "Chromium SwiftShader software WebGL" };
    record("pinned Three.js runtime, real WebGL2 context and depth buffer", { renderer: report.renderer });

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
      const framing = checkFraming(scene, await renderDiagnostics(), canvasBox);
      assert.ok(current.rendererInfo.drawCalls > 0 && current.rendererInfo.triangles > 0,
        "Actual Three renderer must submit native geometry");
      record(`native scene controls and actual camera framing: ${scene.id}`,
        { objects: current.objectCount, plots: scene.series.length, ...framing });
      record(`live native mesh transforms and primitive geometry: ${scene.id}`,
        await checkLiveMeshes(page, scene));
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
    const orbitFraming = checkFraming(arm, await renderDiagnostics(), box);
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

    // Click a real link, not its list button, using the actual camera projection.
    // At this time the upper link's center is unobscured in the default view.
    await page.locator("#view3d").click();
    const pickedLink = arm.objects.find(object => object.type === "box" && object.id.startsWith("upperArm."));
    assert.ok(pickedLink, "Native shoulder link is missing");
    current = await state();
    const pickedFrame = pickedLink.frames[pickedLink.frames.length === 1 ? 0 : current.index];
    const targetPoint = nativePoint(pickedFrame, [0.5, 0, 0]);
    const projectedLink = await page.evaluate(point => window.__domelica.projectWorld(point), targetPoint);
    box = await page.locator("#scene").boundingBox();
    await page.mouse.click(box.x + projectedLink.x, box.y + projectedLink.y);
    current = await state();
    assert.equal(current.selected, pickedLink.id, "Raycaster did not pick the actual native link");
    assert.ok((await page.locator("#inspector").textContent()).includes(pickedLink.id));
    if (await page.locator("#objects").evaluate(element => element.open)) await page.locator("#objects summary").click();
    record("raycaster selection of an actual native link", { selected: current.selected, worldPoint: targetPoint });

    await switchTo(pendulum);
    current = await seekTime(pendulum, 1.0);
    await page.locator("#viewxy").click();
    current = await state();
    box = await page.locator("#scene").boundingBox();
    const pendulumFraming = checkFraming(pendulum, await renderDiagnostics(), box);
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
    const mobileFraming = checkFraming(arm, await renderDiagnostics(), box);
    await screenshot("05-mobile.png");
    record("390 px mobile layout and trajectory framing", { dimensions, ...mobileFraming });

    // Isolated graphics fixtures exercise the production renderer. These are
    // deliberately synthetic rendering checks, not Modelica simulation evidence.
    const graphicsPage = await context.newPage();
    const graphicsErrors = [];
    graphicsPage.on("pageerror", error => graphicsErrors.push(error.message));
    await graphicsPage.goto(fileURL, { waitUntil: "load" });
    await graphicsPage.waitForFunction(() => window.__domelica?.available === true);
    try {
      // Calibrate the visible front and back surfaces through this exact
      // production camera, material, lighting and tone-mapping path. Raw native
      // RGB is not an output-pixel oracle once physically based lighting is used.
      const renderDepthCase = async mode => {
        await graphicsPage.evaluate(mode => {
          const makeBox = (id, color, z) => ({ id, type: "box", color,
            frames: [[1.2, 0, 0, 0, 1.2, 0, 0, 0, 0.1, -0.6, 0, z]] });
          const front = makeBox("synthetic.front", [0, 255, 0], 0.35);
          const back = makeBox("synthetic.back", [255, 0, 0], -0.35);
          const objects = mode === "front-only" ? [front] : mode === "back-only" ? [back]
            : mode === "front-first" ? [front, back] : [back, front];
          const scene = { id: "synthetic-depth-" + mode, title: "Synthetic depth-buffer regression",
            description: "Graphics fixture only; these boxes are not native simulation evidence.",
            model: "synthetic.graphics.depth", times: [0, 1], objects,
            // Fixed bounds keep camera and bounds-derived lights identical for
            // references and overlaps, including the isolated single-box cases.
            bounds: { min: [-1, -1, -1], max: [1, 1, 1] }, series: [] };
          D.scenes.push(scene);
          window.__domelica.changeScene(scene.id);
          document.querySelector("#viewxy").click();
        }, mode);
        const result = await graphicsPage.evaluate(() => {
          window.__domelica.draw();
          const canvas = document.querySelector("#scene"), gl = canvas.getContext("webgl2");
          const rgba = new Uint8Array(4);
          gl.readPixels(Math.floor(canvas.width / 2), Math.floor(canvas.height / 2), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, rgba);
          const camera = window.__domelica.getRenderDiagnostics();
          return { rgba: Array.from(rgba), error: gl.getError(), selected: window.__domelica.getState().selected,
            projectionMatrix: camera.projectionMatrix, matrixWorldInverse: camera.matrixWorldInverse };
        });
        assert.equal(result.error, 0, "WebGL pixel readback failed");
        assert.equal(result.selected, null, "Reference and overlap must have identical unselected materials");
        assert.equal(result.rgba[3], 255, "Depth fixture must paint an opaque surface at the sampled pixel");
        return result;
      };
      const pixelDifference = (a, b) => Math.max(...a.map((value, i) => Math.abs(value - b[i])));
      const frontReference = await renderDepthCase("front-only");
      const backReference = await renderDepthCase("back-only");
      assert.deepEqual(backReference.projectionMatrix, frontReference.projectionMatrix);
      assert.deepEqual(backReference.matrixWorldInverse, frontReference.matrixWorldInverse);
      // One 8-bit code value permits final readback rounding. The reference
      // acceptance regions must be disjoint, so an invisible/frontless scene
      // cannot pass merely because two arbitrarily similar colors were chosen.
      const pixelTolerance = 1;
      const referenceSeparation = pixelDifference(frontReference.rgba, backReference.rgba);
      assert.ok(referenceSeparation > 2 * pixelTolerance,
        `Front/back reference pixels are not distinguishable: ${JSON.stringify(frontReference.rgba)} / ${JSON.stringify(backReference.rgba)}`);
      const depthCases = [];
      for (const mode of ["front-first", "back-first"]) {
        const pixel = await renderDepthCase(mode);
        assert.deepEqual(pixel.projectionMatrix, frontReference.projectionMatrix);
        assert.deepEqual(pixel.matrixWorldInverse, frontReference.matrixWorldInverse);
        const frontDifference = pixelDifference(pixel.rgba, frontReference.rgba);
        const backDifference = pixelDifference(pixel.rgba, backReference.rgba);
        assert.ok(frontDifference <= pixelTolerance && backDifference > pixelTolerance,
          `Overlap did not retain the isolated front surface (${mode}): pixel ${JSON.stringify(pixel.rgba)}, ` +
          `front ${JSON.stringify(frontReference.rgba)}, back ${JSON.stringify(backReference.rgba)}`);
        const fixtureBox = await graphicsPage.locator("#scene").boundingBox();
        await graphicsPage.mouse.click(fixtureBox.x + fixtureBox.width / 2, fixtureBox.y + fixtureBox.height / 2);
        const selected = await graphicsPage.evaluate(() => window.__domelica.getState().selected);
        assert.equal(selected, "synthetic.front", "Picking must return the nearest intersected native-shaped mesh");
        depthCases.push({ mode, centerRGBA: pixel.rgba, frontDifference, backDifference, selected });
      }
      record("synthetic opaque depth-buffer and nearest-surface picking regression", {
        frontReferenceRGBA: frontReference.rgba, backReferenceRGBA: backReference.rgba,
        pixelTolerance, referenceSeparation, cases: depthCases,
        scope: "Graphics fixture only; separate from native physics evidence" });

      // The real demonstrations contain boxes/cylinders/cones. Exercise the
      // remaining advertised sphere convention through the same renderer.
      const sphereSnapshot = await graphicsPage.evaluate(() => {
        const scene = { id: "synthetic-sphere", title: "Synthetic sphere contract",
          description: "Graphics fixture only", model: "synthetic.graphics.sphere", times: [0, 1],
          objects: [{ id: "synthetic.sphere", type: "sphere", color: [80, 180, 220],
            frames: [[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]] }],
          bounds: { min: [0, -0.5, -0.5], max: [1, 0.5, 0.5] }, series: [] };
        D.scenes.push(scene); window.__domelica.changeScene(scene.id);
        return window.__domelica.getObjectTransform("synthetic.sphere", true);
      });
      checkUnitGeometry({ id: "synthetic.sphere", type: "sphere" }, sphereSnapshot);
      record("synthetic sphere canonical geometry contract", { vertices: sphereSnapshot.geometryPositions.length / 3,
        scope: "Graphics fixture only; separate from native physics evidence" });

      const canLoseContext = await graphicsPage.evaluate(() => {
        const gl = document.querySelector("#scene").getContext("webgl2");
        const extension = gl.getExtension("WEBGL_lose_context");
        if (!extension) return false;
        extension.loseContext(); return true;
      });
      assert.equal(canLoseContext, true, "CI WebGL context-loss extension is unavailable");
      await graphicsPage.waitForFunction(() => window.__domelica.getState().rendererInfo.contextLost);
      assert.equal(await graphicsPage.locator("#error").isVisible(), true);
      assert.match(await graphicsPage.locator("#error").textContent(), /context.*lost/i);
      assert.equal(await graphicsPage.locator("#play").isDisabled(), true);
      assert.equal(await graphicsPage.locator("#scrub").isDisabled(), true);
      assert.equal(await graphicsPage.evaluate(() => window.__domelica.getState().playing), false);
      assert.deepEqual(graphicsErrors, []);
      record("WebGL context loss visibly pauses playback");
    } finally {
      await graphicsPage.close();
    }

    // Test an unavailable graphics capability explicitly. This isolated page
    // cannot create WebGL; the delivered application must explain the limitation.
    const unavailableContext = await browser.newContext({ viewport: { width: 1100, height: 800 }, reducedMotion: "reduce" });
    await unavailableContext.route(/^https?:\/\//, route => route.abort());
    await unavailableContext.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
        if (this.id === "scene" && /^(webgl2?|experimental-webgl)$/.test(kind)) return null;
        return original.call(this, kind, ...args);
      };
    });
    const unavailablePage = await unavailableContext.newPage(), unavailableErrors = [];
    unavailablePage.on("pageerror", error => unavailableErrors.push(error.message));
    await unavailablePage.goto(fileURL, { waitUntil: "load" });
    await unavailablePage.locator("#error").waitFor({ state: "visible" });
    assert.match(await unavailablePage.locator("#error").textContent(), /WebGL2/);
    assert.equal(await unavailablePage.locator("#play").isDisabled(), true);
    assert.equal(await unavailablePage.locator("#scrub").isDisabled(), true);
    assert.equal(await unavailablePage.evaluate(() => window.__domelica?.available === true), false);
    assert.deepEqual(unavailableErrors, []);
    record("WebGL2 unavailable has an explicit visible failure state", {
      message: await unavailablePage.locator("#error").textContent(),
    });
    await unavailableContext.close();

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
