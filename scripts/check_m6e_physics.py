#!/usr/bin/env python3
"""Small independent oracle: one continuous rope, A/B 2kg, C mass explicit."""
import argparse
import csv
import json
import math
from pathlib import Path


def check(path):
    with path.open(newline="", encoding="utf8") as f:
        rows=list(csv.DictReader(f))
    if len(rows)<290:
        raise ValueError("Missing native samples")
    def get(row,name):
        x=float(row[name])
        if not math.isfinite(x):
            raise ValueError("Nonfinite "+name)
        return x
    mA,mB,mC,g=[get(rows[0],n) for n in
        ("massA","massB","carrierMassC","g")]
    if abs(mA-2)>1e-8 or abs(mB-2)>1e-8 or mC<=0:
        raise ValueError("2kg A/B with a finite declared C carriage mass required")
    T=2*g/(1/mA+4/mB+1/mC)
    aA=g-T/mA
    aB=g-2*T/mB
    aC=g+T/mC
    d0={k:get(rows[0],k) for k in
        ("time","aPosition[2]","bPosition[2]","cPosition[2]","ropeLength",
         "totalEnergy","massA","massB","carrierMassC")}
    maxerr={k:0.0 for k in ("trajectory_m","velocity_mps","acceleration_mps2","constraint_m",
      "force_N","energy_J","rope_length_m","constraint_power_W")}
    def err(key,*items):
        maxerr[key]=max(maxerr[key],*[abs(x) for x in items])
    t0=d0["time"]
    for row in rows:
        t=get(row,"time")-t0
        for prefix,accel,initial in (("a",aA,d0["aPosition[2]"]),
                                    ("b",aB,d0["bPosition[2]"]),
                                    ("c",aC,d0["cPosition[2]"])):
            d=.5*accel*t*t
            err("trajectory_m",get(row,prefix+"Drop")-d,
                get(row,prefix+"Position[2]")-(initial-d))
            err("velocity_mps",get(row,prefix+"DownSpeed")-accel*t,
                get(row,prefix+"Velocity[2]")+accel*t)
            err("acceleration_mps2",get(row,prefix+"DownAcceleration")-accel,
                get(row,prefix+"Acceleration[2]")+accel)
        qA,qB,qC=[get(row,s+"Drop") for s in ("a","b","c")]
        vA,vB,vC=[get(row,s+"DownSpeed") for s in ("a","b","c")]
        err("constraint_m",qA+2*qB-qC)
        err("constraint_power_W",get(row,"ropePower"),
            (vA+2*vB-vC)*T)
        err("force_N",get(row,"ropeTension")-T,
            mA*aA-(mA*g-T),mB*aB-(mB*g-2*T),
            mC*aC-(mC*g+T))
        err("rope_length_m",get(row,"ropeLength")-d0["ropeLength"])
        kinetic=.5*(mA*vA*vA+mB*vB*vB+mC*vC*vC)
        energy=g*(mA*get(row,"aPosition[2]")+mB*get(row,"bPosition[2]")
                  +mC*get(row,"cPosition[2]"))+kinetic
        err("energy_J",energy-d0["totalEnergy"],
            get(row,"totalEnergy")-d0["totalEnergy"])
        if get(row,"ropeTension")<=0:
            raise ValueError("No positive rope tension")
    limit=2e-6
    failures={k:v for k,v in maxerr.items() if v>limit}
    result={"status":"pass" if not failures else "fail",
      "samples":len(rows),"stopTime_s":get(rows[-1],"time"),
      "assumptions":{"massA_kg":mA,"massB_kg":mB,
        "illustrative_C_carriage_kg":mC,"gravity_mps2":g,
        "one_continuous_rope":True},
      "analytic":{"tension_N":T,"A_down_mps2":aA,"B_down_mps2":aB,
        "C_down_mps2":aC,"massless_C_limit_tension_N":0.0},
      "maxErrors":maxerr}
    if failures:
        raise ValueError(json.dumps(result,indent=2))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    result=check(args.csv)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
