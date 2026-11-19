#!/usr/bin/env python3
"""Local-only parameter-to-native-runtime HTTP bridge for a precompiled assembly.

The browser never executes native code itself. Only allowlisted, finite numeric
parameters reach an unchanged, precompiled OpenModelica simulation executable.
No external Python packages, compiler, Modelica Standard Library or Node required.
"""
from __future__ import annotations

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlsplit

from compiled_model import parameters_for, read_json, verify_bundle

MAX_BODY = 8192
MAX_RUNS = 8


class LocalLab(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, bundle, results_root, timeout=120, runner=None):
        host, port = address
        if host not in ("127.0.0.1", "::1"):
            raise ValueError("Only loopback binding is supported")
        self.bundle = Path(bundle).resolve(strict=True)
        verify_bundle(self.bundle)
        self.config = read_json(self.bundle / "configuration.json")
        parameters_for(self.config["parameters"], {})
        self.results_root = Path(results_root).resolve()
        if self.results_root == self.bundle or self.results_root.is_relative_to(self.bundle):
            raise ValueError("Results cannot be written inside the immutable runtime bundle")
        self.results_root.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.runner = runner or subprocess.run
        self.run_lock = threading.Lock()
        self.saved = {}
        self.order = deque()
        super().__init__(address, LabHandler)

    def launch(self, request):
        if not isinstance(request, dict) or set(request) != {"parameters"}:
            raise ValueError("Expected an object containing only 'parameters'")
        supplied = request["parameters"]
        if not isinstance(supplied, dict):
            raise ValueError("'parameters' must be a numeric object")
        requested = parameters_for(self.config["parameters"], supplied)
        identity = "r" + secrets.token_hex(8)
        directory = self.results_root / identity
        script = self.bundle / "scripts" / "compiled_model.py"
        builder = self.bundle / "scripts" / "build_observation_lab.py"
        native = [sys.executable, str(script), "run", "--bundle", str(self.bundle),
                  "--output-dir", str(directory), "--id", "custom", "--timeout", str(self.timeout)]
        for key, value in requested.items():
            native.extend(("--set", f"{key}={value:.17g}"))
        self._execute(native, self.timeout + 20, "Native simulation")
        view = directory / "viewer.html"
        self._execute([sys.executable, str(builder), "--manifest", str(directory / "experiments.json"),
                       "--results-dir", str(directory), "--output", str(view)],
                      self.timeout + 20, "Viewer export")
        report = read_json(directory / "compiled-run-report.json")
        html_report = read_json(directory / "viewer_build.json")
        if not report.get("passed") or len(report.get("runs", [])) != 1 or not view.is_file():
            raise RuntimeError("Native result or HTML evidence was not produced")
        actual = report["runs"][0]["actualParameters"]
        self.saved[identity] = view
        self.order.append(identity)
        while len(self.order) > MAX_RUNS:
            expired = self.order.popleft()
            self.saved.pop(expired, None)
            shutil.rmtree(self.results_root / expired, ignore_errors=True)
        return {"runId": identity, "url": f"/runs/{identity}/viewer.html",
                "parameters": actual, "samples": report["runs"][0]["samples"],
                "simulatedSeconds": report["runs"][0]["stopTime"] - report["runs"][0]["startTime"],
                "htmlSHA256": html_report["htmlSHA256"],
                "runtimeCompilerInvocations": report["runtimeCompilerInvocations"]}

    def _execute(self, command, timeout, stage):
        try:
            result = self.runner(command, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"{stage} exceeded the time limit") from error
        if result.returncode != 0:
            print(f"{stage} failed:\n{(result.stderr or result.stdout)[-4000:]}", file=sys.stderr)
            raise RuntimeError(f"{stage} failed. The requested values may violate a physical constraint; check the server log.")


class LabHandler(BaseHTTPRequestHandler):
    server: LocalLab

    def log_message(self, format, *args):
        print(f"LocalLab {self.address_string()}: {format % args}", file=sys.stderr)

    def _host_ok(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}",
                                                 f"localhost:{self.server.server_port}",
                                                 f"[::1]:{self.server.server_port}")

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        return not origin or origin in (f"http://127.0.0.1:{self.server.server_port}",
                                        f"http://localhost:{self.server.server_port}",
                                        f"http://[::1]:{self.server.server_port}")

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        if self.path == "/":
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                             "connect-src 'self'; frame-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, value):
        data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self._send(status, data, "application/json; charset=utf-8")

    def _get_route(self):
        if urlsplit(self.path).query or urlsplit(self.path).fragment:
            return self._json(404, {"error": "Not found"})
        if self.path == "/":
            html = (self.server.bundle / "viewer" / "parameter-lab.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path == "/app.js":
            data = (self.server.bundle / "viewer" / "parameter-lab.js").read_bytes()
            return self._send(200, data, "text/javascript; charset=utf-8")
        if self.path == "/api/config":
            parameters = self.server.config["parameters"]
            return self._json(200, {"model": self.server.config["model"], "parameters": parameters,
                                    "note": "Numbers are applied before a fresh native simulation, not during playback."})
        parts = self.path.split("/")
        if len(parts) == 4 and parts[1] == "runs" and parts[3] == "viewer.html":
            saved_path = self.server.saved.get(parts[2])
            if saved_path and saved_path.is_file():
                return self._send(200, saved_path.read_bytes(), "text/html; charset=utf-8")
        return self._json(404, {"error": "Not found"})

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "Loopback host required"})
        try:
            return self._get_route()
        except OSError:
            return self._json(500, {"error": "Required packaged application file unavailable"})

    def do_POST(self):
        if not self._host_ok() or not self._origin_ok():
            return self._json(403, {"error": "Only this local application may submit runs"})
        if self.path != "/api/run":
            return self._json(404, {"error": "Not found"})
        if (self.headers.get("X-Domelica-Request") != "1" or
                self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"):
            return self._json(415, {"error": "A local JSON request is required"})
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            return self._json(413, {"error": "Invalid request size"})
        try:
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict) or set(request) != {"parameters"}:
                raise ValueError("Expected a single parameters object")
            supplied = request["parameters"]
            if not isinstance(supplied, dict):
                raise ValueError("Parameters must be an object")
            parameters_for(self.server.config["parameters"], supplied)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            return self._json(400, {"error": str(error)[:250]})
        if not self.server.run_lock.acquire(blocking=False):
            return self._json(409, {"error": "Another simulation is already running"})
        try:
            return self._json(200, self.server.launch(request))
        except (RuntimeError, ValueError, OSError) as error:
            return self._json(422, {"error": str(error)[:300]})
        finally:
            self.server.run_lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="Unpacked M5C compiled-model directory")
    parser.add_argument("--results-dir", type=Path, default=Path("parameter-runs"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535 or not 1 <= args.timeout <= 3600:
        parser.error("Invalid port or timeout")
    server = LocalLab(("127.0.0.1", args.port), args.bundle, args.results_dir, args.timeout)
    print(f"Open http://127.0.0.1:{server.server_port}/ in your browser", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
