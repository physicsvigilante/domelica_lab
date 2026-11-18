#!/usr/bin/env python3
"""Independently verify native coupled motion and the new spring composition.

The fixed numerical problem definitions and analytical oracles below are not
read from the Modelica output. Only the native solver results drive playback.
The accepted M4 completion/CSV reader is reused without changing its behavior.
"""

import argparse
import json
import math
from pathlib import Path
import sys

from verify_m4 import check_completion, digest, dot, read_case, require_close, track, vector

ROOT = Path(__file__).resolve().parent.parent
PREFIXES = ("m4b_moving_wedge", "m4b_spring_wedge")


def columns(spring):
    result = ["time", "displacement", "speed", "acceleration", "wedgeDisplacement", "wedgeSpeed",
        "wedgeAcceleration", "horizontalMomentum", "kineticEnergy", "gravitationalEnergy",
        "totalEnergy", "normalReaction", "guidePower", "wedgeBody.m", "massBody.m",
        "groundGuide.s", "groundGuide.v", "groundGuide.a", "relativeGuide.s", "relativeGuide.v",
        "relativeGuide.a", "wedgeMass", "blockMass", "inclineAngle", "g", "inclineLength",
        "startAlong", "blockLength", "blockHeight", "blockWidth", "deckThickness", "baseHeight"]
    vectors = ("blockPosition", "wedgePosition", "blockVelocity", "wedgeVelocity", "centerOfMass",
        "guideForceOnBlock", "guideForceOnWedge", "groundReaction", "massBody.frame_a.r_0",
        "wedgeBody.frame_a.r_0", "massBody.v_0", "wedgeBody.v_0", "groundGuide.frame_b.r_0",
        "relativeGuide.frame_a.r_0", "relativeGuide.frame_b.r_0", "relativeGuide.frame_a.f",
        "relativeGuide.frame_b.f", "groundGuide.frame_b.f", "surfaceOrigin")
    result += [f"{name}[{i}]" for name in vectors for i in (1,2,3)]
    if spring:
        result += ["springStiffness", "springFreeLength", "anchorAlong", "springLength",
            "springExtension", "springForce", "elasticEnergy", "composedEnergy", "internalSpring.f",
            "internalSpring.length", "internalSpring.c", "internalSpring.s_unstretched"]
        result += [f"{name}[{i}]" for name in ("internalSpring.frame_a.r_0", "internalSpring.frame_b.r_0",
            "internalSpring.frame_a.f", "internalSpring.frame_b.f") for i in (1,2,3)]
    return result


