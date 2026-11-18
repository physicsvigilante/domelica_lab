#!/usr/bin/env python3
"""Verify native MSL fluid qualification runs and authored tank-loop experiments.

Physical constants and limits were declared before the first native run;
additional temporal and derivative gates were declared before the diagnostic
solver comparison. This checks component identities, closed mass, modeled
internal energy, native integration, and finite-window control. It is not
experimental validation or an independent solution of the complete fluid DAE.
No verifier value drives motion.
"""
import csv
import hashlib
import json
import math
from pathlib import Path

from verify_csv import close, read_csv


ROOT = Path(__file__).resolve().parent.parent
RHO, GRAVITY, AREA, P_AMBIENT = 995.586, 9.80665, 0.25, 101325.0
TRACKING_BAND = 0.025  # m, throughout the final 20 s of each reference plateau
CASES = (
    dict(id="m3-nominal", prefix="m3_tanks_nominal", model="ControlledTankLoop",
         initialLevelA=0.9, initialLevelB=0.5, valveScale=1.0, returnBranchCount=1),
    dict(id="m3-restricted", prefix="m3_tanks_restricted", model="ControlledTankRestrictedValve",
         initialLevelA=0.9, initialLevelB=0.5, valveScale=0.55, returnBranchCount=1),
    dict(id="m3-initial", prefix="m3_tanks_initial", model="ControlledTankInitialLevels",
         initialLevelA=0.5, initialLevelB=0.9, valveScale=1.0, returnBranchCount=1),
    dict(id="m3-parallel", prefix="m3_tanks_parallel", model="ControlledTankParallelReturn",
         initialLevelA=0.9, initialLevelB=0.5, valveScale=1.0, returnBranchCount=2),
)
PLATEAUS = ((0.0, 100.0, 0.8), (100.0, 200.0, 0.9), (200.0, 300.0, 0.78))
PUMP_DERIVATIVE_COLUMNS = ("der(plant.pump.head)", "der(supplyFlow)", "der(plant.pump.V_flow)")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(prefix):
    return {f"native{kind}_SHA256": sha(ROOT / f"{prefix}_res.{kind.lower()}")
            for kind in ("CSV", "MAT")}


def coverage(rows, stop, interval, prefix):
    close(rows[0]["time"], 0, 1e-8, f"{prefix} start")
    close(rows[-1]["time"], stop, 1e-6, f"{prefix} stop")
    gap = max(b["time"]-a["time"] for a, b in zip(rows, rows[1:]))
    if len(rows) < round(stop/interval)+1 or gap > interval+1e-6:
        raise AssertionError(f"{prefix}: incomplete native output grid, n={len(rows)}, max gap={gap}")


def integral(rows, value):
    return sum((b["time"]-a["time"])*(value(a)+value(b))/2
               for a, b in zip(rows, rows[1:]))


def scheduled_values(t, steps):
    """Both event sides are legitimate native samples at a discontinuity."""
    value = steps[0][1]
    for at, next_value in steps[1:]:
        if abs(t-at) <= 1e-7:
            return (value, next_value)
        if t < at:
            break
        value = next_value
    return (value,)


def require_schedule_events(rows, name, steps, scale=1):
    for at, value in steps[1:]:
        previous = steps[steps.index((at, value))-1][1]
        event = [r[name]/scale for r in rows if abs(r["time"]-at) <= 1e-7]
        if not any(abs(x-previous) <= 1e-7 for x in event) or not any(abs(x-value) <= 1e-7 for x in event):
            raise AssertionError(f"{name}: missing pre/post native event samples at {at} s")


