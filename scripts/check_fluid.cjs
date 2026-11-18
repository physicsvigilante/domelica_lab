#!/usr/bin/env node
"use strict";
// Check the delivered SVG drawing and native data, rather than a replacement model.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createHash } = require("node:crypto");
const { chromium } = require("playwright");

const input = path.resolve(process.argv[2] || "artifacts/fluid-preview.html");
const directory = path.dirname(input), output = path.join(directory, "fluid-checks");
fs.mkdirSync(output, { recursive: true });
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const report = { passed: false, artifact: path.basename(input), artifactSha256: null,
  browser: null, steps: [], screenshots: [], pageErrors: [], consoleErrors: [], unexpectedRequests: [] };
const record = (name, detail = {}) => { report.steps.push({ name, passed: true, ...detail }); console.log("PASS", name); };
const expectedIndex = (times, target) => {
  let index = 0;
  for (let i = 0; i < times.length; i++) if (times[i] <= target) index = i;
  return index;
};
function middleDirection(points) {
  const lengths = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1]));
  let distance = lengths.reduce((a, b) => a + b, 0) * .52;
  for (let i = 0; i < lengths.length; i++) {
    if (distance <= lengths[i] && lengths[i] > 0) {
      return [(points[i + 1][0] - points[i][0]) / lengths[i], (points[i + 1][1] - points[i][1]) / lengths[i]];
    }
    distance -= lengths[i];
  }
  throw new Error("No finite direction on schematic path");
}

