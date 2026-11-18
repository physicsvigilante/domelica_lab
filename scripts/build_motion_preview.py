#!/usr/bin/env python3
"""Build the two motion demonstrations from complete, verified native outputs."""
import hashlib
import json
import os
from pathlib import Path

from build_preview import add_series
from native_motion_scene import export_scene

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = ROOT / "artifacts"
    runtime_path = output / "three-runtime.js"
    renderer = json.loads((output / "three-runtime.json").read_text())
    package = json.loads((ROOT / "package.json").read_text())
    if (renderer["runtimeSHA256"] != digest(runtime_path)
            or renderer["version"] != package["dependencies"]["three"]
            or renderer["packageLockSHA256"] != digest(ROOT / "package-lock.json")
            or renderer["entrySHA256"] != digest(ROOT / "viewer/three-runtime.js")):
        raise ValueError("Renderer inputs changed; rebuild with npm run build:runtime")
    definitions = json.loads((ROOT / "viewer/motion-experiments.json").read_text())
    metrics_path = output / "m4-metrics.json"
    metrics = json.loads(metrics_path.read_text())
    if metrics.get("passed") is not True:
        raise ValueError("Motion physical acceptance must pass before publishing playback")
    required_sources = {"scripts/verify_m4.py", "scripts/native_m4.mos", "scripts/export_native_csv.py",
        "DomelicaLab/Examples/GrooveSlide3D.mo", "DomelicaLab/Examples/TwoSpringOscillator3D.mo",
        "DomelicaLab/package.mo", "DomelicaLab/package.order", "DomelicaLab/Examples/package.mo",
        "DomelicaLab/Examples/package.order"}
    required_inputs = {"m4-native-toolchain.txt"}
    for definition in definitions:
        prefix = definition["prefix"]
        required_inputs.update(f"{prefix}{suffix}" for suffix in ("_res.mat", "_res.csv", "_visual.xml", ".log"))
        required_inputs.add(f"artifacts/{prefix}-completion.json")
    for field, required in (("sourceSHA256", required_sources), ("inputsSHA256", required_inputs)):
        hashes = metrics.get(field, {})
        if not isinstance(hashes, dict) or not required.issubset(hashes):
            raise ValueError(f"Physical acceptance is missing required {field} bindings")
        for relative, expected in hashes.items():
            path = (ROOT / relative).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file() or digest(path) != expected:
                raise ValueError(f"Physical acceptance is stale for {relative}; run the native verification again")
    scenes, inputs = [], {}
    for definition in definitions:
        prefix = definition["prefix"]
        csv_path, xml_path = ROOT / f"{prefix}_res.csv", ROOT / f"{prefix}_visual.xml"
        scene = export_scene(xml_path, csv_path)
        case = metrics.get("cases", {}).get(definition["id"], {})
        if (case.get("passed") is not True or case.get("model") != definition["model"]
                or case.get("samples") != len(scene["times"])
                or case.get("startTime") != scene["times"][0]
                or case.get("stopTime") != scene["times"][-1]):
            raise ValueError(f"Physical acceptance does not match the native scene {definition['id']}")
        scene.update({key: definition[key] for key in ("id", "title", "description", "model", "camera")})
        add_series(scene, csv_path, definition["series"])
        scenes.append(scene)
        for path in (csv_path, xml_path, ROOT / f"{prefix}_res.mat"):
            if not path.is_file():
                raise ValueError(f"Missing primary native input: {path.name}")
            inputs[path.name] = digest(path)
        print(f"Native motion {scene['id']}: {len(scene['objects'])} objects, {len(scene['times'])} samples")
    toolchain_path = ROOT / "m4-native-toolchain.txt"
    toolchain = dict(line.split("=", 1) for line in toolchain_path.read_text().splitlines() if "=" in line)
    inputs[toolchain_path.name] = digest(toolchain_path)
    inputs["artifacts/m4-metrics.json"] = digest(metrics_path)
    source_paths = sorted((ROOT / "DomelicaLab").rglob("*.mo"))
    source_paths += sorted((ROOT / "DomelicaLab").rglob("package.order"))
    source_paths += sorted((ROOT / "scripts").glob("*.py"))
    source_paths += sorted((ROOT / "scripts").glob("*.mos"))
    source_paths += sorted((ROOT / "scripts").glob("*.cjs"))
    source_paths += [ROOT / name for name in ("viewer/motion-experiments.json", "viewer/motion.template.html",
        "viewer/motion-spring.js", "viewer/three-runtime.js", "package.json", "package-lock.json", "docs/m1-baseline.json")]
    source_paths += sorted((ROOT / "docs").glob("M4_*.md"))
    source_paths += [ROOT / ".github/workflows/motion-modelica.yml"]
    provenance = {
        "revision": os.environ.get("MODEL_SOURCE_REVISION", "local build; inspect source hashes"),
        "checkoutRevision": os.environ.get("CHECKOUT_REVISION", ""),
        "runUrl": os.environ.get("NATIVE_RUN_URL", ""),
        "compiler": toolchain.get("compiler", "Native OpenModelica results; see run log"),
        "toolchain": toolchain, "renderer": renderer,
        "method": "Native MAT read by OpenModelica; native visual XML geometry and complete native sample times",
        "inputsSHA256": inputs,
        "sourceSHA256": {str(p.relative_to(ROOT)): digest(p) for p in source_paths},
        "limitations": [
            "Recorded simulation playback; parameter changes require native simulation again.",
            "Q31 ends at the groove endpoint; no impact, rebound or stop is simulated.",
            "Spring helix tessellation differs from OMEdit; native length, radius, winding count and transforms are preserved.",
            "Spring width and height use OMEdit 1.27.1's radius interpretation.",
            "No CAD, contact detection, spring wire contact or damping is implied by the visual geometry.",
            "OMEdit GUI execution has not been verified by these browser checks.",
            "Compiler container is pinned; the requested MSL package maintenance revision is recorded separately.",
        ],
    }
    payload = {"schema": "domelica.motion-scene.v1", "provenance": provenance, "scenes": scenes, "metrics": metrics}
    template = (ROOT / "viewer/motion.template.html").read_text()
    substitutions = {
        "__THREE_RUNTIME__": runtime_path.read_text(),
        "__SPRING_RENDERER__": (ROOT / "viewer/motion-spring.js").read_text(),
        "__NATIVE_MODEL_DATA__": json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c"),
    }
    for marker, value in substitutions.items():
        if template.count(marker) != 1:
            raise ValueError(f"Expected exactly one {marker}")
        if marker != "__NATIVE_MODEL_DATA__" and "</script" in value.lower():
            raise ValueError("Unsafe inline script delimiter")
        template = template.replace(marker, value)
    preview = output / "motion-preview.html"
    preview.write_text(template)
    (output / "motion-scenes.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
    manifest = {**provenance, "previewSHA256": digest(preview), "scenes": [
        {"id": s["id"], "model": s["model"], "objects": len(s["objects"]), "samples": len(s["times"]),
         "startTime": s["times"][0], "stopTime": s["times"][-1]} for s in scenes]}
    (output / "motion-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS motion playback: {preview} ({preview.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
