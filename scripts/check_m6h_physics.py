#!/usr/bin/env python3
"""Focused 10s native acceptance: 8/4.5 kg, spring, lift-off and e=0 hard stop."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path


def check(csv_path: Path):
    with csv_path.open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    if len(rows)<995:
        raise ValueError("Expected >=995 10-second native samples")
    def v(row,name):
        try:
            number=float(row[name])
        except (ValueError,KeyError) as e:
            raise ValueError("Missing numeric native signal "+name) from e
        if not math.isfinite(number):
            raise ValueError("Non-finite "+name)
        return number

    first=rows[0]
    massA,massB,k,g=[v(first,key) for key in
                       ("massA","massB","springK","gravity")]
    if abs(massA-8)>1e-10 or abs(massB-4.5)>1e-10 or k<=0:
        raise ValueError("Wrong mass or spring configuration")
    if abs(k-20)>1e-10:
        raise ValueError("Missing explicitly assumed k=20 N/m")
    if abs(v(first,"time"))>1e-8 or abs(v(rows[-1],"time")-10)>1e-7:
        raise ValueError("10 second output time range was not completed")
    if abs(v(first,"aLift"))>1e-8 or abs(v(first,"aUpSpeed"))>1e-7:
        raise ValueError("A must initially rest on its hard floor")
    if abs(v(first,"springExtension"))>1e-8:
        raise ValueError("Spring must start at natural length")

    errors={key:0.0 for key in (
        "native_position_m","native_rope_length_m","native_spring_force_N",
        "native_B_Newton_mps2","native_energy_J","spring_extension_m")}
    def err(key,*values):
        errors[key]=max(errors[key],*(abs(x) for x in values))
    initialRope=v(first,"routedRopeLength")
    prevT=-1
    contactStates=[]
    energies=[]
    heights=[]
    speeds=[]
    for row in rows:
        t=v(row,"time")
        if t<prevT-1e-10:
            raise ValueError("Recorded times reversed")
        prevT=t
        qa,qb,ql=[v(row,key) for key in ("aLift","bDrop","ropeLeftRise")]
        yA,yB,yL=[v(row,key) for key in
                  ("aPosition[2]","bPosition[2]","ropeLeftPosition[2]")]
        va,vb=[v(row,key) for key in ("aUpSpeed","bDownSpeed")]
        tension=v(row,"springForce")
        normal=v(row,"floorNormal")
        E=v(row,"totalEnergy")
        K=.5*(massA*va*va+massB*vb*vb)
        P=g*(massA*yA+massB*yB)
        S=.5*k*v(row,"springExtension")**2
        err("native_position_m",
            yA-v(row,"aRestHeight")-qa,
            yB-v(row,"bInitialHeight")+qb,
            yL-v(row,"aRestHeight")-v(row,"springFreeLength")-ql)
        err("native_rope_length_m",v(row,"routedRopeLength")-initialRope,ql-qb)
        err("native_spring_force_N",tension-k*(ql-qa),
            v(row,"ropeTension")-tension)
        err("spring_extension_m",v(row,"springExtension")-(ql-qa))
        err("native_B_Newton_mps2",
            v(row,"bDownAcceleration")-(g-tension/massB))
        err("native_energy_J",E-(K+P+S))
        if qa < -1e-5:
            raise ValueError("A penetrated the hard floor")
        if tension < -1e-5:
            raise ValueError("Taut-rope domain violated: compressive tension")
        if normal < -1e-5:
            raise ValueError("Floor applied pulling instead of pushing")
        contactStates.append(v(row,"aFloor.stopped"))
        energies.append(E)
        heights.append(qa)
        speeds.append(va)
    # Count actual native free→hard-stop transitions, not merely low positions.
    contactTransitions=[i for i in range(1,len(rows))
        if contactStates[i] == -1 and contactStates[i-1] != -1]
    liftTransitions=[i for i in range(1,len(rows))
        if contactStates[i] != -1 and contactStates[i-1] == -1]
    if max(heights)<0.08 or not liftTransitions or not contactTransitions:
        raise ValueError("No bona fide lift-off plus subsequent floor impact")
    impactEvents=[]
    for i in contactTransitions:
        # Right after an inelastic impact the native hard-stop velocity MUST
        # be zero, not a reversed upward bounce. Later lift-off is allowed.
        if abs(speeds[i])>2e-4:
            raise ValueError("A rebounded or retained nonzero velocity after impact")
        hold=[j for j in range(i,min(i+6,len(rows)))
              if contactStates[j] == -1]
        if (len(hold)<3 or
                max(abs(speeds[j]) for j in hold)>2e-4 or
                max(heights[j] for j in hold)>2e-4):
            raise ValueError("A failed to remain at rest immediately after impact")
        impactEvents.append({
            "time_s":v(rows[i],"time"),
            "postImpactSpeed_mps":speeds[i],
            "postImpactFloorHeight_m":heights[i]})
    if energies[-1]>=energies[0]-1:
        raise ValueError("Inelastic impacts did not dissipate noticeable energy")
    maxRise=max(energies[i+1]-energies[i] for i in range(len(rows)-1))
    if maxRise>0.1:
        raise ValueError("Mechanical energy increased without any energy source")
    if any(value>1e-4 for value in errors.values()):
        raise ValueError("Native physics identity failed: "+json.dumps(errors))
    return {
        "status":"pass","samples":len(rows),"duration_s":10.0,
        "given":{"massA_kg":massA,"massB_kg":massB},
        "illustrative":{"springK_N_per_m":k,
                         "springFreeLength_m":v(first,"springFreeLength"),
                         "gravity_mps2":g},
        "contactLaw":"MSL MassWithStopAndFriction hard lower stop: reinit(v,0), restitution 0",
        "liftOffTransitions":len(liftTransitions),
        "inelasticGroundImpacts":len(contactTransitions),
        "impactSamples":impactEvents,
        "maxALift_m":max(heights),
        "energyInitial_J":energies[0],"energyFinal_J":energies[-1],
        "netMechanicalEnergyLoss_J":energies[0]-energies[-1],
        "maxStepEnergyRise_J":maxRise,
        "maxAbsErrors":errors}

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    result=check(a.csv)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
