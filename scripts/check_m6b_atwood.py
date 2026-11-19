#!/usr/bin/env python3
"""Independent closed-form Atwood verification of fresh Modelica Q68 results."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path


def check(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {
            "time", "lightMass", "heavyMass", "g", "lightDisplacement",
            "heavyDisplacement", "lightSpeed", "heavySpeed", "lightTension",
            "heavyTension", "lightStringLength", "heavyStringLength",
            "stringLength", "totalEnergy", "lightBob.m", "heavyBob.m",
        }
        for side in ("light", "heavy"):
            for name in ("Position", "Velocity", "Acceleration", "StringOnBob"):
                required.update(f"{side}{name}[{i}]" for i in range(1, 4))
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError("Missing native columns: " + ", ".join(missing))
        rows = list(reader)
    if len(rows) < 900:
        raise ValueError("Insufficient native samples")

    def read(row, key):
        value = float(row[key])
        if not math.isfinite(value):
            raise ValueError("Non-finite native value: " + key)
        return value

    times = [read(row, "time") for row in rows]
    if not math.isclose(times[0], 0, abs_tol=1e-12) \
            or not math.isclose(times[-1], 2, abs_tol=1e-10) \
            or any(b < a for a, b in zip(times, times[1:])):
        raise ValueError("Wrong native simulation time window")

    m, M, g = (read(rows[0], k) for k in ("lightBob.m", "heavyBob.m", "g"))
    if abs(m - 13) > 1e-10 or abs(M - 15) > 1e-10 \
            or abs(g - 9.8) > 1e-10:
        raise ValueError("Nominal exercise parameters must be 13:15 and g=9.8")
    a = (M-m)*g/(M+m)
    T = 2*m*M*g/(M+m)
    if not math.isclose(a, 0.7, abs_tol=1e-12):
        raise ValueError("Analytic acceleration mismatch")

    height0 = {
        "light": read(rows[0], "lightPosition[2]"),
        "heavy": read(rows[0], "heavyPosition[2]"),
    }
    initial_rope = read(rows[0], "stringLength")
    initial_energy = read(rows[0], "totalEnergy")
    checks = {
        "samples": len(rows), "analyticAcceleration_mps2": a,
        "analyticTension_N": T, "analyticMassRatio": m/M,
        "maxDisplacementError_m": 0.0, "maxVelocityError_mps": 0.0,
        "maxAccelerationError_mps2": 0.0, "maxTensionError_N": 0.0,
        "maxConstraintError_m": 0.0, "maxStringLengthDrift_m": 0.0,
        "maxForceBalanceResidual_N": 0.0, "maxEnergyRelativeDrift": 0.0,
        "minNativeTension_N": float("inf"),
    }

    for row, t in zip(rows, times):
        d = 0.5*a*t*t
        v = a*t
        for side, sign in (("light", 1), ("heavy", -1)):
            y = read(row, f"{side}Position[2]")
            vy = read(row, f"{side}Velocity[2]")
            ay = read(row, f"{side}Acceleration[2]")
            mass = m if side == "light" else M
            tension = read(row, f"{side}Tension")
            force = [read(row, f"{side}StringOnBob[{i}]") for i in range(1, 4)]
            acceleration = [read(row, f"{side}Acceleration[{i}]") for i in range(1, 4)]
            velocity = [read(row, f"{side}Velocity[{i}]") for i in range(1, 4)]
            position = [read(row, f"{side}Position[{i}]") for i in range(1, 4)]
            checks["maxDisplacementError_m"] = max(checks["maxDisplacementError_m"],
                abs(y-height0[side]-sign*d),
                abs(read(row,f"{side}Displacement")-d))
            checks["maxVelocityError_mps"] = max(checks["maxVelocityError_mps"],
                abs(vy-sign*v),abs(read(row,f"{side}Speed")-v))
            checks["maxAccelerationError_mps2"] = max(checks["maxAccelerationError_mps2"],
                abs(ay-sign*a))
            checks["maxTensionError_N"] = max(checks["maxTensionError_N"],
                abs(tension-T),abs(force[1]-T))
            checks["minNativeTension_N"] = min(checks["minNativeTension_N"], tension)
            residual = math.sqrt(sum(
                (mass*acceleration[i]-force[i]+(mass*g if i==1 else 0))**2
                for i in range(3)))
            checks["maxForceBalanceResidual_N"] = max(
                checks["maxForceBalanceResidual_N"], residual)
            if abs(velocity[0])>1e-7 or abs(velocity[2])>1e-7 or abs(position[2])>1e-7:
                raise ValueError("The bobs unexpectedly left their vertical guide plane")

        checks["maxConstraintError_m"] = max(checks["maxConstraintError_m"],
            abs(read(row,"lightDisplacement")-read(row,"heavyDisplacement")),
            abs((read(row,"lightPosition[2]")-height0["light"]) +
                (read(row,"heavyPosition[2]")-height0["heavy"])))
        checks["maxStringLengthDrift_m"] = max(checks["maxStringLengthDrift_m"],
            abs(read(row,"stringLength")-initial_rope))
        checks["maxEnergyRelativeDrift"] = max(checks["maxEnergyRelativeDrift"],
            abs(read(row,"totalEnergy")-initial_energy)/max(1,abs(initial_energy)))
        if not read(row,"lightStringLength")>0.25 or not read(row,"heavyStringLength")>0.25:
            raise ValueError("String segment contacted idealized pulley endpoint")

    checks["lightFinalRise_m"] = (
        read(rows[-1],"lightPosition[2]")-height0["light"])
    checks["heavyFinalDrop_m"] = (
        height0["heavy"]-read(rows[-1],"heavyPosition[2]"))
    limits = {
        "maxDisplacementError_m": 2e-4, "maxVelocityError_mps": 2e-4,
        "maxAccelerationError_mps2": 1e-4, "maxTensionError_N": 2e-3,
        "maxConstraintError_m": 1e-6, "maxStringLengthDrift_m": 1e-6,
        "maxForceBalanceResidual_N": 1e-4, "maxEnergyRelativeDrift": 1e-5,
    }
    failed = [k for k, limit in limits.items() if checks[k] > limit]
    if checks["minNativeTension_N"] <= 0:
        failed.append("nonpositiveTension")
    if abs(checks["lightFinalRise_m"]-1.4)>2e-4 \
            or abs(checks["heavyFinalDrop_m"]-1.4)>2e-4:
        failed.append("Q68FinalDisplacement")
    if failed:
        raise ValueError("Atwood native/analytic check failed: " +
                         ", ".join(f"{key}={checks.get(key)!r}" for key in failed))
    return {
        "passed": True, "model": "DomelicaLab.Examples.AtwoodFixedPulley3D",
        "checks": checks,
        "scope": "Nominal 0-2 s analytic Atwood trajectory, force balance and constrained geometry at every native sample; no new numerical dynamics solver.",
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    try:
        result=check(args.csv)
    except Exception as error:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({"passed":False,"error":str(error)},indent=2)+"\n")
        raise
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
