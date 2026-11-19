#!/usr/bin/env python3
"""Independent per-sample oracle for the user-supplied two-rope P1..P4 diagram.

The diagram prescribes A's 6 m/s² leftward acceleration. It does NOT specify
masses, radii, wheel inertia or driving force; our nominal values are illustrative.
Two taut ropes imply s_A=2*s_P1 and s_P1=3*s_B. For a driven A:
    a_P1=a_A/2, a_B=a_A/6 (up);
    3*T2-M_B*g=M_B*a_B, 2*T1=T2;
    F_drive-T1=M_A*a_A.
Checks OpenModelica native observations without prescribing any native motion.
"""
from __future__ import annotations
import argparse
import csv
import json
from math import isfinite, pi
from pathlib import Path


def check(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    if len(rows)<3:
        raise ValueError("Native result must have at least three sampled rows")
    def get(row, name):
        try:
            x=float(row[name])
        except (KeyError,TypeError,ValueError) as error:
            raise ValueError(f"Missing or nonnumeric native column {name!r}") from error
        if not isfinite(x):
            raise ValueError(f"Nonfinite native value in {name}")
        return x
    first=rows[0]
    mA,mB,g,aA = [get(first,name) for name in
                   ("massA","massB","g","givenLeftAcceleration")]
    r1,r2,r3,r4 = [get(first,name) for name in ("r1","r2","r3","r4")]
    xWall,xA0,xP10,xP2,yP2,yP4,yB0,offset = [
        get(first,name) for name in ("wallX","initialAX","initialP1X","p2X",
                                      "p2Y","p4Y","initialBY","p3HeightAboveB")]
    if min(mA,mB,g,aA,r1,r2,r3,r4)<=0:
        raise ValueError("Invalid nominal positive physical parameters")
    aP1=aA/2
    aB=aA/6
    tension2=mB*(g+aB)/3
    tension1=tension2/2
    drive=mA*aA+tension1
    p3X=xP2+r2+r3
    p4X=p3X+r3+r4
    bX=p4X+r4
    yP1=yP2+r2
    yA=yP1-r1
    rope1_0=(xP10-xWall)+(xP10-xA0)+pi*r1
    rope2_0=(xP2-xP10)+(yP2-yB0-offset)+(yP4-yB0-offset)+(yP4-yB0)
    rope2_0+=pi*(r2/2+r3+r4)
    e0=g*(mA*yA+mB*yB0)
    t0=get(first,"time")
    max_error={k:0.0 for k in [
        "position_m","velocity_mps","acceleration_mps2","rope_length_m",
        "constraint_m","constraint_velocity_mps","constraint_acceleration_mps2",
        "tension_N","force_balance_N","power_W","work_J","energy_J","geometry_m"]}
    def error(kind,*residuals):
        max_error[kind]=max(max_error[kind],*(abs(v) for v in residuals))
    previous=t0
    for row in rows:
        t=get(row,"time")
        if t<previous:
            raise ValueError("Native times must be nondecreasing")
        previous=t
        elapsed=t-t0
        qa=aA*elapsed**2/2
        q1=aP1*elapsed**2/2
        qb=aB*elapsed**2/2
        vA=aA*elapsed
        vP1=aP1*elapsed
        vB=aB*elapsed
        xA=xA0-qa
        x1=xP10-q1
        yB=yB0+qb
        centres={
            "p1Center":(x1,yP1,0),
            "p2Center":(xP2,yP2,0),
            "p3Center":(p3X,yB+offset,0),
            "p3CarrierBase":(p3X,yB,0),
            "p4Center":(p4X,yP4,0),
            "wallAnchor":(xWall,yP1+r1,0),
        }
        for prefix,expected in centres.items():
            for i,component in enumerate(expected,start=1):
                error("geometry_m",get(row,f"{prefix}[{i}]")-component)
        for prefix,position,velocity,acceleration in [
            ("a",(xA,yA,0),(-vA,0,0),(-aA,0,0)),
            ("b",(bX,yB,0),(0,vB,0),(0,aB,0))]:
            for i in range(3):
                error("position_m",get(row,f"{prefix}Position[{i+1}]")-position[i])
                error("velocity_mps",get(row,f"{prefix}Velocity[{i+1}]")-velocity[i])
                error("acceleration_mps2",get(row,f"{prefix}Acceleration[{i+1}]")-acceleration[i])
        for name,reference in [
            ("aLeftDisplacement",qa),("p1LeftDisplacement",q1),("bRise",qb)]:
            error("position_m",get(row,name)-reference)
        for name,reference in [
            ("aLeftSpeed",vA),("p1LeftSpeed",vP1),("bUpSpeed",vB)]:
            error("velocity_mps",get(row,name)-reference)
        for name,reference in [
            ("aLeftAcceleration",aA),("p1LeftAcceleration",aP1),
            ("bUpAcceleration",aB)]:
            error("acceleration_mps2",get(row,name)-reference)

        T1=get(row,"tensionS1")
        T2=get(row,"tensionS2")
        force=get(row,"leftDriveForce")
        error("tension_N",T1-tension1,T2-tension2)
        error("force_balance_N",T2-2*T1,force-T1-mA*aA,
              3*T2-mB*g-mB*aB,get(row,"p1NetRopeForce"))
        error("constraint_m",qa-2*q1,q1-3*qb)
        error("constraint_velocity_mps",vA-2*vP1,vP1-3*vB)
        error("constraint_acceleration_mps2",aA-2*aP1,aP1-3*aB)
        error("rope_length_m",
              get(row,"ropeS1Length")-rope1_0,
              get(row,"ropeS2Length")-rope2_0,
              (x1-xWall)+(x1-xA)+pi*r1-rope1_0,
              (xP2-x1)+(yP2-yB-offset)+(yP4-yB-offset)+(yP4-yB)
                +pi*(r2/2+r3+r4)-rope2_0)
        for prefix,expected in (
                ("aRopeForce",(T1,0,0)),
                ("aExternalForce",(-force,0,0)),
                ("bRopeForce",(0,3*T2,0))):
            for i,component in enumerate(expected,start=1):
                error("tension_N",get(row,f"{prefix}[{i}]")-component)
        K=0.5*(mA*vA*vA+mB*vB*vB)
        U=g*(mA*yA+mB*yB)
        E=K+U
        error("energy_J",
              get(row,"kineticEnergy")-K,
              get(row,"potentialEnergy")-U,
              get(row,"totalEnergy")-E)
        P=force*vA
        W=force*qa
        error("power_W",get(row,"externalPower")-P)
        error("work_J",get(row,"driveWork")-W,E-e0-W)
        if T1<=0 or T2<=0 or force<=0:
            raise ValueError("Nominal model entered slack/compressive or reversed-force regime")
        if xA-xWall<=0.25 or x1-xA<=r1+.25 or x1-xWall<=r1+.25:
            raise ValueError("Nominal horizontal route clearance violated")
        if xP2-x1<=r2+.25 or yP2-(yB+offset)<=r2+r3+.25:
            raise ValueError("Nominal P1/P2/P3 clearance violated")
        if yP4-(yB+offset)<=r3+r4+.25 or yP4-yB<=r4+.25:
            raise ValueError("Nominal P3/P4/B clearance violated")
    if previous-t0<=0 or get(rows[-1],"bRise")<0.1:
        raise ValueError("No nontrivial simulated motion of B")
    tolerances={key:1e-6 for key in max_error}
    tolerances["energy_J"]=max(1e-6,1e-8*abs(e0))
    failures={key:value for key,value in max_error.items() if value>tolerances[key]}
    report={
        "status":"fail" if failures else "pass",
        "samples":len(rows),"startTime_s":t0,"stopTime_s":previous,
        "source":{"AaccelerationLeft_mps2":aA,"massA_kg":mA,"massB_kg":mB,
                  "pulleyRadii_m":[r1,r2,r3,r4],"sourceIsDiagramPrescribedAcceleration":True},
        "analytic":{"P1accelerationLeft_mps2":aP1,"BaccelerationUp_mps2":aB,
                    "ropeS1Tension_N":tension1,"ropeS2Tension_N":tension2,
                    "appliedForceLeft_N":drive,"ropeS1Length_m":rope1_0,
                    "ropeS2Length_m":rope2_0},
        "final":{"AleftDisplacement_m":get(rows[-1],"aLeftDisplacement"),
                 "P1leftDisplacement_m":get(rows[-1],"p1LeftDisplacement"),
                 "Brise_m":get(rows[-1],"bRise")},
        "maxAbsoluteErrors":max_error,"tolerances":tolerances
    }
    if failures:
        raise ValueError(json.dumps(report,indent=2))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv",required=True,type=Path)
    parser.add_argument("--report",required=True,type=Path)
    args=parser.parse_args()
    result=check(args.csv)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