def verify_speed_trajectory(rows, case_id, prefix):
    """Check time evolution independently of exported derivative aliases.

    A native pointwise derivative identity can pass even when a reconstructed
    state follows an incorrect trajectory. Integrate the declared first-order
    ODE from its recorded input/output, and use an exact constant-input oracle
    for the first second of the initial-high-B experiment.
    """
    residuals = {}
    if case_id == "m3-initial":
        selected = [row for row in rows if 0 <= row["time"] <= 1+1e-9]
        if len(selected) < 11 or not any(abs(row["time"]-1) <= 1e-9 for row in selected):
            raise AssertionError(f"{prefix}: missing native samples for the exact first-second speed oracle")
        close(rows[0]["filteredFraction"], 0.3, 1e-9, f"{prefix} exact speed oracle initial state")
        worst = 0.0
        for row in selected:
            context = f"{prefix} t={row['time']:.9g}"
            close(row["pumpFraction"], 0.001, 1e-9, f"{context} exact speed oracle constant input")
            expected = 0.001+0.299*math.exp(-row["time"]/2)
            error = row["filteredFraction"]-expected
            close(error, 0, 1e-6, f"{context} exact first-order speed trajectory")
            worst = max(worst, abs(error))
        residuals["initialSpeedOracleFraction"] = worst
    cumulative = absolute_cumulative = worst = 0.0
    initial = rows[0]["filteredFraction"]
    previous = rows[0]
    for row in rows:
        dt = row["time"]-previous["time"]
        rate = (row["pumpFraction"]-row["filteredFraction"])/2
        old_rate = (previous["pumpFraction"]-previous["filteredFraction"])/2
        cumulative += dt*(rate+old_rate)/2
        absolute_cumulative += dt*(abs(rate)+abs(old_rate))/2
        error = row["filteredFraction"]-initial-cumulative
        close(error, 0, 0.0001+0.002*absolute_cumulative,
              f"{prefix} t={row['time']:.9g} independently integrated speed trajectory")
        worst = max(worst, abs(error))
        previous = row
    residuals["speedTrajectoryFraction"] = worst
    return residuals


def verify_pump_head_derivative(rows, prefix):
    """Check the full affinity-law chain rule when native derivatives exist."""
    available_columns = [name for name in PUMP_DERIVATIVE_COLUMNS if name in rows[0]]
    derivative_rows = [row for row in rows if row["supplyFlow"] > 1e-5
                       and "der(plant.pump.head)" in row
                       and ("der(supplyFlow)" in row or "der(plant.pump.V_flow)" in row)]
    report = dict(available=bool(derivative_rows), nativeColumns=available_columns,
                  samples=len(derivative_rows), toleranceMPerS=1e-5,
                  scope="Open pump check valve only, supplyFlow > 1e-5 kg/s")
    if not derivative_rows:
        report["unavailableReason"] = "No open-valve samples with both native head and flow derivatives exported."
        return report
    worst = 0.0
    for row in derivative_rows:
        ratio = row["pumpRPM"]/1200
        ratio_derivative = row["filteredFractionDerivative"]
        flow = row["supplyFlow"]/RHO
        flow_derivative = (row["der(supplyFlow)"]/RHO if "der(supplyFlow)" in row
                           else row["der(plant.pump.V_flow)"])
        nominal_flow = flow/ratio
        if nominal_flow < 0:
            head, slope = 10-250*nominal_flow, -250
        elif nominal_flow > 0.008:
            head, slope = -2250*(nominal_flow-0.008), -2250
        else:
            head = 10-250*nominal_flow-125000*nominal_flow**2
            slope = -250-250000*nominal_flow
        expected = (2*ratio*ratio_derivative*head
                    + slope*(ratio*flow_derivative-flow*ratio_derivative))
        error = row["der(plant.pump.head)"]-expected
        close(error, 0, 1e-5, f"{prefix} t={row['time']:.9g} native pump-head derivative chain rule")
        worst = max(worst, abs(error))
    report.update(passed=True, maxAbsErrorMPerS=worst)
    return report


