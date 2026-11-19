#!/usr/bin/env python3
"""Export explicitly mapped native observations; never integrate dynamics.

The manifest specifies component ownership, signs, reference points and units.
Only a small declarative operation set is accepted. Unknown operations, missing
columns, nonfinite data and mismatched units fail rather than producing guesses.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path


SCHEMA = "domelica.observations/v1"
OUTPUT_SCHEMA = "domelica.observation-scenes/v1"
UNITS = {"force": "N", "velocity": "m/s", "acceleration": "m/s^2", "torque": "N*m"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def columns_for(expression):
    """List source columns used by a supported vector expression."""
    op = expression.get("op")
    if op == "columns":
        columns = expression["columns"]
        if len(columns) != 3:
            raise ValueError("A vector must name exactly three columns")
        return list(columns)
    if op == "constant":
        if len(expression["value"]) != 3:
            raise ValueError("A constant vector must have three components")
        return []
    if op == "resolve1":
        if len(expression["vectorColumns"]) != 3:
            raise ValueError("resolve1 needs three local vector columns")
        prefix = expression["matrixPrefix"]
        return list(expression["vectorColumns"]) + [
            f"{prefix}[{r},{c}]" for r in range(1, 4) for c in range(1, 4)
        ]
    if op == "uniformGravity":
        if len(expression["directionColumns"]) != 3:
            raise ValueError("Uniform gravity needs three direction columns")
        return [expression["massColumn"], expression["gColumn"]] + list(expression["directionColumns"])
    raise ValueError(f"Unsupported vector operation {op!r}")


def evaluate(expression, row):
    """Return a world-resolved vector. No solver, differentiation or time stepping."""
    op = expression["op"]
    if op == "columns":
        result = [row[name] for name in expression["columns"]]
    elif op == "constant":
        result = [float(value) for value in expression["value"]]
    elif op == "resolve1":
        # Modelica MultiBody R.T maps world -> local. resolve1 therefore uses
        # transpose(T), NOT T. Sign -1 changes force INTO a spring to its force
        # ON the receiving body at that same connection.
        local = [row[name] for name in expression["vectorColumns"]]
        prefix = expression["matrixPrefix"]
        sign = float(expression.get("sign", 1))
        result = [sign * sum(row[f"{prefix}[{j+1},{i+1}]"] * local[j] for j in range(3)) for i in range(3)]
    elif op == "uniformGravity":
        direction = [row[name] for name in expression["directionColumns"]]
        norm = math.sqrt(sum(value * value for value in direction))
        if norm == 0:
            raise ValueError("Uniform gravity direction has zero length")
        magnitude = row[expression["massColumn"]] * row[expression["gColumn"]]
        result = [magnitude * value / norm for value in direction]
    else:
        raise ValueError(f"Unsupported vector operation {op!r}")
    if not all(math.isfinite(value) for value in result):
        raise ValueError("An observation evaluated to a nonfinite vector")
    return result


def export_scene(scene, csv_root):
    path = Path(csv_root) / scene["csv"]
    overlays = []
    required = {"time"}
    body_ids = {body["id"] for body in scene["bodies"]}
    if len(body_ids) != len(scene["bodies"]):
        raise ValueError("Body IDs must be unique within a scene")
    seen_ids = set()
    for definition in scene["overlays"]:
        if definition["id"] in seen_ids:
            raise ValueError(f"Duplicate overlay id: {definition['id']}")
        seen_ids.add(definition["id"])
        if definition["body"] not in body_ids:
            raise ValueError(f"Unknown receiving body: {definition['body']}")
        if UNITS.get(definition["kind"]) != definition["unit"]:
            raise ValueError(f"Unexpected kind/unit pair: {definition['kind']}/{definition['unit']}")
        if definition["frame"] != "world":
            raise ValueError("Exported vectors must be world-resolved")
        if definition["source"]["mode"] not in {"native", "native-transform", "derived"}:
            raise ValueError("Unknown source mode")
        permitted_operations = {
            "native": {"columns"},
            "native-transform": {"resolve1"},
            "derived": {"uniformGravity", "constant"},
        }
        if definition["vector"].get("op") not in permitted_operations[definition["source"]["mode"]]:
            raise ValueError(f"Source mode does not describe its operation: {definition['id']}")
        if not definition.get("signConvention"):
            raise ValueError("A sign convention is required")
        position_expression = {"op": "columns", "columns": definition["point"]["columns"]}
        position_columns = columns_for(position_expression)
        vector_columns = columns_for(definition["vector"])
        if set(definition["source"]["columns"]) != set(vector_columns):
            raise ValueError(f"Source column declaration disagrees with vector expression: {definition['id']}")
        required.update(position_columns)
        required.update(vector_columns)
        overlay = {key: copy.deepcopy(value) for key, value in definition.items() if key != "vector"}
        overlay["positions"] = []
        overlay["vectors"] = []
        overlays.append(overlay)
    times = []
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames or []
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate native CSV headers: {path.name}")
        missing = required - set(names)
        if missing:
            raise ValueError(f"Missing native columns in {path.name}: {sorted(missing)}")
        for row_number, text_row in enumerate(reader, start=2):
            try:
                row = {name: float(text_row[name]) for name in required}
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid native numeric value on {path.name}:{row_number}") from error
            if not all(math.isfinite(value) for value in row.values()):
                raise ValueError(f"Nonfinite native value on {path.name}:{row_number}")
            time = row["time"]
            if times and time < times[-1]:
                raise ValueError(f"Native timestamps decrease on {path.name}:{row_number}")
            times.append(time)  # Retain duplicate timestamps; they may encode events.
            for definition, overlay in zip(scene["overlays"], overlays):
                overlay["positions"].append([row[name] for name in definition["point"]["columns"]])
                overlay["vectors"].append(evaluate(definition["vector"], row))
    if len(times) < 2:
        raise ValueError("At least two native samples are required")
    return {
        "id": scene["id"], "model": scene["model"], "times": times,
        "bodies": copy.deepcopy(scene["bodies"]), "overlays": overlays,
        "notes": copy.deepcopy(scene.get("notes", [])),
        "provenance": {
            "csv": path.name, "csvSha256": sha256(path),
            "sampleCount": len(times),
            "duplicateTimestamps": sum(a == b for a, b in zip(times, times[1:])),
            "sourceColumns": sorted(required),
            "newSimulationDuringExport": False,
            "description": "Observation export from the recorded native OpenModelica run. No equations of motion are solved by this exporter.",
        },
    }


def export_observations(manifest_path, csv_root, output_path=None):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA:
        raise ValueError(f"Expected {SCHEMA}")
    scene_ids = [scene["id"] for scene in manifest["scenes"]]
    if len(scene_ids) != len(set(scene_ids)):
        raise ValueError("Scene IDs must be unique")
    result = {
        "schema": OUTPUT_SCHEMA,
        "provenance": {**manifest.get("provenance", {}), "manifestSha256": sha256(manifest_path), "newSimulationDuringExport": False},
        "scenes": [export_scene(scene, csv_root) for scene in manifest["scenes"]],
    }
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("csv_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = export_observations(args.manifest, args.csv_root, args.output)
    print(json.dumps({"output": str(args.output), "scenes": [{"id": item["id"], "samples": len(item["times"]), "overlays": len(item["overlays"])} for item in result["scenes"]]}))


if __name__ == "__main__":
    main()
