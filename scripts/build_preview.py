#!/usr/bin/env python3
"""Build a fully offline HTML playback from verified native OpenModelica CSVs."""
import csv
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def sample(path: Path, columns: tuple[str, ...]) -> list[list[float]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(columns) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing columns in {path}: {sorted(missing)}")
        rows = [[float(row[col]) for col in columns] for row in reader]
    if len(rows) < 50 or any(not math.isfinite(v) for row in rows for v in row):
        raise ValueError(f"Invalid native samples from {path}")
    return rows


def main() -> None:
    # M0's 2D projection is specific to the authored joint orientation and arm geometry.
    # Refuse to build a misleading scene if those parameters are changed in Modelica.
    source = (ROOT / "DomelicaLab/Examples/MotorizedPendulum3D.mo").read_text()
    for pattern in (
        r"armLength\s*=\s*0\.7\b",
        r"widthDirection\s*=\s*\{1,0,0\}",
        r"width\s*=\s*0\.06\b",
        r"n=\{0,0,1\}",
        r"r=\{0,-armLength,0\}",
    ):
        if not re.search(pattern, source):
            raise ValueError(f"Scene geometry no longer matches authored Modelica: {pattern}")
    payload = {
        "kind": "DomelicaLab-M0-native-result-playback",
        "model": "DomelicaLab.Examples.MotorizedPendulum3D",
        "geometry": {"armLengthM": 0.7, "armWidthM": 0.06},
        "signals": ["time_s", "angle_rad", "angularVelocity_rad_s", "motorCurrent_A"],
        "pendulum": sample(
            ROOT / "m0_motorized_pendulum_res.csv",
            ("time", "angle", "angularVelocity", "motorCurrent"),
        ),
        "thermal": sample(
            ROOT / "m0_thermal_step_res.csv",
            ("time", "temperature"),
        ),
    }
    template = (ROOT / "viewer/preview.template.html").read_text(encoding="utf-8")
    marker = "__NATIVE_MODEL_DATA__"
    if template.count(marker) != 1:
        raise ValueError("Viewer payload marker must occur exactly once")
    html = template.replace(marker, json.dumps(payload, separators=(",", ":"), allow_nan=False))
    output = ROOT / "artifacts/browser-preview.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    if output.stat().st_size < 10000:
        raise ValueError("Unexpectedly small browser preview")
    print(f"PASS offline preview built from native traces: {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