def verify_case(case):
    prefix = case["prefix"]
    names = (
        "time", "crossArea", "tankHeight", "initialLevelA", "initialLevelB", "valveScale",
        "returnBranchCount", "controllerGain", "integralTime", "tankALevel", "tankBLevel",
        "tankAPressure", "tankBPressure", "supplyFlow", "returnFlow", "bypassFlow", "pumpRPM",
        "pumpPressureRise", "pumpPower", "pumpEnergy", "valveOpening", "targetLevel", "levelError",
        "totalMass", "massResidual", "totalInternalEnergy", "tankATemperature", "tankBTemperature",
        "tankALevelDerivative", "tankBLevelDerivative", "internalEnergyDerivative", "transferredMass",
        "controllerRaw", "controllerIntegral", "controllerIntegralDerivative", "pumpFraction",
        "filteredFraction", "filteredFractionDerivative", "controller.u_s", "controller.u_m",
        "plant.pump.medium.d", "plant.pump.m", "plant.pump.U", "plant.pump.port_a.p",
        "plant.pump.port_b.p", "plant.pump.port_a.m_flow", "plant.pump.port_b.m_flow",
        "plant.supplyPipe.port_a.p", "plant.supplyPipe.port_b.p",
        "plant.supplyPipe.port_a.m_flow", "plant.supplyPipe.port_b.m_flow",
        "plant.returnPipe.port_a.p", "plant.returnPipe.port_b.p",
        "plant.returnPipe.port_a.m_flow", "plant.returnPipe.port_b.m_flow",
        "plant.returnValve.port_a.p", "plant.returnValve.port_b.p",
        "plant.returnValve.port_a.m_flow", "plant.returnValve.port_b.m_flow",
        "plant.tankA.m", "plant.tankB.m", "plant.tankA.U", "plant.tankB.U",
        "plant.tankA.medium.d", "plant.tankB.medium.d",
    ) + tuple(f"plant.tank{tank}.ports[{port}].m_flow" for tank in "AB" for port in range(1, 5))
    if case["returnBranchCount"] == 2:
        names += ("bypassPipe.port_a.m_flow", "bypassPipe.port_b.m_flow",
                  "bypassPipe.port_a.p", "bypassPipe.port_b.p", "bypassPipe.length", "bypassPipe.diameter")
    csv_path = ROOT / f"{prefix}_res.csv"
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        native_columns = next(csv.reader(stream), [])
    names += tuple(name for name in PUMP_DERIVATIVE_COLUMNS if name in native_columns)
    rows = read_csv(csv_path, names)
    coverage(rows, 300, 0.1, prefix)
    first, last = rows[0], rows[-1]
    expected_mass = RHO*(AREA*1.4+0.001)
    for key, value in {"tankALevel": case["initialLevelA"], "tankBLevel": case["initialLevelB"],
                       "tankATemperature": 293.15, "tankBTemperature": 293.15,
                       "pumpEnergy": 0, "transferredMass": 0, "controllerIntegral": 0.1,
                       "filteredFraction": 0.3}.items():
        close(first[key], value, 1e-7, f"{prefix} initial {key}")
    speed_residuals = verify_speed_trajectory(rows, case["id"], prefix)
    parameters = {key: case[key] for key in ("initialLevelA", "initialLevelB", "valveScale", "returnBranchCount")}
    parameters.update(crossArea=AREA, tankHeight=1.2, controllerGain=3, integralTime=30)
    residuals = {key: 0.0 for key in (
        "massKg", "tankMassFlowKgS", "hydrostaticPa", "valveFlowKgS", "pumpHeadPa",
        "pumpPowerW", "modeledInternalEnergyDerivativeW", "sampledPumpEnergyJ",
        "storedInternalEnergyJ", "sampledTransferredMassKg", "controllerFraction",
    )}
    residuals.update(speed_residuals)
    cumulative_power = cumulative_abs_power = cumulative_transfer = cumulative_abs_transfer = 0.0
    prev = first
    for row in rows:
        context = f"{prefix} t={row['time']:.9g}"
        for key, expected in parameters.items():
            close(row[key], expected, 1e-10, f"{context} parameter {key}")
        for name in ("plant.tankA.medium.d", "plant.tankB.medium.d", "plant.pump.medium.d"):
            close(row[name], RHO, 1e-8, f"{context} constant water density")
        close(row["plant.pump.m"], RHO*0.001, 1e-8, f"{context} stored pump mass")
        for tank in "AB":
            level = row[f"tank{tank}Level"]
            if not 0.05 < level < 1.15:
                raise AssertionError(f"{context}: tank {tank} outside declared wet/nonoverflow range: {level}")
            close(row[f"plant.tank{tank}.m"], RHO*AREA*level, 1e-7, f"{context} tank {tank} storage")
            port_net = sum(row[f"plant.tank{tank}.ports[{p}].m_flow"] for p in range(1, 5))
            mass_flow_error = RHO*AREA*row[f"tank{tank}LevelDerivative"]-port_net
            close(mass_flow_error, 0, 1e-7, f"{context} tank {tank} differential mass balance")
            pressure_error = row[f"tank{tank}Pressure"]-(P_AMBIENT+RHO*GRAVITY*level)
            close(pressure_error, 0, 1e-5, f"{context} bottom-port hydrostatic pressure {tank}")
            close(row[f"plant.tank{tank}.ports[4].m_flow"], 0, 1e-10, f"{context} sensor zero flow")
            residuals["tankMassFlowKgS"] = max(residuals["tankMassFlowKgS"], abs(mass_flow_error))
            residuals["hydrostaticPa"] = max(residuals["hydrostaticPa"], abs(pressure_error))
        mass = row["plant.tankA.m"]+row["plant.tankB.m"]+row["plant.pump.m"]
        close(row["totalMass"], mass, 1e-7, f"{context} all storage included")
        close(mass, expected_mass, 1e-5, f"{context} closed mass inventory")
        close(row["massResidual"], mass-expected_mass, 1e-7, f"{context} displayed mass residual")
        residuals["massKg"] = max(residuals["massKg"], abs(mass-expected_mass))
        supply, returned, bypass = (row[n] for n in ("supplyFlow", "returnFlow", "bypassFlow"))
        close(row["plant.tankA.ports[1].m_flow"], -supply, 1e-7, f"{context} pump inlet connection")
        close(row["plant.tankB.ports[1].m_flow"], supply, 1e-7, f"{context} supply outlet connection")
        close(row["plant.tankB.ports[2].m_flow"], -returned, 1e-7, f"{context} return inlet connection")
        close(row["plant.tankA.ports[2].m_flow"], returned, 1e-7, f"{context} return outlet connection")
        close(row["plant.tankB.ports[3].m_flow"], -bypass, 1e-7, f"{context} branch inlet connection")
        close(row["plant.tankA.ports[3].m_flow"], bypass, 1e-7, f"{context} branch outlet connection")
        for component, signed_flow in (("pump", supply), ("supplyPipe", supply),
                                       ("returnPipe", returned), ("returnValve", returned)):
            close(row[f"plant.{component}.port_a.m_flow"], signed_flow, 1e-7, f"{context} {component} port a")
            close(row[f"plant.{component}.port_b.m_flow"], -signed_flow, 1e-7, f"{context} {component} port b")
        if case["returnBranchCount"] == 2:
            close(row["bypassPipe.port_a.m_flow"], bypass, 1e-7, f"{context} actual added branch")
            close(row["bypassPipe.port_b.m_flow"], -bypass, 1e-7, f"{context} branch continuity")
            close(row["bypassPipe.port_a.p"], row["tankBPressure"], 1e-5, f"{context} branch B pressure")
            close(row["bypassPipe.port_b.p"], row["tankAPressure"], 1e-5, f"{context} branch A pressure")
            close(row["bypassPipe.length"], 4, 1e-10, f"{context} branch length")
            close(row["bypassPipe.diameter"], 0.016, 1e-10, f"{context} branch diameter")
        else:
            close(bypass, 0, 1e-10, f"{context} unconnected branch has no flow")
        for actual, expected in (
            ("plant.pump.port_a.p", "tankAPressure"),
            ("plant.supplyPipe.port_a.p", "plant.pump.port_b.p"),
            ("plant.supplyPipe.port_b.p", "tankBPressure"),
            ("plant.returnPipe.port_a.p", "tankBPressure"),
            ("plant.returnPipe.port_b.p", "plant.returnValve.port_a.p"),
            ("plant.returnValve.port_b.p", "tankAPressure"),
        ):
            close(row[actual], row[expected], 1e-5, f"{context} pressure connection {actual}")
        for component, flow in (("supplyPipe", supply), ("returnPipe", returned)):
            dp = row[f"plant.{component}.port_a.p"]-row[f"plant.{component}.port_b.p"]
            if dp*flow < -1e-5:
                raise AssertionError(f"{context}: horizontal {component} adds hydraulic power")
        expected_opening = scheduled_values(row["time"], ((0, 0.65), (140, 1), (240, 0.45)))
        if min(abs(row["valveOpening"]-case["valveScale"]*x) for x in expected_opening) > 1e-8:
            raise AssertionError(f"{context}: wrong native valve schedule")
        valve_dp = row["plant.returnValve.port_a.p"]-row["plant.returnValve.port_b.p"]
        valve_error = returned-row["valveOpening"]*(2/5000)*valve_dp
        close(valve_error, 0, 1e-7, f"{context} native linear valve law")
        residuals["valveFlowKgS"] = max(residuals["valveFlowKgS"], abs(valve_error))
        rpm = row["pumpRPM"]
        close(rpm, max(1200*row["filteredFraction"], 1e-3), 1e-7, f"{context} pump speed signal")
        if not 1.2-1e-6 <= rpm <= 1800+1e-6 or supply < -1e-7:
            raise AssertionError(f"{context}: pump speed bounds or check-valve direction violated")
        dp = row["plant.pump.port_b.p"]-row["plant.pump.port_a.p"]
        close(row["pumpPressureRise"], dp, 1e-5, f"{context} pump pressure alias")
        speed_ratio, q = rpm/1200, supply/RHO
        expected_head = 10*speed_ratio**2-250*speed_ratio*q-125000*q*q
        head_error = dp-RHO*GRAVITY*expected_head
        if supply > 1e-7:
            close(head_error, 0, 1e-4, f"{context} pump similarity curve")
            residuals["pumpHeadPa"] = max(residuals["pumpHeadPa"], abs(head_error))
        elif dp < RHO*GRAVITY*10*speed_ratio**2-1e-4:
            raise AssertionError(f"{context}: closed pump check valve below shutoff head")
        power_error = row["pumpPower"]-dp*q/0.8
        close(power_error, 0, 1e-5, f"{context} pump shaft power and efficiency")
        residuals["pumpPowerW"] = max(residuals["pumpPowerW"], abs(power_error))
        targets = scheduled_values(row["time"], ((0, 0.8), (100, 0.9), (200, 0.78)))
        if min(abs(row["targetLevel"]-x) for x in targets) > 1e-8:
            raise AssertionError(f"{context}: wrong target profile")
        error = row["targetLevel"]-row["tankBLevel"]
        close(row["levelError"], error, 1e-8, f"{context} feedback sign")
        close(row["controller.u_s"], row["targetLevel"], 1e-8, f"{context} controller reference connection")
        close(row["controller.u_m"], row["tankBLevel"], 1e-8, f"{context} controller measurement connection")
        raw = 3*(error+row["controllerIntegral"])
        close(row["controllerRaw"], raw, 1e-7, f"{context} PI composition")
        control_error = row["pumpFraction"]-min(1.5, max(0.001, raw))
        close(control_error, 0, 1e-7, f"{context} control limits")
        close(row["controllerIntegralDerivative"], (error+(row["pumpFraction"]-raw)/(3*0.9))/30,
              1e-8, f"{context} PI anti-windup")
        close(2*row["filteredFractionDerivative"], row["pumpFraction"]-row["filteredFraction"],
              1e-8, f"{context} native speed response")
        residuals["controllerFraction"] = max(residuals["controllerFraction"], abs(control_error))
        native_u = row["plant.tankA.U"]+row["plant.tankB.U"]+row["plant.pump.U"]
        close(row["totalInternalEnergy"], native_u, 1e-6, f"{context} all modeled energy storage")
        energy_rate_error = row["internalEnergyDerivative"]-row["pumpPower"]
        close(energy_rate_error, 0, 1e-4, f"{context} modeled internal-energy balance")
        residuals["modeledInternalEnergyDerivativeW"] = max(residuals["modeledInternalEnergyDerivativeW"], abs(energy_rate_error))
        dt = row["time"]-prev["time"]
        net, prev_net = supply-returned-bypass, prev["supplyFlow"]-prev["returnFlow"]-prev["bypassFlow"]
        cumulative_power += dt*(row["pumpPower"]+prev["pumpPower"])/2
        cumulative_abs_power += dt*(abs(row["pumpPower"])+abs(prev["pumpPower"]))/2
        cumulative_transfer += dt*(net+prev_net)/2
        cumulative_abs_transfer += dt*(abs(net)+abs(prev_net))/2
        energy_tolerance = 0.05+0.002*cumulative_abs_power
        energy_error = row["pumpEnergy"]-cumulative_power
        storage_error = native_u-first["totalInternalEnergy"]-row["pumpEnergy"]
        transfer_error = row["transferredMass"]-cumulative_transfer
        close(energy_error, 0, energy_tolerance, f"{context} independent sampled shaft energy")
        close(storage_error, 0, energy_tolerance, f"{context} integrated modeled internal energy")
        close(transfer_error, 0, 0.05+0.002*cumulative_abs_transfer, f"{context} independent sampled transfer")
        close(row["plant.tankB.m"]-first["plant.tankB.m"], row["transferredMass"],
              1e-5, f"{context} native integrated tank B mass")
        for key, value in (("sampledPumpEnergyJ", energy_error), ("storedInternalEnergyJ", storage_error),
                           ("sampledTransferredMassKg", transfer_error)):
            residuals[key] = max(residuals[key], abs(value))
        prev = row
    head_derivative = verify_pump_head_derivative(rows, prefix)
    if head_derivative["available"]:
        residuals["pumpHeadDerivativeMPerS"] = head_derivative["maxAbsErrorMPerS"]
    require_schedule_events(rows, "targetLevel", ((0, 0.8), (100, 0.9), (200, 0.78)))
    require_schedule_events(rows, "valveOpening", ((0, 0.65), (140, 1), (240, 0.45)), case["valveScale"])
    tails = []
    for start, stop, target in PLATEAUS:
        selected = [r for r in rows if stop-20 <= r["time"] < stop-1e-7
                    or (stop == 300 and abs(r["time"]-stop) < 1e-7)]
        if len(selected) < 199:
            raise AssertionError(f"{prefix}: missing final-window samples for plateau ending {stop}")
        worst = max(abs(r["tankBLevel"]-target) for r in selected)
        if worst > TRACKING_BAND:
            raise AssertionError(f"{prefix}: final 20 s tracking window ending {stop}: {worst:.6g} m > {TRACKING_BAND} m")
        tails.append(dict(startS=start, stopS=stop, targetM=target,
                          windowStartS=stop-20, maxAbsErrorM=worst, passed=True))
    if case["returnBranchCount"] == 2 and max(abs(r["bypassFlow"]) for r in rows) < 0.01:
        raise AssertionError(f"{prefix}: new topology branch never carries meaningful flow")
    if case["id"] == "m3-nominal" and not (min(r["returnFlow"] for r in rows) < -0.01 and max(r["returnFlow"] for r in rows) > 0.01):
        raise AssertionError("Nominal native return path must demonstrate actual flow reversal")
    metrics = dict(
        finalTankALevelM=last["tankALevel"], finalTankBLevelM=last["tankBLevel"],
        peakPumpPowerW=max(r["pumpPower"] for r in rows), pumpEnergyJ=last["pumpEnergy"],
        maxAbsMassResidualKg=residuals["massKg"],
        trackingRMSEM=math.sqrt(integral(rows, lambda r: r["levelError"]**2)/300),
        maxTailLevelErrorM=max(t["maxAbsErrorM"] for t in tails),
        peakSupplyFlowKgS=max(r["supplyFlow"] for r in rows),
        minReturnFlowKgS=min(r["returnFlow"] for r in rows),
        maxReturnFlowKgS=max(r["returnFlow"] for r in rows),
        finalBypassFlowKgS=last["bypassFlow"], totalMassKg=last["totalMass"],
    )
    print(f"PASS {prefix}: {len(rows)} native samples; RMSE {metrics['trackingRMSEM']:.6g} m; "
          f"worst tail {metrics['maxTailLevelErrorM']:.6g} m; mass residual {residuals['massKg']:.3g} kg")
    return dict(id=case["id"], prefix=prefix, model="DomelicaLab.Examples."+case["model"],
                samples=len(rows), parameters=parameters, metrics=metrics, plateaus=tails,
                verification=dict(passed=True, residualMaxima=residuals,
                                  nativePumpHeadDerivative=head_derivative), **identity(prefix))


