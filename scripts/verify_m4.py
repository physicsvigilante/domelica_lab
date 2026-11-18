#!/usr/bin/env python3
"""Check native motion against independent closed-form and balance oracles.

The two nominal problem definitions are fixed below, not read from the solver.
The formulas are used only for verification. The viewer receives native results.
--completion-only uses OpenModelica's own MAT reader and fresh simulation log;
normal verification consumes and validates that hash-bound evidence as well as CSV.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_completion(prefix, stop, minimum_samples):
    """No partial MAT, stale log, or initialization-only success is accepted."""
    from export_native_csv import NativeBatchReader, _query, _read_columns

    prefix = Path(prefix)
    mat_path = Path(str(prefix) + "_res.mat").resolve()
    log_path = Path(str(prefix) + ".log").resolve()
    xml_path = Path(str(prefix) + "_visual.xml").resolve()
    for path in (mat_path, log_path, xml_path):
        if not path.is_file():
            raise ValueError(f"Missing current native output: {path.name}")
    log = log_path.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^LOG_SUCCESS\s*\|\s*info\s*\|\s*The simulation finished successfully\.\s*$",
                     log, re.MULTILINE):
        raise ValueError(f"{prefix.name}: native log does not confirm completed simulation")
    if not re.search(r"^LOG_SUCCESS\s*\|\s*info\s*\|\s*The initialization finished successfully", log, re.MULTILINE):
        raise ValueError(f"{prefix.name}: native log does not confirm initialization")
    with tempfile.TemporaryDirectory(prefix="domelica-motion-completion-") as directory:
        reader = NativeBatchReader(directory)
        count = _query(reader, f"readSimulationResultSize({json.dumps(str(mat_path))})")
        if type(count) is not int or count < minimum_samples:
            raise ValueError(f"{prefix.name}: {count} native samples; need {minimum_samples}")
        times = _read_columns(reader, mat_path, ["time"], count)[0]
        compiler = _query(reader, "getVersion()")
    if (any(b < a for a, b in zip(times, times[1:]))
            or abs(times[0]) > 1e-9 or abs(times[-1]-stop) > 1e-9):
        raise ValueError(f"{prefix.name}: native times {times[0]}..{times[-1]}; expected 0..{stop}")
    proof = {
        "passed": True, "prefix": prefix.name, "compiler": compiler,
        "samples": count, "startTime": times[0], "stopTime": times[-1],
        "nativeTimeSHA256": hashlib.sha256(json.dumps(times, separators=(",", ":")).encode()).hexdigest(),
        "inputsSHA256": {p.name: digest(p) for p in (mat_path, log_path, xml_path)},
    }
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / f"{prefix.name}-completion.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(f"PASS native completion: {prefix.name}; {count} samples; {times[0]}..{times[-1]} s", flush=True)
    return proof


def read_case(prefix, stop, minimum_samples, required):
    csv_path = ROOT / f"{prefix}_res.csv"
    proof_path = ROOT / "artifacts" / f"{prefix}-completion.json"
    proof = json.loads(proof_path.read_text())
    if proof.get("passed") is not True or proof.get("prefix") != prefix:
        raise AssertionError(f"{prefix}: invalid completion evidence")
    for name in (f"{prefix}_res.mat", f"{prefix}.log", f"{prefix}_visual.xml"):
        if proof.get("inputsSHA256", {}).get(name) != digest(ROOT / name):
            raise AssertionError(f"{prefix}: changed or unbound native input {name}")
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames or []
        if len(names) != len(set(names)) or set(required)-set(names):
            raise AssertionError(f"{prefix}: duplicate columns or missing {sorted(set(required)-set(names))}")
        rows = []
        for i, source in enumerate(reader, 2):
            if None in source or None in source.values():
                raise AssertionError(f"{prefix}: malformed CSV line {i}")
            row = {name: float(source[name]) for name in required}
            if not all(math.isfinite(value) for value in row.values()):
                raise AssertionError(f"{prefix}: nonfinite native value on line {i}")
            rows.append(row)
    if len(rows) < minimum_samples or len(rows) != proof["samples"]:
        raise AssertionError(f"{prefix}: CSV sample count disagrees with native completion evidence")
    times = [r["time"] for r in rows]
    if (abs(times[0]) > 1e-9 or abs(times[-1]-stop) > 1e-9
            or any(b<a for a,b in zip(times,times[1:]))):
        raise AssertionError(f"{prefix}: incomplete or unordered CSV time coverage")
    native_time_hash = hashlib.sha256(json.dumps(times, separators=(",", ":")).encode()).hexdigest()
    if native_time_hash != proof["nativeTimeSHA256"]:
        raise AssertionError(f"{prefix}: CSV time sequence differs from native MAT sequence")
    return rows


def require_close(actual, expected, tolerance, context):
    if abs(actual-expected) > tolerance:
        raise AssertionError(f"{context}: actual {actual:.12g}, expected {expected:.12g}, tolerance {tolerance:g}")


def vector(row, name):
    return [row[f"{name}[{i}]"] for i in (1,2,3)]


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def track(maxima, name, actual, expected, tolerance, time):
    error = abs(actual-expected)
    maxima[name] = max(maxima.get(name, 0.0), error)
    require_close(actual, expected, tolerance, f"{name} at {time:.9g} s")


def common_columns():
    return ["time", "displacement", "speed", "acceleration", "kineticEnergy",
            "potentialEnergy", "totalEnergy", "massBody.m", "guide.s", "guide.v", "guide.a"] + [
        f"{name}[{axis}]" for name in ("position", "velocity", "guideReaction", "massBody.frame_a.r_0", "massBody.v_0")
        for axis in (1,2,3)]


def verify_groove():
    rows = read_case("m4_groove_slide", 2, 401, common_columns()+["normalReaction", "sideReaction", "reactionPower"])
    # Definition from Q31 and the declared visualization choices, independently
    # written here. No parameters or aliases are used to construct the oracle.
    mass, gravity, alpha, beta, length, center_offset = 1.0, 10.0, math.pi/6, math.pi/6, 5.0, 0.094
    direction = [math.sin(beta)*math.cos(alpha), math.sin(beta)*math.sin(alpha), math.cos(beta)]
    normal = [-math.sin(alpha), math.cos(alpha), 0.0]
    initial = [length*d+center_offset*n for d,n in zip(direction,normal)]
    accel = gravity*math.sin(alpha)*math.sin(beta)
    reaction = [-mass*accel*direction[0], mass*(gravity-accel*direction[1]), -mass*accel*direction[2]]
    energy0 = mass*gravity*initial[1]
    maxima = {}
    for row in rows:
        t = row["time"]
        q, v = 0.5*accel*t*t, accel*t
        track(maxima,"displacementError_m",row["displacement"],q,5e-7,t)
        track(maxima,"speedError_m_s",row["speed"],v,5e-7,t)
        track(maxima,"accelerationError_m_s2",row["acceleration"],accel,5e-7,t)
        require_close(row["massBody.m"],mass,1e-12,"Q31 declared body mass")
        for alias, component in (("displacement","guide.s"),("speed","guide.v"),("acceleration","guide.a")):
            require_close(row[alias],row[component],1e-12,f"Q31 {alias} alias")
        for j in range(3):
            actual = row[f"position[{j+1}]"]
            track(maxima,"positionError_m",actual,initial[j]-direction[j]*q,5e-7,t)
            require_close(actual,row[f"massBody.frame_a.r_0[{j+1}]"],1e-12,"Q31 native center")
            track(maxima,"velocityError_m_s",row[f"velocity[{j+1}]"],-direction[j]*v,5e-7,t)
            require_close(row[f"velocity[{j+1}]"],row[f"massBody.v_0[{j+1}]"],1e-12,"Q31 native velocity")
            track(maxima,"reactionError_N",row[f"guideReaction[{j+1}]"],reaction[j],1e-6,t)
        require_close(row["normalReaction"],mass*gravity*math.cos(alpha),1e-6,"Q31 plane normal reaction")
        require_close(row["sideReaction"],mass*gravity*math.sin(alpha)*math.cos(beta),1e-6,"Q31 groove side reaction")
        if row["normalReaction"] <= 0:
            raise AssertionError("Q31 requires a positive plane contact reaction")
        require_close(row["reactionPower"],0,1e-6,"Q31 constraint does no work")
        actual_energy = 0.5*mass*dot(vector(row,"velocity"),vector(row,"velocity"))+mass*gravity*row["position[2]"]
        track(maxima,"energyDrift_J",actual_energy,energy0,1e-5,t)
        require_close(row["kineticEnergy"],0.5*mass*dot(vector(row,"velocity"),vector(row,"velocity")),1e-9,"Q31 kinetic monitor")
        require_close(row["potentialEnergy"],mass*gravity*row["position[2]"],1e-9,"Q31 potential monitor")
        require_close(row["totalEnergy"],actual_energy,1e-9,"Q31 total energy monitor")
        if not -5e-7 <= row["displacement"] <= length+5e-7:
            raise AssertionError("Q31 output extends beyond the finite groove")
    require_close(rows[-1]["displacement"],length,5e-7,"Q31 arrival at O")
    return {"passed": True, "model": "DomelicaLab.Examples.GrooveSlide3D",
            "samples": len(rows), "startTime": rows[0]["time"], "stopTime": rows[-1]["time"],
            "arrivalTime_s": rows[-1]["time"], "travel_m": rows[-1]["displacement"],
            "terminalSpeed_m_s": rows[-1]["speed"], "maxErrors": maxima,
            "scope": "Gravity-driven constrained motion through arrival; no end impact"}


def verify_springs():
    required = common_columns()+["upperExtension", "lowerExtension", "upperForce", "lowerForce",
        "gravitationalEnergy", "elasticEnergy", "upperSpring.length", "lowerSpring.length",
        "upperSpring.f", "lowerSpring.f", "upperSpring.frame_b.f[2]", "lowerSpring.frame_a.f[2]"]
    rows = read_case("m4_two_spring", 6, 1201, required)
    mass, gravity, ku, kl, free_length = 4.0, 10.0, 100.0, 300.0, 0.6
    omega = math.sqrt((ku+kl)/mass)
    equilibrium = mass*gravity/(ku+kl)
    maxima = {}
    for row in rows:
        t = row["time"]
        q = equilibrium*(1-math.cos(omega*t))
        v = equilibrium*omega*math.sin(omega*t)
        a = gravity*math.cos(omega*t)
        track(maxima,"displacementError_m",row["displacement"],q,5e-7,t)
        track(maxima,"speedError_m_s",row["speed"],v,5e-6,t)
        track(maxima,"accelerationError_m_s2",row["acceleration"],a,5e-5,t)
        require_close(row["massBody.m"],mass,1e-12,"Q90 declared body mass")
        for alias, component in (("displacement","guide.s"),("speed","guide.v"),("acceleration","guide.a")):
            require_close(row[alias],row[component],1e-12,f"Q90 {alias} alias")
        for j, expected in enumerate((0,-q,0)):
            track(maxima,"positionError_m",row[f"position[{j+1}]"],expected,5e-7,t)
            require_close(row[f"position[{j+1}]"],row[f"massBody.frame_a.r_0[{j+1}]"],1e-12,"Q90 native center")
            require_close(row[f"velocity[{j+1}]"],row[f"massBody.v_0[{j+1}]"],1e-12,"Q90 native velocity")
            require_close(row[f"guideReaction[{j+1}]"],0,1e-6,"Q90 unforced guide")
        track(maxima,"velocityError_m_s",row["velocity[2]"],-v,5e-6,t)
        actual_q = row["displacement"]
        require_close(row["upperExtension"],actual_q,1e-9,"Q90 upper spring stretches")
        require_close(row["lowerExtension"],-actual_q,1e-9,"Q90 lower spring compresses")
        require_close(row["upperSpring.length"],free_length+actual_q,1e-9,"Q90 upper spring geometry")
        require_close(row["lowerSpring.length"],free_length-actual_q,1e-9,"Q90 lower spring geometry")
        require_close(row["upperForce"],-row["upperSpring.frame_b.f[2]"],1e-10,"Q90 upper native connector force")
        require_close(row["lowerForce"],-row["lowerSpring.frame_a.f[2]"],1e-10,"Q90 lower native connector force")
        track(maxima,"springForceResidual_N",row["upperForce"],ku*actual_q,1e-6,t)
        track(maxima,"springForceResidual_N",row["lowerForce"],kl*actual_q,1e-6,t)
        require_close(row["upperSpring.f"],ku*actual_q,1e-6,"Q90 signed upper line force")
        require_close(row["lowerSpring.f"],-kl*actual_q,1e-6,"Q90 signed lower line force")
        balance = mass*row["acceleration"] - (mass*gravity-row["upperForce"]-row["lowerForce"])
        track(maxima,"forceBalanceResidual_N",balance,0,1e-6,t)
        ke = 0.5*mass*dot(vector(row,"velocity"),vector(row,"velocity"))
        grav = mass*gravity*row["position[2]"]
        elastic = 0.5*ku*row["upperExtension"]**2+0.5*kl*row["lowerExtension"]**2
        actual_energy = ke+grav+elastic
        track(maxima,"energyDrift_J",actual_energy,0,5e-5,t)
        for name,expected in (("kineticEnergy",ke),("gravitationalEnergy",grav),("elasticEnergy",elastic),
                              ("potentialEnergy",grav+elastic),("totalEnergy",actual_energy)):
            require_close(row[name],expected,1e-9,f"Q90 {name} monitor")
        if min(row["upperSpring.length"],row["lowerSpring.length"]) <= 0.39:
            raise AssertionError("Q90 leaves its qualified spring-length range")
    # Verify enough actual movement and reversals exist to exercise visible motion.
    if max(r["displacement"] for r in rows)-min(r["displacement"] for r in rows) < 0.19:
        raise AssertionError("Q90 did not complete the intended oscillation amplitude")
    reversals = sum(a["speed"]*b["speed"]<0 for a,b in zip(rows,rows[1:]))
    if reversals < 18:
        raise AssertionError(f"Q90 insufficient velocity reversals: {reversals}")
    return {"passed": True, "model": "DomelicaLab.Examples.TwoSpringOscillator3D",
            "samples": len(rows), "startTime": rows[0]["time"], "stopTime": rows[-1]["time"],
            "equilibriumDrop_m": equilibrium, "analyticalPeriod_s": 2*math.pi/omega,
            "observedTravelRange_m": [min(r["displacement"] for r in rows),max(r["displacement"] for r in rows)],
            "velocityReversals": reversals, "maxErrors": maxima,
            "scope": "Ideal massless undamped linear springs and constrained vertical motion"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completion-only", nargs=3, metavar=("PREFIX","STOP","MIN_SAMPLES"))
    args = parser.parse_args()
    if args.completion_only:
        prefix, stop, count = args.completion_only
        stop, count = float(stop), int(count)
        if not math.isfinite(stop) or stop <= 0 or count < 2:
            parser.error("positive finite stop and minimum of two samples required")
        check_completion(prefix, stop, count)
        return
    cases = {"groove-slide": verify_groove(), "two-spring": verify_springs()}
    source_files = [Path(__file__), ROOT/"scripts/native_m4.mos", ROOT/"scripts/export_native_csv.py",
        ROOT/"DomelicaLab/Examples/GrooveSlide3D.mo", ROOT/"DomelicaLab/Examples/TwoSpringOscillator3D.mo",
        ROOT/"DomelicaLab/package.mo", ROOT/"DomelicaLab/package.order",
        ROOT/"DomelicaLab/Examples/package.mo", ROOT/"DomelicaLab/Examples/package.order"]
    input_files = [ROOT/f"{prefix}{suffix}" for prefix in ("m4_groove_slide","m4_two_spring")
                   for suffix in ("_res.mat","_res.csv","_visual.xml",".log")]
    input_files += [ROOT/"artifacts"/f"{prefix}-completion.json" for prefix in ("m4_groove_slide","m4_two_spring")]
    input_files += [ROOT/"m4-native-toolchain.txt"]
    report = {"passed": True, "cases": cases,
        "method": "Closed-form nominal trajectories, world geometry, native component forces and independent energy balances at every native sample",
        "sourceSHA256": {str(p.relative_to(ROOT)):digest(p) for p in source_files},
        "inputsSHA256": {str(p.relative_to(ROOT)):digest(p) for p in input_files},
        "limitations": ["Nominal simulations only; no collision, coil contact, damping or experimental validation.",
            "Q31's run ends at the groove endpoint with nonzero speed; no impact law is implied.",
            "Native GUI animation and browser rendering require separate visual verification."]}
    out = ROOT/"artifacts/m4-metrics.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2)+"\n")
    for name, case in cases.items():
        print(f"PASS {name}: {case['samples']} native samples, errors {json.dumps(case['maxErrors'],sort_keys=True)}")
    print(f"PASS M4 physics report: {out}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
