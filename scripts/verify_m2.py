#!/usr/bin/env python3
"""Verify the declared M2 compositions and summarize their native trajectories.

The experiment constants below are an independent statement of the intended
cases. They are not copied from the native results. The script checks component
laws, interfaces, sampled energy integrals, geometry and tracking; it does not
independently solve or experimentally validate the complete spatial dynamics.
"""
import hashlib
import json
import math
from pathlib import Path

from native_scene import export_scene
from verify_csv import close, read_csv


ROOT = Path(__file__).resolve().parent.parent
CASES = (
    dict(id="m2-nominal", prefix="m2_controlled_nominal", model="ControlledThermalArm3D",
         forearmDensity=850.0, controllerGain=18.0, derivativeTime=0.12, coolingConductance=0.4),
    dict(id="m2-heavy", prefix="m2_controlled_heavy", model="ControlledArmHeavyLoad",
         forearmDensity=1700.0, controllerGain=18.0, derivativeTime=0.12, coolingConductance=0.4),
    dict(id="m2-retuned", prefix="m2_controlled_retuned", model="ControlledArmRetuned",
         forearmDensity=1700.0, controllerGain=30.0, derivativeTime=0.22, coolingConductance=0.4),
    dict(id="m2-reduced-cooling", prefix="m2_controlled_cooling", model="ControlledArmReducedCooling",
         forearmDensity=1700.0, controllerGain=30.0, derivativeTime=0.22, coolingConductance=0.08),
)
STEPS = ((1.0, 0.25, 1.0, 10.0), (10.0, 1.0, -0.35, 20.0), (20.0, -0.35, 0.65, 30.0))
TRACKING_BAND = 0.03  # rad; declared before observing the native runs
PARAMETER_UNITS = {
    "forearmDensity": "kg/m3", "controllerGain": "V/rad", "integralTime": "s",
    "derivativeTime": "s", "coolingConductance": "W/K", "voltageLimit": "V",
}


def trapezoid(rows, value):
    """Time-weighted integral; duplicate event samples contribute zero duration."""
    return sum(0.5 * (b["time"] - a["time"]) * (value(a) + value(b))
               for a, b in zip(rows, rows[1:]))


def reference_values(t):
    for at, previous, target, _ in STEPS:
        if abs(t - at) <= 1e-7:
            return (previous, target)
    return (0.25 if t < 1 else 1.0 if t < 10 else -0.35 if t < 20 else 0.65,)