def verify_empty_tanks():
    prefix = "m3_msl_empty"
    names = ("time", "tank1.level", "tank2.level", "tank1.m", "tank2.m", "tank1.medium.d",
             "tank2.medium.d", "pipe.port_a.m_flow", "pipe.port_b.m_flow",
             "tank1.ports[1].m_flow", "tank2.ports[1].m_flow", "pipe.height_ab")
    rows = read_csv(ROOT / f"{prefix}_res.csv", names)
    coverage(rows, 50, 0.05, prefix)
    close(rows[0]["tank1.level"], 1, 1e-7, "stock empty tank1 initial level")
    close(rows[0]["tank2.level"], 0.001, 1e-7, "stock empty tank2 initial film")
    initial_mass = RHO*1.001
    max_mass_error = cumulative = cumulative_abs = max_integral_error = 0.0
    prev = rows[0]
    for row in rows:
        context = f"{prefix} t={row['time']:.9g}"
        for tank in (1, 2):
            if not 0 < row[f"tank{tank}.level"] < 1.1:
                raise AssertionError(f"{context}: empty or overflowing stock tank")
            close(row[f"tank{tank}.medium.d"], RHO, 1e-8, f"{context} stock liquid density")
            close(row[f"tank{tank}.m"], RHO*row[f"tank{tank}.level"], 1e-7, f"{context} stock tank storage")
        close(row["pipe.height_ab"], -1, 1e-10, f"{context} native elevation difference")
        flow = row["pipe.port_a.m_flow"]
        close(row["pipe.port_b.m_flow"], -flow, 1e-7, f"{context} pipe continuity")
        close(row["tank1.ports[1].m_flow"], -flow, 1e-7, f"{context} source tank connection")
        close(row["tank2.ports[1].m_flow"], flow, 1e-7, f"{context} receiving tank connection")
        mass_error = row["tank1.m"]+row["tank2.m"]-initial_mass
        close(mass_error, 0, 1e-4, f"{context} complete stock water inventory")
        max_mass_error = max(max_mass_error, abs(mass_error))
        dt = row["time"]-prev["time"]
        cumulative += dt*(flow+prev["pipe.port_a.m_flow"])/2
        cumulative_abs += dt*(abs(flow)+abs(prev["pipe.port_a.m_flow"]))/2
        integral_error = row["tank2.m"]-rows[0]["tank2.m"]-cumulative
        close(integral_error, 0, 0.05+0.002*cumulative_abs, f"{context} sampled tank transfer")
        max_integral_error = max(max_integral_error, abs(integral_error))
        prev = row
    close(rows[-1]["tank1.level"], 0.001, 1e-4, "stock empty-tank 1 mm outlet residual")
    close(rows[-1]["tank2.level"], 1.0, 1e-4, "stock receiving tank final level")
    if max(abs(r["pipe.port_a.m_flow"]) for r in rows if r["time"] >= 45) > 1e-3:
        raise AssertionError("Stock empty-tank flow did not stop at the dry outlet")
    print(f"PASS {prefix}: {len(rows)} samples; final upstream level {rows[-1]['tank1.level']:.7g} m")
    return dict(id="m3-msl-empty", prefix=prefix, model="Modelica.Fluid.Examples.Tanks.EmptyTanks",
                samples=len(rows), verification=dict(passed=True, maxAbsMassResidualKg=max_mass_error,
                maxSampledTransferResidualKg=max_integral_error),
                metrics=dict(finalUpstreamLevelM=rows[-1]["tank1.level"], finalDownstreamLevelM=rows[-1]["tank2.level"]),
                **identity(prefix))


