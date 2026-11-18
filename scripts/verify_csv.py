#!/usr/bin/env python3
"""Check native CSVs against independent oracles for the nominal examples.

The constants below deliberately describe the documented nominal experiments,
not values copied out of the solver output. When an experiment's intended
parameters change, update its oracle explicitly. No check is used for rendering.
"""
import csv
import math
from pathlib import Path


def read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, float]]:
    if not path.is_file():
        raise AssertionError(f"Missing native result: {path}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        missing = sorted(set(required) - set(columns))
        if missing:
            raise AssertionError(
                f"{path}: missing {missing}; available columns: {columns[:30]}"
            )
        result = []
        for row in reader:
            values = {name: float(row[name]) for name in required}
            if not all(math.isfinite(value) for value in values.values()):
                raise AssertionError(f"{path}: non-finite {values}")
            result.append(values)
    if len(result) < 50:
        raise AssertionError(f"{path}: too few points ({len(result)})")
    times = [r["time"] for r in result]
    if any(b < a for a, b in zip(times, times[1:])):
        raise AssertionError(f"{path}: time is not monotone")
    return result


def close(actual: float, expected: float, tol: float, context: str) -> None:
    if abs(actual - expected) > tol:
        raise AssertionError(
            f"{context}: expected {expected:.7g}, got {actual:.7g} (tol {tol})"
        )


def main() -> None:
    p = read_csv(
        Path("m0_motorized_pendulum_res.csv"),
        (
            "time", "angle", "angularVelocity", "motorCurrent", "hinge.a",
            "der(drive.inductor.i)", "command.y",
        ),
    )
    close(p[0]["time"], 0, 1e-8, "pendulum start time")
    close(p[-1]["time"], 4, 1e-5, "pendulum end time")
    close(p[0]["angle"], 0.3, 1e-7, "pendulum initial angle")
    close(p[0]["angularVelocity"], 0, 1e-7, "pendulum initial angular velocity")
    close(p[0]["motorCurrent"], 0, 1e-7, "pendulum initial armature current")
    if not any(abs(row["motorCurrent"]) > 0.05 for row in p if row["time"] > 0.6):
        raise AssertionError("motor current never responds to voltage step")
    if not any(abs(row["angle"] - p[0]["angle"]) > 1e-3 for row in p[1:]):
        raise AssertionError("pendulum did not move")

    # Nominal arm: a uniform 0.7 x 0.06 x 0.05 m box, density 850 kg/m^3.
    # The hinge is at the center of an end face; rotation is about its Z axis.
    # MSL World defaults to Modelica.Constants.g_n = 9.80665 m/s^2.
    length, width, height, density = 0.7, 0.06, 0.05, 850
    mass = length * width * height * density
    inertia = mass * (length**2 / 3 + width**2 / 12)
    max_torque_residual = max_voltage_residual = 0.0
    for row in p:
        t, phi, w, i = (
            row["time"], row["angle"], row["angularVelocity"], row["motorCurrent"]
        )
        # The CSV can contain both sides of the step event at exactly 0.5 s.
        if abs(t - 0.5) > 1e-8:
            close(row["command.y"], 0 if t < 0.5 else 18, 1e-7,
                  f"pendulum commanded voltage at t={t:.6g}")
        # Independent Newton-Euler balance and armature loop voltage balance.
        torque_residual = (
            inertia * row["hinge.a"]
            + mass * 9.80665 * length / 2 * math.sin(phi)
            + 0.15 * w - 2 * i
        )
        voltage_residual = (
            0.05 * row["der(drive.inductor.i)"] + 2 * i + 2 * w - row["command.y"]
        )
        close(torque_residual, 0, 1e-5, f"pendulum torque balance at t={t:.6g}")
        close(voltage_residual, 0, 1e-5, f"armature voltage balance at t={t:.6g}")
        max_torque_residual = max(max_torque_residual, abs(torque_residual))
        max_voltage_residual = max(max_voltage_residual, abs(voltage_residual))

    h = read_csv(Path("m0_thermal_step_res.csv"), ("time", "temperature"))
    close(h[0]["time"], 0, 1e-8, "thermal start time")
    close(h[0]["temperature"], 293.15, 1e-4, "thermal initial temperature")
    close(h[-1]["time"], 5, 1e-5, "thermal end time")
    # Independent lumped heat balance: C * dT/dt = Q - G * (T-Tamb).
    # Check the entire trace, including the constant-temperature pre-step segment.
    max_thermal_error = 0.0
    for row in h:
        t = row["time"]
        elapsed = max(0, t - 0.5)
        expected = 293.15 + (90 / 1.2) * (1 - math.exp(-1.2 * elapsed / 15))
        close(row["temperature"], expected, 1e-3,
              f"thermal analytic solution at t={t:.6g}")
        max_thermal_error = max(max_thermal_error, abs(row["temperature"] - expected))

    b = read_csv(
        Path("m0_msl_double_pendulum_res.csv"),
        ("time", "revolute1.phi", "revolute1.w", "revolute2.phi", "revolute2.w"),
    )
    close(b[0]["time"], 0, 1e-8, "MSL baseline start time")
    close(b[-1]["time"], 1, 1e-5, "MSL baseline end time")
    for joint in ("revolute1", "revolute2"):
        if not any(abs(row[f"{joint}.phi"] - b[0][f"{joint}.phi"]) > 1e-3 for row in b):
            raise AssertionError(f"MSL baseline {joint} did not move")
        if not any(abs(row[f"{joint}.w"]) > 1e-3 for row in b):
            raise AssertionError(f"MSL baseline {joint} angular velocity stayed zero")
    print(
        "PASS native CSV verification: "
        f"max pendulum torque residual {max_torque_residual:.3g} N.m; "
        f"max armature voltage residual {max_voltage_residual:.3g} V; "
        f"max thermal analytic error {max_thermal_error:.3g} K; "
        "finite moving MSL baseline joints"
    )


if __name__ == "__main__":
    main()
