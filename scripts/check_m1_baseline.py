#!/usr/bin/env python3
"""Require M2 to reuse the accepted M1 physics and native renderer unchanged."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    baseline = json.loads((root / "docs/m1-baseline.json").read_text())
    failures = []
    for name, expected in baseline["immutableSourcesSHA256"].items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(name)
    if failures:
        raise AssertionError("M2 changed accepted baseline sources: " + ", ".join(failures))
    print(f"PASS M1 baseline {baseline['revision'][:12]}: "
          f"{len(baseline['immutableSourcesSHA256'])} unchanged sources; "
          "new Modelica compositions reuse the scene exporter and Three.js viewer")


if __name__ == "__main__":
    main()
