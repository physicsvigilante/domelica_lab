#!/usr/bin/env python3
"""Focused native MAT adapter checks; optionally compare accepted native CSVs.

Usage: python3 scripts/test_native_mat.py --reference-dir PATH --report PATH
No compiler or simulation is invoked. Reference files must be existing pairs
named *_res.mat and *_res.csv from the native OpenModelica reader.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from native_mat import NativeMatError, NativeMatResult


REFERENCE_DIR = None
REFERENCE_RESULTS = []


def _transpose(rows):
    return [list(values) for values in zip(*rows)]


def _text_rows(strings):
    encoded = [text.encode("utf-8") for text in strings]
    width = max(map(len, encoded)) + 1
    return [list(value.ljust(width, b"\0")) for value in encoded]


def _matrix(name, rows, precision=0, kind=0, endian="<"):
    code = {0: "d", 2: "i", 5: "B"}[precision]
    values = [value for column in zip(*rows) for value in column]
    encoded = name.encode("ascii") + b"\0"
    machine = 0 if endian == "<" else 1
    header = struct.pack(endian + "5i", machine * 1000 + precision * 10 + kind,
                         len(rows), len(rows[0]), 0, len(encoded))
    return header + encoded + struct.pack(endian + str(len(values)) + code, *values)


def _fixture(storage="binTrans", endian="<", index=2, parameter_end=3.25,
             values=None, times=None, version="1.1"):
    names = ["time", "p", "negativeP", "x", "negativeX", "a[1,1]", "'μ body'"]
    info = [[0, 1, 0, -1], [1, 2, 0, 0], [1, -2, 0, 0],
            [2, index, 0, -1], [2, -2, 0, -1], [2, 2, 0, -1], [2, 2, 0, -1]]
    text = _text_rows(names)
    descriptions = _text_rows(["native time", "parameter", "negative parameter",
                               "variable", "negative variable", "indexed alias", "quoted alias"])
    data1 = [[0., 1.], [3.25, parameter_end]]
    data2 = [times or [0., .5, 1., 1.], values or [2., 3., 4., 4.]]
    if storage == "binTrans":
        text, descriptions, info = map(_transpose, (text, descriptions, info))
    else:
        data1, data2 = map(_transpose, (data1, data2))
    return b"".join([
        _matrix("Aclass", _text_rows(["Atrajectory", version, "", storage]), 5, 1, endian),
        _matrix("name", text, 5, 1, endian),
        _matrix("description", descriptions, 5, 1, endian),
        _matrix("dataInfo", info, 2, 0, endian),
        _matrix("data_1", data1, 0, 0, endian),
        _matrix("data_2", data2, 0, 0, endian),
    ])


class NativeMatTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="domelica-mat-reader-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "native.mat"

    def read(self, content):
        self.path.write_bytes(content)
        return NativeMatResult(self.path)

    def test_parameters_aliases_names_and_duplicate_times(self):
        result = self.read(_fixture())
        self.assertEqual(result.times, [0., .5, 1., 1.])
        self.assertEqual(result.names, ["time", "'μ body'", "a[1,1]", "negativeP", "negativeX", "p", "x"])
        self.assertEqual(result.column("p"), [3.25] * 4)
        self.assertEqual(result.column("negativeP"), [-3.25] * 4)
        self.assertEqual(result.column("negativeX"), [-2., -3., -4., -4.])
        self.assertEqual(result.column("'μ body'"), result.column("a[1,1]"))
        with self.assertRaises(KeyError):
            result.column("absent")

    def test_normal_storage_and_big_endian(self):
        result = self.read(_fixture(storage="binNormal", endian=">"))
        self.assertEqual(result.times, [0., .5, 1., 1.])
        self.assertEqual(result.column("negativeP"), [-3.25] * 4)
        self.assertEqual(result.column("x"), [2., 3., 4., 4.])

    def test_csv_keeps_parameters_aliases_and_original_samples(self):
        result = self.read(_fixture())
        output = result.write_csv(self.path.with_suffix(".csv"))
        with output.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 4)
        self.assertEqual([float(row["time"]) for row in rows], result.times)
        self.assertEqual([float(row["negativeP"]) for row in rows], [-3.25] * 4)
        self.assertEqual([float(row["'μ body'"]) for row in rows], [2., 3., 4., 4.])

    def test_reject_truncated_header_and_payload(self):
        for content in (_fixture()[:12], _fixture()[:-1]):
            with self.subTest(length=len(content)), self.assertRaises(NativeMatError):
                self.read(content)

    def test_reject_complex_and_unsupported_identity(self):
        complex_data = bytearray(_fixture())
        complex_data[12:16] = struct.pack("<i", 1)
        for content in (bytes(complex_data), _fixture(version="2.0")):
            with self.subTest(header=content[:20]), self.assertRaises(NativeMatError):
                self.read(content)

    def test_reject_invalid_native_index(self):
        for index in (0, 300):
            with self.subTest(index=index), self.assertRaises(NativeMatError):
                self.read(_fixture(index=index))

    def test_reject_nonfinite_values(self):
        with self.assertRaises(NativeMatError):
            self.read(_fixture(values=[2., float("nan"), 4., 4.]))

    def test_reject_varying_parameter(self):
        with self.assertRaises(NativeMatError):
            self.read(_fixture(parameter_end=4.))

    def test_reject_backward_time(self):
        with self.assertRaises(NativeMatError):
            self.read(_fixture(times=[0., .75, .5, 1.]))

    def test_accepted_native_recordings(self):
        if REFERENCE_DIR is None:
            self.skipTest("No existing native reference directory supplied")
        files = sorted(REFERENCE_DIR.glob("*_res.mat"))
        self.assertTrue(files, "Reference directory has no native MAT recordings")
        for mat_path in files:
            with self.subTest(recording=mat_path.name):
                csv_path = mat_path.with_suffix(".csv")
                self.assertTrue(csv_path.is_file(), "Each MAT requires its accepted native-reader CSV")
                native = NativeMatResult(mat_path)
                columns = {name: native.column(name) for name in native.names}
                with csv_path.open(newline="", encoding="utf-8") as stream:
                    reader = csv.DictReader(stream)
                    self.assertEqual(set(reader.fieldnames), set(native.names))
                    count, samples = 0, 0
                    for i, row in enumerate(reader):
                        self.assertLess(i, len(native.times))
                        for name, values in columns.items():
                            expected = float(row[name])
                            if values[i] != expected:
                                self.fail(f"Native value mismatch: {mat_path.name}, {name}, sample {i}: {values[i]!r} != {expected!r}")
                            count += 1
                        samples += 1
                self.assertEqual(samples, len(native.times))
                exported = native.write_csv(Path(self.directory.name) / (mat_path.stem + ".csv"))
                # Byte identity is additional evidence when the original native
                # exporter uses the same Python CSV serialization and ordering.
                report = {
                    "recording": mat_path.name,
                    "samples": samples,
                    "columns": len(native.names),
                    "comparedValues": count,
                    "exactNumericMatch": True,
                    "csvByteIdentical": exported.read_bytes() == csv_path.read_bytes(),
                    "negativeAliases": sum(index < 0 for _, index in native._info.values()),
                    "parameterOrInvariantNames": sum(channel == 1 for channel, _ in native._info.values()),
                    "duplicateTimestamps": sum(a == b for a, b in zip(native.times, native.times[1:])),
                    "matSHA256": hashlib.sha256(mat_path.read_bytes()).hexdigest(),
                    "nativeCsvSHA256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                }
                REFERENCE_RESULTS.append(report)


def main():
    global REFERENCE_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    REFERENCE_DIR = args.reference_dir
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeMatTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "passed": result.wasSuccessful(),
        "testsRun": result.testsRun,
        "skipped": len(result.skipped),
        "compilerInvoked": False,
        "simulationExecuted": False,
        "references": REFERENCE_RESULTS,
        "scope": "MAT serialization and format checks only; no numerical physics verification.",
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