def verify_pumping_system():
    prefix = "m3_msl_pumping"
    names = ("time", "reservoir.level", "reservoir.m", "pumps.m", "pumps.N", "PT1.y",
             "source.ports[1].m_flow", "sink.ports[1].m_flow", "sink.ports[2].m_flow",
             "reservoirPressure.p_rel", "controller.y", "userValve.opening", "pipe.height_ab")
    rows = read_csv(ROOT / f"{prefix}_res.csv", names)
    coverage(rows, 2000, 0.4, prefix)
    close(rows[0]["reservoir.level"], 2.2, 1e-7, "stock pumping initial reservoir")
    initial_mass = rows[0]["reservoir.m"]+rows[0]["pumps.m"]
    cumulative = cumulative_abs = max_error = 0.0
    previous = rows[0]
    states = set()
    for row in rows:
        context = f"{prefix} t={row['time']:.9g}"
        if not 0 < row["reservoir.level"] < 3:
            raise AssertionError(f"{context}: reservoir outside stock tank bounds")
        close(row["pipe.height_ab"], 50, 1e-10, f"{context} stock elevation")
        close(row["pumps.N"], max(row["PT1.y"], 0.001), 1e-6, f"{context} stock pump standby floor")
        options = scheduled_values(row["time"], ((0, 1e-6), (200, 1.000001)))
        if min(abs(row["userValve.opening"]-x) for x in options) > 1e-7:
            raise AssertionError(f"{context}: stock demand-valve event changed")
        pressure, on = row["reservoirPressure.p_rel"], row["controller.y"]
        if on not in (0, 1):
            raise AssertionError(f"{context}: non-Boolean native on/off controller result")
        if pressure < 18000-0.01 and on != 1 or pressure > 22000+0.01 and on != 0:
            raise AssertionError(f"{context}: stock hysteresis controller inconsistent with pressure")
        if row["time"] > 200:
            states.add(on)
        if row["time"] > 500 and not 12000 < pressure < 28000:
            raise AssertionError(f"{context}: stock pressure regulation left declared broad envelope")
        # Only reservoir and finite pump volume store mass; the pipe and valve do not.
        flow = -row["source.ports[1].m_flow"]-row["sink.ports[1].m_flow"]-row["sink.ports[2].m_flow"]
        old_flow = -previous["source.ports[1].m_flow"]-previous["sink.ports[1].m_flow"]-previous["sink.ports[2].m_flow"]
        dt = row["time"]-previous["time"]
        cumulative += dt*(flow+old_flow)/2
        cumulative_abs += dt*(abs(flow)+abs(old_flow))/2
        error = row["reservoir.m"]+row["pumps.m"]-initial_mass-cumulative
        close(error, 0, 0.2+0.002*cumulative_abs, f"{context} sampled open-system mass balance")
        max_error = max(max_error, abs(error))
        previous = row
    if states != {0, 1}:
        raise AssertionError("Stock pumping controller did not exercise both on and off states after demand")
    require_schedule_events(rows, "userValve.opening", ((0, 1e-6), (200, 1.000001)))
    print(f"PASS {prefix}: {len(rows)} samples; demand event and both pump control states verified")
    return dict(id="m3-msl-pumping", prefix=prefix, model="Modelica.Fluid.Examples.PumpingSystem",
                samples=len(rows), verification=dict(passed=True, maxSampledMassResidualKg=max_error),
                metrics=dict(finalReservoirLevelM=rows[-1]["reservoir.level"],
                             minGaugePressurePa=min(r["reservoirPressure.p_rel"] for r in rows),
                             maxGaugePressurePa=max(r["reservoirPressure.p_rel"] for r in rows)), **identity(prefix))


