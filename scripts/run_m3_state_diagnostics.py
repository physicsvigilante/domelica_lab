#!/usr/bin/env python3
"""Run one bounded, native M3 state/solver diagnostic without changing gates.

Each matrix job has an isolated checkout. It creates an extending Modelica
model, uses only native state-selection and solver options, and preserves both
complete and partial native evidence. An export of partial results never makes
the completion guard pass. The original native MAT reader/exporter remains the
only result-reading path.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "m3_tanks_initial"
TIMEOUT_SECONDS = 300
CASES = {
    "hybrid": dict(states={"speed": "always", "a": "always", "b": "always"},
                   omcOptions="", method="dassl", solverFlag="-nls=hybrid"),
    "speed_a": dict(states={"speed": "always", "a": "always"},
                    omcOptions="", method="dassl", solverFlag=""),
    "speed_b": dict(states={"speed": "always", "b": "always"},
                    omcOptions="", method="dassl", solverFlag=""),
    "prefer_dummy": dict(states={"speed": "prefer", "a": "prefer", "b": "prefer"},
                         omcOptions="--indexReductionMethod=dummyDerivatives", method="dassl", solverFlag=""),
    "kinsol": dict(states={"speed": "always", "a": "always", "b": "always"},
                   omcOptions="", method="dassl", solverFlag="-nls=kinsol"),
    "dae_ida": dict(states={"speed": "always", "a": "always", "b": "always"},
                    omcOptions="--daeMode", method="ida", solverFlag="-daeMode"),
    "curve_derivative": dict(states={}, omcOptions="", method="dassl", solverFlag="", curveDerivative=True),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_curve_binding():
    """Change only the exact pump curve binding in this isolated matrix job.

    The production redeclaration is not replaceable, so an outer nested
    redeclaration would be invalid. Keep original and modified bytes as
    diagnostic evidence; the six other candidate jobs never call this helper.
    """
    path = ROOT / "DomelicaLab/Components/TwoTankLoopPlant.mo"
    directory = ROOT / "artifacts/m3-state-diagnostics/curve_derivative"
    directory.mkdir(parents=True, exist_ok=True)
    original = path.read_bytes()
    original_path = directory / "TwoTankLoopPlant.original.mo"
    modified_path = directory / "TwoTankLoopPlant.modified.mo"
    original_path.write_bytes(original)
    old = ("    redeclare function flowCharacteristic =\n"
           "      Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.quadraticFlow(\n"
           "        V_flow_nominal={0,0.004,0.008}, head_nominal={10,7,0}),")
    new = "    redeclare function flowCharacteristic = M3DiagnosticFlow,"
    text = original.decode("utf-8")
    report = {"path": str(path.relative_to(ROOT)), "exactMatches": text.count(old),
              "originalSHA256": sha(original_path), "originalBinding": old,
              "modifiedBinding": new,
              "scope": "Only the isolated curve_derivative checkout; native curve values delegated unchanged to MSL."}
    if report["exactMatches"] != 1:
        (directory / "source-patch.json").write_text(json.dumps(report, indent=2) + "\n")
        raise ValueError("Expected exactly one original native pump curve binding; refusing diagnostic patch")
    modified = text.replace(old, new, 1).encode("utf-8")
    path.write_bytes(modified)
    modified_path.write_bytes(modified)
    report["modifiedSHA256"] = sha(modified_path)
    report["originalCopy"] = str(original_path.relative_to(ROOT))
    report["modifiedCopy"] = str(modified_path.relative_to(ROOT))
    (directory / "source-patch.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def write_native_inputs(candidate):
    settings = CASES[candidate]
    states = settings["states"]
    modifiers = ([f"speedResponse(y(stateSelect=StateSelect.{states['speed']}))"]
                 if "speed" in states else [])
    tank_modifiers = [f"tank{letter.upper()}(level(stateSelect=StateSelect.{states[letter]}))"
                      for letter in ("a", "b") if letter in states]
    if tank_modifiers:
        modifiers.append("plant(" + ", ".join(tank_modifiers) + ")")
    functions = ""
    source_patch = None
    if settings.get("curveDerivative"):
        # Delegate every head value to the original MSL function. Supply only
        # its exact derivative, including MSL's linear extrapolation outside
        # the nominal points; preserve automatic native state selection.
        functions = '''function M3DiagnosticFlowDerivative
  input Modelica.Units.SI.VolumeFlowRate V_flow;
  input Real der_V_flow(unit="m3/s2");
  output Real der_head(unit="m/s");
algorithm
  der_head := (if V_flow < 0 then -250
    elseif V_flow > 0.008 then -2250
    else -250 - 250000*V_flow)*der_V_flow;
end M3DiagnosticFlowDerivative;

function M3DiagnosticFlow
  extends Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.baseFlow;
algorithm
  head := Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.quadraticFlow(
    V_flow, {0, 0.004, 0.008}, {10, 7, 0});
  annotation(derivative=M3DiagnosticFlowDerivative, Inline=false);
end M3DiagnosticFlow;

'''
        source_patch = patch_curve_binding()
    modification = "(\n    " + ",\n    ".join(modifiers) + ")" if modifiers else ""
    model = (functions + "model M3Diagnostic\n"
             f"  \"Native state/solver diagnostic: {candidate}\"\n"
             "  extends DomelicaLab.Examples.ControlledTankInitialLevels" + modification + ";\n"
             "end M3Diagnostic;\n")
    model_path = ROOT / "M3Diagnostic.mo"
    model_path.write_text(model, encoding="utf-8")
    options = ""
    if settings["omcOptions"]:
        options = (f"if not setCommandLineOptions({json.dumps(settings['omcOptions'])}) then\n"
                   '  print("ERROR: native diagnostic compiler option rejected.\\n");\n'
                   "  print(getErrorString());\n  exit(1);\nend if;\n")
    simflags = " ".join(x for x in (settings["solverFlag"], "-lv=LOG_EVENTS,LOG_EVENTS_V,LOG_DSS") if x)
    script = (
        f'print("M3_DIAGNOSTIC_START {candidate}\\n");\n'
        'print("Compiler: " + getVersion() + "\\n");\n'
        'if not loadModel(Modelica, {"4.1.0"}) then\n'
        '  print("ERROR: cannot load MSL 4.1.0.\\n");\n'
        '  print(getErrorString());\n  exit(1);\nend if;\n'
        'if not loadFile("DomelicaLab/package.mo") then\n'
        '  print("ERROR: cannot load DomelicaLab.\\n");\n'
        '  print(getErrorString());\n  exit(1);\nend if;\n'
        'if not loadFile("M3Diagnostic.mo") then\n'
        '  print("ERROR: cannot load diagnostic extension.\\n");\n'
        '  print(getErrorString());\n  exit(1);\nend if;\n'
        + options
        + 'print(checkModel(M3Diagnostic) + "\\n");\n'
        'print(getErrorString());\n'
        'simulate(M3Diagnostic, startTime=0, stopTime=300, numberOfIntervals=3000,\n'
        f'  tolerance=1e-10, method={json.dumps(settings["method"])}, outputFormat="mat",\n'
        f'  fileNamePrefix="{PREFIX}", simflags={json.dumps(simflags)});\n'
        'print(getErrorString());\n'
        f'print("M3_DIAGNOSTIC_OMC_RETURNED {candidate}\\n");\n'
    )
    mos_path = ROOT / "m3_state_diagnostic.mos"
    mos_path.write_text(script, encoding="utf-8")
    return {**settings, "sourcePatch": source_patch, "simflags": simflags, "modelSHA256": sha(model_path),
            "scriptSHA256": sha(mos_path)}


def run_bounded(name, command, directory):
    log_path = directory / (name + ".log")
    started = time.monotonic()
    result = {"name": name, "command": command, "timeoutSeconds": TIMEOUT_SECONDS,
              "timedOut": False, "log": str(log_path.relative_to(ROOT))}
    print(f"START {name}: {' '.join(command)}", flush=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       text=True, start_new_session=True)
            try:
                result["returncode"] = process.wait(timeout=TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                result["timedOut"] = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=30)
                result["returncode"] = 124
                log.write(f"\nDIAGNOSTIC TIMEOUT: process group stopped after {TIMEOUT_SECONDS} seconds.\n")
    except OSError as error:
        result["returncode"] = 127
        result["error"] = str(error)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nDIAGNOSTIC LAUNCH ERROR: {error}\n")
    result["elapsedSeconds"] = time.monotonic() - started
    text = log_path.read_text(encoding="utf-8", errors="replace")
    print(text[-16000:], end="" if text.endswith("\n") else "\n", flush=True)
    print(f"END {name}: exit {result['returncode']}; {result['elapsedSeconds']:.2f} seconds; full log {result['log']}", flush=True)
    with (ROOT / "diagnostic_stdout.log").open("a", encoding="utf-8") as log:
        log.write(f"\nSTAGE {name}\n")
        log.write(text)
        log.write("\n" + json.dumps(result, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=CASES)
    args = parser.parse_args()
    directory = ROOT / "artifacts/m3-state-diagnostics" / args.candidate
    directory.mkdir(parents=True, exist_ok=True)
    for suffix in ("_res.mat", "_res.csv", ".log", "_init.xml", "_info.json"):
        (ROOT / (PREFIX + suffix)).unlink(missing_ok=True)
    (ROOT / "diagnostic_stdout.log").write_text("", encoding="utf-8")
    settings = write_native_inputs(args.candidate)
    report = {
        "candidate": args.candidate,
        "revision": os.environ.get("MODEL_SOURCE_REVISION", "local diagnostic"),
        "runUrl": os.environ.get("NATIVE_RUN_URL", ""),
        "requestedSettings": settings,
        "experiment": {"startTime": 0, "stopTime": 300, "numberOfIntervals": 3000, "tolerance": 1e-10},
        "stages": [], "completionPassed": False, "exportPassed": False, "passed": False,
        "scope": "Native diagnostic only. Partial MAT/CSV outputs do not satisfy completion or acceptance.",
    }
    try:
        native = run_bounded("native", ["omc", "m3_state_diagnostic.mos"], directory)
        report["stages"].append(native)
        if (ROOT / (PREFIX + "_res.mat")).is_file():
            completion = run_bounded("completion", [sys.executable, "scripts/check_fluid_completion.py", PREFIX, "300", "3001"], directory)
            report["stages"].append(completion)
            report["completionPassed"] = completion["returncode"] == 0
            # Retain native partial trajectories for diagnosis even when the
            # completion guard failed. This never upgrades completion status.
            export = run_bounded("export", [sys.executable, "-u", "scripts/export_fluid_csv.py", PREFIX], directory)
            report["stages"].append(export)
            report["exportPassed"] = export["returncode"] == 0
        else:
            report["missingNativeMAT"] = True
        report["passed"] = native["returncode"] == 0 and report["completionPassed"] and report["exportPassed"]
    finally:
        report["retainedInputsSHA256"] = {path.name: sha(path) for path in [
            ROOT / "M3Diagnostic.mo", ROOT / "m3_state_diagnostic.mos",
            ROOT / (PREFIX + "_res.mat"), ROOT / (PREFIX + "_res.csv"), ROOT / (PREFIX + ".log"),
            ROOT / (PREFIX + "_init.xml"), ROOT / (PREFIX + "_info.json")]
            if path.is_file()}
        (directory / "candidate-run.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": args.candidate, "completionPassed": report["completionPassed"],
                      "exportPassed": report["exportPassed"], "passed": report["passed"]}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
