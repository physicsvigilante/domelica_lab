#!/usr/bin/env python3
"""Build an offline observation lab from a manifest and native CSV/XML results.

This is a packaging command, never a physics solver. Native geometry comes from
the unchanged repository exporters. Model-specific knowledge lives in JSON.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

from native_motion_scene import export_scene
from observation_data import export_observations

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_manifest(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "domelica.experiments/v1":
        raise ValueError("Expected domelica.experiments/v1")
    experiments = value.get("experiments", [])
    if not experiments:
        raise ValueError("At least one experiment is required")
    for key in ("id", "prefix"):
        values = [experiment[key] for experiment in experiments]
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate experiment {key}")
    for experiment in experiments:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", experiment["id"]):
            raise ValueError("Invalid experiment id")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", experiment["prefix"]):
            raise ValueError("Invalid native result prefix")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)+", experiment["model"]):
            raise ValueError("Invalid qualified Modelica model name")
        simulation = experiment["simulation"]
        start, stop, tolerance = (float(simulation[k]) for k in ("startTime", "stopTime", "tolerance"))
        intervals = simulation["numberOfIntervals"]
        if (not all(math.isfinite(x) for x in (start, stop, tolerance)) or stop <= start
                or tolerance <= 0 or type(intervals) is not int or intervals < 1):
            raise ValueError("Invalid simulation interval, sample count or tolerance")
        if not re.fullmatch(r"[A-Za-z][A-Za-z_0-9]*", simulation.get("method", "dassl")):
            raise ValueError("Invalid solver name")
    return value


def checked_path(base, relative):
    """Resolve a manifest file under its declared root, rejecting traversal."""
    base = Path(base).resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"Manifest path escapes its root: {relative}")
    return path


def attach_series(scene, csv_path, definitions):
    columns = {definition["name"]: [] for definition in definitions}
    times = []
    with Path(csv_path).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            times.append(float(row["time"]))
            for name, values in columns.items():
                value = float(row[name])
                if not math.isfinite(value):
                    raise ValueError(f"Nonfinite chart signal {name}")
                values.append(value)
    if times != scene["times"]:
        raise ValueError("Chart signals and geometry have different native sample times")
    scene["series"] = [{**definition, "values": columns[definition["name"]]} for definition in definitions]


def build(manifest_path, results_dir, output_path):
    manifest_path = Path(manifest_path).resolve()
    results_dir, output_path = Path(results_dir).resolve(), Path(output_path).resolve()
    manifest = read_manifest(manifest_path)
    recording = manifest.get("recording")
    if not recording or not recording.get("inputsSHA256"):
        raise ValueError("A recording with bound native input hashes is required; use a completed run manifest")
    model_root = checked_path(ROOT, manifest["modelica"]["package"]).parent
    for relative, expected in recording.get("modelSourceSHA256", {}).items():
        if digest(checked_path(model_root, relative)) != expected:
            raise ValueError(f"Modelica source differs from the native recording: {relative}")
    for relative, expected in recording["inputsSHA256"].items():
        path = checked_path(results_dir, relative)
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Native recording hash mismatch: {relative}")
    observation_path = checked_path(manifest_path.parent, manifest["observationManifest"])
    observations = export_observations(observation_path, results_dir)
    by_id = {scene["id"]: scene for scene in observations["scenes"]}
    if set(by_id) != {experiment["id"] for experiment in manifest["experiments"]}:
        raise ValueError("Experiment and observation manifest IDs must match exactly")
    scenes = []
    consumed_inputs = {}
    for definition in manifest["experiments"]:
        prefix = definition["prefix"]
        csv_path = checked_path(results_dir, prefix + "_res.csv")
        xml_path = checked_path(results_dir, prefix + "_visual.xml")
        for path in (csv_path, xml_path):
            relative = str(path.relative_to(results_dir))
            if relative not in recording["inputsSHA256"]:
                raise ValueError(f"Consumed native input is not bound to the recording: {relative}")
            consumed_inputs[relative] = digest(path)
        scene = export_scene(xml_path, csv_path)
        overlay_scene = by_id[definition["id"]]
        if overlay_scene["times"] != scene["times"] or overlay_scene["model"] != definition["model"]:
            raise ValueError("Native geometry and observations do not describe the same recording")
        if overlay_scene["provenance"]["csvSha256"] != digest(csv_path):
            raise ValueError("Observation manifest selected a different native CSV")
        simulation = definition["simulation"]
        if not (math.isclose(scene["times"][0], simulation["startTime"], abs_tol=1e-12)
                and math.isclose(scene["times"][-1], simulation["stopTime"], abs_tol=1e-12)):
            raise ValueError("Recording does not reach the declared simulation interval")
        scene.update({key: definition[key] for key in ("id", "model", "title", "description", "camera")})
        if "shortTitle" in definition:
            scene["shortTitle"] = definition["shortTitle"]
        scene["bodies"] = overlay_scene["bodies"]
        scene["overlays"] = overlay_scene["overlays"]
        scene["observationNotes"] = overlay_scene.get("notes", [])
        scene["observationProvenance"] = overlay_scene["provenance"]
        native_object_ids = {obj["id"] for obj in scene["objects"]}
        for body in scene["bodies"]:
            if not set(body.get("objectIds", [])).issubset(native_object_ids):
                raise ValueError(f"Body {body['id']} names an unknown native object")
        attach_series(scene, csv_path, definition.get("series", []))
        scenes.append(scene)
    runtime_path = checked_path(ROOT, manifest["renderer"]["runtime"])
    if digest(runtime_path) != manifest["renderer"]["sha256"]:
        raise ValueError("The bundled Three.js runtime hash changed")
    source_files = [*sorted((ROOT / "scripts").glob("*.py")),
                    *sorted((ROOT / "viewer").glob("*.js")),
                    ROOT / "viewer/observation.template.html", manifest_path, observation_path]
    provenance = {
        "revision": recording.get("sourceCommit", ""),
        "compiler": recording.get("compiler", "Native OpenModelica recording"),
        "runUrl": recording.get("runUrl", ""),
        "recording": recording,
        "newSimulationDuringBuild": False,
        "method": "Native CSV/XML playback; exact sampled positions and vectors; no browser physics solver.",
        "inputsSHA256": consumed_inputs,
        "builderSourceSHA256": {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name: digest(path)
                                for path in source_files},
        "renderer": {"name": "Three.js", "version": "0.187.0", "runtimeSHA256": digest(runtime_path),
                     "fallback": "Canvas 2D XY projection of native geometry and vectors"},
        "limitations": [
            "This build replays the named recording. Physical parameter changes require a new native simulation.",
            "Observation ownership, signs and reference points are explicitly authored metadata.",
            "Gravity arrows are derived from native mass and uniform-gravity parameters, not standalone native force columns.",
            "A torque arrow denotes an axial vector with right-hand-rule direction, not a linear force.",
            "The XY fallback marks out-of-plane vector components separately; it is not a 3D view.",
            "No additional numerical solver validation was performed for this presentation change.",
        ],
    }
    payload = {"schema": "domelica.observation-lab/v1", "provenance": provenance, "scenes": scenes}
    template = (ROOT / "viewer/observation.template.html").read_text(encoding="utf-8")
    substitutions = {
        "__THREE_RUNTIME__": runtime_path.read_text(encoding="utf-8"),
        "__SPRING_RENDERER__": (ROOT / "viewer/motion-spring.js").read_text(encoding="utf-8"),
        "__OBSERVATION_LAYER__": (ROOT / "viewer/observation-layer.js").read_text(encoding="utf-8"),
        "__NATIVE_CANVAS__": (ROOT / "viewer/native-canvas.js").read_text(encoding="utf-8"),
        "__NATIVE_MODEL_DATA__": json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c"),
    }
    for marker, value in substitutions.items():
        if template.count(marker) != 1:
            raise ValueError(f"Expected one template marker {marker}")
        if marker != "__NATIVE_MODEL_DATA__" and "</script" in value.lower():
            raise ValueError("Unsafe inline script delimiter")
        template = template.replace(marker, value)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template, encoding="utf-8")
    payload_path = output_path.with_suffix(".json")
    payload_path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    report = {
        "html": output_path.name, "htmlSHA256": digest(output_path),
        "payload": payload_path.name, "payloadSHA256": digest(payload_path),
        "newSimulationDuringBuild": False,
        "checks": "Native input hashes; finite mapped values; declared units/body references; identical timestamps; simulation end time.",
        "scenes": [{"id": scene["id"], "samples": len(scene["times"]), "objects": len(scene["objects"]),
                    "overlays": len(scene["overlays"])} for scene in scenes],
        "provenance": provenance,
    }
    output_path.with_name(output_path.stem + "_build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "viewer/observation-experiments.json")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/domelica_observation_lab.html")
    args = parser.parse_args()
    report = build(args.manifest, args.results_dir, args.output)
    print(json.dumps({key: report[key] for key in ("html", "htmlSHA256", "newSimulationDuringBuild", "scenes")}, indent=2))


if __name__ == "__main__":
    main()