async function main() {
  let browser, page;
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(directory, "fluid-provenance.json"), "utf8"));
    const dataBytes = fs.readFileSync(path.join(directory, "fluid-scenes.json"));
    const metricsBytes = fs.readFileSync(path.join(directory, "m3-metrics.json"));
    const data = JSON.parse(dataBytes), metrics = JSON.parse(metricsBytes);
    report.artifactSha256 = sha(fs.readFileSync(input));
    assert.equal(report.artifactSha256, manifest.previewSHA256);
    assert.equal(sha(dataBytes), manifest.dataSHA256);
    assert.equal(sha(metricsBytes), manifest.inputsSHA256["artifacts/m3-metrics.json"]);
    assert.deepEqual(data.metrics, metrics);
    assert.equal(data.schema, "domelica.fluid-schematic.v1");
    assert.equal(data.provenance.revision, manifest.revision);
    assert.equal(metrics.verificationScriptSHA256, manifest.sourceSHA256["scripts/verify_m3.py"]);
    assert.deepEqual(data.provenance.sourceSHA256, manifest.sourceSHA256);
    for (const item of [...metrics.cases, ...metrics.qualifications]) {
      assert.equal(item.verification.passed, true);
      assert.equal(item.nativeCSV_SHA256, manifest.inputsSHA256[item.prefix + "_res.csv"]);
      assert.equal(item.nativeMAT_SHA256, manifest.inputsSHA256[item.prefix + "_res.mat"]);
    }
    const scenes = new Map(data.scenes.map(s => [s.id, s]));
    assert.equal(scenes.size, 4);
    assert.deepEqual([...scenes.keys()], manifest.sceneIds);
    report.provenance = manifest;
    record("HTML, native data, metrics, verifier and per-case input identities");

    browser = await chromium.launch({ headless: true });
    report.browser = browser.version();
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
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
    await page.waitForFunction(() => window.__domelicaFluid?.getState().available === true);
    assert.deepEqual(await page.evaluate(() => window.__domelicaFluid.getData()), data);
    assert.equal(await page.locator("#error").isVisible(), false);
    let current = await page.evaluate(() => window.__domelicaFluid.getState());
    assert.equal(current.sceneId, manifest.defaultScene);
    assert.equal(current.playing, false);
    record("self-contained native schematic loads with the verified embedded payload");

    async function snapshot() {
      return page.evaluate(() => {
        const state = window.__domelicaFluid.getState();
        return { state,
          outputs: Array.from(document.querySelectorAll("output[data-signal]"), n => ({ name: n.dataset.signal, value: Number(n.dataset.value) })),
          tanks: Array.from(document.querySelectorAll(".node[data-level]"), n => ({ id: n.dataset.node,
            level: Number(n.dataset.level), capacity: Number(n.dataset.capacity), ratio: Number(n.dataset.ratio),
            drawnRatio: Number(n.dataset.drawnRatio), outOfRange: n.dataset.outOfRange === "true",
            fillHeight: Number(n.querySelector(".tank-fill").getAttribute("height")),
            fillY: Number(n.querySelector(".tank-fill").getAttribute("y")),
            pressure: Number(n.querySelector(".tank-pressure").dataset.value) })),
          flows: Array.from(document.querySelectorAll("[data-edge]"), n => {
            const arrow = n.querySelector(".flow-arrow"), matrix = arrow.getCTM();
            return { id: n.dataset.edge, native: Number(n.dataset.nativeValue), flow: Number(n.dataset.flow),
              direction: Number(n.dataset.direction), visible: getComputedStyle(arrow).display !== "none", forward: [matrix.a, matrix.b] };
          }),
          valves: Array.from(document.querySelectorAll(".node[data-opening]"), n => ({ id: n.dataset.node, opening: Number(n.dataset.opening) })),
          metrics: Array.from(document.querySelectorAll("output[data-metric]"), n => ({ name: n.dataset.metric, value: Number(n.dataset.value) })),
        };
      });
    }
    async function checkNative() {
      const shot = await snapshot(), s = scenes.get(shot.state.sceneId), index = expectedIndex(s.times, shot.state.time);
      const values = new Map(s.series.map(item => [item.name, item.values[index]]));
      assert.equal(shot.state.index, index);
      assert.equal(shot.state.nativeTime, s.times[index]);
      assert.ok(s.times[index] <= shot.state.time);
      assert.ok(index === s.times.length - 1 || s.times[index + 1] > shot.state.time);
      for (const [name, value] of values) assert.equal(shot.state.values[name], value);
      for (const item of shot.outputs) assert.equal(item.value, values.get(item.name));
      assert.equal(shot.tanks.length, 2);
      for (const tank of shot.tanks) {
        const node = s.diagram.nodes.find(n => n.id === tank.id), position = s.diagram.layouts[shot.state.layout].nodes[tank.id];
        const level = values.get(node.level), capacity = values.get(node.capacity), fraction = level / capacity;
        assert.equal(tank.level, level); assert.equal(tank.capacity, capacity); assert.equal(tank.ratio, fraction);
        assert.equal(tank.drawnRatio, Math.max(0, Math.min(1, fraction)));
        assert.equal(tank.outOfRange, fraction < 0 || fraction > 1);
        assert.ok(Math.abs(tank.fillHeight / position[3] - Math.max(0, Math.min(1, fraction))) < 1e-12);
        assert.ok(Math.abs(tank.fillY + tank.fillHeight - position[1] - position[3]) < 1e-9);
        assert.equal(tank.pressure, values.get(node.pressure));
      }
      assert.equal(shot.flows.length, s.diagram.edges.length);
      for (const flow of shot.flows) {
        const edge = s.diagram.edges.find(e => e.id === flow.id), native = values.get(edge.flow), signed = native * edge.orientation;
        assert.equal(flow.native, native); assert.equal(flow.flow, signed); assert.equal(flow.direction, Math.sign(signed));
        assert.equal(flow.visible, signed !== 0);
        if (signed !== 0) {
          const direction = middleDirection(s.diagram.layouts[shot.state.layout].edges[edge.id]);
          assert.ok(Math.sign(signed) * (flow.forward[0] * direction[0] + flow.forward[1] * direction[1]) > 0,
            "Actual SVG arrow points against the signed native flow");
        }
      }
      for (const valve of shot.valves) {
        const node = s.diagram.nodes.find(n => n.id === valve.id); assert.equal(valve.opening, values.get(node.opening));
      }
      for (const item of shot.metrics) assert.equal(item.value, s.verifiedCase.metrics[item.name]);
      return shot.state;
    }

    let checkedSamples = 0, duplicateSamples = 0;
    for (const s of scenes.values()) {
      await page.locator("#caseSelect").selectOption(s.id);
      const duplicated = s.times.filter((t, i) => i > 0 && t === s.times[i - 1]);
      duplicateSamples += duplicated.length;
      const sampleTimes = [...new Set([s.times[0], .37, 99.999, 100, 100.001, 140, 200, 240, s.times.at(-1), ...duplicated.slice(0, 6)])];
      for (const t of sampleTimes.filter(t => t >= s.times[0] && t <= s.times.at(-1))) {
        await page.evaluate(t => window.__domelicaFluid.seek(t), t);
        current = await checkNative(); assert.equal(current.time, t); checkedSamples++;
      }
    }
    assert.ok(duplicateSamples > 0, "Native cases should exercise duplicate event timestamps");
    record("all four cases map native samples into actual tank fill, arrows, pressures, valve states and plots", { checkedSamples, duplicateSamples });

    const directions = new Set(); let negativeExample = null;
    for (const s of scenes.values()) {
      for (const edge of s.diagram.edges) {
        const values = s.series.find(item => item.name === edge.flow).values;
        for (const sign of [-1, 1]) {
          const i = values.findIndex(v => Math.sign(v * edge.orientation) === sign && Math.abs(v) > 1e-6);
          if (i >= 0) {
            await page.evaluate(id => window.__domelicaFluid.setScene(id), s.id);
            await page.evaluate(t => window.__domelicaFluid.seek(t), s.times[i]);
            await checkNative(); directions.add(sign);
            if (sign < 0 && !negativeExample) negativeExample = { scene: s.id, time: s.times[i], edge: edge.id, nativeFlow: values[i] };
            break;
          }
        }
      }
    }
    assert.ok(directions.has(-1) && directions.has(1), "Native cases must exercise actual positive and negative mass flow");
    record("native flow reversal rotates actual SVG arrows; direction is not inferred from pump command", { negativeExample });

    const nominal = scenes.get("m3-nominal"), parallel = scenes.get("m3-parallel");
    assert.ok(nominal.series.find(s => s.name === "bypassFlow").values.every(v => Math.abs(v) < 1e-12));
    assert.equal(parallel.diagram.edges.length, nominal.diagram.edges.length + 1);
    assert.ok(parallel.series.find(s => s.name === "bypassFlow").values.some(v => Math.abs(v) > 1e-6));
    await page.locator("#caseSelect").selectOption(nominal.id);
    assert.equal(await page.locator('[data-edge="bypass"]').count(), 0);
    await page.locator("#caseSelect").selectOption(parallel.id);
    assert.equal(await page.locator('[data-edge="bypass"]').count(), 1);
    await checkNative();
    record("added parallel native pipe appears only in the declared topology and uses its own native flow");

    await page.locator("#caseSelect").selectOption(nominal.id);
    await page.locator("#scrub").evaluate(n => { n.value = "23.37"; n.dispatchEvent(new Event("input", { bubbles: true })); });
    current = await checkNative(); assert.equal(current.time, 23.37);
    await page.locator("#play").click();
    await page.waitForFunction(() => window.__domelicaFluid.getState().time > 24);
    current = await checkNative(); assert.equal(current.playing, true);
    await page.locator("#play").click(); current = await checkNative();
    const pausedTime = current.time;
    await page.waitForTimeout(250);
    assert.equal((await checkNative()).time, pausedTime);
    await page.locator("#speed").selectOption("20");
    assert.equal((await checkNative()).speed, 20);
    await page.locator("#play").click();
    await page.waitForFunction(t => window.__domelicaFluid.getState().time > t + 2, pausedTime);
    await page.locator("#play").click(); await checkNative();
    record("Play, Pause, speed changes and scrubbing share one coherent native-sample clock");

    async function clickComponent(id, blankArea = false) {
      const component = page.locator(`[data-node="${id}"]`);
      // Use ordinary scrolling to put the full target below the sticky clock.
      // The following click still has Playwright's normal hit-target checks.
      await component.evaluate(node => node.scrollIntoView({ block: "center", inline: "nearest" }));
      if (blankArea) {
        await component.locator(".node-hit").click({ position: { x: 8, y: 8 } });
      } else {
        await component.click();
      }
      assert.equal((await checkNative()).selectedNode, id);
    }
    for (const id of ["tankA", "pump", "tankB", "valve"]) await clickComponent(id);
    await clickComponent("tankA");
    await clickComponent("valve", true);
    current = await checkNative(); assert.equal(current.selectedNode, "valve");
    assert.match(await page.locator("#inspectValues").textContent(), /valveOpening/);
    await page.locator('[data-node="pump"]').focus();
    await page.keyboard.press("Enter"); current = await checkNative(); assert.equal(current.selectedNode, "pump");
    await page.keyboard.press("Space");
    assert.equal((await checkNative()).playing, true);
    await page.locator("#caseSelect").selectOption("m3-restricted");
    current = await checkNative(); assert.equal(current.playing, false); assert.equal(current.time, current.start);
    await page.evaluate(() => window.__domelicaFluid.seek(window.__domelicaFluid.getState().end));
    assert.equal(await page.locator("#play").textContent(), "Replay");
    await page.locator("#play").click();
    current = await checkNative(); assert.equal(current.playing, true); assert.ok(current.time < 5);
    await page.locator("#play").click();
    record("component inspection, keyboard playback, coherent scenario switching and end replay");

    async function framing() {
      const geometry = await page.evaluate(() => {
        const root = document.querySelector("#schematic"), box = root.getBoundingClientRect();
        return { viewport: { x: box.x, y: box.y, width: box.width, height: box.height },
          nodes: [...root.querySelectorAll(".node")].map(n => { const b = n.getBoundingClientRect(); return { id: n.dataset.node, x: b.x, y: b.y, width: b.width, height: b.height }; }),
          docWidth: document.documentElement.scrollWidth, windowWidth: innerWidth,
          traces: [...document.querySelectorAll("canvas.plot")].map(canvas => {
            const pixels = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
            let colored = 0;
            for (let i = 0; i < pixels.length; i += 4) if (pixels[i + 3] > 128 && pixels[i + 1] > 150 && pixels[i + 2] > 120) colored++;
            return { width: canvas.width, height: canvas.height, coloredPixels: colored };
          }),
        };
      });
      assert.ok(geometry.docWidth <= geometry.windowWidth + 1, "Page overflows horizontally");
      for (const n of geometry.nodes) {
        assert.ok(n.x >= geometry.viewport.x - 1 && n.y >= geometry.viewport.y - 1);
        assert.ok(n.x + n.width <= geometry.viewport.x + geometry.viewport.width + 1);
        assert.ok(n.y + n.height <= geometry.viewport.y + geometry.viewport.height + 1);
      }
      for (const trace of geometry.traces) assert.ok(trace.coloredPixels > 100, "Native trajectory was not drawn");
      return geometry;
    }
    const screenshot = async name => {
      await page.evaluate(() => scrollTo(0, 0));
      await page.evaluate(() => new Promise(requestAnimationFrame));
      await page.screenshot({ path: path.join(output, name), fullPage: true, animations: "disabled" });
      report.screenshots.push(name);
    };
    await page.locator("#caseSelect").selectOption(nominal.id);
    await page.evaluate(() => window.__domelicaFluid.seek(120)); await checkNative();
    const desktop = await framing();
    await screenshot("01-controlled-tanks.png");
    await page.locator("#caseSelect").selectOption(parallel.id);
    await page.evaluate(() => window.__domelicaFluid.seek(120)); await checkNative();
    await framing(); await screenshot("02-parallel-return.png");
    await page.locator("#caseSelect").selectOption(negativeExample.scene);
    await page.evaluate(t => window.__domelicaFluid.seek(t), negativeExample.time); await checkNative();
    await screenshot("03-native-reverse-flow.png");
    record("desktop native schematics and plotted trajectories are visible without clipping", { desktop });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator("#caseSelect").selectOption(parallel.id);
    await page.evaluate(() => window.__domelicaFluid.seek(120));
    await page.waitForFunction(() => window.__domelicaFluid.getState().layout === "mobile");
    current = await checkNative(); assert.equal(current.layout, "mobile");
    for (const id of ["tankA", "pump", "tankB", "valve"]) await clickComponent(id);
    await clickComponent("tankA");
    await clickComponent("valve", true);
    const mobile = await framing();
    await screenshot("04-mobile-fluid-network.png");
    record("390 px mobile topology retains native bindings, full component framing and readable plots", { mobile });

    assert.equal(await page.locator("[data-qualification]").count(), metrics.qualifications.length);
    assert.equal(metrics.qualifications.length, 2);
    for (const q of metrics.qualifications) {
      const card = page.locator(`[data-qualification="${q.id}"]`);
      assert.equal(await card.getAttribute("data-passed"), "true");
      assert.ok((await card.textContent()).includes(q.model));
    }
    assert.match(await page.locator("main").textContent(), /layout is illustrative, not physical geometry/);
    record("reference qualifications and schematic interpretation are explicitly distinguished");

    const unavailable = await browser.newContext({ reducedMotion: "reduce" });
    await unavailable.route(/^https?:\/\//, route => route.abort());
    await unavailable.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(kind, ...args) { return kind === "2d" ? null : original.call(this, kind, ...args); };
    });
    const unavailablePage = await unavailable.newPage();
    await unavailablePage.goto(fileURL, { waitUntil: "load" });
    await unavailablePage.locator("#error").waitFor({ state: "visible" });
    assert.match(await unavailablePage.locator("#error").textContent(), /Canvas2D/);
    assert.equal(await unavailablePage.locator("#play").isDisabled(), true);
    assert.equal(await unavailablePage.evaluate(() => window.__domelicaFluid.getState().available), false);
    await unavailable.close();
    record("unavailable plot rendering reports a visible failure and disables playback");

    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.unexpectedRequests, []);
    record("fluid viewer runs offline without unexpected browser errors or requests");
    report.passed = true;
  } catch (error) {
    report.error = { name: error.name, message: error.message, stack: error.stack };
    if (page) try { await page.screenshot({ path: path.join(output, "failure.png"), fullPage: true }); report.screenshots.push("failure.png"); } catch (_) { /* Preserve first failure. */ }
    console.error("FAIL native fluid viewer:", error.message); process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
    if (browser) await browser.close();
  }
  if (report.passed) console.log(`PASS native fluid viewer: ${report.steps.length} checks; ${report.screenshots.length} screenshots`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
