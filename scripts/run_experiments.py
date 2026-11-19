#!/usr/bin/env python3
"""Plan or run the manifest's native Modelica experiments in an empty directory.

`plan` only writes a reviewable .mos script. `run` requires an installed omc and
MSL; it executes that script, exports native MAT through the repository reader,
checks only completion/time data, and records input hashes for the viewer build.
The source Modelica package and GitHub are never written by this command.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from build_observation_lab import ROOT, checked_path, digest, read_manifest
from export_native_csv import NativeBatchReader, _read_columns, export_native_csv


def mos_string(value):
    return json.dumps(str(value).replace("\\", "/"), ensure_ascii=False)


def script_for(manifest, package_path):
    version = manifest["modelica"]["mslVersion"]
    lines = [
        '// Generated from experiments.json. Native simulation only; no derived dynamics.',
        'print("DOMELICA_NATIVE_RUN_START\\n");',
        'print("Compiler: " + getVersion() + "\\n");',
        'if not setCommandLineOptions("+d=visxml") then',
        '  print("ERROR: cannot enable native visualization export.\\n"); exit(1);',
        'end if;',
        f'if not loadModel(Modelica, {{{mos_string(version)}}}) then',
        '  print(getErrorString()); exit(1);',
        'end if;',
        f'if not loadFile({mos_string(package_path)}) then',
        '  print(getErrorString()); exit(1);',
        'end if;',
        'writeFile("native-toolchain.txt", "compiler=" + getVersion() + "\\nmslVersion=" + getVersion(Modelica) + "\\nmslSource=" + getSourceFile(Modelica) + "\\n");',
    ]
    for experiment in manifest["experiments"]:
        model, prefix, simulation = experiment["model"], experiment["prefix"], experiment["simulation"]
        lines += [
            f'print("DOMELICA_MODEL_BEGIN::{experiment["id"]}\\n");',
            f'print("CHECKING {experiment["id"]}\\n");',
            f'print(checkModel({model}) + "\\n");',
            'print(getErrorString());',
            f'simulate({model},',
            f'  startTime={simulation["startTime"]}, stopTime={simulation["stopTime"]},',
            f'  numberOfIntervals={simulation["numberOfIntervals"]}, tolerance={simulation["tolerance"]},',
            f'  method={mos_string(simulation.get("method", "dassl"))}, outputFormat="mat", fileNamePrefix={mos_string(prefix)});',
            'print(getErrorString());',
            f'print("DOMELICA_MODEL_END::{experiment["id"]}\\n");',
            f'if not regularFileExists({mos_string(prefix + "_res.mat")}) or not regularFileExists({mos_string(prefix + "_visual.xml")}) then',
            f'  print("ERROR: missing native result for {prefix}\\n"); exit(1);',
            'end if;',
        ]
    lines += ['print("DOMELICA_NATIVE_RUN_COMPLETE\\n");', '']
    return "\n".join(lines)


def execute(manifest_path, run_dir, mode, timeout):
    manifest_path, run_dir = Path(manifest_path).resolve(), Path(run_dir).resolve()
    manifest = read_manifest(manifest_path)
    package_path = checked_path(ROOT, manifest["modelica"]["package"])
    if not package_path.is_file():
        raise FileNotFoundError(f"Modelica package missing: {package_path}")
    if run_dir.is_relative_to(package_path.parent):
        raise ValueError("The run directory must be outside the source Modelica package")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError("Choose an empty run directory to prevent mixing old and new native results")
    compiler = shutil.which("omc")
    if mode == "run" and compiler is None:
        raise RuntimeError("OpenModelica omc is not installed. No simulation was run. Use plan to inspect the generated script.")
    run_dir.mkdir(parents=True, exist_ok=True)
    # Keep every generated/compiled file outside the source package. Freeze a
    # small source copy so a later local edit cannot change this run's identity.
    frozen_package = run_dir / "source" / package_path.parent.name
    shutil.copytree(package_path.parent, frozen_package)
    script = run_dir / "run_native.mos"
    script.write_text(script_for(manifest, frozen_package / package_path.name), encoding="utf-8")
    plan = {"mode": mode, "simulationExecuted": False, "script": script.name,
            "experiments": [{"id": e["id"], "model": e["model"], **e["simulation"]} for e in manifest["experiments"]],
            "manifestSHA256": digest(manifest_path),
            "modelSourceSHA256": {str(p.relative_to(frozen_package)): digest(p) for p in sorted(frozen_package.rglob("*")) if p.is_file()}}
    (run_dir / "run-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if mode == "plan":
        return plan
    # This path is intentionally not invoked when delivering an existing-recording viewer.
    with (run_dir / "native-run.log").open("w", encoding="utf-8") as stream:
        completed = subprocess.run([compiler, str(script)], cwd=run_dir, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False, timeout=timeout)
    log = (run_dir / "native-run.log").read_text(encoding="utf-8", errors="replace")
    if completed.returncode or "DOMELICA_NATIVE_RUN_COMPLETE" not in log:
        raise RuntimeError("Native run did not complete; inspect native-run.log")
    for experiment in manifest["experiments"]:
        ident = experiment["id"]
        begin, end = f"DOMELICA_MODEL_BEGIN::{ident}", f"DOMELICA_MODEL_END::{ident}"
        if log.count(begin) != 1 or log.count(end) != 1 or log.index(begin) >= log.index(end):
            raise RuntimeError(f"Native log markers are missing, duplicated or out of order for {ident}")
        section = log.split(begin, 1)[1].split(end, 1)[0]
        if not re.search(r"LOG_SUCCESS\s*\|\s*info\s*\|\s*The simulation finished successfully\.", section):
            raise RuntimeError(f"Native success message missing for {ident}; inspect native-run.log")
    completions = []
    with tempfile.TemporaryDirectory(prefix="domelica-manifest-reader-") as temporary:
        reader = NativeBatchReader(temporary)
        for experiment in manifest["experiments"]:
            prefix = run_dir / experiment["prefix"]
            mat_path = Path(str(prefix) + "_res.mat")
            times = _read_columns(reader, mat_path, ["time"])[0]
            simulation = experiment["simulation"]
            if (len(times) < 2 or not all(math.isfinite(t) for t in times)
                    or any(b < a for a, b in zip(times, times[1:]))
                    or not math.isclose(times[0], simulation["startTime"], rel_tol=0, abs_tol=1e-10)
                    or not math.isclose(times[-1], simulation["stopTime"], rel_tol=0, abs_tol=1e-10)):
                raise RuntimeError(f"Native run does not cover the requested interval: {experiment['id']}")
            export_native_csv(reader, prefix)
            completions.append({"id": experiment["id"], "samples": len(times), "startTime": times[0], "stopTime": times[-1]})
    toolchain = dict(line.split("=", 1) for line in (run_dir / "native-toolchain.txt").read_text().splitlines() if "=" in line)
    recording = {"kind": "fresh-native-run", "createdUTC": datetime.now(timezone.utc).isoformat(),
                 "compiler": toolchain.get("compiler", "OpenModelica"), "toolchain": toolchain,
                 "sourceDescription": "Frozen local package; modelSourceSHA256 in run-plan.json",
                 "sourceCommit": os.environ.get("MODEL_SOURCE_REVISION", ""),
                 "checkoutRevision": os.environ.get("CHECKOUT_REVISION", ""),
                 "runUrl": os.environ.get("NATIVE_RUN_URL", ""), "completions": completions,
                 "modelSourceSHA256": plan["modelSourceSHA256"],
                 "inputsSHA256": {str(p.relative_to(run_dir)): digest(p) for e in manifest["experiments"]
                                  for suffix in ("_res.csv", "_res.mat", "_visual.xml")
                                  for p in [run_dir / (e["prefix"] + suffix)]}}
    recording["inputsSHA256"].update({name: digest(run_dir / name) for name in ("native-toolchain.txt", "native-run.log", "run-plan.json", "run_native.mos")})
    completed_manifest = copy.deepcopy(manifest)
    completed_manifest["recording"] = recording
    observations = json.loads(checked_path(manifest_path.parent, manifest["observationManifest"]).read_text())
    # Retain definitions but never stamp an old recording's origin on new values.
    observations["provenance"] = {"definitionOrigin": observations.get("provenance", {}),
                                  "recording": recording, "newSimulation": True}
    completed_manifest["observationManifest"] = "observations.json"
    (run_dir / "observations.json").write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    (run_dir / "experiments.json").write_text(json.dumps(completed_manifest, indent=2) + "\n", encoding="utf-8")
    return {"simulationExecuted": True, "manifest": str(run_dir / "experiments.json"), "completions": completions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    parser.add_argument("--manifest", type=Path, default=ROOT / "viewer/observation-experiments.json")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.run_dir, args.mode, args.timeout), indent=2))


if __name__ == "__main__":
    main()
