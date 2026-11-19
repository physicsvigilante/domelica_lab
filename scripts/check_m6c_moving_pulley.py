#!/usr/bin/env python3
"""Independent Newton/energy oracle for native M6C-2D-B CSV recordings.

This checker reads saved native variables; it never generates animation data.
For upward load displacement q and downward counterweight displacement 2q:
    2*T - M*g = M*a; m*g - T = 2*m*a.
Thus a=(2*m-M)*g/(M+4*m), T=3*M*m*g/(M+4*m).
"""
from __future__ import annotations

import argparse
import csv
import json
from math import isfinite, pi
from pathlib import Path


def check(csv_path: Path) -> dict:
    with csv_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    if len(rows) < 3:
        raise ValueError("Expected a sampled native moving-pulley recording")

    def value(row, column):
        number = float(row[column])
        if not isfinite(number):
            raise ValueError(f"Nonfinite native column {column}")
        return number

    first = rows[0]
    M, m, g, r, H, y0, z0 = (
        value(first, column) for column in (
            "loadMass", "counterweightMass", "g", "pulleyRadius",
            "fixedHeight", "initialPulleyHeight", "initialCounterweightHeight"))
    if min(M, m, g, r) <= 0:
        raise ValueError("Native masses, gravity and radius must be positive")
    t0 = value(first, "time")
    a = (2*m-M)*g/(M+4*m)
    tension = 3*M*m*g/(M+4*m)
    initial_length = 3*H-2*y0-z0+2*pi*r
    initial_energy = g*(M*y0+m*z0)
    maxima = {name: 0.0 for name in (
        "position_m", "velocity_m_s", "acceleration_m_s2", "tension_N",
        "displacement_constraint_m", "velocity_constraint_m_s",
        "acceleration_constraint_m_s2", "force_balance_N",
        "constraint_power_W", "energy_J", "rope_length_m")}

    def error(name, *residuals):
        maxima[name] = max(maxima[name], *(abs(x) for x in residuals))

    previous_time = t0
    for row in rows:
        time = value(row, "time")
        if time < previous_time:
            raise ValueError("Native times must be nondecreasing")
        previous_time = time
        elapsed = time-t0
        q, v = a*elapsed*elapsed/2, a*elapsed
        qs, zs, vs, ws, T, F = (value(row, c) for c in (
            "loadDisplacement", "counterweightDisplacement", "loadSpeed",
            "counterweightSpeed", "ropeTension", "loadSupportForce"))
        y, z, ay, az = (value(row, c) for c in (
            "loadPosition[2]", "counterweightPosition[2]",
            "loadAcceleration[2]", "counterweightAcceleration[2]"))
        for prefix, expected_position, expected_velocity, expected_acceleration in (
            ("load", (0, y0+q, 0), (0, v, 0), (0, a, 0)),
            ("counterweight", (3*r, z0-2*q, 0), (0, -2*v, 0), (0, -2*a, 0)),
        ):
            for i in range(3):
                error("position_m", value(row, f"{prefix}Position[{i+1}]")-expected_position[i])
                error("velocity_m_s", value(row, f"{prefix}Velocity[{i+1}]")-expected_velocity[i])
                error("acceleration_m_s2", value(row, f"{prefix}Acceleration[{i+1}]")-expected_acceleration[i])
        for prefix, expected in (
            ("movingPulleyCenter", (0, y0+q, 0)),
            ("fixedPulleyCenter", (2*r, H, 0)),
            ("anchorPosition", (-r, H, 0)),
        ):
            for i, coordinate in enumerate(expected, start=1):
                error("position_m", value(row, f"{prefix}[{i}]")-coordinate)
        error("position_m", qs-q, zs-2*q)
        error("velocity_m_s", vs-v, ws-2*v)
        error("tension_N", T-tension, F-2*tension,
              value(row, "counterweightTension")-tension)
        for prefix, expected in (
            ("loadSupportOnBody", (0, 2*tension, 0)),
            ("counterweightStringOnBody", (0, tension, 0)),
        ):
            for i, component in enumerate(expected, start=1):
                error("tension_N", value(row, f"{prefix}[{i}]")-component)
        error("displacement_constraint_m", zs-2*qs, 2*(y-y0)+(z-z0))
        error("velocity_constraint_m_s", ws-2*vs)
        error("acceleration_constraint_m_s2", az+2*ay)
        error("force_balance_N", F-M*g-M*ay, T-m*g-m*az, F-2*T)
        error("constraint_power_W", F*vs-T*ws)
        independent_kinetic = (M*vs*vs+m*ws*ws)/2
        independent_gravitational = g*(M*y+m*z)
        error("energy_J", independent_kinetic+independent_gravitational-initial_energy,
              value(row, "kineticEnergy")-independent_kinetic,
              value(row, "gravitationalEnergy")-independent_gravitational,
              value(row, "totalEnergy")-initial_energy)
        error("rope_length_m", value(row, "stringLength")-initial_length,
              3*H-2*y-z+2*pi*r-initial_length)
        if T <= 0 or F <= 0 or min(H-y, H-z) <= 0.25 or min(y-r, z) <= 0.2:
            raise ValueError("Recording left the nominal taut, collision-free domain")

    if previous_time-t0 <= 0 or abs(value(rows[-1], "loadDisplacement")) < 1e-3:
        raise ValueError("Expected genuine moving-pulley motion")
    tolerances = {name: 1e-6 for name in maxima}
    tolerances["energy_J"] = 1e-6*max(1, abs(initial_energy))
    failed = {name: maximum for name, maximum in maxima.items() if maximum > tolerances[name]}
    report = {
        "status": "fail" if failed else "pass", "samples": len(rows),
        "startTime_s": t0, "stopTime_s": previous_time,
        "analytical": {"loadAcceleration_m_s2": a, "counterweightAccelerationDown_m_s2": 2*a,
                       "ropeTension_N": tension, "loadSupportForce_N": 2*tension,
                       "ropeLength_m": initial_length},
        "final": {"loadRise_m": value(rows[-1], "loadDisplacement"),
                  "counterweightDrop_m": value(rows[-1], "counterweightDisplacement")},
        "maxAbsoluteErrors": maxima, "tolerances": tolerances,
    }
    if failed:
        raise ValueError(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = check(args.csv)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
