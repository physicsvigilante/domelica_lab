#!/usr/bin/env python3
"""Independent post-cut normal-mode oracle for PDF Q192.

The nominal constants below are deliberately independent of Modelica outputs.
The formulas validate native results; they never generate viewer trajectories.
"""

import json
import math
import sys

from verify_m4 import dot, read_case, require_close, track, vector


CASE_PREFIX = "m4c_pdf_composition"
STOP_TIME = 0.8
MINIMUM_SAMPLES = 801
MODEL = "DomelicaLab.Examples.ReleasedSpringChain3D"
MASS, GRAVITY, STIFFNESS = 1.0, 9.81, 100.0
FREE_LENGTH, HEIGHT, WIDTH, DEPTH = 0.6, 0.16, 0.28, 0.24
TOP_INITIAL_HEIGHT = 5.0
OMEGA_1 = math.sqrt(STIFFNESS / MASS)
OMEGA_2 = math.sqrt(3 * STIFFNESS / MASS)
STATIC_EXTENSION = MASS * GRAVITY / STIFFNESS
INITIAL_HEIGHTS = [TOP_INITIAL_HEIGHT,
                   TOP_INITIAL_HEIGHT - HEIGHT - FREE_LENGTH - 2 * STATIC_EXTENSION,
                   TOP_INITIAL_HEIGHT - 2 * HEIGHT - 2 * FREE_LENGTH - 3 * STATIC_EXTENSION]
INITIAL_CENTER = sum(INITIAL_HEIGHTS) / 3
INITIAL_ENERGY = MASS * GRAVITY * sum(INITIAL_HEIGHTS) + 2.5 * STIFFNESS * STATIC_EXTENSION**2
BODY_NAMES = ("top", "middle", "bottom")
NOMINAL_PARAMETERS = {
    "blockMass": MASS, "stiffness": STIFFNESS, "freeLength": FREE_LENGTH, "g": GRAVITY,
    "blockHeight": HEIGHT, "blockWidth": WIDTH, "blockDepth": DEPTH,
    "topInitialHeight": INITIAL_HEIGHTS[0], "middleInitialHeight": INITIAL_HEIGHTS[1],
    "bottomInitialHeight": INITIAL_HEIGHTS[2],
    "upperInitialExtension": 2*STATIC_EXTENSION, "lowerInitialExtension": STATIC_EXTENSION,
}


def oracle(time):
    """Two relative normal modes plus the independent free-fall center mode."""
    c1, c2 = math.cos(OMEGA_1*time), math.cos(OMEGA_2*time)
    s1, s2 = math.sin(OMEGA_1*time), math.sin(OMEGA_2*time)
    upper = STATIC_EXTENSION * (1.5*c1 + 0.5*c2)
    lower = STATIC_EXTENSION * (1.5*c1 - 0.5*c2)
    upper_v = -STATIC_EXTENSION * (1.5*OMEGA_1*s1 + 0.5*OMEGA_2*s2)
    lower_v = -STATIC_EXTENSION * (1.5*OMEGA_1*s1 - 0.5*OMEGA_2*s2)
    upper_a = -STATIC_EXTENSION * (1.5*OMEGA_1**2*c1 + 0.5*OMEGA_2**2*c2)
    lower_a = -STATIC_EXTENSION * (1.5*OMEGA_1**2*c1 - 0.5*OMEGA_2**2*c2)
    d1, d2 = HEIGHT + FREE_LENGTH + upper, HEIGHT + FREE_LENGTH + lower
    center = INITIAL_CENTER - GRAVITY*time*time/2
    center_v = -GRAVITY*time
    positions = [center + (2*d1+d2)/3, center + (d2-d1)/3, center - (d1+2*d2)/3]
    velocities = [center_v + (2*upper_v+lower_v)/3,
                  center_v + (lower_v-upper_v)/3,
                  center_v - (upper_v+2*lower_v)/3]
    accelerations = [-GRAVITY + (2*upper_a+lower_a)/3,
                    -GRAVITY + (lower_a-upper_a)/3,
                    -GRAVITY - (upper_a+2*lower_a)/3]
    return {"heights": positions, "speeds": velocities, "accelerations": accelerations,
            "extensions": [upper, lower], "center": center, "centerSpeed": center_v}


