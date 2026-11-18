#!/usr/bin/env python3
"""Read-only diagnostic comparison of native state/solver configurations.

This file belongs to a separate diagnostic branch. It does not change the
production verifier or its physical gates, and it never rewrites native results.
The exact initial speed-response oracle addresses an observed discrepancy that
pointwise component identities cannot detect.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import traceback

import verify_m3 as physical


PREFIX = "m3_tanks_initial"
REQUIRED = (
    "time", "tankALevel", "tankBLevel", "levelError", "totalMass", "totalInternalEnergy",
    "pumpEnergy", "pumpPower", "transferredMass", "plant.tankB.m", "supplyFlow", "returnFlow",
    "pumpRPM", "pumpFraction", "filteredFraction", "filteredFractionDerivative",
)
ORACLE_STOP = 1.0
ORACLE_TOLERANCE = 1e-6
OPTIONAL = ("der(plant.pump.head)", "der(supplyFlow)", "der(plant.pump.V_flow)")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(REQUIRED)-set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing diagnostic native signals: {sorted(missing)}")
        names = (*REQUIRED, *(name for name in OPTIONAL if name in (reader.fieldnames or [])))
        rows = [{name: float(row[name]) for name in names} for row in reader]
    if not rows or not all(math.isfinite(value) for row in rows for value in row.values()):
        raise ValueError("Native CSV is empty or contains non-finite diagnostic values")
    if any(b["time"] < a["time"] for a, b in zip(rows, rows[1:])):
        raise ValueError("Native CSV time decreases")
    return rows


def audit(rows):
    first, last = rows[0], rows[-1]
    expected_mass = 995.586*(0.25*1.4+0.001)
    max_mass = max(abs(row["totalMass"]-expected_mass) for row in rows)
    max_storage = max(abs(row["totalInternalEnergy"]-first["totalInternalEnergy"]-row["pumpEnergy"])
                      for row in rows)
    max_transfer = max(abs(row["plant.tankB.m"]-first["plant.tankB.m"]-row["transferredMass"])
                       for row in rows)
    maximum_jump = max(zip(rows, rows[1:]), key=lambda pair: abs(pair[1]["totalMass"]-pair[0]["totalMass"]),
                       default=(first, first))
    before, after = maximum_jump
    result = dict(
        samples=len(rows), startTimeS=first["time"], stopTimeS=last["time"],
        complete300S=abs(first["time"]) <= 1e-9 and abs(last["time"]-300) <= 1e-9 and len(rows) >= 3001,
        maxAbsMassResidualKg=max_mass,
        maxAbsStoredInternalEnergyResidualJ=max_storage,
        maxAbsNativeTransferBalanceResidualKg=max_transfer,
        minimumPumpRPM=min(row["pumpRPM"] for row in rows),
        tankALevelRangeM=[min(row["tankALevel"] for row in rows), max(row["tankALevel"] for row in rows)],
        tankBLevelRangeM=[min(row["tankBLevel"] for row in rows), max(row["tankBLevel"] for row in rows)],
        largestMassIncrement=dict(
            fromTimeS=before["time"], toTimeS=after["time"],
            changeKg=after["totalMass"]-before["totalMass"],
            supplyFlowBeforeKgS=before["supplyFlow"], supplyFlowAfterKgS=after["supplyFlow"],
            pumpRPMBefore=before["pumpRPM"], pumpRPMAfter=after["pumpRPM"]),
    )
    sampled_work = absolute_work = integrated_speed_rate = absolute_speed_rate = squared_error = 0.0
    work_error_max = work_ratio_max = energy_ratio_max = speed_error_max = speed_ratio_max = 0.0
    previous = first
    for row in rows:
        dt = row["time"]-previous["time"]
        sampled_work += dt*(row["pumpPower"]+previous["pumpPower"])/2
        absolute_work += dt*(abs(row["pumpPower"])+abs(previous["pumpPower"]))/2
        # Reconstruct the declared ODE from its input/output, independently of
        # the exported native derivative alias. Native event duplicates have dt=0.
        rate = (row["pumpFraction"]-row["filteredFraction"])/2
        old_rate = (previous["pumpFraction"]-previous["filteredFraction"])/2
        integrated_speed_rate += dt*(rate+old_rate)/2
        absolute_speed_rate += dt*(abs(rate)+abs(old_rate))/2
        speed_error = row["filteredFraction"]-first["filteredFraction"]-integrated_speed_rate
        speed_tolerance = 0.0001+0.002*absolute_speed_rate
        work_error = row["pumpEnergy"]-sampled_work
        work_tolerance = 0.05+0.002*absolute_work
        energy_error = row["totalInternalEnergy"]-first["totalInternalEnergy"]-row["pumpEnergy"]
        work_error_max = max(work_error_max, abs(work_error))
        work_ratio_max = max(work_ratio_max, abs(work_error)/work_tolerance)
        energy_ratio_max = max(energy_ratio_max, abs(energy_error)/work_tolerance)
        speed_error_max = max(speed_error_max, abs(speed_error))
        speed_ratio_max = max(speed_ratio_max, abs(speed_error)/speed_tolerance)
        squared_error += dt*(row["levelError"]**2+previous["levelError"]**2)/2
        previous = row
    result.update(
        trackingRMSEM=math.sqrt(squared_error/max(last["time"]-first["time"], 1e-30)),
        finalPumpEnergyJ=last["pumpEnergy"], maxAbsSampledShaftEnergyResidualJ=work_error_max,
        maxShaftQuadratureToleranceRatio=work_ratio_max,
        maxStoredEnergyToleranceRatio=energy_ratio_max,
        integratedSpeedResponse=dict(
            maxAbsResidual=speed_error_max, maxToleranceRatio=speed_ratio_max,
            tolerance="0.0001 + 0.002 * cumulative absolute speed-fraction derivative integral",
            passed=speed_ratio_max <= 1),
    )
    initial_rows = [row for row in rows if row["time"] <= ORACLE_STOP+1e-9]
    constant_input = all(abs(row["pumpFraction"]-0.001) <= 1e-9 for row in initial_rows)
    correct_start = abs(first["filteredFraction"]-0.3) <= 1e-9 and abs(first["time"]) <= 1e-9
    complete_window = any(abs(row["time"]-ORACLE_STOP) <= 1e-9 for row in initial_rows)
    exact_errors = [abs(row["filteredFraction"]-(0.001+0.299*math.exp(-row["time"]/2)))
                    for row in initial_rows]
    worst = max(exact_errors, default=None)
    oracle = dict(
        formula="filteredFraction(t) = 0.001 + 0.299 * exp(-t/2)",
        windowStartS=0.0, windowStopS=ORACLE_STOP, observedSamples=len(initial_rows),
        inputIsConstantAtLowerLimit=constant_input, correctInitialState=correct_start,
        completeWindow=complete_window, maxAbsError=worst, tolerance=ORACLE_TOLERANCE,
        passed=constant_input and correct_start and complete_window and worst is not None and worst <= ORACLE_TOLERANCE,
    )
    sample01 = min(initial_rows, key=lambda row: abs(row["time"]-0.1), default=None)
    if sample01 is not None:
        oracle["nearPointOneSeconds"] = dict(
            timeS=sample01["time"], actual=sample01["filteredFraction"],
            expected=0.001+0.299*math.exp(-sample01["time"]/2))
    result["exactInitialSpeedResponse"] = oracle
    windows = []
    for start, stop, target in physical.PLATEAUS:
        selected = [row for row in rows if stop-20 <= row["time"] < stop-1e-7
                    or (stop == 300 and abs(row["time"]-stop) <= 1e-7)]
        complete = last["time"] >= stop-1e-9 and len(selected) >= 199
        maximum = max((abs(row["tankBLevel"]-target) for row in selected), default=None)
        windows.append(dict(startS=stop-20, stopS=stop, targetM=target, samples=len(selected),
                            complete=complete, maxAbsErrorM=maximum,
                            passed=complete and maximum is not None and maximum <= physical.TRACKING_BAND))
    result["trackingWindows"] = windows
    derivative_rows = [row for row in rows if row["supplyFlow"] > 1e-5
                       and "der(plant.pump.head)" in row
                       and ("der(supplyFlow)" in row or "der(plant.pump.V_flow)" in row)]
    derivative_audit = dict(available=bool(derivative_rows), samples=len(derivative_rows),
                            scope="Open pump check valve only, supplyFlow > 1e-5 kg/s",
                            toleranceMPerS=1e-5)
    if derivative_rows:
        worst_error, worst_example = 0.0, None
        for row in derivative_rows:
            ratio = row["pumpRPM"]/1200
            ratio_derivative = row["filteredFractionDerivative"]
            flow = row["supplyFlow"]/995.586
            flow_derivative = row["der(supplyFlow)"]/995.586 if "der(supplyFlow)" in row else row["der(plant.pump.V_flow)"]
            nominal_flow = flow/ratio
            if nominal_flow < 0:
                head, slope = 10-250*nominal_flow, -250
            elif nominal_flow > 0.008:
                head, slope = -2250*(nominal_flow-0.008), -2250
            else:
                head, slope = 10-250*nominal_flow-125000*nominal_flow**2, -250-250000*nominal_flow
            expected = 2*ratio*ratio_derivative*head + slope*(ratio*flow_derivative-flow*ratio_derivative)
            actual = row["der(plant.pump.head)"]
            error = abs(actual-expected)
            if error > worst_error:
                worst_error = error
                worst_example = dict(timeS=row["time"], nativeDerivativeMPerS=actual,
                                     chainRuleDerivativeMPerS=expected)
        derivative_audit.update(maxAbsErrorMPerS=worst_error, worstExample=worst_example,
                                passed=worst_error <= 1e-5)
    result["nativePumpHeadDerivative"] = derivative_audit
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", help="Diagnostic matrix label")
    parser.add_argument("--results-root", type=Path, default=physical.ROOT)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.candidate):
        parser.error("candidate must contain only letters, digits, underscores, and hyphens")
    result_root = args.results_root.resolve()
    output_dir = args.output_dir or result_root / "artifacts/m3-state-diagnostics" / args.candidate
    output_dir.mkdir(parents=True, exist_ok=True)
    report = dict(schema="domelica.fluid-state-diagnostic.v1", candidate=args.candidate,
                  prefix=PREFIX, passed=False,
                  productionVerifierSHA256=digest(Path(physical.__file__)),
                  diagnosticVerifierSHA256=digest(Path(__file__)),
                  definitions=dict(
                      productionGates="The unchanged verify_m3.verify_case for m3-initial is executed directly.",
                      oracle="An independent exact response is valid only while the observed native input stays at 0.001 and the initial output is 0.3.",
                      purpose="Diagnostic solver comparison; this is not a published production acceptance artifact."))
    for suffix, key in (("_res.csv", "nativeCSV_SHA256"), ("_res.mat", "nativeMAT_SHA256"), (".log", "nativeLogSHA256")):
        path = result_root / (PREFIX+suffix)
        if path.is_file():
            report[key] = digest(path)
    try:
        rows = read_rows(result_root / (PREFIX+"_res.csv"))
        report["audit"] = audit(rows)
    except Exception as error:
        report["auditError"] = f"{type(error).__name__}: {error}"
    try:
        physical.ROOT = result_root
        case = next(case for case in physical.CASES if case["id"] == "m3-initial")
        case_result = physical.verify_case(case)
        report["productionGates"] = dict(passed=True, metrics=case_result["metrics"],
                                         verification=case_result["verification"])
    except Exception as error:
        report["productionGates"] = dict(passed=False, error=f"{type(error).__name__}: {error}",
                                         traceback=traceback.format_exc().splitlines()[-8:])
    audit_result = report.get("audit", {})
    report["passed"] = bool(
        report["productionGates"]["passed"] and audit_result.get("complete300S")
        and audit_result.get("exactInitialSpeedResponse", {}).get("passed")
        and audit_result.get("integratedSpeedResponse", {}).get("passed")
        and (not audit_result.get("nativePumpHeadDerivative", {}).get("available")
             or audit_result["nativePumpHeadDerivative"].get("passed")))
    output_path = output_dir / "verification.json"
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(dict(candidate=args.candidate, passed=report["passed"],
                         productionGates=report["productionGates"]["passed"],
                         maxAbsMassResidualKg=audit_result.get("maxAbsMassResidualKg"),
                         exactSpeedError=audit_result.get("exactInitialSpeedResponse", {}).get("maxAbsError"),
                         report=str(output_path)), allow_nan=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
