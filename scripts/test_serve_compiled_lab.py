#!/usr/bin/env python3
"""Guard tests for the loopback-only HTML/native-run bridge (no solver needed)."""
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from serve_compiled_lab import LocalLab


class BridgeGuards(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="domelica-http-guards-")
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        bundle = root / "bundle"
        (bundle / "viewer").mkdir(parents=True)
        (bundle / "viewer" / "parameter-lab.html").write_text("<html>Run fresh simulation <script src='/app.js'></script></html>")
        (bundle / "viewer" / "parameter-lab.js").write_text("window.domelica = true;")
        definitions = {"cartMass": {"default": 2, "unit": "kg", "minimumExclusive": 0},
                       "bobMass": {"default": 1, "unit": "kg", "minimumExclusive": 0},
                       "springStiffness": {"default": 20, "unit": "N/m", "minimumExclusive": 0},
                       "initialAngle": {"default": 0.5, "unit": "rad", "minimumExclusive": -1.57, "maximumExclusive": 1.57}}
        (bundle / "configuration.json").write_text(json.dumps({"parameters": definitions, "model": "Cart"}))
        (bundle / "build.json").write_text(json.dumps({"schema": "domelica.compiled-model/v1", "compilerInvocations": 1, "filesSHA256": {}}))
        self.server = LocalLab(("127.0.0.1", 0), bundle, root / "runs")
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def query(self, path, value=None, headers=None):
        body = json.dumps(value).encode() if value is not None else None
        req = Request(self.base + path, data=body, method="POST" if body is not None else "GET",
                      headers={"Content-Type": "application/json", "X-Domelica-Request": "1", **(headers or {})})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def test_app_and_config_available(self):
        status, page, headers = self.query("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Run fresh simulation", page)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.query("/app.js")[0], 200)
        status, body, _ = self.query("/api/config")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["parameters"]), 4)

    def test_wrong_origin_and_host_refused(self):
        self.assertEqual(self.query("/api/run", {"parameters": {}}, {"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.query("/", headers={"Host": "evil.example"})[0], 403)

    def test_bad_parameter_names_and_values_refused(self):
        for params in ({"unknown": 2}, {"cartMass": 0}, {"bobMass": -4}, {"initialAngle": 1.57},
                       {"springStiffness": "20"}, {"cartMass": True}):
            with self.subTest(params=params):
                self.assertEqual(self.query("/api/run", {"parameters": params})[0], 400)
        self.assertEqual(self.query("/api/run", {"extra": 1})[0], 400)
        self.assertEqual(self.query("/api/run", {"parameters": []})[0], 400)

    def test_csrf_header_and_path_guards(self):
        self.assertEqual(self.query("/api/run", {"parameters": {}}, {"X-Domelica-Request": ""})[0], 415)
        self.assertEqual(self.query("/runs/../viewer.html")[0], 404)
        self.assertEqual(self.query("/runs/guess/viewer.html")[0], 404)
        self.assertEqual(self.query("/api/config?file=../secret")[0], 404)
        self.assertEqual(self.query("/not-an-endpoint")[0], 404)

    def test_public_requests_did_not_run_solver(self):
        self.assertEqual(self.query("/api/run", {"parameters": {"cartMass": -7}})[0], 400)
        self.assertEqual(list(self.server.results_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
