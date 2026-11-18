#!/usr/bin/env python3
"""Build offline 3D playback from native geometry/results, with input provenance."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path

from native_scene import export_scene

ROOT = Path(__file__).resolve().parent.parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_series(scene: dict, csv_path: Path, definitions: list[dict]) -> None:
    """Attach measured signals without resampling, interpolation or recomputation."""
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = {"time", *(s["name"] for s in definitions)}
        missing = columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{csv_path}: missing plotted signals {sorted(missing)}")
        rows = [{name: float(row[name]) for name in columns} for row in reader]
    if any(not math.isfinite(v) for row in rows for v in row.values()):
        raise ValueError(f"{csv_path}: non-finite plotted signals")
    if [r["time"] for r in rows] != scene["times"]:
        raise ValueError(f"{csv_path}: plotted signals and native scene times differ")
    scene["series"] = [{**s, "values": [row[s["name"]] for row in rows]} for s in definitions]


def main() -> None:
    runtime_path = ROOT / "artifacts/three-runtime.js"
    runtime_info_path = ROOT / "artifacts/three-runtime.json"
    if not runtime_path.is_file() or not runtime_info_path.is_file():
        raise ValueError("Missing offline Three.js runtime; run npm ci and npm run build:runtime")
    runtime = runtime_path.read_text(encoding="utf-8")
    renderer = json.loads(runtime_info_path.read_text())
    package = json.loads((ROOT / "package.json").read_text())
    if (renderer["runtimeSHA256"] != digest(runtime_path)
            or renderer["version"] != package["dependencies"]["three"]
            or renderer["packageLockSHA256"] != digest(ROOT / "package-lock.json")
            or renderer["entrySHA256"] != digest(ROOT / "viewer/three-runtime.js")):
        raise ValueError("Offline renderer inputs changed; rebuild with npm run build:runtime")
    if "</script" in runtime.lower():
        raise ValueError("Renderer contains an unsafe inline-script delimiter")
    definitions = json.loads((ROOT / "viewer/experiments.json").read_text())
    metrics_path = ROOT / "artifacts/m2-metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else None
    scenes, inputs = [], {}
    for definition in definitions:
        prefix = definition["prefix"]
        csv_path = ROOT / f"{prefix}_res.csv"
        xml_path = ROOT / f"{prefix}_visual.xml"
        scene = export_scene(xml_path, csv_path)
        scene.update({k: definition[k] for k in ("id", "title", "description", "model")})
        add_series(scene, csv_path, definition["series"])
        for key in ("scenario", "parameters"):
            if key in definition:
                scene[key] = definition[key]
        scenes.append(scene)
        for path in (csv_path, xml_path, ROOT / f"{prefix}_res.mat"):
            if path.is_file():
                inputs[path.name] = digest(path)
        print(f"Native scene {scene['id']}: {len(scene['objects'])} objects, {len(scene['times'])} samples")

    toolchain_path = ROOT / "native-toolchain.txt"
    toolchain = {}
    if toolchain_path.is_file():
        for line in toolchain_path.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                toolchain[key] = value
        inputs[toolchain_path.name] = digest(toolchain_path)
    sources = sorted((ROOT / "DomelicaLab").rglob("*.mo"))
    sources += sorted((ROOT / "DomelicaLab").rglob("package.order"))
    sources += sorted((ROOT / "scripts").glob("*.py"))
    sources += sorted((ROOT / "scripts").glob("*.mos"))
    sources += sorted((ROOT / "scripts").glob("*.cjs"))
    sources += [ROOT / "viewer/experiments.json", ROOT / "viewer/preview.template.html",
                ROOT / "viewer/three-runtime.js", ROOT / "package.json", ROOT / "package-lock.json"]
    sources += [path for path in (ROOT / "viewer/comparisons.json", ROOT / "viewer/comparison.template.html",
                                 ROOT / "docs/m1-baseline.json")
                if path.is_file()]
    if metrics_path.is_file():
        inputs["artifacts/m2-metrics.json"] = digest(metrics_path)
    provenance = {
        "revision": os.environ.get("MODEL_SOURCE_REVISION", "local build; inspect source hashes"),
        "checkoutRevision": os.environ.get("CHECKOUT_REVISION", ""),
        "runUrl": os.environ.get("NATIVE_RUN_URL", ""),
        "compiler": toolchain.get("compiler", "Native OpenModelica results; see run log"),
        "toolchain": toolchain,
        "renderer": renderer,
        "method": "Native MAT results read through OpenModelica; visxml geometry and sampled transforms",
        "inputsSHA256": inputs,
        "sourceSHA256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "limitations": [
            "Offline sampled playback, not an in-browser Modelica solver.",
            "Primitive subset: boxes, circular cylinders, real cones and spheres.",
            "No CAD assets, surfaces, vectors, advanced expressions or interactive model changes.",
            "Three.js WebGL2 renderer; supported opaque primitives only.",
            "MSL version is requested; its package-manager maintenance revision is not locked.",
        ],
    }
    payload = {"schema": "domelica.native-scene.v1", "provenance": provenance, "scenes": scenes}
    if metrics is not None:
        payload["metrics"] = metrics
    template = (ROOT / "viewer/preview.template.html").read_text(encoding="utf-8")
    marker = "__NATIVE_MODEL_DATA__"
    runtime_marker = "__THREE_RUNTIME__"
    if template.count(marker) != 1 or template.count(runtime_marker) != 1:
        raise ValueError("Viewer data and runtime markers must each occur exactly once")
    encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    output_dir = ROOT / "artifacts"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "native-scenes.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    output = output_dir / "browser-preview.html"
    output.write_text(template.replace(runtime_marker, runtime).replace(marker, encoded), encoding="utf-8")
    manifest = {**provenance, "previewSHA256": digest(output), "scenes": [
        {"id": s["id"], "model": s["model"], "objects": len(s["objects"]),
         "samples": len(s["times"]), "startTime": s["times"][0], "stopTime": s["times"][-1]}
        for s in scenes]}
    (output_dir / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS offline native 3D preview: {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
