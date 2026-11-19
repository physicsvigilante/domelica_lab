#!/usr/bin/env python3
"""Check executable reuse and one fresh result against the established reader.

This job runs after the compiler-free runtime job. It starts omc only to read a
saved MAT file; it never builds a model, runs dynamics or compares trajectories
with another physics solver.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from export_native_csv import NativeBatchReader, export_native_csv
from native_mat import NativeMatResult

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(results_dir):
    results_dir = Path(results_dir).resolve()
    summary = json.loads((results_dir / "compiled-run-report.json").read_text())
    configuration = json.loads((ROOT / "viewer/compiled-experiments.json").read_text())
    manifest = json.loads((results_dir / "experiments.json").read_text())
    require(summary["passed"], "The native runtime phase did not pass")
    require(summary["buildCompilerInvocations"] == 1, "Expected exactly one model build")
    require(summary["runtimeCompilerInvocations"] == 0, "The runtime phase invoked a compiler")
    environment = summary["runtimeEnvironment"]
    require(environment["requireNoCompiler"] and environment["compilerToolsAbsent"],
            "The clean runtime gate was not enforced")
    require(not any(environment["tools"].values()), "A development tool was found in the runtime job")
    presets = {row["id"]: row for row in configuration["presets"]}
    runs = {row["id"]: row for row in summary["runs"]}
    require(set(runs) == set(presets) and len(runs) == 3, "The three declared variants were not all run")
    require(manifest["recording"]["executionMode"] == "compiled-executable-reuse",
            "Viewer manifest has the wrong execution origin")
    require(manifest["recording"]["buildIdentity"]["executableSHA256"] == summary["executableSHA256"],
            "Viewer and runtime refer to different compiled executables")
    cases = []
    visual_hashes = set()
    for identity, run in runs.items():
        require(run["nativeCompleted"] and run["exitCode"] == 0, "Native run did not complete: " + identity)
        require(run["compilerInvocations"] == 0, "A run invoked compilation: " + identity)
        require(run["executableBeforeSHA256"] == run["executableAfterSHA256"] == summary["executableSHA256"],
                "Executable changed for " + identity)
        require(run["requestedParameters"] == presets[identity]["parameters"],
                "The requested variant changed: " + identity)
        native = NativeMatResult(results_dir / (run["prefix"] + "_res.mat"))
        for name, expected in presets[identity]["parameters"].items():
            require(all(abs(value - expected) <= 1e-12 for value in native.column(name)),
                    "Fresh native parameter differs: " + identity + ": " + name)
        visual_hashes.add(digest(results_dir / (run["prefix"] + "_visual.xml")))
        cases.append({"id": identity, "samples": len(native.times), "columns": len(native.names),
                      "actualParameters": run["actualParameters"],
                      "elapsedSimulationSeconds": run["elapsedSimulationSeconds"]})
    require(len(visual_hashes) == 1, "Fixed-geometry runs must reuse the generated visual XML")
    require(len({row["dynamicTrajectorySHA256"] for row in runs.values()}) == 3,
            "The variants did not produce distinct motion recordings")

    # One fresh result is sufficient for this format boundary; the remaining
    # runs use the same binary, output format and decoder. No additional solve.
    baseline = runs[configuration["presets"][0]["id"]]
    original_mat = results_dir / (baseline["prefix"] + "_res.mat")
    native = NativeMatResult(original_mat)
    values_compared = 0
    with tempfile.TemporaryDirectory(prefix="domelica-reader-crosscheck-") as temporary:
        prefix = Path(temporary) / "reference"
        shutil.copy2(original_mat, prefix.with_name("reference_res.mat"))
        reference_csv = export_native_csv(NativeBatchReader(temporary), prefix)
        with reference_csv.open(newline="", encoding="utf-8") as stream:
            rows = csv.DictReader(stream)
            require(rows.fieldnames == native.names, "Native variable inventories differ")
            columns = [native.column(name) for name in native.names]
            count = 0
            for index, row in enumerate(rows):
                require(index < len(native.times), "Reference reader returned extra samples")
                for name, column in zip(native.names, columns):
                    require(float(row[name]) == column[index],
                            f"Reader mismatch at sample {index}, variable {name}")
                    values_compared += 1
                count += 1
            require(count == len(native.times), "Native sample counts differ")
        same_csv_bytes = reference_csv.read_bytes() == (results_dir / (baseline["prefix"] + "_res.csv")).read_bytes()
        require(same_csv_bytes, "The serialized CSV differs from the established native reader")
    return {"passed": True, "modelBuilds": 1, "runtimeCompilerInvocations": 0,
            "runtimeEnvironment": environment, "executableSHA256": summary["executableSHA256"],
            "runs": cases, "sharedVisualXMLSHA256": next(iter(visual_hashes)),
            "referenceReader": {"recording": baseline["id"], "nativeValuesCompared": values_compared,
                                "csvByteIdentical": same_csv_bytes, "additionalSimulations": 0},
            "scope": "Native serialization, parameter propagation and executable reuse; no independent dynamics comparison."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = check(args.results_dir)
    except Exception as error:
        args.output.write_text(json.dumps({"passed": False, "error": str(error)}, indent=2) + "\n")
        raise
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
