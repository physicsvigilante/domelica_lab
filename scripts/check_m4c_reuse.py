#!/usr/bin/env python3
"""Reject changes to the accepted physics, native data path, and renderer."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / "docs/m4c-reused-sources.json").read_text())
    failures = []
    for name, expected in manifest["immutableSourcesSHA256"].items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(name)
    if failures:
        raise AssertionError("M4C changed accepted sources: " + ", ".join(failures))
    print(f"PASS accepted-source reuse: {len(manifest['immutableSourcesSHA256'])} files; "
          "existing models, native readers/exporters, and renderers are unchanged")


if __name__ == "__main__":
    main()