def verify_case(case):
    prefix = case["prefix"]
    frames = tuple(f"plant.{body}.{frame}.r_0[{axis}]"
                   for body in ("upperArm", "forearm")
                   for frame in ("frame_a", "frame_b") for axis in (1, 2, 3))
    parameter_columns = tuple(PARAMETER_UNITS)
    names = (
        "time", "desiredAngle", "shoulderAngle", "elbowAngle", "trackingError",
        "shoulderSpeed", "elbowSpeed", "motorSpeed", "motorCurrent", "appliedVoltage",
        "windingTemperature", "copperLoss", "inputPower", "electricalEnergy", "copperEnergy",
        "currentDerivative", "temperatureDerivative", "controllerIntegral",
        "controllerDerivative", "controllerDerivativeState", "integratorDerivative",
        "rawControlVoltage", "controller.u_s", "controller.u_m",
        "plant.drive.resistor.R_actual", "plant.gear.flange_a.tau", "plant.gear.flange_b.tau",
        "plant.forearm.body.m", "plant.upperArm.body.m",
        "tipPosition[1]", "tipPosition[2]", "tipPosition[3]",
    ) + frames + parameter_columns
    csv_path = ROOT / f"{prefix}_res.csv"
    rows = read_csv(csv_path, names)
    first, last = rows[0], rows[-1]
    close(first["time"], 0, 1e-8, f"{prefix} start")
    close(last["time"], 30, 1e-6, f"{prefix} stop")
    largest_gap = max(b["time"] - a["time"] for a, b in zip(rows, rows[1:]))
    if len(rows) < 1501 or largest_gap > 0.020001:
        raise AssertionError(f"{prefix}: expected the complete 0.02 s output grid; "
                             f"got {len(rows)} samples and maximum gap {largest_gap:.9g} s")
    for name, expected in {
        "shoulderAngle": 0.25, "elbowAngle": -0.4, "shoulderSpeed": 0,
        "elbowSpeed": 0, "motorCurrent": 0, "windingTemperature": 293.15,
        "electricalEnergy": 0, "copperEnergy": 0, "controllerIntegral": 0,
        "controllerDerivativeState": -0.25, "controllerDerivative": 0,
    }.items():
        close(first[name], expected, 1e-7, f"{prefix} initial {name}")

    parameters = {name: case[name] for name in ("forearmDensity", "controllerGain", "derivativeTime", "coolingConductance")}
    parameters.update(integralTime=1.2, voltageLimit=12.0)
    for row in rows:
        for name, expected in parameters.items():
            close(row[name], expected, 1e-10, f"{prefix} parameter {name}")
    close(first["plant.forearm.body.m"], case["forearmDensity"] * 0.45 * 0.05 * 0.04,
          1e-8, f"{prefix} actual forearm mass")
    close(first["plant.upperArm.body.m"], 850 * 0.55 * 0.065 * 0.05,
          1e-8, f"{prefix} actual upper-arm mass")

    residuals = {key: 0.0 for key in (
        "voltageV", "heatW", "gearPowerW", "linkLengthM", "electricalEnergyJ",
        "copperEnergyJ", "storedHeatJ", "controllerV", "antiWindupPerS", "sceneEndpointsM",
    )}
    energy = {key: 0.0 for key in ("electrical", "electricalAbs", "copper", "heat", "heatAbs")}
    previous = first
    positive_limit = negative_limit = False
    anti_windup_samples = 0
    k, ti, td, g = case["controllerGain"], 1.2, case["derivativeTime"], case["coolingConductance"]

    for row in rows:
        t, i, temp = row["time"], row["motorCurrent"], row["windingTemperature"]
        context = f"{prefix} t={t:.9g}"
        if min(abs(row["desiredAngle"] - x) for x in reference_values(t)) > 1e-7:
            raise AssertionError(f"{context}: wrong desired angle {row['desiredAngle']}")
        error = row["desiredAngle"] - row["shoulderAngle"]
        close(row["trackingError"], error, 1e-8, f"{context} tracking error sign")
        close(row["controller.u_s"], row["desiredAngle"], 1e-8, f"{context} controller setpoint wiring")
        close(row["controller.u_m"], row["shoulderAngle"], 1e-8, f"{context} controller measurement wiring")
        raw = k * (error + row["controllerIntegral"] + row["controllerDerivative"])
        close(row["rawControlVoltage"], raw, 1e-6, f"{context} native PID components")
        bounded = min(12.0, max(-12.0, raw))
        controller_error = row["appliedVoltage"] - bounded
        close(controller_error, 0, 1e-6, f"{context} voltage limiter")
        close(row["controllerDerivative"], 10 * (-row["shoulderAngle"] - row["controllerDerivativeState"]),
              1e-6, f"{context} filtered derivative of measurement")
        anti_windup = (error + (row["appliedVoltage"] - raw) / (k * 0.9)) / ti
        anti_windup_error = row["integratorDerivative"] - anti_windup
        close(anti_windup_error, 0, 1e-6, f"{context} anti-windup feedback")
        if abs(raw) > 12 + 1e-5:
            anti_windup_samples += 1
        positive_limit |= row["appliedVoltage"] >= 12 - 1e-7
        negative_limit |= row["appliedVoltage"] <= -12 + 1e-7

        resistance = 2 * (1 + 0.0039 * (temp - 293.15))
        close(row["plant.drive.resistor.R_actual"], resistance, 1e-7, f"{context} R(T)")
        voltage_error = 0.05 * row["currentDerivative"] + resistance * i + 0.5 * row["motorSpeed"] - row["appliedVoltage"]
        close(voltage_error, 0, 1e-5, f"{context} electrical loop")
        close(row["copperLoss"], i * i * resistance, 1e-5, f"{context} copper loss")
        close(row["inputPower"], row["appliedVoltage"] * i, 1e-5, f"{context} signed input power")
        net_heat = row["copperLoss"] - g * (temp - 293.15)
        heat_error = 40 * row["temperatureDerivative"] - net_heat
        close(heat_error, 0, 1e-5, f"{context} winding heat balance")

        tau_a, tau_b = row["plant.gear.flange_a.tau"], row["plant.gear.flange_b.tau"]
        close(row["motorSpeed"], 5 * row["shoulderSpeed"], 1e-6, f"{context} gear speed ratio")
        close(tau_a, 0.5 * i, 1e-6, f"{context} motor torque")
        close(tau_b, -5 * tau_a, 1e-6, f"{context} gear torque ratio")
        gear_power = tau_a * row["motorSpeed"] + tau_b * row["shoulderSpeed"]
        close(gear_power, 0, 1e-5, f"{context} ideal gear power")

        dt = t - previous["time"]
        previous_heat = previous["copperLoss"] - g * (previous["windingTemperature"] - 293.15)
        for key, now, before in (
            ("electrical", row["inputPower"], previous["inputPower"]),
            ("electricalAbs", abs(row["inputPower"]), abs(previous["inputPower"])),
            ("copper", row["copperLoss"], previous["copperLoss"]),
            ("heat", net_heat, previous_heat), ("heatAbs", abs(net_heat), abs(previous_heat)),
        ):
            energy[key] += 0.5 * dt * (now + before)
        energy_errors = {
            "electricalEnergyJ": row["electricalEnergy"] - energy["electrical"],
            "copperEnergyJ": row["copperEnergy"] - energy["copper"],
            "storedHeatJ": 40 * (temp - 293.15) - energy["heat"],
        }
        for key, cumulative in (("electricalEnergyJ", "electricalAbs"),
                                ("copperEnergyJ", "copper"), ("storedHeatJ", "heatAbs")):
            # Native integration is checked against independent trapezoidal
            # quadrature of the .02 s output samples, including event endpoints.
            close(energy_errors[key], 0, 0.5 + 0.002 * energy[cumulative], f"{context} sampled {key}")
            residuals[key] = max(residuals[key], abs(energy_errors[key]))

        for body, length in (("upperArm", 0.55), ("forearm", 0.45)):
            actual_length = math.sqrt(sum((row[f"plant.{body}.frame_b.r_0[{axis}]"] -
                                          row[f"plant.{body}.frame_a.r_0[{axis}]"])**2
                                         for axis in (1, 2, 3)))
            close(actual_length, length, 1e-7, f"{context} {body} length")
            residuals["linkLengthM"] = max(residuals["linkLengthM"], abs(actual_length - length))
        for axis in (1, 2, 3):
            close(row[f"plant.upperArm.frame_b.r_0[{axis}]"], row[f"plant.forearm.frame_a.r_0[{axis}]"],
                  1e-8, f"{context} elbow frame coincidence")
            close(row[f"tipPosition[{axis}]"], row[f"plant.forearm.frame_b.r_0[{axis}]"],
                  1e-8, f"{context} tip position")
        for key, value in (("voltageV", voltage_error), ("heatW", heat_error),
                           ("gearPowerW", gear_power), ("controllerV", controller_error),
                           ("antiWindupPerS", anti_windup_error)):
            residuals[key] = max(residuals[key], abs(value))
        previous = row

    if not positive_limit or not negative_limit or not anti_windup_samples:
        raise AssertionError(f"{prefix}: reference must exercise both voltage limits and anti-windup")
    for at, before, target, _ in STEPS:
        event = [r["desiredAngle"] for r in rows if abs(r["time"] - at) <= 1e-7]
        if not all(any(abs(value - expected) < 1e-7 for value in event) for expected in (before, target)):
            raise AssertionError(f"{prefix}: native reference event at {at}s must retain both sides")

    plateaus = []
    for start, previous_target, target, stop in STEPS:
        segment = [r for r in rows if start - 1e-7 <= r["time"] < stop - 1e-7
                   and abs(r["desiredAngle"] - target) < 1e-7]
        if stop == 30:
            segment += [r for r in rows if abs(r["time"] - stop) < 1e-7]
        tail = [r for r in segment if r["time"] >= stop - 2]
        if not tail:
            raise AssertionError(f"{prefix}: missing plateau tail ending at {stop}")
        tail_error = max(abs(r["trackingError"]) for r in tail)
        if tail_error > TRACKING_BAND:
            raise AssertionError(f"{prefix}: tracking exceeds predeclared {TRACKING_BAND} rad band "
                                 f"during the final 2 s of the plateau ending at {stop} s: {tail_error:.6g} rad")
        outside = [i for i, r in enumerate(segment) if abs(r["trackingError"]) > TRACKING_BAND]
        settled_index = outside[-1] + 1 if outside else 0
        settling = segment[settled_index]["time"] - start if settled_index < len(segment) else None
        direction = 1 if target > previous_target else -1
        overshoot = max(0.0, *(direction * (r["shoulderAngle"] - target) for r in segment))
        plateaus.append(dict(startTime=start, endTime=stop, targetAngleRad=target,
                             overshootRad=overshoot, settlingTimeS=settling,
                             finalWindowMaxAbsErrorRad=tail_error))

    # Compare exporter geometry to separately reported physical body frames at
    # every native sample. No shape or joint formulas are added to the exporter.
    scene = export_scene(ROOT / f"{prefix}_visual.xml", csv_path)
    close(len(scene["times"]), len(rows), 0, f"{prefix} scene sample count")
    objects = {shape["id"]: shape for shape in scene["objects"]}
    for body in ("upperArm", "forearm"):
        shape = objects[f"plant.{body}.frameTranslation.shape"]
        if shape["type"] != "box":
            raise AssertionError(f"{prefix}: unexpected native body shape")
        for index, row in enumerate(rows):
            frame = shape["frames"][0 if len(shape["frames"]) == 1 else index]
            for endpoint, native_frame in ((frame[9:12], "frame_a"),
                                           ([frame[9 + j] + frame[j] for j in range(3)], "frame_b")):
                for axis, value in enumerate(endpoint, 1):
                    error = value - row[f"plant.{body}.{native_frame}.r_0[{axis}]"]
                    close(error, 0, 1e-8, f"{prefix} native scene endpoint {body} axis {axis}")
                    residuals["sceneEndpointsM"] = max(residuals["sceneEndpointsM"], abs(error))

    metrics = {
        "trackingRmseRad": math.sqrt(trapezoid(rows, lambda r: r["trackingError"]**2) / 30),
        "maxAbsErrorRad": max(abs(r["trackingError"]) for r in rows),
        "finalAbsErrorRad": abs(last["trackingError"]),
        "peakCurrentA": max(abs(r["motorCurrent"]) for r in rows),
        "peakTemperatureK": max(r["windingTemperature"] for r in rows),
        "electricalEnergyJ": last["electricalEnergy"],
        "copperEnergyJ": last["copperEnergy"],
        "saturationDurationS": trapezoid(rows, lambda r: float(abs(r["appliedVoltage"]) >= 12 - 1e-7)),
    }
    if metrics["peakTemperatureK"] <= 293.15 + 0.01 or metrics["copperEnergyJ"] <= 0:
        raise AssertionError(f"{prefix}: thermal response was not exercised")
    verification = {"passed": True, "maximumResiduals": residuals,
                    "antiWindupSamples": anti_windup_samples, "trackingBandRad": TRACKING_BAND,
                    "maximumOutputGapS": largest_gap,
                    "trackingTailWindowS": 2.0, "sampledEnergyTolerance": "0.5 J + 0.002 times accumulated absolute power integral",
                    "scope": "Component/interface laws, tracking and native geometry; not independent full-dynamics or experimental validation"}
    result = dict(id=case["id"], prefix=prefix, model="DomelicaLab.Examples." + case["model"],
                  parameters=parameters, metrics=metrics, plateaus=plateaus,
                  verification=verification, samples=len(rows),
                  nativeCSV_SHA256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                  nativeXML_SHA256=hashlib.sha256((ROOT / f"{prefix}_visual.xml").read_bytes()).hexdigest(),
                  nativeMAT_SHA256=hashlib.sha256((ROOT / f"{prefix}_res.mat").read_bytes()).hexdigest())
    print(f"PASS {prefix}: RMSE {metrics['trackingRmseRad']:.6g} rad; "
          f"peak current {metrics['peakCurrentA']:.6g} A; peak T {metrics['peakTemperatureK']:.6g} K; "
          f"net supply energy {metrics['electricalEnergyJ']:.6g} J; copper heat {metrics['copperEnergyJ']:.6g} J; "
          f"max native scene endpoint error {residuals['sceneEndpointsM']:.3g} m")
    return result