def required_columns():
    columns = list(NOMINAL_PARAMETERS) + ["time", "topHeight", "middleHeight", "bottomHeight", "centerHeight", "centerSpeed",
               "upperExtension", "lowerExtension", "upperTension", "lowerTension",
               "translationalEnergy", "rotationalEnergy", "kineticEnergy", "gravitationalEnergy",
               "elasticEnergy", "potentialEnergy", "totalEnergy"]
    vectors = ["centerOfMass", "centerVelocity", "centerAcceleration",
               "upperStart", "upperEnd", "lowerStart", "lowerEnd"]
    for body in BODY_NAMES:
        columns += [f"{body}Body.{parameter}" for parameter in ("m", "length", "width", "height", "density")]
        vectors += [f"{body}Position", f"{body}Velocity", f"{body}Acceleration", f"{body}AngularVelocity",
                    f"{body}Body.frame_a.r_0", f"{body}Body.v_0", f"{body}Body.a_0",
                    f"{body}Body.frame_a.R.w", f"{body}Body.frame_a.f", f"{body}Body.frame_a.t",
                    f"{body}Body.r_CM", f"{body}Free.frame_b.f", f"{body}Free.frame_b.t"]
        columns += [f"{body}Body.frame_a.R.T[{i},{j}]" for i in (1, 2, 3) for j in (1, 2, 3)]
        columns += [f"{body}Body.I[{i},{j}]" for i in (1, 2, 3) for j in (1, 2, 3)]
    for spring in ("upper", "lower"):
        columns += [f"{spring}Spring.{parameter}" for parameter in ("length", "f", "c", "s_unstretched", "m")]
        for frame in ("a", "b"):
            vectors += [f"{spring}Spring.frame_{frame}.r_0", f"{spring}Spring.frame_{frame}.f"]
    columns += [f"{name}[{axis}]" for name in vectors for axis in (1, 2, 3)]
    if len(set(columns)) != len(columns):
        raise AssertionError("Duplicate Q192 verification column")
    return columns


