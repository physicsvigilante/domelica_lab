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


def verify_spatial_arm() -> None:
    """Check M1 constitutive laws, interfaces, and rigid geometry.

    This does not independently solve the spatial arm's equations of motion;
    it checks the nominal composition and its electrical/thermal balances.
    """
    frame_columns = tuple(
        f"{body}.{frame}.r_0[{axis}]"
        for body in ("upperArm", "forearm")
        for frame in ("frame_a", "frame_b")
        for axis in (1, 2, 3)
    )
    rows = read_csv(
        Path("m1_thermal_geared_arm_res.csv"),
        (
            "time", "shoulderAngle", "elbowAngle", "shoulderSpeed", "elbowSpeed",
            "motorSpeed", "motorCurrent", "windingTemperature", "copperLoss",
            "appliedVoltage", "currentDerivative", "temperatureDerivative",
            "gear.flange_a.tau", "gear.flange_b.tau", "drive.resistor.R_actual",
            "tipPosition[1]", "tipPosition[2]", "tipPosition[3]",
        ) + frame_columns,
    )
    first = rows[0]
    close(first["time"], 0, 1e-8, "spatial arm start time")
    close(rows[-1]["time"], 8, 1e-5, "spatial arm end time")
    for name, initial in (
        ("shoulderAngle", 0.25), ("elbowAngle", -0.4),
        ("shoulderSpeed", 0), ("elbowSpeed", 0), ("motorCurrent", 0),
        ("windingTemperature", 293.15),
    ):
        close(first[name], initial, 1e-7, f"spatial arm initial {name}")

    maxima = {name: 0.0 for name in ("voltage", "heat", "gear power", "length", "heat integral")}
    integrated_heat = 0.0
    previous = first
    for row in rows:
        t, current, temperature = row["time"], row["motorCurrent"], row["windingTemperature"]
        # Nominal command: zero, a 0.5 s rise, a 2 s plateau, a 0.5 s fall, zero.
        expected_voltage = (
            0 if t <= 0.5 else 12 * (t - 0.5) if t < 1 else
            6 if t <= 3 else 12 * (3.5 - t) if t < 3.5 else 0
        )
        close(row["appliedVoltage"], expected_voltage, 1e-7,
              f"spatial arm voltage command at t={t:.6g}")

        # Nominal copper R_ref=2 ohm at 293.15 K, alpha=0.0039 /K;
        # armature L=0.05 H, motor torque/back-EMF constant k=0.5 in SI units.
        resistance = 2 * (1 + 0.0039 * (temperature - 293.15))
        close(row["drive.resistor.R_actual"], resistance, 1e-7,
              f"winding temperature feedback at t={t:.6g}")
        voltage_residual = (
            0.05 * row["currentDerivative"] + resistance * current
            + 0.5 * row["motorSpeed"] - row["appliedVoltage"]
        )
        close(voltage_residual, 0, 1e-5, f"spatial arm voltage balance at t={t:.6g}")
        close(row["copperLoss"], current**2 * resistance, 1e-5,
              f"winding copper loss at t={t:.6g}")

        # C=40 J/K, G=0.4 W/K. Joint friction is not routed to this winding.
        net_heat = row["copperLoss"] - 0.4 * (temperature - 293.15)
        heat_residual = 40 * row["temperatureDerivative"] - net_heat
        close(heat_residual, 0, 1e-5, f"winding heat balance at t={t:.6g}")
        previous_net_heat = previous["copperLoss"] - 0.4 * (previous["windingTemperature"] - 293.15)
        integrated_heat += 0.5 * (t - previous["time"]) * (net_heat + previous_net_heat)
        stored_heat_error = 40 * (temperature - first["windingTemperature"]) - integrated_heat
        # Independent integration from the 0.01 s native samples (trapezoidal rule).
        close(stored_heat_error, 0, 0.02, f"winding integrated heat balance at t={t:.6g}")

        # Ideal 5:1 gear: connector torques are positive into each component.
        tau_a, tau_b = row["gear.flange_a.tau"], row["gear.flange_b.tau"]
        close(row["motorSpeed"], 5 * row["shoulderSpeed"], 1e-6,
              f"gear speed ratio at t={t:.6g}")
        close(tau_a, 0.5 * current, 1e-6, f"motor torque conversion at t={t:.6g}")
        close(tau_b, -5 * tau_a, 1e-6, f"gear torque ratio at t={t:.6g}")
        gear_power_residual = tau_a * row["motorSpeed"] + tau_b * row["shoulderSpeed"]
        close(gear_power_residual, 0, 1e-5, f"ideal gear power balance at t={t:.6g}")

        for body, expected_length in (("upperArm", 0.55), ("forearm", 0.45)):
            measured_length = math.sqrt(sum(
                (row[f"{body}.frame_b.r_0[{axis}]"] - row[f"{body}.frame_a.r_0[{axis}]"])**2
                for axis in (1, 2, 3)
            ))
            close(measured_length, expected_length, 1e-6,
                  f"{body} rigid link length at t={t:.6g}")
            maxima["length"] = max(maxima["length"], abs(measured_length - expected_length))
        for axis in (1, 2, 3):
            close(row[f"upperArm.frame_b.r_0[{axis}]"], row[f"forearm.frame_a.r_0[{axis}]"],
                  1e-7, f"elbow frame coincidence axis {axis} at t={t:.6g}")
            close(row[f"tipPosition[{axis}]"], row[f"forearm.frame_b.r_0[{axis}]"],
                  1e-7, f"tip position axis {axis} at t={t:.6g}")
        maxima["voltage"] = max(maxima["voltage"], abs(voltage_residual))
        maxima["heat"] = max(maxima["heat"], abs(heat_residual))
        maxima["gear power"] = max(maxima["gear power"], abs(gear_power_residual))
        maxima["heat integral"] = max(maxima["heat integral"], abs(stored_heat_error))
        previous = row

    for name in ("shoulderAngle", "elbowAngle"):
        if max(row[name] for row in rows) - min(row[name] for row in rows) < 1e-3:
            raise AssertionError(f"spatial arm {name} did not change")
    z_positions = [row["tipPosition[3]"] for row in rows]
    z_range = max(z_positions) - min(z_positions)
    if z_range < 1e-3:
        raise AssertionError("spatial arm tip did not move out of the shoulder's XY plane")
    peak_temperature = max(row["windingTemperature"] for row in rows)
    if peak_temperature - first["windingTemperature"] < 1e-3:
        raise AssertionError("winding did not heat up")
    print(
        "PASS spatial arm component and interface checks: "
        f"max voltage residual {maxima['voltage']:.3g} V; "
        f"max heat residual {maxima['heat']:.3g} W; "
        f"max gear power residual {maxima['gear power']:.3g} W; "
        f"max rigid link length error {maxima['length']:.3g} m; "
        f"max integrated heat error {maxima['heat integral']:.3g} J; "
        f"tip Z range {z_range:.3f} m; peak winding temperature {peak_temperature:.3f} K"
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
    verify_spatial_arm()


if __name__ == "__main__":
    main()
