#!/usr/bin/env python3
"""Package native fluid results in a declarative, offline engineering schematic.

Diagram coordinates are authored presentation data. Levels, pressures, valve
openings and flow directions come from verified native result columns. This
builder and the browser contain no fluid equations or numerical fluid solver.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")


def validate_diagram(definition, series):
    diagram = definition["diagram"]
    nodes = diagram["nodes"]
    edges = diagram["edges"]
    node_ids = [node["id"] for node in nodes]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError(f"{definition['id']}: duplicate schematic nodes")
    edge_ids = [edge["id"] for edge in edges]
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError(f"{definition['id']}: duplicate schematic edges")
    supported = {"tank", "pump", "valve", "boundary", "junction"}
    for node in nodes:
        if node["type"] not in supported:
            raise ValueError(f"Unsupported schematic symbol: {node['type']}")
        fields = [node[k] for k in ("level", "capacity", "pressure", "opening", "speed", "target") if k in node]
        fields += [r["signal"] for r in node.get("readouts", [])]
        if any(name not in series for name in fields):
            raise ValueError(f"Missing native binding on {definition['id']}/{node['id']}")
        if node["type"] == "tank":
            for key in ("level", "capacity"):
                if key not in node or series[node[key]]["unit"] != "m":
                    raise ValueError("Tank level and height must bind native length columns in metres")
            if any(v <= 0 for v in series[node["capacity"]]["values"]):
                raise ValueError("Tank height must be positive")
    for edge in edges:
        if edge["from"] not in node_ids or edge["to"] not in node_ids:
            raise ValueError("Schematic edge references an unknown node")
        if edge.get("orientation", 1) not in (-1, 1):
            raise ValueError("Flow orientation must be +1 or -1")
        if edge["flow"] not in series or series[edge["flow"]]["unit"] != "kg/s":
            raise ValueError("Schematic edges must bind native mass-flow columns in kg/s")
    for layout_name, layout in diagram["layouts"].items():
        if layout["width"] <= 0 or layout["height"] <= 0:
            raise ValueError("Invalid schematic view box")
        if set(layout["nodes"]) != set(node_ids) or set(layout["edges"]) != set(edge_ids):
            raise ValueError(f"Incomplete {layout_name} topology layout")
        for position in layout["nodes"].values():
            if not all(math.isfinite(v) for v in position):
                raise ValueError("Non-finite schematic coordinate")
        for points in layout["edges"].values():
            if len(points) < 2 or any(len(p) != 2 for p in points):
                raise ValueError("Each schematic edge needs at least two 2D points")
            if not all(math.isfinite(v) for p in points for v in p):
                raise ValueError("Non-finite edge coordinate")
    if "desktop" not in diagram["layouts"] or "mobile" not in diagram["layouts"]:
        raise ValueError("Both desktop and mobile schematic layouts are required")


def main():
    config_path = ROOT / "viewer/fluid-experiments.json"
    template_path = ROOT / "viewer/fluid.template.html"
    metrics_path = ROOT / "artifacts/m3-metrics.json"
    verifier_path = ROOT / "scripts/verify_m3.py"
    config = json.loads(config_path.read_text())
    metrics = json.loads(metrics_path.read_text())
    if metrics.get("schema") != "domelica.fluid-metrics.v1":
        raise ValueError("Missing verified native fluid metrics")
    if metrics.get("verificationScriptSHA256") != digest(verifier_path):
        raise ValueError("Fluid verifier changed after metric verification")
    cases = {case["id"]: case for case in metrics["cases"]}
    if len(cases) != len(metrics["cases"]):
        raise ValueError("Duplicate verified case IDs")
    scenes, inputs = [], {"artifacts/m3-metrics.json": digest(metrics_path)}
    for case in [*metrics["cases"], *metrics.get("qualifications", [])]:
        if case.get("verification", {}).get("passed") is not True:
            raise ValueError(f"Unverified native fluid evidence: {case['id']}")
        for suffix, key in (("_res.csv", "nativeCSV_SHA256"), ("_res.mat", "nativeMAT_SHA256")):
            path = ROOT / (case["prefix"] + suffix)
            if digest(path) != case.get(key):
                raise ValueError(f"Native fluid evidence identity changed: {path.name}")
            inputs[path.name] = digest(path)
    for definition in config["scenes"]:
        case = cases[definition["id"]]
        if case["prefix"] != definition["prefix"] or case["model"] != definition["model"]:
            raise ValueError(f"Schematic and native model identity differ: {definition['id']}")
        if case.get("verification", {}).get("passed") is not True:
            raise ValueError(f"Native fluid verification failed: {definition['id']}")
        for suffix, key in (("_res.csv", "nativeCSV_SHA256"), ("_res.mat", "nativeMAT_SHA256")):
            path = ROOT / (definition["prefix"] + suffix)
            actual = digest(path)
            if actual != case.get(key):
                raise ValueError(f"Verified native input changed: {path.name}")
            inputs[path.name] = actual
        series = {s["name"]: {**s, "values": []} for s in definition["series"]}
        if len(series) != len(definition["series"]):
            raise ValueError("Duplicate native signal bindings")
        times = []
        with (ROOT / (definition["prefix"] + "_res.csv")).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            missing = {"time", *series} - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{definition['id']}: missing columns {sorted(missing)}")
            for row in reader:
                times.append(float(row["time"]))
                for name in series:
                    series[name]["values"].append(float(row[name]))
        if len(times) < 2 or times[-1] <= times[0] or any(b < a for a, b in zip(times, times[1:])):
            raise ValueError("Native result times must be non-decreasing and span a nonempty interval")
        if not all(math.isfinite(v) for v in times):
            raise ValueError("Non-finite native time")
        if not all(math.isfinite(v) for s in series.values() for v in s["values"]):
            raise ValueError("Non-finite native display signal")
        for plot in definition["plots"]:
            if not plot["signals"] or any(name not in series for name in plot["signals"]):
                raise ValueError("Plot references an absent native signal")
            if any(series[name]["unit"] != plot["unit"] for name in plot["signals"]):
                raise ValueError("A plot must use one explicitly declared native unit")
        for readout in definition["readouts"]:
            if readout["signal"] not in series:
                raise ValueError("Readout references an absent native signal")
        for metric in definition.get("measurements", []):
            value = case["metrics"][metric["name"]]
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Displayed metric must be a finite verified value")
        validate_diagram(definition, series)
        scenes.append({**definition, "times": times, "series": list(series.values()),
                       "verifiedCase": case})
        print(f"Native fluid schematic {definition['id']}: {len(times)} samples; "
              f"{len(definition['diagram']['nodes'])} nodes; {len(definition['diagram']['edges'])} flow paths")
    ids = [scene["id"] for scene in scenes]
    if not ids or len(set(ids)) != len(ids) or config["defaultScene"] not in ids:
        raise ValueError("Invalid schematic scene selection")
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
    sources += [ROOT / name for name in ("scripts/native_m3.mos", "scripts/export_native_csv.py", "scripts/verify_csv.py",
                "scripts/verify_m3.py", "scripts/build_fluid_preview.py", "scripts/check_fluid.cjs",
                "viewer/fluid.template.html", "viewer/fluid-experiments.json")]
    provenance = {
        "revision": os.environ.get("MODEL_SOURCE_REVISION", "local build; inspect source hashes"),
        "checkoutRevision": os.environ.get("CHECKOUT_REVISION", ""),
        "runUrl": os.environ.get("NATIVE_RUN_URL", ""),
        "compiler": toolchain.get("compiler", "Native OpenModelica results; see run log"),
        "toolchain": toolchain,
        "inputsSHA256": inputs,
        "sourceSHA256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "method": "Native MAT results read through OpenModelica; authored schematic topology bound to native result columns",
        "limitations": [
            "Diagram coordinates are authored engineering layout, not physical 3D geometry or pipe dimensions.",
            "Offline native-sample playback; selecting a scenario does not run a new simulation.",
            "Tank fill shows native level divided by native tank height; any out-of-range level is reported.",
            "Arrows show the sign of native mass flow; arrow length is not a flow-magnitude scale.",
            "MSL version is requested; its package-manager maintenance revision is not locked.",
        ],
    }
    payload = {"schema": "domelica.fluid-schematic.v1", "config": {
        k: v for k, v in config.items() if k != "scenes"}, "scenes": scenes,
        "metrics": metrics, "provenance": provenance}
    template = template_path.read_text(encoding="utf-8")
    if template.count("__FLUID_DATA__") != 1:
        raise ValueError("Fluid payload marker must occur exactly once")
    output_dir = ROOT / "artifacts"
    output_dir.mkdir(exist_ok=True)
    data_path = output_dir / "fluid-scenes.json"
    data_path.write_text(encode(payload) + "\n", encoding="utf-8")
    output = output_dir / "fluid-preview.html"
    output.write_text(template.replace("__FLUID_DATA__", encode(payload)), encoding="utf-8")
    manifest = {**provenance, "previewSHA256": digest(output), "dataSHA256": digest(data_path),
                "sceneIds": ids, "defaultScene": config["defaultScene"], "bytes": output.stat().st_size}
    (output_dir / "fluid-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS offline fluid schematic: {len(scenes)} cases; {output.stat().st_size} bytes; {manifest['previewSHA256']}")


if __name__ == "__main__":
    main()
