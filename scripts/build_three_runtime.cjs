#!/usr/bin/env node
"use strict";

// Build the pinned official library as one offline script. No physics or scene
// data is generated here. The MIT license travels inside the downloadable HTML.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const vm = require("node:vm");
const esbuild = require("esbuild");

const root = path.resolve(__dirname, "..");
const outputDir = path.join(root, "artifacts");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const threeRoot = path.dirname(path.dirname(require.resolve("three")));
const threePackage = JSON.parse(fs.readFileSync(path.join(threeRoot, "package.json"), "utf8"));
const sha256 = content => crypto.createHash("sha256").update(content).digest("hex");

async function main() {
  if (threePackage.version !== manifest.dependencies.three || esbuild.version !== manifest.devDependencies.esbuild) {
    throw new Error("Installed renderer/build versions differ from package.json; run npm ci");
  }
  const license = fs.readFileSync(path.join(threeRoot, "LICENSE"), "utf8");
  if (license.includes("*/") || /<\/script/i.test(license)) throw new Error("Unexpected license delimiters");
  fs.mkdirSync(outputDir, { recursive: true });
  const result = await esbuild.build({
    absWorkingDir: root,
    entryPoints: ["viewer/three-runtime.js"],
    bundle: true,
    format: "iife",
    globalName: "THREE",
    platform: "browser",
    target: "es2022",
    minify: true,
    write: false,
    metafile: true,
    legalComments: "inline",
    banner: { js: `/*! Three.js ${threePackage.version}\n${license}\n*/` },
  });
  if (result.outputFiles.length !== 1) throw new Error("Expected exactly one self-contained renderer script");
  if (Object.values(result.metafile.outputs).some(output => output.imports.length)) {
    throw new Error("Renderer bundle unexpectedly depends on another file");
  }
  const runtime = result.outputFiles[0].text;
  if (/<\/script/i.test(runtime)) throw new Error("Renderer bundle is unsafe to embed in a script tag");
  // Check that the delivered bundle itself exposes the expected revision/API.
  // This evaluates the official library definitions; it does not create WebGL.
  const context = { console };
  vm.runInNewContext(runtime, context, { timeout: 5000 });
  const revision = String(context.THREE?.REVISION);
  if (revision !== threePackage.version.split(".")[1] || typeof context.THREE.WebGLRenderer !== "function") {
    throw new Error("Bundled Three.js revision or WebGLRenderer export is incorrect");
  }
  const metadata = {
    name: "Three.js",
    version: threePackage.version,
    revision,
    backend: "WebGL2",
    runtimeSHA256: sha256(runtime),
    license: "MIT",
    licenseSHA256: sha256(license),
    esbuildVersion: esbuild.version,
    packageLockSHA256: sha256(fs.readFileSync(path.join(root, "package-lock.json"))),
    entrySHA256: sha256(fs.readFileSync(path.join(root, "viewer/three-runtime.js"))),
  };
  fs.writeFileSync(path.join(outputDir, "three-runtime.js"), runtime);
  fs.writeFileSync(path.join(outputDir, "three-runtime.json"), JSON.stringify(metadata, null, 2) + "\n");
  fs.writeFileSync(path.join(outputDir, "three.LICENSE.txt"), license);
  console.log(`PASS offline Three.js r${revision} runtime: ${Buffer.byteLength(runtime)} bytes, ${metadata.runtimeSHA256}`);
}

main().catch(error => { console.error(error); process.exitCode = 1; });
