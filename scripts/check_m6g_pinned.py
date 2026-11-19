#!/usr/bin/env python3
"""Check the pinned upstream geometry-authoring artifact without accessing its repo.

The actual resolver ran in domelica_mecha's own CI; its complete source/output
hashes and artifact URL are recorded here. This downstream verification does
not claim to recompute the upstream route-selection algorithm.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from math import cos, pi, sin
from pathlib import Path
from rope2d_geometry import evaluate_route


def require(ok,why):
    if not ok:
        raise ValueError(why)


def near(a,b,tol=1e-9):
    return abs(a-b)<=tol


def compare_point(got,want,label):
    require(len(got)==len(want) and all(near(a,b) for a,b in zip(got,want)),
            f"Upstream reference {label} inconsistent with authoring intent")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--intent",type=Path,required=True)
    p.add_argument("--routes",type=Path,required=True)
    p.add_argument("--proof",type=Path,required=True)
    p.add_argument("--modelica",type=Path,required=True)
    args=p.parse_args()
    intent=json.loads(args.intent.read_text(encoding="utf8"))
    routes=json.loads(args.routes.read_text(encoding="utf8"))
    proof=json.loads(args.proof.read_text(encoding="utf8"))
    upstream=proof["upstream"]
    require(upstream["commit"]=="ede82116f3654b6c99043927f3d7a5cb69780801",
            "Unexpected upstream version")
    require(upstream["routeAlgorithm"]=="resolve_string_route_numeric",
            "Wrong upstream geometry-authoring algorithm")
    sha=lambda file:hashlib.sha256(file.read_bytes()).hexdigest()
    require(sha(args.intent)==proof["geometryIntentSHA256"],
            "Geometry input was modified after upstream authoring")
    require(sha(args.modelica)==upstream["modelicaGeometrySHA256"],
            "Modelica physical geometry differs from the exact upstream output")
    require(set(routes["attachments"])=={"anchor","Arope","Acenter","Caxle","B"},
            "Unexpected native attachment binding")
    require(set(routes["pulleys"])=={"C","Top"},
            "Unexpected native pulley binding")
    g=intent["geometry"]
    theta=pi*intent["inclinationDegrees"]/180
    u=(cos(theta),sin(theta))
    n=(-sin(theta),cos(theta))
    c=tuple(g["cInitial"])
    def add(a,b):return (a[0]+b[0],a[1]+b[1])
    def along(a,b,d):return add(a,(b[0]*d,b[1]*d))
    anchor=along(along(c,u,-g["anchorSeparation"]),n,g["movingRadius"])
    a=along(c,u,-g["blockGap"])
    arope=along(a,n,-g["movingRadius"])
    top=along(along(c,u,g["redirectDistance"]),n,-g["topRadius"])
    b=(top[0]+g["topRadius"],top[1]-g["bInitialLeg"])
    positions={"anchor":anchor,"Arope":arope,"Acenter":a,
               "Caxle":c,"B":b}
    pulleys={"C":{"center":c,"radius":g["movingRadius"]},
             "Top":{"center":top,"radius":g["topRadius"]}}
    ref=proof["reference"]
    require(ref["inclinationDegrees"]==30,
            "Missing authoring angle provenance")
    for name,value in positions.items():
        compare_point(ref["attachmentPositions"][name],value,name)
    for name,value in pulleys.items():
        compare_point(ref["pulleyCentersAndRadii"][name]["center"],value["center"],name)
        require(near(ref["pulleyCentersAndRadii"][name]["radius"],value["radius"]),
                "Radius differs from intent")
    proof_routes={r["id"]:r for r in proof["routes"]}
    require(set(proof_routes)=={"S1","S2"},
            "Expected two independent rope authoring certificates")
    for route in routes["ropes"]:
        claimed=proof_routes[route["id"]]
        require(route["nodes"]==claimed["resolved"],
                "Manual route branches differ from upstream resolved branch")
        require(claimed["uniqueAfterIntent"] is True and claimed["backend"]=="numeric",
                "No unique native numeric resolution")
        geom=evaluate_route(route["nodes"],positions,pulleys)
        require(near(geom["length"],claimed["totalReferenceLength_m"],1e-8),
                "Upstream route length differs from the downstream geometry kernel")
        require(len(geom["arcs"])==1 and
                near(geom["arcs"][0]["sweep"],claimed["referenceArcSweepRadians"],1e-8),
                "Upstream arc branch differs from local playback geometry")
    print(json.dumps({
        "status":"pass",
        "source":"upstream domelica_mecha authoring artifact",
        "sourceRun":upstream["runUrl"],
        "authoringInputMatched":True,
        "modelicaGeometryPackageMatched":True,
        "branchesAndLengthsMatched":True,
        "physicalSimulationRunHere":False
    },indent=2))


if __name__=="__main__":
    main()
