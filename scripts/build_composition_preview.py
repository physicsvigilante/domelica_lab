#!/usr/bin/env python3
"""Package M4C native results with the accepted, unchanged motion viewer.

New metadata names observations used only by browser acceptance. The ordinary
and spring exporters still provide every rendered shape, transform and sample.
"""
import json
import math
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from build_coupled_preview import attach_observations, digest, validate_hashes
from build_preview import add_series
from native_motion_scene import export_scene
import native_scene

ROOT = Path(__file__).resolve().parent.parent


def attach_composition_observations(scene, csv_path, xml_path, definition):
    """Copy native evidence; none of these observations drives the meshes."""
    observations = definition["observations"]
    objects = {item["id"]: item for item in scene["objects"]}
    if observations["rigidGroup"]:
        raise ValueError("M4C uses native segment probes, not a translated rigid-group assumption")
    attach_observations(scene, csv_path, definition)
    roles = [body["role"] for body in observations["bodies"]]
    if not roles or len(roles) != len(set(roles)):
        raise ValueError("Need distinct native body-observation roles")
    for body in observations["bodies"]:
        point = body["localPoint"]
        if len(point) != 3 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in point):
            raise ValueError(f"Invalid canonical observation point for {body['object']}")
        if objects[body["object"]]["type"] == "spring":
            raise ValueError("Observe spring attachments using native spring frames")
    columns = set()
    for segment in observations.get("segments", []):
        if segment["object"] not in objects or objects[segment["object"]]["type"] == "spring":
            raise ValueError(f"Invalid native segment object {segment['object']}")
        for key in ("localPointA", "localPointB"):
            if len(segment[key]) != 3 or not all(math.isfinite(v) for v in segment[key]):
                raise ValueError(f"Invalid canonical segment point {key}")
        for vector in (segment["frameA"], segment["frameB"]):
            columns.update(f"{vector}[{k}]" for k in (1, 2, 3))
    if observations["pick"]["object"] not in objects:
        raise ValueError("Picking observation names an unknown native object")
    if len(observations["checkTimes"]) != 4 or len(set(observations["checkTimes"])) != 4:
        raise ValueError("Choose four distinct times for actual rendered-mesh checks")
    if not scene["times"][0] < observations["screenshotTime"] <= scene["times"][-1]:
        raise ValueError("Screenshot must show a non-initial native sample")
    if columns:
        probes = {"times": scene["times"]}
        add_series(probes, csv_path, [{"name": name} for name in sorted(columns)])
        scene["probes"].update({item["name"]: item["values"] for item in probes["series"]})

    # Retain only native dimensions needed for geometry checks, not a duplicate
    # of all position/orientation columns. Native physical-frame probes above
    # independently constrain the new moving bodies, rod and spring attachments.
    # The accepted leaf parser reads the spring width/height radius convention.
    counts = {"length": 1, "width": 1, "height": 1, "extra": 1}
    references, definitions = {}, []
    for element in ET.parse(xml_path).getroot():
        ident = element.findtext("ident").strip()
        fields = {name: native_scene._field(element, name, size, ident, references)
                  for name, size in counts.items()}
        definitions.append((ident, element.findtext("type").strip(), fields))
    signals = native_scene._read_csv(csv_path, references)
    if signals["time"] != scene["times"]:
        raise ValueError("Native observation fields and rendered geometry have different sample times")
    scene["nativeDimensions"] = [{
        "id": ident, "type": kind,
        "fields": {name: native_scene._compress([
            [value if tag == "const" else signals[value][i] for tag, value in expression]
            for i in range(len(scene["times"]))]) for name, expression in fields.items()},
    } for ident, kind, fields in definitions]


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
    definitions = json.loads((ROOT / "viewer/composition-experiments.json").read_text())
    if not definitions or len({d["id"] for d in definitions}) != len(definitions):
        raise ValueError("Need nonempty experiment definitions with unique identifiers")
    if len({d["prefix"] for d in definitions}) != len(definitions):
        raise ValueError("Native result prefixes must be unique")
    for definition in definitions:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", definition["id"]):
            raise ValueError("Invalid experiment identifier")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", definition["prefix"]):
            raise ValueError("Invalid native result prefix")
        if not re.fullmatch(r"DomelicaLab\.Examples\.[A-Za-z_][A-Za-z_0-9]*", definition["model"]):
            raise ValueError("Expected a named DomelicaLab example")
    metrics_path = output / "m4c-metrics.json"
    metrics = json.loads(metrics_path.read_text())
    if metrics.get("passed") is not True:
        raise ValueError("M4C physical acceptance must pass before playback is built")
    required_sources = {
        "scripts/verify_m4c.py", "scripts/verify_m4c_cart.py", "scripts/verify_m4c_pdf.py",
        "scripts/verify_m4.py", "scripts/native_m4c.mos", "scripts/export_native_csv.py",
        "DomelicaLab/package.mo", "DomelicaLab/package.order",
        "DomelicaLab/Examples/package.mo", "DomelicaLab/Examples/package.order",
        *(d["model"].replace(".", "/") + ".mo" for d in definitions),
    }
    required_inputs = {"m4c-native-toolchain.txt"}
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
        attach_composition_observations(scene, csv_path, xml_path, definition)
        scenes.append(scene)
        print(f"Native composition {scene['id']}: {len(scene['objects'])} objects, {len(scene['times'])} samples")

    toolchain = dict(line.split("=", 1) for line in (ROOT / "m4c-native-toolchain.txt").read_text().splitlines() if "=" in line)
    inputs = dict(metrics["inputsSHA256"])
    inputs["artifacts/m4c-metrics.json"] = digest(metrics_path)
    source_paths = set(metrics["sourceSHA256"])
    source_paths.update({
        "scripts/build_composition_preview.py", "scripts/check_composition.cjs",
        "scripts/build_coupled_preview.py", "scripts/build_preview.py", "scripts/native_scene.py",
        "scripts/native_motion_scene.py", "scripts/build_three_runtime.cjs",
        "viewer/composition-experiments.json", "viewer/motion.template.html", "viewer/motion-spring.js",
        "viewer/three-runtime.js", "package.json", "package-lock.json", "docs/m1-baseline.json",
        "scripts/check_m4c_reuse.py", "docs/m4c-reused-sources.json", ".github/workflows/composition-modelica.yml",
    })
    source_paths.update(str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("M4C_*.md"))
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
            "New Modelica assemblies and observation metadata reuse the accepted native exporter and renderer unchanged.",
            "The pendulum has a massless rigid rod and point mass; its sphere depicts position, not rotational inertia.",
            "The released chain starts immediately after the thread is cut; no thread-fracture or contact model is added.",
            "Joints and springs are ideal; damping, impacts, material deformation and wire contact are excluded.",
            "Spring width and height follow OMEdit 1.27.1's coil-radius and wire-radius interpretation.",
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
    preview = output / "composition-preview.html"
    preview.write_text(template)
    (output / "composition-scenes.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
    manifest = {**provenance, "previewSHA256": digest(preview), "scenes": [
        {"id": s["id"], "model": s["model"], "objects": len(s["objects"]), "samples": len(s["times"]),
         "startTime": s["times"][0], "stopTime": s["times"][-1]} for s in scenes]}
    (output / "composition-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS composition playback: {preview} ({preview.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