def main():
    destination = ROOT / "artifacts/m2-metrics.json"
    if destination.exists():
        destination.unlink()
    results = [verify_case(case) for case in CASES]
    # Contrasts establish changed native solutions without assuming which
    # controller has better tracking or which thermal trajectory will be hottest.
    comparisons = []
    for baseline, variant in zip(results, results[1:]):
        deltas = {key: variant["metrics"][key] - baseline["metrics"][key] for key in baseline["metrics"]}
        if not any(abs(delta) > 1e-5 for delta in deltas.values()):
            raise AssertionError(f"No native response difference: {baseline['id']} vs {variant['id']}")
        comparisons.append({"baselineId": baseline["id"], "variantId": variant["id"],
                            "changedParameters": {key: {"baseline": value, "variant": variant["parameters"][key], "unit": PARAMETER_UNITS[key]}
                                                  for key, value in baseline["parameters"].items()
                                                  if variant["parameters"][key] != value},
                            "metricDeltas": deltas})
    definitions = {
        "trackingRmseRad": {"label": "Tracking RMSE", "unit": "rad", "description": "Square root of time-weighted squared error over 0–30 s, including command steps"},
        "maxAbsErrorRad": {"label": "Maximum tracking error", "unit": "rad", "description": "Largest absolute native sampled desired-minus-actual shoulder angle"},
        "finalAbsErrorRad": {"label": "Final tracking error", "unit": "rad", "description": "Absolute shoulder error at 30 s"},
        "peakCurrentA": {"label": "Peak absolute current", "unit": "A", "description": "Largest absolute native sampled armature current"},
        "peakTemperatureK": {"label": "Peak winding temperature", "unit": "K", "description": "Maximum native sampled winding temperature"},
        "electricalEnergyJ": {"label": "Net supply energy", "unit": "J", "description": "Native integral of voltage times current; signed, including returned energy"},
        "copperEnergyJ": {"label": "Copper heat", "unit": "J", "description": "Native integral of positive winding i²R loss"},
        "saturationDurationS": {"label": "Time at voltage limit", "unit": "s", "description": "Sampled trapezoidal duration at either ±12 V limit; approximate at output resolution"},
    }
    report = {"schema": "domelica.control-comparison-metrics.v1", "definitions": definitions,
              "parameterUnits": PARAMETER_UNITS,
              "verificationScriptSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "plateauDefinitions": {
                  "overshootRad": "Largest excursion beyond the target in the step direction, clipped to zero",
                  "settlingTimeS": "Time from the command step to the first sample after the last error outside ±0.03 rad before the next step; null if absent",
                  "finalWindowMaxAbsErrorRad": "Largest error in the last 2 s of the plateau, excluding the next command's event"},
              "cases": results, "comparisons": comparisons,
              "scope": "Nominal illustrative Modelica experiments, not measured machine specifications"}
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"PASS M2 verified metrics: {destination}")


if __name__ == "__main__":
    main()
