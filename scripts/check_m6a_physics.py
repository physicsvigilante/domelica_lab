#!/usr/bin/env python3
"""Bounded physical consistency of M6A native CSV; not another dynamics solver."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

def check(csv_file):
    with Path(csv_file).open(newline="", encoding="utf-8") as stream:
        reader=csv.DictReader(stream)
        required=["time","leftAngle","rightAngle","totalEnergy","pendulumLength",
                  "springLength","springFreeLength","leftBob.m","rightBob.m","world.g",
                  "world.n[1]","world.n[2]","world.n[3]"]
        for side in ("left","right"):
            for name in ("Position","PivotPosition","Velocity","Acceleration","SpringOnBob","RodOnBob"):
                required.extend(f"{side}{name}[{i}]" for i in (1,2,3))
        missing=set(required)-set(reader.fieldnames or [])
        if missing:
            raise ValueError("Missing native variables: "+", ".join(sorted(missing)))
        raw=list(reader)
    if len(raw)<400:
        raise ValueError("Unexpected native sample count")
    samples=sorted(set([0,1,len(raw)//4,len(raw)//2,3*len(raw)//4,len(raw)-1]))
    def val(row,name):
        value=float(row[name])
        if not math.isfinite(value):
            raise ValueError("Nonfinite native variable: "+name)
        return value
    def xyz(row,name):
        return [val(row,f"{name}[{i}]") for i in (1,2,3)]
    def norm(a):
        return math.sqrt(sum(x*x for x in a))
    times=[val(row,"time") for row in raw]
    if times[0]!=0 or not math.isclose(times[-1],5,abs_tol=1e-10) or any(b<a for a,b in zip(times,times[1:])):
        raise ValueError("Missing or decreasing native time samples")
    angle0=[val(raw[0],name) for name in ("leftAngle","rightAngle")]
    if abs(angle0[0]-math.radians(24))>1e-10 or abs(angle0[1]-math.radians(-12))>1e-10:
        raise ValueError("Incorrect initial native release angles")
    length=val(raw[0],"pendulumLength")
    checkvals={"maxRodLengthError_m":0,"maxNewtonResidual_N":0,
               "maxSpringActionReaction_N":0,"minBobSeparation_m":float("inf"),
               "initialAngles_rad":angle0,"samples":len(raw),
               "timeStart_s":times[0],"timeStop_s":times[-1]}
    for index in samples:
        row=raw[index]
        masses={side:val(row,side+"Bob.m") for side in ("left","right")}
        gravity=[val(row,"world.g")*val(row,f"world.n[{i}]") for i in (1,2,3)]
        spring_forces={}
        position={}
        for side in ("left","right"):
            position[side]=xyz(row,side+"Position")
            pivot=xyz(row,side+"PivotPosition")
            rod_error=abs(norm([x-y for x,y in zip(position[side],pivot)])-length)
            checkvals["maxRodLengthError_m"]=max(checkvals["maxRodLengthError_m"],rod_error)
            spring=xyz(row,side+"SpringOnBob")
            rod=xyz(row,side+"RodOnBob")
            spring_forces[side]=spring
            acceleration=xyz(row,side+"Acceleration")
            residual=norm([masses[side]*acceleration[i]-spring[i]-rod[i]-masses[side]*gravity[i]
                           for i in range(3)])
            checkvals["maxNewtonResidual_N"]=max(checkvals["maxNewtonResidual_N"],residual)
        checkvals["maxSpringActionReaction_N"]=max(checkvals["maxSpringActionReaction_N"],
                    norm([spring_forces["left"][i]+spring_forces["right"][i] for i in range(3)]))
        gap=norm([position["left"][i]-position["right"][i] for i in range(3)])
        checkvals["minBobSeparation_m"]=min(checkvals["minBobSeparation_m"],gap)
        if abs(gap-val(row,"springLength"))>1e-6:
            raise ValueError("Spring endpoint geometry differs from native positions")
    e=[val(row,"totalEnergy") for row in raw]
    drift=max(abs(x-e[0]) for x in e)/max(1,abs(e[0]))
    checkvals["maxEnergyRelativeDrift"]=drift
    if checkvals["maxRodLengthError_m"]>1e-6:
        raise ValueError("Pendulum rod constraints drifted")
    if checkvals["maxSpringActionReaction_N"]>1e-5:
        raise ValueError("Spring forces violate action/reaction")
    if checkvals["maxNewtonResidual_N"]>1e-4:
        raise ValueError("Native rod/spring/weight force balance mismatch")
    if checkvals["minBobSeparation_m"]<=.36:
        raise ValueError("The bobs approached the contact exclusion")
    if drift>1e-4:
        raise ValueError("Undamped mechanical energy drift exceeds tolerance")
    if max(abs(val(row,"leftAngle")-val(row,"rightAngle")) for row in raw)<.01:
        raise ValueError("Expected relative pendulum motion is absent")
    return {"passed":True,"model":"DomelicaLab.Examples.SpringCoupledPendulums3D",
            "checks":checkvals,"inspectedIndices":samples,
            "scope":"Native force balances, geometry and energy only; no independent dynamics solver."}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    try:
        report=check(args.csv)
    except Exception as error:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({"passed":False,"error":str(error)},indent=2)+"\n")
        raise
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
