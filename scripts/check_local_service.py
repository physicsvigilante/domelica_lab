#!/usr/bin/env python3
"""Focused end-to-end HTTP test against the actual compiler-free runtime.

Runs exactly one additional non-preset numerical request, checks its native
provenance and packaged viewer, and exercises refusal of unsafe inputs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import threading
import urllib.error
import urllib.request

from compiled_model import verify_bundle
from serve_compiled_lab import LocalLab


def request(base, path, value=None, headers=None):
    body = None if value is None else json.dumps(value).encode("utf-8")
    fields = {"Content-Type": "application/json", "X-Domelica-Request": "1", **(headers or {})}
    req = urllib.request.Request(base + path, data=body, headers=fields,
                                 method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = response.read()
            return response.status, data, response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


def check(bundle, output):
    bundle = Path(bundle).resolve()
    verify_bundle(bundle)
    executable = bundle / "native" / "cart_compiled"
    original = sha256(executable.read_bytes()).hexdigest()
    for tool in ("omc", "gcc", "g++", "clang", "make"):
        if shutil.which(tool):
            raise AssertionError(f"Compiler-free acceptance environment has {tool}")
    service = LocalLab(("127.0.0.1", 0), bundle, output / "runs", timeout=60)
    base = f"http://127.0.0.1:{service.server_port}"
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        status, page, headers = request(base, "/")
        assert status == 200 and b"Run fresh simulation" in page and b"/app.js" in page
        assert "default-src 'none'" in headers["Content-Security-Policy"]
        status, js, _ = request(base, "/app.js")
        assert status == 200 and b"fetch(\"/api/run\"" in js
        status, raw, _ = request(base, "/api/config")
        config = json.loads(raw)
        assert status == 200 and set(config["parameters"]) == {"cartMass", "bobMass", "springStiffness", "initialAngle"}
        status, raw, _ = request(base, "/api/run", {"parameters": {"cartMass": 0}})
        assert status == 400 and "cartMass" in json.loads(raw)["error"]
        status, raw, _ = request(base, "/api/run", {"parameters": {"cartMass": 5}},
                                 {"Origin": "https://untrusted.example"})
        assert status == 403
        status, raw, _ = request(base, "/api/run", {"parameters": {"newBody": 1}})
        assert status == 400
        assert not list((output / "runs").iterdir()), "Invalid requests started a run"
        values = {"cartMass": 3.37, "bobMass": 0.76, "springStiffness": 18, "initialAngle": 0.55}
        status, raw, _ = request(base, "/api/run", {"parameters": values})
        answer = json.loads(raw)
        assert status == 200, answer
        assert answer["parameters"] == values, answer
        assert answer["runtimeCompilerInvocations"] == 0
        assert answer["samples"] >= 100 and answer["simulatedSeconds"] == 6
        status, html, _ = request(base, answer["url"])
        assert status == 200 and b"DomelicaObservationLayer" in html
        assert sha256(html).hexdigest() == answer["htmlSHA256"]
        status, _, _ = request(base, "/runs/../viewer.html")
        assert status == 404
        status, _, _ = request(base, "/runs/not-yours/viewer.html")
        assert status == 404
        verify_bundle(bundle)
        assert sha256(executable.read_bytes()).hexdigest() == original
        return {"passed": True, "runId": answer["runId"], "actualParameters": answer["parameters"],
                "samples": answer["samples"], "simulatedSeconds": answer["simulatedSeconds"],
                "resultHtmlSHA256": answer["htmlSHA256"], "executableSHA256": original,
                "nativeCompilations": 0,
                "checks": ["HTTP form and config served", "local security refusal", "parameter validation",
                           "fresh non-preset native calculation", "same executable", "native result HTML served",
                           "path traversal refused", "source/result identity"]}
    finally:
        service.shutdown()
        service.server_close()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = check(args.bundle, args.output)
    (args.output / "local-http-check.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
