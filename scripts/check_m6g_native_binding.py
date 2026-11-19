#!/usr/bin/env python3
"""Bounded authority check: upstream authored geometry agrees with native M6F state."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proof",type=Path,required=True)
    p.add_argument("--csv",type=Path,required=True)
    args=p.parse_args()
    proof=json.loads(args.proof.read_text(encoding="utf-8"))
    with args.csv.open(encoding="utf-8",newline="") as file:
        row=next(csv.DictReader(file))
    def get(key):
        v=float(row[key])
        if not math.isfinite(v):
            raise ValueError("Nonfinite native value: "+key)
        return v
    def close(name,measured,expected):
        if abs(measured-expected)>1e-8:
            raise ValueError(f"Native vs upstream geometry mismatch in {name}: {measured} != {expected}")
    refs=proof["reference"]
    mappings={"anchor":"anchorPosition","Arope":"aRopeEndpoint",
              "Acenter":"aPosition","Caxle":"cPosition","B":"bPosition"}
    for key,prefix in mappings.items():
        for i,expected in enumerate(refs["attachmentPositions"][key],1):
            close(prefix+f"[{i}]",get(prefix+f"[{i}]"),expected)
    for key,prefix,radius in (("C","cPosition","movingRadius"),
                              ("Top","fixedPulleyCenter","topRadius")):
        source=refs["pulleyCentersAndRadii"][key]
        for i,expected in enumerate(source["center"],1):
            close(prefix+f"[{i}]",get(prefix+f"[{i}]"),expected)
        close(radius,get(radius),source["radius"])
    lengths={"S1":"ropeS1Length","S2":"ropeS2Length"}
    for route in proof["routes"]:
        close(route["id"]+" routed native length",
              get(lengths[route["id"]]),route["totalReferenceLength_m"])
    print(json.dumps({"status":"pass","source":"pinned domelica_mecha numeric route",
                      "nativeInitialGeometryMatched":True,
                      "ropeCount":len(proof["routes"]),
                      "referenceAngleDeg":refs["inclinationDegrees"]}))


if __name__=="__main__":
    main()
