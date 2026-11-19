#!/usr/bin/env python3
"""Focused native oracle for the 30-degree inclined, two-rope moving pulley."""
from __future__ import annotations
import argparse
import csv
import json
from math import cos, isfinite, pi, sin
from pathlib import Path

def check(path):
    with path.open(newline="",encoding="utf8") as file:
        rows=list(csv.DictReader(file))
    if len(rows)<450:
        raise ValueError("Native recording has too few samples")
    def value(row,key):
        v=float(row[key])
        if not isfinite(v):
            raise ValueError(f"Nonfinite {key}")
        return v
    first=rows[0]
    mA,mB,g,theta=[value(first,n) for n in ("massA","massB","g","slopeAngle")]
    if mA<=0 or mB<=0 or g<=0 or abs(theta-pi/6)>1e-9:
        raise ValueError("Expected positive masses/gravity and a 30 degree incline")
    aB=g*(mB-2*mA*sin(theta))/(mB+4*mA)
    aC=aB
    aA=2*aC
    T1=mA*(g*sin(theta)+aA)
    T2=2*T1
    if T1<=0 or T2<=0 or aB<=0:
        raise ValueError("Demonstration is outside the positive-tension nominal regime")
    t0=value(first,"time")
    yA0=value(first,"aPosition[2]")
    yB0=value(first,"bPosition[2]")
    yC0=value(first,"cPosition[2]")
    energy0=value(first,"totalEnergy")
    lengths=[value(first,n) for n in ("ropeS1Length","ropeS2Length")]
    maxima={k:0.0 for k in ("kinematics_m","velocity_mps","acceleration_mps2",
         "tension_N","force_balance_N","constraint_m","rope_length_m","energy_J")}
    def err(k,*res):
        maxima[k]=max(maxima[k],*(abs(x) for x in res))
    for row in rows:
        t=value(row,"time")-t0
        QA=.5*aA*t*t
        QC=.5*aC*t*t
        QB=.5*aB*t*t
        VA=aA*t
        VC=aC*t
        VB=aB*t
        qA,qC,qB=[value(row,k) for k in ("aRise","cRise","bDrop")]
        vA,vC,vB=[value(row,k) for k in ("aUpSpeed","cUpSpeed","bDownSpeed")]
        err("kinematics_m",qA-QA,qC-QC,qB-QB,
            value(row,"aPosition[2]")-(yA0+QA*sin(theta)),
            value(row,"cPosition[2]")-(yC0+QC*sin(theta)),
            value(row,"bPosition[2]")-(yB0-QB))
        err("velocity_mps",vA-VA,vC-VC,vB-VB)
        err("acceleration_mps2",
            value(row,"aUpAcceleration")-aA,
            value(row,"cUpAcceleration")-aC,
            value(row,"bDownAcceleration")-aB,
            value(row,"aAcceleration[2]")-aA*sin(theta),
            value(row,"bAcceleration[2]")+aB)
        t1,t2=[value(row,k) for k in ("tensionS1","tensionS2")]
        err("tension_N",t1-T1,t2-T2)
        err("constraint_m",qA-2*qC,qC-qB)
        err("force_balance_N",
            t1-mA*g*sin(theta)-mA*aA,
            mB*g-t2-mB*aB,t2-2*t1,
            value(row,"cNetRopeForce"))
        for j,name in enumerate(("ropeS1Length","ropeS2Length")):
            err("rope_length_m",value(row,name)-lengths[j])
        err("energy_J",value(row,"totalEnergy")-energy0)
        if t1<=0 or t2<=0:
            raise ValueError("Rope became non-tensile")
        if value(row,"blockGap")+qC-qA<=.25:
            raise ValueError("A approached pulley C too closely")
    final=rows[-1]
    if value(final,"aRise")<.05:
        raise ValueError("No real upslope motion")
    failures={k:v for k,v in maxima.items() if v>1e-6}
    report={"status":"fail" if failures else "pass","samples":len(rows),
      "assumptions":{"mA_kg":mA,"mB_kg":mB,"frictionless":True,"incline_deg":theta*180/pi},
      "analytical":{"aA_up_mps2":aA,"aC_up_mps2":aC,"aB_down_mps2":aB,
        "T_s1_N":T1,"T_s2_N":T2},
      "final":{"A_up_m":value(final,"aRise"),"C_up_m":value(final,"cRise"),
        "B_down_m":value(final,"bDrop")}, "maxAbsErrors":maxima}
    if failures:
        raise ValueError(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    a=p.parse_args()
    r=check(a.csv)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r,indent=2))
