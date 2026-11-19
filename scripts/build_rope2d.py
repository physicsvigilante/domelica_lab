#!/usr/bin/env python3
"""Build self-contained 2D SVG playback from native CSV and declarative rope routes.

OpenModelica owns mass/motion/constraints. rope2d_geometry owns only numeric
tangent/arc display geometry. The HTML owns only pixel projection and styling.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

from rope2d_geometry import evaluate_route

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_route(route):
    require(route.get("schema") == "domelica.rope-routes-2d/v1", "Unknown route contract")
    require(route.get("plane") == "xy", "Only Modelica world XY plane admitted in first slice")
    core = {"schema", "plane", "recording", "attachments", "pulleys",
            "ropes", "bodies", "metrics"}
    require(set(route) in (core, core | {"rigidLinks"}), "Unexpected route fields")
    require(route["ropes"] and route["bodies"] and route["pulleys"], "Empty scene")
    for nodes in (item["nodes"] for item in route["ropes"]):
        for node in nodes:
            if node["kind"] == "attachment":
                require(set(node) == {"kind", "ref"}, "Unexpected attachment node fields")
                require(node["ref"] in route["attachments"], "Unknown attachment")
            elif node["kind"] == "pulley":
                require(set(node) == {"kind", "ref", "incomingSide", "outgoingSide", "wrap"},
                        "Unexpected pulley node fields")
                require(node["ref"] in route["pulleys"], "Unknown pulley")
            else:
                raise ValueError("Unknown rope node kind")
    for body in route["bodies"]:
        require(body["at"] in route["attachments"], "Unknown body attachment")
    for pulley in route["pulleys"].values():
        require(set(pulley) == {"centerColumns", "radiusColumn"}, "Unknown pulley attributes")
    link_ids = set()
    for link in route.get("rigidLinks", []):
        require(set(link) == {"id", "points"}, "Rigid-link fields must be declarative")
        require(isinstance(link["id"], str) and link["id"] and link["id"] not in link_ids,
                "Duplicate or empty rigid link ID")
        link_ids.add(link["id"])
        require(2 <= len(link["points"]) <= 32, "Rigid link requires 2..32 native points")
        for columns in link["points"]:
            require(len(columns) == 2 and all(isinstance(c, str) and c for c in columns),
                    "Rigid-link XY point requires two native columns")


def validate_style(style, body_ids):
    require(style.get("schema") == "domelica.rope-style-2d/v1", "Unknown style contract")
    require(set(style) == {"schema", "background", "foreground", "rope",
                           "pulley", "bodyMarkerRadiusPx", "bodies"}, "Style cannot supply physical geometry")
    require(set(style["rope"]) == {"stroke", "widthPx"}, "Invalid rope style")
    require(set(style["pulley"]) == {"fill", "stroke", "strokeWidthPx"}, "Invalid pulley style")
    require(set(style["bodies"]) == set(body_ids), "Style bodies must match physical bodies")
    for value in [style["background"], style["foreground"], style["rope"]["stroke"],
                  style["pulley"]["fill"], style["pulley"]["stroke"],
                  *[item["fill"] for item in style["bodies"].values()]]:
        require(isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value),
                "Use literal 6-digit hex colors")
    for item in style["bodies"].values():
        require(set(item) == {"fill"}, "Body style cannot contain physical geometry")
    for value in [style["rope"]["widthPx"], style["pulley"]["strokeWidthPx"],
                  style["bodyMarkerRadiusPx"]]:
        require(isinstance(value, (int, float)) and math.isfinite(value) and 0 < value < 50,
                "Invalid decorative pixel width")


def generate(csv_path, native_path, route_path, style_path):
    config, style = read_json(route_path), read_json(style_path)
    validate_route(config)
    validate_style(style, [b["id"] for b in config["bodies"]])
    record = read_json(native_path)
    native = record.get("recording", {})
    require(native.get("kind") == "fresh-native-run", "Require a fresh native recording manifest")
    require(config["recording"]["csv"] == Path(csv_path).name, "CSV/route identity mismatch")
    require(native.get("inputsSHA256", {}).get(Path(csv_path).name) == digest(csv_path),
            "Native input hash mismatch")
    require(any(item["id"] == config["recording"]["experimentId"] and
                item["model"] == config["recording"]["model"]
                for item in record["experiments"]), "Wrong native model for this route")
    require(any(item["id"] == config["recording"]["experimentId"]
                for item in native["completions"]), "No native completion for route")

    required = {"time"}
    for columns in config["attachments"].values():
        require(len(columns) == 2, "Attachment requires two native position columns")
        required.update(columns)
    for entry in config["pulleys"].values():
        require(len(entry["centerColumns"]) == 2, "Pulley requires two center columns")
        required.update(entry["centerColumns"])
        required.add(entry["radiusColumn"])
    for body in config["bodies"]:
        required.add(body["massColumn"])
    for metric in config["metrics"]:
        required.add(metric["column"])
    for link in config.get("rigidLinks", []):
        for columns in link["points"]:
            required.update(columns)

    with Path(csv_path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or [])
        require(not missing, "Missing native geometry columns: " + ", ".join(sorted(missing)))
        raw = list(reader)
    require(2 <= len(raw) <= 10001, "Outside bounded native sample count")

    def number(row, column):
        value = float(row[column])
        require(math.isfinite(value), "Nonfinite native value: " + column)
        return value

    times = []
    frames = []
    bounds = []
    base_lengths = {}
    rigid_reference_lengths = {}
    maxima = {item["id"]: 0 for item in config["ropes"]}
    for row in raw:
        t = number(row, "time")
        require(not times or t >= times[-1], "Nonmonotonic native time")
        times.append(t)
        attachments = {id: [number(row, col) for col in columns]
                       for id, columns in config["attachments"].items()}
        pulleys = {id: {"center": [number(row, col) for col in source["centerColumns"]],
                        "radius": number(row, source["radiusColumn"])}
                   for id, source in config["pulleys"].items()}
        bodies = {b["id"]: {"position": attachments[b["at"]],
                             "mass": number(row, b["massColumn"]),
                             "label": b["label"]}
                  for b in config["bodies"]}
        routes = {}
        for rope in config["ropes"]:
            geom = evaluate_route(rope["nodes"], attachments, pulleys)
            name = rope["id"]
            base_lengths.setdefault(name, geom["length"])
            error = abs(geom["length"] - base_lengths[name])
            maxima[name] = max(maxima[name], error)
            if rope.get("lengthPolicy") == "constant":
                require(error <= rope["tolerance"], "Native rope length constraint violated: " + name)
            routes[name] = {"points": geom["points"], "length": geom["length"],
                            "arcs": [{key: arc[key] for key in ("pulley", "center", "radius", "sweep", "clockwise")}
                                     for arc in geom["arcs"]]}
            bounds.extend(geom["points"])
        for p in pulleys.values():
            c, r = p["center"], p["radius"]
            bounds.extend([(c[0]-r,c[1]-r),(c[0]+r,c[1]+r)])
        # Rigid visual connections are sampled from Modelica, never invented
        # or used to impose mechanical constraints in the geometry layer.
        links = {}
        for link in config.get("rigidLinks", []):
            points = [[number(row, c) for c in columns] for columns in link["points"]]
            lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
            require(all(length > 1e-9 for length in lengths),
                    "Degenerate native rigid-link segment: " + link["id"])
            reference = rigid_reference_lengths.setdefault(link["id"], lengths)
            require(all(abs(a-b) < 1e-6 for a, b in zip(lengths, reference)),
                    "Native rigid link changed length: " + link["id"])
            links[link["id"]] = points
            bounds.extend(points)
        frame = {"pulleys": pulleys, "bodies": bodies, "ropes": routes,
                 "metrics": {metric["id"]: number(row, metric["column"])
                             for metric in config["metrics"]}}
        if links:
            frame["rigidLinks"] = links
        frames.append(frame)
    require(len({item["id"] for item in config["ropes"]}) == len(config["ropes"]), "Duplicate rope IDs")
    require(times[-1] > times[0], "Empty native time interval")
    data = {"schema": "domelica.rope-playback-2d/v1",
            "provenance": {"csvSHA256": digest(csv_path), "routesSHA256": digest(route_path),
                           "styleSHA256": digest(style_path),
                           "sourceCommit": native.get("sourceCommit", ""),
                           "experimentId": config["recording"]["experimentId"]},
            "times": times, "frames": frames, "style": style, "metrics": config["metrics"],
            "bounds": [min(x for x,y in bounds), min(y for x,y in bounds),
                       max(x for x,y in bounds), max(y for x,y in bounds)],
            "maxRopeLengthDrift_m": maxima}
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--native-manifest", type=Path, required=True)
    p.add_argument("--routes", type=Path, default=ROOT/"viewer/m6c-2d-routes.json")
    p.add_argument("--style", type=Path, default=ROOT/"viewer/m6c-2d-style.json")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    data = generate(a.csv, a.native_manifest, a.routes, a.style)
    template = (ROOT/"viewer/rope2d.template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(template.replace("__RECORDING_JSON__", payload), encoding="utf-8")
    print(json.dumps({"passed": True, "html": str(a.output), "sha256": digest(a.output),
                      "samples": len(data["times"]), "maxRopeLengthDrift_m": data["maxRopeLengthDrift_m"],
                      "sourceCommit": data["provenance"]["sourceCommit"]}, indent=2))


if __name__ == "__main__":
    main()
