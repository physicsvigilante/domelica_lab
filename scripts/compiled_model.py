#!/usr/bin/env python3
"""Build one fixed assembly, then run its native executable without a compiler.

The runtime path uses only Python's standard library and the qualified native
MAT reader. It never translates Modelica or substitutes equations of motion.
The first supported assembly exposes four nonstructural Real parameters.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = ("cartMass", "bobMass", "springStiffness", "initialAngle")
MODEL = "DomelicaLab.Examples.CartPendulumSpring3D"
COMPILERS = ("omc", "gcc", "g++", "cc", "c++", "clang", "make")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def beneath(base, relative):
    base = Path(base).resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"Path escapes its root: {relative}")
    return path


def empty_directory(path):
    path = Path(path).resolve()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"A fresh empty directory is required: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def valid_id(value):
    if not re.fullmatch(r"[a-z][a-z0-9-]*", value):
        raise ValueError("Run id must contain lowercase letters, digits and hyphens")
    return value


def parameters_for(definitions, requested):
    if set(definitions) != set(PARAMETERS):
        raise ValueError("This compiled-assembly contract exposes exactly four parameters")
    unknown = set(requested) - set(definitions)
    if unknown:
        raise ValueError(f"Unsupported parameter overrides: {sorted(unknown)}")
    values = {}
    for name, definition in definitions.items():
        raw = requested.get(name, definition["default"])
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{name} must be a finite number")
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
        if "minimumExclusive" in definition and value <= definition["minimumExclusive"]:
            raise ValueError(f"{name} is below its allowed domain")
        if "maximumExclusive" in definition and value >= definition["maximumExclusive"]:
            raise ValueError(f"{name} is above its allowed domain")
        values[name] = value
    return values


def parse_overrides(items):
    values = {}
    for item in items:
        if "=" not in item:
            raise ValueError("Each --set must have the form name=value")
        name, raw = item.split("=", 1)
        if name in values:
            raise ValueError(f"Duplicate override: {name}")
        try:
            values[name] = float(raw)
        except ValueError as error:
            raise ValueError(f"Invalid numerical override: {item}") from error
    return values


def load_configuration(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    configuration = read_json(manifest_path)
    if configuration.get("schema") != "domelica.compiled-experiments/v1":
        raise ValueError("Expected domelica.compiled-experiments/v1")
    if configuration.get("model") != MODEL or configuration.get("prefix") != "cart_compiled":
        raise ValueError("This first compiled contract is for CartPendulumSpring3D")
    parameters_for(configuration["parameters"], {})
    ids = [valid_id(preset["id"]) for preset in configuration["presets"]]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Preset ids must be unique")
    for preset in configuration["presets"]:
        parameters_for(configuration["parameters"], preset["parameters"])
    prototype_path = beneath(manifest_path.parent, configuration["prototypeManifest"])
    prototype = read_json(prototype_path)
    definitions = [e for e in prototype["experiments"] if e["id"] == configuration["prototypeId"]]
    if len(definitions) != 1 or definitions[0]["model"] != configuration["model"]:
        raise ValueError("Compiled model and prototype experiment differ")
    observation_path = beneath(prototype_path.parent, prototype["observationManifest"])
    observations = read_json(observation_path)
    scenes = [s for s in observations["scenes"] if s["id"] == configuration["prototypeId"]]
    if len(scenes) != 1 or scenes[0]["model"] != configuration["model"]:
        raise ValueError("Compiled model and observation prototype differ")
    configuration.update({"modelica": prototype["modelica"], "renderer": prototype["renderer"],
                          "prototypeExperiment": definitions[0], "prototypeObservation": scenes[0]})
    return configuration


def mos_string(value):
    return json.dumps(str(value).replace("\\", "/"))


def build_script(configuration, package):
    simulation = configuration["prototypeExperiment"]["simulation"]
    model, prefix = configuration["model"], configuration["prefix"]
    return "\n".join([
        'print("DOMELICA_COMPILED_BUILD_BEGIN\\n");',
        'if not setCommandLineOptions("+d=visxml") then print(getErrorString()); exit(1); end if;',
        f'if not loadModel(Modelica, {{{mos_string(configuration["modelica"]["mslVersion"])}}}) then print(getErrorString()); exit(1); end if;',
        f'if not loadFile({mos_string(package)}) then print(getErrorString()); exit(1); end if;',
        'writeFile("native-toolchain.txt", "compiler=" + getVersion() + "\\nmslVersion=" + getVersion(Modelica) + "\\nmslSource=" + getSourceFile(Modelica) + "\\n");',
        f'print(checkModel({model}) + "\\n");',
        'print(getErrorString());',
        f'buildModel({model}, startTime={simulation["startTime"]}, stopTime={simulation["stopTime"]},',
        f' numberOfIntervals={simulation["numberOfIntervals"]}, tolerance={simulation["tolerance"]},',
        f' method={mos_string(simulation["method"])}, outputFormat="mat", fileNamePrefix={mos_string(prefix)});',
        'print(getErrorString());',
        f'if not regularFileExists("{prefix}") or not regularFileExists("{prefix}_init.xml") or not regularFileExists("{prefix}_visual.xml") then print("ERROR: compiled files missing\\n"); exit(1); end if;',
        'print("DOMELICA_COMPILED_BUILD_COMPLETE\\n");', ""])


def parameter_metadata(init_path):
    variables = {node.attrib["name"]: node for node in ET.parse(init_path).getroot().iter("ScalarVariable")}
    result = {}
    for name in PARAMETERS:
        node = variables.get(name)
        if node is None:
            raise ValueError(f"Public parameter missing from generated initialization XML: {name}")
        real = node.find("Real")
        if real is None or real.attrib.get("isValueChangeable", node.attrib.get("isValueChangeable")) != "true":
            raise ValueError(f"Generated parameter is not runtime-changeable: {name}; {node.attrib}; {None if real is None else real.attrib}")
        result[name] = {"scalarVariable": dict(node.attrib), "Real": dict(real.attrib)}
    return result


def shared_libraries(executable, library_dir):
    """Copy the linked closure, including its matching ELF loader and libc."""
    result = subprocess.run(["ldd", str(executable)], capture_output=True, text=True, check=True, timeout=30)
    if "not found" in result.stdout:
        raise ValueError("The freshly compiled executable has unresolved shared libraries")
    paths = []
    for line in result.stdout.splitlines():
        match = re.search(r"(?:=>\s+)?(/\S+)\s+\(", line)
        if match:
            paths.append(Path(match.group(1)))
    if not paths:
        raise ValueError("Expected a dynamically linked Linux executable")
    library_dir.mkdir(parents=True)
    entries, loader = [], None
    for path in dict.fromkeys(paths):
        target = library_dir / path.name
        if target.exists() and sha(target) != sha(path):
            raise ValueError(f"Conflicting shared library basename: {path.name}")
        shutil.copy2(path, target)
        entries.append({"name": target.name, "origin": str(path), "sha256": sha(target)})
        if re.match(r"ld-linux.*\.so", path.name):
            loader = target.name
    if loader is None:
        raise ValueError("Matching Linux ELF loader was not found")
    return {"loader": loader, "libraries": entries, "ldd": result.stdout}


def copy_runtime_support(bundle):
    files = [
        "scripts/compiled_model.py", "scripts/native_mat.py", "scripts/build_observation_lab.py",
        "scripts/observation_data.py", "scripts/native_scene.py", "scripts/native_motion_scene.py",
        "viewer/observation.template.html", "viewer/observation-layer.js", "viewer/native-canvas.js",
        "viewer/motion-spring.js", "artifacts/three-runtime.js", "artifacts/three-runtime.json",
        "artifacts/three.LICENSE.txt",
        "docs/M5C_COMPILED_RUNS.md",
    ]
    for relative in files:
        source, target = ROOT / relative, bundle / relative
        if not source.is_file():
            raise FileNotFoundError(f"Build the pinned viewer runtime before packaging: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for name in ("LICENSE", "LICENSE.md", "NOTICE"):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, bundle / name)


def collect_notices(bundle, dependencies, compiler, toolchain):
    """Preserve available distribution notices; report missing ones explicitly."""
    destination = bundle / "licenses"
    destination.mkdir()
    found, missing, packages = [], [], set()
    query = shutil.which("dpkg-query")
    origins = [entry["origin"] for entry in dependencies["libraries"]] + [compiler]
    if query:
        for origin in origins:
            candidates = [origin, str(Path(origin).resolve())]
            owners = []
            for candidate in dict.fromkeys(candidates):
                completed = subprocess.run([query, "-S", candidate], capture_output=True, text=True,
                                           check=False, timeout=15)
                if completed.returncode == 0:
                    owners.extend(line.split(": ", 1)[0] for line in completed.stdout.splitlines() if ": " in line)
            if not owners:
                missing.append({"origin": origin, "reason": "No owning package found by dpkg-query"})
            packages.update(owners)
    else:
        missing.append({"origin": "runtime dependencies", "reason": "dpkg-query unavailable"})
    # Runtime static objects may belong to another OpenModelica binary package.
    for pattern in ("*omc*", "*openmodelica*", "*modelica*"):
        packages.update(path.name for path in Path("/usr/share/doc").glob(pattern) if path.is_dir())
    for package in sorted(packages):
        source = Path("/usr/share/doc") / package.split(":", 1)[0] / "copyright"
        if source.is_file():
            target = destination / (re.sub(r"[^A-Za-z0-9_.+-]", "_", package) + ".copyright")
            shutil.copy2(source, target)
            found.append({"source": str(source), "file": str(target.relative_to(bundle)), "sha256": sha(target)})
        else:
            missing.append({"origin": package, "reason": "Installed copyright notice not found"})
    msl_root = Path(toolchain.get("mslSource", "/unavailable")).parent
    msl_found = False
    for relative in ("LICENSE", "LICENSE.txt", "LICENSE.md", "Resources/Documentation/License.html",
                     "Resources/Documentation/ModelicaLicense2.html"):
        source = msl_root / relative
        if source.is_file():
            target = destination / ("MSL-" + source.name)
            shutil.copy2(source, target)
            found.append({"source": str(source), "file": str(target.relative_to(bundle)), "sha256": sha(target)})
            msl_found = True
    if not msl_found:
        # Current MSL embeds its license text in the UsersGuide package.
        source = msl_root / "UsersGuide" / "ModelicaLicense2.mo"
        if not source.is_file():
            source = msl_root / "UsersGuide" / "ModelicaLicense.mo"
        if source.is_file():
            target = destination / ("MSL-" + source.name)
            shutil.copy2(source, target)
            found.append({"source": str(source), "file": str(target.relative_to(bundle)), "sha256": sha(target)})
        else:
            missing.append({"origin": "Modelica Standard Library", "reason": "Standalone license notice not found at checked paths"})
    found.append({"source": "Bundled Three.js distribution", "file": "artifacts/three.LICENSE.txt",
                  "sha256": sha(bundle / "artifacts/three.LICENSE.txt")})
    return {"preserved": found, "missing": missing}


def build(manifest_path, bundle_path, timeout):
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise ValueError("This package qualification currently targets Linux x86-64")
    configuration = load_configuration(manifest_path)
    compiler = shutil.which("omc")
    if compiler is None:
        raise RuntimeError("The authoring/build step requires OpenModelica omc")
    bundle_path = Path(bundle_path).resolve()
    source_package = beneath(ROOT, configuration["modelica"]["package"])
    if bundle_path.is_relative_to(source_package.parent):
        raise ValueError("Bundle must be outside the Modelica source package")
    bundle = empty_directory(bundle_path)
    work = empty_directory(bundle.with_name(bundle.name + "-build"))
    evidence, native = bundle / "evidence", bundle / "native"
    evidence.mkdir(); native.mkdir()
    frozen_source = bundle / source_package.parent.name
    shutil.copytree(source_package.parent, frozen_source)
    copy_runtime_support(bundle)
    write_json(bundle / "configuration.json", configuration)
    script = evidence / "build.mos"
    script.write_text(build_script(configuration, frozen_source / source_package.name), encoding="utf-8")
    started = time.monotonic()
    with (evidence / "build.log").open("w", encoding="utf-8") as log:
        process = subprocess.run([compiler, str(script)], cwd=work, stdout=log, stderr=subprocess.STDOUT,
                                 check=False, timeout=timeout)
    seconds = time.monotonic() - started
    text = (evidence / "build.log").read_text(encoding="utf-8", errors="replace")
    if process.returncode or text.count("DOMELICA_COMPILED_BUILD_COMPLETE") != 1:
        raise RuntimeError("Native build failed; inspect evidence/build.log")
    prefix = configuration["prefix"]
    for suffix in ("", "_init.xml", "_visual.xml", "_info.json"):
        source = work / (prefix + suffix)
        if suffix != "_info.json" or source.is_file():
            shutil.copy2(source, native / source.name)
    metadata = parameter_metadata(native / (prefix + "_init.xml"))
    dependencies = shared_libraries(native / prefix, native / "lib")
    shutil.copy2(work / "native-toolchain.txt", evidence / "native-toolchain.txt")
    toolchain = dict(line.split("=", 1) for line in (evidence / "native-toolchain.txt").read_text().splitlines() if "=" in line)
    notices = collect_notices(bundle, dependencies, compiler, toolchain)
    model_hashes = {str(path.relative_to(frozen_source)): sha(path) for path in sorted(frozen_source.rglob("*")) if path.is_file()}
    report = {
        "schema": "domelica.compiled-model/v1", "model": configuration["model"], "prefix": prefix,
        "createdUTC": datetime.now(timezone.utc).isoformat(), "compilerInvocations": 1,
        "nativeSimulationsDuringBuild": 0, "buildSeconds": seconds, "toolchain": toolchain,
        "sourceCommit": os.environ.get("MODEL_SOURCE_REVISION", ""),
        "checkoutRevision": os.environ.get("CHECKOUT_REVISION", ""),
        "runUrl": os.environ.get("NATIVE_RUN_URL", ""), "modelSourceSHA256": model_hashes,
        "parameterMetadata": metadata, "dependencies": dependencies,
        "notices": notices,
        "platform": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "executable": "native/" + prefix, "initXML": "native/" + prefix + "_init.xml",
        "visualXML": "native/" + prefix + "_visual.xml", "loader": "native/lib/" + dependencies["loader"],
        "filesSHA256": {str(path.relative_to(bundle)): sha(path) for path in sorted(bundle.rglob("*")) if path.is_file()},
        "scope": "One Linux x86-64 assembly; four run-start Real parameters; no structural or geometry overrides.",
    }
    write_json(bundle / "build.json", report)
    return report


def verify_bundle(bundle):
    report = read_json(bundle / "build.json")
    if report.get("schema") != "domelica.compiled-model/v1" or report.get("compilerInvocations") != 1:
        raise ValueError("Expected a single-build native bundle")
    for relative, expected in report["filesSHA256"].items():
        path = beneath(bundle, relative)
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f"Compiled bundle file changed: {relative}")
    return report


def require_close(actual, expected, label, absolute=1e-10):
    if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=absolute):
        raise ValueError(f"Native parameter propagation failed: {label}: {actual} != {expected}")


def qualify_result(result, requested, simulation):
    """Check override propagation and initialization, not trajectory accuracy."""
    times = result.times
    if (len(times) < 2 or any(b < a for a, b in zip(times, times[1:]))
            or not math.isclose(times[0], simulation["startTime"], rel_tol=0, abs_tol=1e-10)
            or not math.isclose(times[-1], simulation["stopTime"], rel_tol=0, abs_tol=1e-10)):
        raise ValueError("Native recording did not complete its requested interval")
    checked = {}

    def constant(name, expected=None):
        values = result.column(name)
        value = values[0]
        if any(v != value for v in values):
            raise ValueError(f"Expected a constant native parameter: {name}")
        if expected is not None:
            require_close(value, expected, name)
        checked[name] = value
        return value

    actual = {name: constant(name, requested[name]) for name in PARAMETERS}
    for name in ("cartBody.m", "cartBody.body.m"):
        constant(name, actual["cartMass"])
    constant("bob.m", actual["bobMass"])
    constant("wallSpring.c", actual["springStiffness"])
    length, width, height = (constant(name) for name in ("cartLength", "cartWidth", "cartHeight"))
    constant("cartBody.density", actual["cartMass"] / (length * width * height))
    expected_inertia = [actual["cartMass"] * (width * width + height * height) / 12,
                        actual["cartMass"] * (length * length + width * width) / 12,
                        actual["cartMass"] * (length * length + height * height) / 12]
    for axis, expected in enumerate(expected_inertia, 1):
        for name in (f"cartBody.I[{axis},{axis}]", f"cartBody.body.I_{axis}{axis}"):
            constant(name, expected)
    for name in ("hinge.phi", "pendulumAngle"):
        require_close(result.column(name)[0], actual["initialAngle"], name + " at t=0")
        checked[name + " at t=0"] = result.column(name)[0]
    rod = constant("rodLength")
    delta = [result.column(f"bobPosition[{i}]")[0] - result.column(f"pivotPosition[{i}]")[0] for i in range(1, 4)]
    expected_delta = [rod * math.sin(actual["initialAngle"]), -rod * math.cos(actual["initialAngle"]), 0]
    for i, (value, expected) in enumerate(zip(delta, expected_delta), 1):
        require_close(value, expected, f"initial bob-pivot displacement[{i}]")
    checked["initialBobMinusPivot"] = delta
    return {"actualParameters": actual, "checkedNativeValues": checked, "samples": len(times),
            "startTime": times[0], "stopTime": times[-1],
            "dynamicTrajectorySHA256": hashlib.sha256(json.dumps({
                name: result.column(name) for name in ("cartDisplacement", "pendulumAngle")
            }, separators=(",", ":"), allow_nan=False).encode()).hexdigest()}


def run_case(bundle, build_report, configuration, output, case, timeout):
    from native_mat import NativeMatResult
    identity = valid_id(case["id"])
    requested = parameters_for(configuration["parameters"], case.get("parameters", {}))
    prefix = "m5c_" + identity.replace("-", "_")
    case_dir = output / "cases" / identity
    case_dir.mkdir(parents=True)
    executable = beneath(bundle, build_report["executable"])
    before = sha(executable)
    override_path = case_dir / "overrides.txt"
    override_path.write_text("".join(f"{name}={value:.17g}\n" for name, value in requested.items()), encoding="utf-8")
    result_path = output / (prefix + "_res.mat")
    command = [str(beneath(bundle, build_report["loader"])), "--library-path", str(bundle / "native/lib"),
               str(executable), "-f=" + str(beneath(bundle, build_report["initXML"])),
               "-inputPath=" + str(bundle / "native"), "-overrideFile=" + str(override_path),
               "-r=" + str(result_path), "-outputFormat=mat"]
    started = time.monotonic()
    with (case_dir / "native.log").open("w", encoding="utf-8") as log:
        process = subprocess.run(command, cwd=case_dir, stdout=log, stderr=subprocess.STDOUT,
                                 check=False, timeout=timeout)
    seconds = time.monotonic() - started
    log_text = (case_dir / "native.log").read_text(encoding="utf-8", errors="replace")
    after = sha(executable)
    if process.returncode or not re.search(r"LOG_SUCCESS\s*\|\s*info\s*\|\s*The simulation finished successfully\.", log_text):
        raise RuntimeError(f"Native run {identity} failed; inspect {case_dir / 'native.log'}")
    if before != after or before != build_report["filesSHA256"][build_report["executable"]]:
        raise ValueError("The compiled executable changed between runs")
    result = NativeMatResult(result_path)
    qualification = qualify_result(result, requested, configuration["prototypeExperiment"]["simulation"])
    result.write_csv(output / (prefix + "_res.csv"))
    shutil.copy2(beneath(bundle, build_report["visualXML"]), output / (prefix + "_visual.xml"))
    details = {"id": identity, "prefix": prefix, "requestedParameters": requested, **qualification,
               "command": command, "elapsedSimulationSeconds": seconds, "exitCode": process.returncode,
               "executableBeforeSHA256": before, "executableAfterSHA256": after,
               "nativeCompleted": True, "compilerInvocations": 0}
    write_json(case_dir / "run.json", details)
    actual = qualification["actualParameters"]
    experiment = copy.deepcopy(configuration["prototypeExperiment"])
    experiment.update({"id": identity, "prefix": prefix,
                       "title": case.get("label", "Custom parameters"), "shortTitle": case.get("label", identity),
                       "description": (f"Cart {actual['cartMass']:g} kg · bob {actual['bobMass']:g} kg · "
                                       f"spring {actual['springStiffness']:g} N/m · release {math.degrees(actual['initialAngle']):g}°. "
                                       "A fresh OpenModelica calculation using the same compiled executable. "
                                       "The rod is massless, the bob is a point mass, and joints and spring are ideal.")})
    observation = copy.deepcopy(configuration["prototypeObservation"])
    observation.update({"id": identity, "csv": prefix + "_res.csv"})
    observation["notes"] = observation.get("notes", []) + [
        "This recording was freshly simulated from the shared compiled assembly. Parameters are set before initialization; playback does not change them."]
    return experiment, observation, details


def execute(bundle_path, output_path, mode, identity, overrides, timeout, require_no_compiler=False):
    bundle = Path(bundle_path).resolve()
    build_report = verify_bundle(bundle)
    configuration = read_json(bundle / "configuration.json")
    environment = {name: shutil.which(name) for name in COMPILERS}
    if require_no_compiler and any(environment.values()):
        raise RuntimeError(f"Compiler-free acceptance requires these tools absent: {environment}")
    if mode == "presets":
        if overrides:
            raise ValueError("--set is only available with run, not presets")
        cases = configuration["presets"]
    else:
        cases = [{"id": valid_id(identity), "label": "Custom parameters", "parameters": overrides}]
    # Validate before creating output or launching any native process.
    for case in cases:
        parameters_for(configuration["parameters"], case.get("parameters", {}))
    output = Path(output_path).resolve()
    if output == bundle or output.is_relative_to(bundle):
        raise ValueError("Run results must be outside the immutable compiled bundle")
    output = empty_directory(output)
    source_name = Path(configuration["modelica"]["package"]).parent.name
    shutil.copytree(bundle / source_name, output / "source" / source_name)
    experiments, scenes, runs = [], [], []
    for case in cases:
        experiment, scene, run = run_case(bundle, build_report, configuration, output, case, timeout)
        experiments.append(experiment); scenes.append(scene); runs.append(run)
    verify_bundle(bundle)
    if len({run["dynamicTrajectorySHA256"] for run in runs}) != len(runs):
        raise ValueError("Different preset requests did not produce distinct motion recordings")
    report = {"schema": "domelica.compiled-runs/v1", "passed": True,
              "executionMode": "compiled-executable-reuse", "runtimeCompilerInvocations": 0,
              "runtimeEnvironment": {"tools": environment, "requireNoCompiler": require_no_compiler,
                                     "compilerToolsAbsent": not any(environment.values()),
                                     "platform": platform.platform(), "python": platform.python_version()},
              "buildManifestSHA256": sha(bundle / "build.json"),
              "executableSHA256": build_report["filesSHA256"][build_report["executable"]],
              "buildCompilerInvocations": build_report["compilerInvocations"], "runs": runs,
              "scope": "Parameter propagation, initialization pose, native completion and unchanged executable; no independent trajectory accuracy campaign."}
    write_json(output / "compiled-run-report.json", report)
    recording = {"kind": "fresh-native-run", "executionMode": "compiled-executable-reuse",
                 "createdUTC": datetime.now(timezone.utc).isoformat(),
                 "compiler": build_report["toolchain"]["compiler"], "toolchain": build_report["toolchain"],
                 "sourceCommit": build_report["sourceCommit"], "checkoutRevision": build_report["checkoutRevision"],
                 "runUrl": os.environ.get("NATIVE_RUN_URL", build_report["runUrl"]),
                 "modelSourceSHA256": build_report["modelSourceSHA256"],
                 "buildIdentity": {"manifestSHA256": report["buildManifestSHA256"], "executableSHA256": report["executableSHA256"],
                                   "initXMLSHA256": build_report["filesSHA256"][build_report["initXML"]],
                                   "visualXMLSHA256": build_report["filesSHA256"][build_report["visualXML"]]},
                 "runtimeCompilerInvocations": 0,
                 "completions": [{key: run[key] for key in ("id", "samples", "startTime", "stopTime")} for run in runs],
                 "parameterRuns": [{key: run[key] for key in ("id", "requestedParameters", "actualParameters")} for run in runs],
                 "inputsSHA256": {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob("*"))
                                  if path.is_file() and not path.is_relative_to(output / "source")}}
    manifest = {"schema": "domelica.experiments/v1", "modelica": configuration["modelica"],
                "renderer": configuration["renderer"], "observationManifest": "observations.json",
                "recording": recording, "experiments": experiments}
    write_json(output / "observations.json", {"schema": "domelica.observations/v1",
               "provenance": {"recording": recording, "newSimulation": True}, "scenes": scenes})
    write_json(output / "experiments.json", manifest)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "run", "presets"))
    parser.add_argument("--manifest", type=Path, default=ROOT / "viewer/compiled-experiments.json")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--id", default="custom")
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--require-no-compiler", action="store_true")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.mode == "build":
        if args.overrides or args.output_dir or args.require_no_compiler:
            parser.error("Runtime options do not apply to build")
        result = build(args.manifest, args.bundle, args.timeout)
        print(json.dumps({key: result[key] for key in ("model", "compilerInvocations", "nativeSimulationsDuringBuild", "buildSeconds", "parameterMetadata")}, indent=2))
    else:
        if args.output_dir is None:
            parser.error("run/presets requires --output-dir")
        result = execute(args.bundle, args.output_dir, args.mode, args.id, parse_overrides(args.overrides), args.timeout, args.require_no_compiler)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