def verify_case(spring=False):
    prefix = PREFIXES[int(spring)]
    stop, minimum = (6.0,1201) if spring else (1.0,401)
    rows = read_case(prefix,stop,minimum,columns(spring))

    # Independent declared test definitions: Q106 itself supplies only symbols.
    M, m, gravity, angle = 2.0,1.0,10.0,math.pi/6
    c,s = math.cos(angle),math.sin(angle)
    length, start, height, body_length = 4.0,(2.5 if spring else 3.6),0.18,0.3
    surface, wedge_com = [0.0,0.22,0.0],[length*c/2,0.06,0.0]
    initial = [start*c-height*s/2,surface[1]+start*s+height*c/2,0.0]
    normal, uphill = [-s,c,0.0],[c,s,0.0]
    beta = m*c/(M+m)
    effective_mass = m*(M+m*s*s)/(M+m)
    initial_acceleration = m*gravity*s/effective_mass
    stiffness, free_length, anchor_along = 10.0,1.15,3.8
    omega = math.sqrt(stiffness/effective_mass)
    equilibrium = m*gravity*s/stiffness
    initial_energy = gravity*(M*wedge_com[1]+m*initial[1])
    initial_com_x = (M*wedge_com[0]+m*initial[0])/(M+m)
    expected_parameters = {"wedgeMass":M,"blockMass":m,"inclineAngle":angle,"g":gravity,
        "inclineLength":length,"startAlong":start,"blockLength":body_length,"blockHeight":height,
        "blockWidth":0.28,"deckThickness":0.08,"baseHeight":0.12,"wedgeBody.m":M,"massBody.m":m}
    if spring:
        expected_parameters.update({"springStiffness":stiffness,"springFreeLength":free_length,
            "anchorAlong":anchor_along,"internalSpring.c":stiffness,
            "internalSpring.s_unstretched":free_length})
    maxima = {}
    min_normal, min_ground, min_clearance = math.inf,math.inf,math.inf

    for row in rows:
        t = row["time"]
        if spring:
            q = equilibrium*(1-math.cos(omega*t))
            qd = equilibrium*omega*math.sin(omega*t)
            qdd = initial_acceleration*math.cos(omega*t)
        else:
            q,qd,qdd = initial_acceleration*t*t/2,initial_acceleration*t,initial_acceleration
        X,Xd,Xdd = beta*q,beta*qd,beta*qdd
        for name,expected in expected_parameters.items():
            require_close(row[name],expected,1e-11,f"{prefix} declared {name}")
        for j,value in enumerate(surface,1):
            require_close(row[f"surfaceOrigin[{j}]"],value,1e-12,f"{prefix} deck reference")
        for alias,expected,tolerance in (("displacement",q,1e-6),("speed",qd,5e-6),
            ("acceleration",qdd,5e-5),("wedgeDisplacement",X,1e-6),
            ("wedgeSpeed",Xd,5e-6),("wedgeAcceleration",Xdd,5e-5)):
            track(maxima,alias+"Error",row[alias],expected,tolerance,t)
        for alias,component in (("displacement","relativeGuide.s"),("speed","relativeGuide.v"),
            ("acceleration","relativeGuide.a"),("wedgeDisplacement","groundGuide.s"),
            ("wedgeSpeed","groundGuide.v"),("wedgeAcceleration","groundGuide.a")):
            require_close(row[alias],row[component],1e-11,f"{prefix} native {alias}")

        expected_positions = {"blockPosition":[initial[0]+X-c*q,initial[1]-s*q,0.0],
            "wedgePosition":[wedge_com[0]+X,wedge_com[1],0.0]}
        expected_velocities = {"blockVelocity":[Xd-c*qd,-s*qd,0.0],"wedgeVelocity":[Xd,0.0,0.0]}
        for name,expected in {**expected_positions,**expected_velocities}.items():
            for j,value in enumerate(expected,1):
                track(maxima,"worldPositionError_m" if "Position" in name else "worldVelocityError_m_s",
                    row[f"{name}[{j}]"],value,1e-6 if "Position" in name else 5e-6,t)
        for alias,component in (("blockPosition","massBody.frame_a.r_0"),
            ("wedgePosition","wedgeBody.frame_a.r_0"),("blockVelocity","massBody.v_0"),
            ("wedgeVelocity","wedgeBody.v_0")):
            for j in (1,2,3):
                require_close(row[f"{alias}[{j}]"],row[f"{component}[{j}]"],1e-11,
                    f"{prefix} native {alias}")
        actual_q,actual_X = row["displacement"],row["wedgeDisplacement"]
        for j in range(3):
            require_close(row[f"groundGuide.frame_b.r_0[{j+1}]"],actual_X if j==0 else 0.0,
                1e-10,f"{prefix} native wedge origin")
            relative = row[f"relativeGuide.frame_b.r_0[{j+1}]"]-row[f"relativeGuide.frame_a.r_0[{j+1}]"]
            track(maxima,"relativeConstraintError_m",relative,-actual_q*uphill[j],1e-8,t)
            expected_com = (M*row[f"wedgePosition[{j+1}]"]+m*row[f"blockPosition[{j+1}]"])/(M+m)
            require_close(row[f"centerOfMass[{j+1}]"],expected_com,1e-10,f"{prefix} COM monitor")
        momentum = M*row["wedgeVelocity[1]"]+m*row["blockVelocity[1]"]
        track(maxima,"horizontalMomentumDrift_kg_m_s",momentum,0.0,1e-7,t)
        require_close(row["horizontalMomentum"],momentum,1e-10,f"{prefix} momentum monitor")
        track(maxima,"horizontalCOMDrift_m",row["centerOfMass[1]"],initial_com_x,1e-7,t)

        # Test the actual native force balances independently of monitor aliases.
        actual_qdd,actual_Xdd = row["acceleration"],row["wedgeAcceleration"]
        expected_normal = m*(gravity*c-actual_Xdd*s)
        joint_block = [-row[f"relativeGuide.frame_b.f[{j}]"] for j in (1,2,3)]
        joint_wedge = [-row[f"relativeGuide.frame_a.f[{j}]"] for j in (1,2,3)]
        ground = [-row[f"groundGuide.frame_b.f[{j}]"] for j in (1,2,3)]
        spring_block,spring_wedge = [0.0]*3,[0.0]*3
        for j in range(3):
            require_close(row[f"guideForceOnBlock[{j+1}]"],joint_block[j],1e-11,f"{prefix} block joint force alias")
            require_close(row[f"guideForceOnWedge[{j+1}]"],joint_wedge[j],1e-11,f"{prefix} wedge joint force alias")
            require_close(row[f"groundReaction[{j+1}]"],ground[j],1e-11,f"{prefix} ground force alias")
            track(maxima,"jointActionReactionResidual_N",joint_block[j]+joint_wedge[j],0.0,1e-7,t)
            track(maxima,"normalForceResidual_N",joint_block[j],expected_normal*normal[j],1e-7,t)
        track(maxima,"normalForceResidual_N",row["normalReaction"],expected_normal,1e-7,t)
        require_close(ground[0],0.0,1e-8,f"{prefix} no external horizontal reaction")
        require_close(ground[2],0.0,1e-8,f"{prefix} planar ground reaction")
        track(maxima,"groundForceResidual_N",ground[1],(M+m)*gravity-m*s*actual_qdd,1e-7,t)

        elastic = 0.0
        if spring:
            actual_force = stiffness*actual_q
            for alias,expected in (("springExtension",actual_q),("springLength",free_length+actual_q),
                ("internalSpring.length",free_length+actual_q),("springForce",actual_force),
                ("internalSpring.f",actual_force)):
                track(maxima,"springGeometryForceResidual",row[alias],expected,1e-7,t)
            spring_block = [-row[f"internalSpring.frame_b.f[{j}]"] for j in (1,2,3)]
            spring_wedge = [-row[f"internalSpring.frame_a.f[{j}]"] for j in (1,2,3)]
            anchor=[actual_X+anchor_along*c-height*s/2,surface[1]+anchor_along*s+height*c/2,0.0]
            attachment=[row[f"blockPosition[{j+1}]"]+body_length/2*uphill[j] for j in range(3)]
            for j in range(3):
                track(maxima,"springActionReactionResidual_N",spring_block[j]+spring_wedge[j],0.0,1e-7,t)
                track(maxima,"springForceResidual_N",spring_block[j],actual_force*uphill[j],1e-7,t)
                require_close(row[f"internalSpring.frame_a.r_0[{j+1}]"],anchor[j],1e-8,f"{prefix} moving spring anchor")
                require_close(row[f"internalSpring.frame_b.r_0[{j+1}]"],attachment[j],1e-8,f"{prefix} block spring attachment")
            elastic=stiffness*actual_q*actual_q/2
            require_close(row["elasticEnergy"],elastic,1e-8,f"{prefix} spring energy monitor")
            if row["springLength"] < free_length-1e-6:
                raise AssertionError(f"{prefix}: spring left the nominal tensile range")
        actual_block_acceleration=[actual_Xdd-c*actual_qdd,-s*actual_qdd,0.0]
        for j in range(3):
            block_net=joint_block[j]+spring_block[j]-(m*gravity if j==1 else 0.0)
            wedge_net=joint_wedge[j]+spring_wedge[j]+ground[j]-(M*gravity if j==1 else 0.0)
            track(maxima,"blockNewtonResidual_N",block_net,m*actual_block_acceleration[j],1e-7,t)
            track(maxima,"wedgeNewtonResidual_N",wedge_net,M*actual_Xdd if j==0 else 0.0,1e-7,t)
        guide_power=dot(joint_block,vector(row,"blockVelocity"))+dot(joint_wedge,vector(row,"wedgeVelocity"))
        track(maxima,"constraintPowerResidual_W",guide_power,0.0,1e-7,t)
        require_close(row["guidePower"],guide_power,1e-10,f"{prefix} guide power monitor")

        kinetic=(M*dot(vector(row,"wedgeVelocity"),vector(row,"wedgeVelocity"))
            +m*dot(vector(row,"blockVelocity"),vector(row,"blockVelocity")))/2
        gravitational=gravity*(M*row["wedgePosition[2]"]+m*row["blockPosition[2]"])
        energy=kinetic+gravitational+elastic
        for name,expected in (("kineticEnergy",kinetic),("gravitationalEnergy",gravitational),
            ("totalEnergy",kinetic+gravitational)):
            require_close(row[name],expected,1e-8,f"{prefix} energy monitor {name}")
        if spring:
            require_close(row["composedEnergy"],energy,1e-8,f"{prefix} composed energy monitor")
        track(maxima,"energyDrift_J",energy,initial_energy,5e-5,t)
        clearance=min(start-actual_q-body_length/2,length-body_length/2-(start-actual_q))
        min_clearance=min(min_clearance,clearance)
        min_normal,min_ground=min(min_normal,expected_normal),min(min_ground,ground[1])
        if clearance < -1e-7 or expected_normal <= 0.0 or ground[1] <= 0.0:
            raise AssertionError(f"{prefix}: outside finite maintained-contact regime at t={t:g}")

    if max(r["wedgeDisplacement"] for r in rows) < (0.28 if spring else 0.96):
        raise AssertionError(f"{prefix}: wedge did not visibly recoil")
    reversals=sum(a["speed"]*b["speed"]<0 for a,b in zip(rows,rows[1:]))
    if spring and reversals < 6:
        raise AssertionError(f"{prefix}: insufficient coupled reversals {reversals}")
    result={"passed":True,"model":"DomelicaLab.Examples."+("SpringWedge3D" if spring else "MovingWedge3D"),
        "samples":len(rows),"startTime":rows[0]["time"],"stopTime":rows[-1]["time"],
        "relativeTravelRange_m":[min(r["displacement"] for r in rows),max(r["displacement"] for r in rows)],
        "wedgeTravelRange_m":[min(r["wedgeDisplacement"] for r in rows),max(r["wedgeDisplacement"] for r in rows)],
        "minimumNormalReaction_N":min_normal,"minimumGroundReaction_N":min_ground,
        "minimumDeckFootprintClearance_m":min_clearance,"velocityReversals":reversals,
        "maxErrors":maxima,
        "scope":"Ideal coupled translation with maintained frictionless contact; no separation or endpoint impact"}
    if spring:
        result.update({"effectiveRelativeMass_kg":effective_mass,"equilibriumRelativeDrop_m":equilibrium,
            "analyticalPeriod_s":2*math.pi/omega})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completion-only",nargs=3,metavar=("PREFIX","STOP","MIN_SAMPLES"))
    args=parser.parse_args()
    if args.completion_only:
        prefix,stop,count=args.completion_only
        stop,count=float(stop),int(count)
        if not math.isfinite(stop) or stop<=0 or count<2:
            parser.error("positive finite stop and minimum of two samples required")
        check_completion(prefix,stop,count)
        return
    cases={"moving-wedge":verify_case(),"spring-wedge":verify_case(True)}
    source_files=[Path(__file__),ROOT/"scripts/verify_m4.py",ROOT/"scripts/native_m4b.mos",
        ROOT/"scripts/export_native_csv.py",ROOT/"DomelicaLab/Examples/MovingWedge3D.mo",
        ROOT/"DomelicaLab/Examples/SpringWedge3D.mo",ROOT/"DomelicaLab/package.mo",
        ROOT/"DomelicaLab/package.order",ROOT/"DomelicaLab/Examples/package.mo",
        ROOT/"DomelicaLab/Examples/package.order"]
    input_files=[ROOT/f"{prefix}{suffix}" for prefix in PREFIXES
        for suffix in ("_res.mat","_res.csv","_visual.xml",".log")]
    input_files += [ROOT/"artifacts"/f"{prefix}-completion.json" for prefix in PREFIXES]
    input_files += [ROOT/"m4b-native-toolchain.txt"]
    report={"passed":True,"cases":cases,
        "method":"Independent closed-form coupled trajectories and all-native-sample momentum, COM, constraint, force and energy balances",
        "sourceSHA256":{str(p.relative_to(ROOT)):digest(p) for p in source_files},
        "inputsSHA256":{str(p.relative_to(ROOT)):digest(p) for p in input_files},
        "limitations":["Two nominal illustrative parameter sets; no broad parameter sweep or experimental validation.",
            "Bilateral prismatic constraints with positive contact-force and finite-footprint guards; no separation or impact model.",
            "The spring is ideal, massless and undamped; no wire contact, coil limits or friction.",
            "Native scene rendering and OMEdit GUI execution require separate visual verification."]}
    output=ROOT/"artifacts/m4b-metrics.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    for name,case in cases.items():
        print(f"PASS {name}: {case['samples']} native samples, errors {json.dumps(case['maxErrors'],sort_keys=True)}")
    print(f"PASS M4B physics report: {output}")


if __name__=="__main__":
    try:
        main()
    except (AssertionError,OSError,ValueError,KeyError) as error:
        print(f"ERROR: {error}",file=sys.stderr,flush=True)
        raise SystemExit(1)
