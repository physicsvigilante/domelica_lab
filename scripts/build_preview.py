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
    definitions = json.loads((ROOT / "viewer/experiments.json").read_text())
    scenes, inputs = [], {}
    for definition in definitions:
        prefix = definition["prefix"]
        csv_path = ROOT / f"{prefix}_res.csv"
        xml_path = ROOT / f"{prefix}_visual.xml"
        scene = export_scene(xml_path, csv_path)
        scene.update({k: definition[k] for k in ("id", "title", "description", "model")})
        add_series(scene, csv_path, definition["series"])
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
    sources += [ROOT / "viewer/experiments.json", ROOT / "viewer/preview.template.html"]
    provenance = {
        "revision": os.environ.get("MODEL_SOURCE_REVISION", "local build; inspect source hashes"),
        "checkoutRevision": os.environ.get("CHECKOUT_REVISION", ""),
        "runUrl": os.environ.get("NATIVE_RUN_URL", ""),
        "compiler": toolchain.get("compiler", "Native OpenModelica results; see run log"),
        "toolchain": toolchain,
        "method": "Native MAT results read through OpenModelica; visxml geometry and sampled transforms",
        "inputsSHA256": inputs,
        "sourceSHA256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "limitations": [
            "Offline sampled playback, not an in-browser Modelica solver.",
            "Primitive subset: boxes, circular cylinders, real cones and spheres.",
            "No CAD assets, surfaces, vectors, advanced expressions or interactive model changes.",
            "Shaded polygon renderer can show ordering artifacts at intersecting surfaces.",
            "MSL version is requested; its package-manager maintenance revision is not locked.",
        ],
    }
    payload = {"schema": "domelica.native-scene.v1", "provenance": provenance, "scenes": scenes}
    template = (ROOT / "viewer/preview.template.html").read_text(encoding="utf-8")
    marker = "__NATIVE_MODEL_DATA__"
    if template.count(marker) != 1:
        raise ValueError("Viewer payload marker must occur exactly once")
    encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    output_dir = ROOT / "artifacts"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / "browser-preview.html"
    output.write_text(template.replace(marker, encoded), encoding="utf-8")
    manifest = {**provenance, "previewSHA256": digest(output), "scenes": [
        {"id": s["id"], "model": s["model"], "objects": len(s["objects"]),
         "samples": len(s["times"]), "startTime": s["times"][0], "stopTime": s["times"][-1]}
        for s in scenes]}
    (output_dir / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS offline native 3D preview: {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
