#!/usr/bin/env python3
"""Package all native frames and vectors in a compact, lossless chat preview.

The inline projection uses the same two generic JS modules as the offline lab.
Gzip compresses bytes only; samples and numeric values are not downsampled.
"""
import argparse
import base64
import gzip
import json
from pathlib import Path


def build(payload_path, template_path, modules_dir, output):
    payload = json.loads(Path(payload_path).read_text())
    preview = {"scenes": [{key: scene[key] for key in (
        "id", "title", "shortTitle", "model", "times", "bounds", "objects", "bodies", "overlays"
    ) if key in scene} for scene in payload["scenes"]]}
    data = json.dumps(preview, separators=(",", ":"), allow_nan=False).encode()
    compressed = gzip.compress(data, compresslevel=9, mtime=0)
    template = Path(template_path).read_text()
    replacements = {
        "__OBSERVATION_LAYER__": (Path(modules_dir) / "observation-layer.js").read_text(),
        "__NATIVE_CANVAS__": (Path(modules_dir) / "native-canvas.js").read_text(),
        "__COMPRESSED_DATA__": base64.b64encode(compressed).decode(),
    }
    for key, value in replacements.items():
        if template.count(key) != 1:
            raise ValueError(f"Expected one {key}")
        template = template.replace(key, value)
    if len(template.encode()) >= 1_000_000:
        raise ValueError("Inline preview exceeds the size budget")
    if json.loads(gzip.decompress(base64.b64decode(replacements["__COMPRESSED_DATA__"]))) != preview:
        raise ValueError("Lossless packing roundtrip failed")
    Path(output).write_text(template)
    return {"bytes": len(template.encode()), "rawPayloadBytes": len(data), "samples": [len(scene["times"]) for scene in preview["scenes"]], "lossless": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("modules", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.payload, args.template, args.modules, args.output)))