def main():
    qualifications = [verify_pumping_system(), verify_empty_tanks()]
    cases = [verify_case(case) for case in CASES]
    result = dict(schema="domelica.fluid-metrics.v1", verificationScriptSHA256=sha(Path(__file__)),
                  definitions=dict(
                      tracking="Time-weighted RMSE over 0..300 s, including reference and valve changes.",
                      trackingAcceptance="Absolute level error <=0.025 m throughout the final 20 s of each target plateau.",
                      pressure="Absolute pressure at zero-height, lossless tank ports; tank surfaces are at 101325 Pa.",
                      mass="Closed inventory includes both tanks and the 0.001 m3 pump; pipes and valves store no mass.",
                      energy="Signed pump shaft energy; modeled fluid internal energy includes both tanks and the pump. Tank potential/kinetic energy is outside this simplified model.",
                      sampleIntegralTolerance="Authored energy: 0.05 J + 0.002 times cumulative absolute work; mass transfer: 0.05 kg + 0.002 times cumulative absolute transfer.",
                      speedTrajectory="Native speed-fraction change is checked against the sampled integral of (controller output - speed fraction)/2, tolerance 0.0001 + 0.002 times its cumulative absolute integral. The initial-high-B case also requires the exact first-second response 0.001 + 0.299*exp(-t/2) within 1e-6.",
                      pumpHeadDerivative="When native head and flow derivative columns are exported, the full speed/flow affinity-law chain rule must hold within 1e-5 m/s on open-valve samples with supplyFlow > 1e-5 kg/s. Availability and checked sample count are recorded per case.",
                      visualization="Illustrative engineering schematic; values and direction come from native solver results."),
                  qualifications=qualifications, cases=cases)
    output = ROOT / "artifacts/m3-metrics.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(f"PASS M3: {len(qualifications)} stock qualifications and {len(cases)} authored experiments; {output}")


if __name__ == "__main__":
    main()
