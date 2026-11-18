#!/usr/bin/env python3
"""Render additional native compositions through the unchanged M4 viewer.

No trajectories, shapes or transforms are reconstructed here. Experiment
metadata selects native result columns and optional native observation probes
used by the browser checker. The accepted exporter and template are reused.
"""
import hashlib
import json
import os
from pathlib import Path
import re

from build_preview import add_series
from native_motion_scene import export_scene

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_hashes(hashes, required, label):
    if not isinstance(hashes, dict) or not required.issubset(hashes):
        raise ValueError(f"Physical acceptance is missing required {label} bindings")
    for relative, expected in hashes.items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or digest(path) != expected:
            raise ValueError(f"Physical acceptance is stale for {relative}; run native verification again")


def attach_observations(scene, csv_path, definition):
    """Copy native coordinates; observations never feed rendering or physics."""
    observations = definition["observations"]
    ids = {item["id"]: item for item in scene["objects"]}
    referenced = set(observations["rigidGroup"] + observations["fixedObjects"])
    referenced.update(body["object"] for body in observations["bodies"])
    referenced.update(spring["object"] for spring in observations["springs"])
    if referenced - ids.keys():
        raise ValueError(f"Unknown observed native objects: {sorted(referenced - ids.keys())}")
    vectors = {body["position"] for body in observations["bodies"]}
    for spring in observations["springs"]:
        if ids[spring["object"]]["type"] != "spring":
            raise ValueError(f"Expected native spring geometry for {spring['object']}")
        vectors.update((spring["frameA"], spring["frameB"]))
    columns = sorted(f"{vector}[{i}]" for vector in vectors for i in (1, 2, 3))
    probe_scene = {"times": scene["times"]}
    add_series(probe_scene, csv_path, [{"name": name} for name in columns])
    scene["observations"] = observations
    scene["probes"] = {item["name"]: item["values"] for item in probe_scene["series"]}


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
    definitions = json.loads((ROOT / "viewer/coupled-experiments.json").read_text())
    if not definitions or len({d["id"] for d in definitions}) != len(definitions):
        raise ValueError("Need nonempty experiment definitions with unique identifiers")
    if len({d["prefix"] for d in definitions}) != len(definitions):
        raise ValueError("Native result prefixes must be unique")
    for definition in definitions:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", definition["prefix"]):
            raise ValueError("Invalid native result prefix")
        if not re.fullmatch(r"DomelicaLab\.Examples\.[A-Za-z_][A-Za-z_0-9]*", definition["model"]):
            raise ValueError("Expected a named DomelicaLab example")
    metrics_path = output / "m4b-metrics.json"
    metrics = json.loads(metrics_path.read_text())
    if metrics.get("passed") is not True:
        raise ValueError("Coupled motion physical acceptance must pass before playback is built")
    required_sources = {
        "scripts/verify_m4b.py", "scripts/verify_m4.py", "scripts/native_m4b.mos",
        "scripts/export_native_csv.py", "DomelicaLab/package.mo", "DomelicaLab/package.order",
        "DomelicaLab/Examples/package.mo", "DomelicaLab/Examples/package.order",
        *(d["model"].replace(".", "/") + ".mo" for d in definitions),
    }
    required_inputs = {"m4b-native-toolchain.txt"}
    for definition in definitions:
        prefix = definition["prefix"]
        required_inputs.update(f"{prefix}{suffix}" for suffix in ("_res.mat", "_res.csv", "_visual.xml", ".log"))
        required_inputs.add(f"artifacts/{prefix}-completion.json")
    validate_hashes(metrics.get("sourceSHA256"), required_sources, "sourceSHA256")
    validate_hashes(metrics.get("inputsSHA256"), required_inputs, "inputsSHA256")

    scenes = []
    for definition in definitions:
        prefix = definition["prefix"]
        csv_path, xml_path = ROOT / f"{prefix}_res.csv", ROOT / f"{prefix}_visual.xml"
        scene = export_scene(xml_path, csv_path)
        case = metrics.get("cases", {}).get(definition["id"], {})
        if (case.get("passed") is not True or case.get("model") != definition["model"]
                or case.get("samples") != len(scene["times"])
                or case.get("startTime") != scene["times"][0]
                or case.get("stopTime") != scene["times"][-1]):
            raise ValueError(f"Physical acceptance does not match native scene {definition['id']}")
        scene.update({key: definition[key] for key in ("id", "title", "description", "model", "camera")})
        add_series(scene, csv_path, definition["series"])
        attach_observations(scene, csv_path, definition)
        scenes.append(scene)
        print(f"Native composition {scene['id']}: {len(scene['objects'])} objects, {len(scene['times'])} samples")

    toolchain_path = ROOT / "m4b-native-toolchain.txt"
    toolchain = dict(line.split("=", 1) for line in toolchain_path.read_text().splitlines() if "=" in line)
    # The exact native inputs, logs and completion records are inherited from
    # the verified report, then bound again together with the report itself.
    inputs = dict(metrics["inputsSHA256"])
    inputs["artifacts/m4b-metrics.json"] = digest(metrics_path)
    source_paths = set(metrics["sourceSHA256"])
    source_paths.update({
        "scripts/build_coupled_preview.py", "scripts/check_coupled.cjs", "scripts/build_preview.py",
        "scripts/native_scene.py", "scripts/native_motion_scene.py", "scripts/build_three_runtime.cjs",
        "viewer/coupled-experiments.json", "viewer/motion.template.html", "viewer/motion-spring.js",
        "viewer/three-runtime.js", "package.json", "package-lock.json", "docs/m1-baseline.json",
        "scripts/check_m4b_reuse.py", "docs/m4b-reused-sources.json",
        ".github/workflows/coupled-modelica.yml",
    })
    source_paths.update(str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("M4B_*.md"))
    provenance = {
        "revision": os.environ.get("MODEL_SOURCE_REVISION", "local build; inspect source hashes"),
        "checkoutRevision": os.environ.get("CHECKOUT_REVISION", ""),
        "runUrl": os.environ.get("NATIVE_RUN_URL", ""),
        "compiler": toolchain.get("compiler", "Native OpenModelica results; see run log"),
        "toolchain": toolchain, "renderer": renderer,
        "method": "Native MAT read by OpenModelica; native visual XML geometry and complete native sample times",
        "inputsSHA256": inputs,
        "sourceSHA256": {relative: digest(ROOT / relative) for relative in sorted(source_paths)},
        "limitations": [
            "Recorded simulation playback; changing physical parameters requires a new native simulation.",
            "The rigid ramp depicts the ideal wedge using native boxes; visual shapes do not supply contact laws.",
            "Prismatic constraints maintain contact and fixed orientations; separation, impacts and end stops are excluded.",
            "The un-sprung run ends before leaving the support with nonzero velocities.",
            "Spring motion is ideal and undamped; native dimensions and transforms are preserved with smooth helix tessellation.",
            "Spring width and height follow OMEdit 1.27.1's radius interpretation; wire contact is not modeled.",
            "OMEdit GUI execution has not been verified by the browser checks.",
            "Compiler container is pinned; requested MSL package maintenance revision is recorded separately.",
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
    preview = output / "coupled-preview.html"
    preview.write_text(template)
    (output / "coupled-scenes.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
    manifest = {**provenance, "previewSHA256": digest(preview), "scenes": [
        {"id": s["id"], "model": s["model"], "objects": len(s["objects"]), "samples": len(s["times"]),
         "startTime": s["times"][0], "stopTime": s["times"][-1]} for s in scenes]}
    (output / "coupled-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS coupled playback: {preview} ({preview.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