def verify_pdf():
    rows = read_case(CASE_PREFIX, STOP_TIME, MINIMUM_SAMPLES, required_columns())
    maxima = {}
    minimum_lengths = [math.inf, math.inf]
    minimum_clearance = math.inf
    minimum_lower_edge = math.inf
    extension_ranges = [[math.inf, -math.inf], [math.inf, -math.inf]]
    expected_inertias = [MASS*(HEIGHT**2+DEPTH**2)/12,
                         MASS*(WIDTH**2+DEPTH**2)/12,
                         MASS*(HEIGHT**2+WIDTH**2)/12]

    for row in rows:
        t = row["time"]
        expected = oracle(t)
        for name, value in NOMINAL_PARAMETERS.items():
            require_close(row[name], value, 1e-12, f"Q192 declared illustrative parameter {name}")
        heights, speeds, accelerations = [], [], []
        translational = rotational = 0.0
        for index, body in enumerate(BODY_NAMES):
            position = vector(row, f"{body}Position")
            velocity = vector(row, f"{body}Velocity")
            acceleration = vector(row, f"{body}Acceleration")
            omega = vector(row, f"{body}AngularVelocity")
            heights.append(position[1])
            speeds.append(velocity[1])
            accelerations.append(acceleration[1])
            require_close(row[f"{body}Body.m"], MASS, 1e-12, f"Q192 {body} native mass")
            for name, value in (("length", HEIGHT), ("width", WIDTH), ("height", DEPTH),
                                ("density", MASS/(HEIGHT*WIDTH*DEPTH))):
                require_close(row[f"{body}Body.{name}"], value, 1e-12, f"Q192 {body} native {name}")
            require_close(row[f"{body}Height"], position[1], 1e-12, f"Q192 {body} height alias")
            for axis in range(3):
                target_y = axis == 1
                track(maxima, "positionError_m", position[axis], expected["heights"][index] if target_y else 0,
                      3e-7, t)
                track(maxima, "speedError_m_s", velocity[axis], expected["speeds"][index] if target_y else 0,
                      3e-6, t)
                track(maxima, "accelerationError_m_s2", acceleration[axis],
                      expected["accelerations"][index] if target_y else 0, 3e-5, t)
                for alias, native in ((f"{body}Position", f"{body}Body.frame_a.r_0"),
                                      (f"{body}Velocity", f"{body}Body.v_0"),
                                      (f"{body}Acceleration", f"{body}Body.a_0"),
                                      (f"{body}AngularVelocity", f"{body}Body.frame_a.R.w")):
                    require_close(row[f"{alias}[{axis+1}]"], row[f"{native}[{axis+1}]"], 1e-11,
                                  f"Q192 direct {alias} binding")
                track(maxima, "angularVelocity_rad_s", omega[axis], 0, 1e-8, t)
                require_close(row[f"{body}Body.r_CM[{axis+1}]"], 0, 1e-12, f"Q192 {body} COM frame")
                for native in (f"{body}Free.frame_b.f", f"{body}Free.frame_b.t", f"{body}Body.frame_a.t"):
                    require_close(row[f"{native}[{axis+1}]"], 0, 1e-8, f"Q192 {native} stays unforced")
                for j in range(3):
                    require_close(row[f"{body}Body.frame_a.R.T[{axis+1},{j+1}]"],
                                  float(axis == j), 1e-8, f"Q192 {body} unrotated body frame")
                    require_close(row[f"{body}Body.I[{axis+1},{j+1}]"],
                                  expected_inertias[axis] if axis == j else 0, 1e-12,
                                  f"Q192 {body} independently calculated inertia")
            translational += MASS*dot(velocity, velocity)/2
            rotational += sum(inertia*w*w/2 for inertia, w in zip(expected_inertias, omega))

        tensions = []
        for index, spring in enumerate(("upper", "lower")):
            length = row[f"{spring}Spring.length"]
            extension = length-FREE_LENGTH
            force = row[f"{spring}Spring.f"]
            for name, value in (("c", STIFFNESS), ("s_unstretched", FREE_LENGTH), ("m", 0.0)):
                require_close(row[f"{spring}Spring.{name}"], value, 1e-12, f"Q192 {spring} native {name}")
            tensions.append(force)
            minimum_lengths[index] = min(minimum_lengths[index], length)
            extension_ranges[index][0] = min(extension_ranges[index][0], extension)
            extension_ranges[index][1] = max(extension_ranges[index][1], extension)
            require_close(row[f"{spring}Extension"], extension, 1e-11, "Q192 native spring extension alias")
            require_close(row[f"{spring}Tension"], force, 1e-11, "Q192 native line-force alias")
            track(maxima, "extensionError_m", extension, expected["extensions"][index], 6e-7, t)
            track(maxima, "springForceError_N", force, STIFFNESS*expected["extensions"][index], 6e-5, t)
            track(maxima, "springLawResidual_N", force, STIFFNESS*extension, 1e-7, t)
            start, end = vector(row, f"{spring}Start"), vector(row, f"{spring}End")
            for axis in range(3):
                require_close(start[axis], row[f"{spring}Spring.frame_a.r_0[{axis+1}]"], 1e-11,
                              f"Q192 native {spring} start")
                require_close(end[axis], row[f"{spring}Spring.frame_b.r_0[{axis+1}]"], 1e-11,
                              f"Q192 native {spring} end")
                expected_start = heights[index]-HEIGHT/2 if axis == 1 else 0
                expected_end = heights[index+1]+HEIGHT/2 if axis == 1 else 0
                track(maxima, "springAttachmentResidual_m", start[axis], expected_start, 1e-8, t)
                track(maxima, "springAttachmentResidual_m", end[axis], expected_end, 1e-8, t)
                require_close(row[f"{spring}Spring.frame_a.f[{axis+1}]"], force if axis == 1 else 0,
                              1e-7, f"Q192 {spring} frame_a connector force")
                require_close(row[f"{spring}Spring.frame_b.f[{axis+1}]"], -force if axis == 1 else 0,
                              1e-7, f"Q192 {spring} frame_b connector force")
            distance = math.sqrt(sum((a-b)**2 for a, b in zip(start, end)))
            track(maxima, "springLengthResidual_m", length, distance, 1e-9, t)
            clearance = heights[index]-heights[index+1]-HEIGHT
            minimum_clearance = min(minimum_clearance, clearance)
            if length <= 0.4 or clearance <= 0.4:
                raise AssertionError("Q192 left its qualified positive-length, separate-body regime")

        # y=0 is only a recording-limit reference; the model contains no floor.
        lower_edge = min(heights)-HEIGHT/2
        minimum_lower_edge = min(minimum_lower_edge, lower_edge)
        if lower_edge <= 0.1:
            raise AssertionError("Q192 left its nominal clearance above the y=0 observation plane")

        top_force, middle_force, bottom_force = -tensions[0], tensions[0]-tensions[1], tensions[1]
        for body, acceleration, spring_force in zip(BODY_NAMES, accelerations,
                                                    (top_force, middle_force, bottom_force)):
            track(maxima, "bodyForceBalanceResidual_N", MASS*acceleration,
                  spring_force-MASS*GRAVITY, 1e-7, t)
            for axis in (1, 2, 3):
                require_close(row[f"{body}Body.frame_a.f[{axis}]"], spring_force if axis == 2 else 0,
                              1e-7, f"Q192 {body} native applied force")
        center = sum(heights)/3
        center_speed = sum(speeds)/3
        center_accel = sum(accelerations)/3
        track(maxima, "centerFreeFallError_m", center, expected["center"], 3e-7, t)
        track(maxima, "centerSpeedError_m_s", center_speed, expected["centerSpeed"], 3e-6, t)
        track(maxima, "centerAccelerationError_m_s2", center_accel, -GRAVITY, 1e-7, t)
        for name, actual in (("centerOfMass", center), ("centerVelocity", center_speed),
                             ("centerAcceleration", center_accel)):
            for axis in (1, 2, 3):
                require_close(row[f"{name}[{axis}]"], actual if axis == 2 else 0, 1e-9,
                              f"Q192 {name} native monitor")
        require_close(row["centerHeight"], center, 1e-11, "Q192 center height alias")
        require_close(row["centerSpeed"], center_speed, 1e-11, "Q192 center speed alias")
        gravitational = MASS*GRAVITY*sum(heights)
        elastic = sum(force*force/(2*STIFFNESS) for force in tensions)
        total_energy = translational+rotational+gravitational+elastic
        track(maxima, "totalEnergyDrift_J", total_energy, INITIAL_ENERGY, 2e-5, t)
        for name, actual in (("translationalEnergy", translational), ("rotationalEnergy", rotational),
                             ("kineticEnergy", translational+rotational), ("gravitationalEnergy", gravitational),
                             ("elasticEnergy", elastic), ("potentialEnergy", gravitational+elastic),
                             ("totalEnergy", total_energy)):
            require_close(row[name], actual, 1e-8, f"Q192 {name} independently reconstructed")

    for body, initial_acceleration in zip(BODY_NAMES, (-3*GRAVITY, 0, 0)):
        require_close(rows[0][f"{body}Acceleration[2]"], initial_acceleration, 1e-6,
                      f"Q192 {body} post-cut initial acceleration")
    if min(high-low for low, high in extension_ranges) < 0.3:
        raise AssertionError("Q192 did not exercise both observable internal spring motions")
    if INITIAL_CENTER-rows[-1]["centerHeight"] < 3.1:
        raise AssertionError("Q192 did not exhibit the qualified center-of-mass free fall")
    return {
        "passed": True, "model": MODEL, "prefix": CASE_PREFIX,
        "sourceProblem": {"file": "01_mechanics.pdf", "pdfPage": 26, "printedPage": "6.160", "number": 192},
        "samples": len(rows), "startTime": rows[0]["time"], "stopTime": rows[-1]["time"],
        "method": "Independent closed-form normal modes plus center-of-mass free fall; native force, energy and geometry checks at every sample",
        "illustrativeParameters": {"massEach_kg": MASS, "springStiffnessEach_N_m": STIFFNESS,
                                   "springFreeLengthEach_m": FREE_LENGTH, "gravity_m_s2": GRAVITY,
                                   "blockHeight_m": HEIGHT, "topInitialHeight_m": TOP_INITIAL_HEIGHT},
        "normalModePeriods_s": [2*math.pi/OMEGA_1, 2*math.pi/OMEGA_2],
        "initialAccelerationsUpward_m_s2": [rows[0][f"{body}Acceleration[2]"] for body in BODY_NAMES],
        "centerOfMassDrop_m": INITIAL_CENTER-rows[-1]["centerHeight"],
        "minimumSpringLengths_m": minimum_lengths,
        "minimumBodySurfaceClearance_m": minimum_clearance,
        "minimumBodyLowerEdgeHeight_m": minimum_lower_edge,
        "observationPlaneHeight_m": 0.0,
        "springExtensionRanges_m": extension_ranges,
        "initialMechanicalEnergy_J": INITIAL_ENERGY, "maxErrors": maxima,
        "scope": "Post-cut initial-value simulation of a free three-body chain; no cutting event, guide, floor, impact, spring mass, damping or coil contact; all numerical choices illustrative",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(verify_pdf(), indent=2))
    except (AssertionError, OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
