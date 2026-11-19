#!/usr/bin/env python3
"""M6G: use domelica_mecha upstream to AUTHOR an M6F incline's rope geometry.

Input: compact 30-degree relative construction and ordered route intent.
Upstream: numeric selected-branch resolver + exact tangent/arc geometry.
Output: resolved route JSON for unchanged domelica_lab viewer, Modelica
        parameter package, and an authoring provenance/certificate report.

No dynamics are solved here. Never claim inferred picture dimensions or masses.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from math import cos, isfinite, pi, sin
from pathlib import Path

from physics_sandbox.models import AttachmentPoint, IdealPulley, Scene, String, StringRouteNode
from physics_sandbox.route_resolution import PassageIntentSpec, resolve_string_route_numeric

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM_SHA="ede82116f3654b6c99043927f3d7a5cb69780801"
REQUIRED_GEOM={"cInitial","movingRadius","topRadius","anchorSeparation",
               "blockGap","redirectDistance","bInitialLeg"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def point_add(a, b):
    return (a[0]+b[0],a[1]+b[1])


def point_offset(a, unit, value):
    return (a[0]+unit[0]*value,a[1]+unit[1]*value)


def author(input_path, binding_path):
    intent=json.loads(Path(input_path).read_text(encoding="utf-8"))
    binding=json.loads(Path(binding_path).read_text(encoding="utf-8"))
    require(intent.get("schema")=="domelica.geometry-authoring-2d/v1",
            "Unsupported geometry-intent contract")
    require(set(intent)=={"schema","purpose","physicalAuthority","plane",
                          "inclinationDegrees","geometry","strings"} and intent["plane"]=="xy",
            "Geometry intent has non-geometry fields or unsupported plane")
    require(intent["inclinationDegrees"]==30,
            "Bounded incline witness is for the diagram's 30° angle")
    g=intent["geometry"]
    require(set(g)==REQUIRED_GEOM and len(g["cInitial"])==2,
            "Reference geometry must provide exact supported relative inputs")
    require(all(type(x) in (int,float) and isfinite(x) for x in
                [*g["cInitial"],*(g[k] for k in REQUIRED_GEOM if k!="cInitial")]),
            "Nonfinite or nonnumeric geometry input")
    require(all(g[k]>0 for k in REQUIRED_GEOM if k!="cInitial"),
            "Lengths/radii must be positive")
    theta=pi*intent["inclinationDegrees"]/180
    upslope=(cos(theta),sin(theta))
    normal=(-sin(theta),cos(theta))
    down=(-0.0,-1.0)
    c=tuple(g["cInitial"])
    a=point_offset(c,upslope,-g["blockGap"])
    anchor=point_add(point_offset(c,upslope,-g["anchorSeparation"]),
                     (g["movingRadius"]*normal[0],g["movingRadius"]*normal[1]))
    arope=point_offset(a,normal,-g["movingRadius"])
    top=point_offset(point_offset(c,upslope,g["redirectDistance"]),
                     normal,-g["topRadius"])
    b=(top[0]+g["topRadius"],top[1]-g["bInitialLeg"])
    positions={"anchor":anchor,"Arope":arope,"Acenter":a,
               "Caxle":c,"B":b}
    pulley_data={"C":(c,g["movingRadius"]),"Top":(top,g["topRadius"])}
    vector_names={"upslope":upslope,"downslope":tuple(-x for x in upslope),
                  "down":down,"up":(0.0,1.0)}
    require(len(intent["strings"])==2 and
            {r["id"] for r in intent["strings"]}=={"S1","S2"},
            "Expected two independently routed strings")
    require(binding.get("schema")=="domelica.rope-routes-2d/v1"
            and set(r["id"] for r in binding["ropes"])=={"S1","S2"},
            "M6F binding does not match authored physical ropes")
    scene=Scene("0.1",
        attachments=tuple(AttachmentPoint(name,"world",pos)
                          for name,pos in positions.items()),
        pulleys=tuple(IdealPulley(name,center,r,"world")
                      for name,(center,r) in pulley_data.items()),
        strings=tuple(String(s["id"],tuple(
            StringRouteNode(node["kind"],node["ref"],None,None,None,None)
            for node in s["route"])) for s in intent["strings"]))
    prepared=deepcopy(binding)
    route_by_id={r["id"]:r for r in prepared["ropes"]}
    report={"schema":"domelica.geometry-authoring-proof-2d/v1",
            "upstream":{"repository":"physicsvigilante/domelica_mecha",
                        "commit":UPSTREAM_SHA,
                        "routeAlgorithm":"resolve_string_route_numeric",
                        "geometryAlgorithm":"FLOAT_OPERATIONS local_geometry"},
            "geometryIntentSHA256":hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
            "reference":{"attachmentPositions":positions,
                         "pulleyCentersAndRadii":{
                            name:{"center":center,"radius":rad}
                            for name,(center,rad) in pulley_data.items()},
                         "inclinationDegrees":intent["inclinationDegrees"]},
            "routes":[]}
    for s in intent["strings"]:
        source_nodes=s["route"]
        require(all(set(node)==({"kind","ref"} if node["kind"]=="attachment"
                                else {"kind","ref","intent"})
                    for node in source_nodes), "Route intent contains resolved branches")
        require(len(s["orientedLegs"])==len(source_nodes)-1,
                "Every straight leg needs only its semantic travel direction")
        require(all(n in vector_names for n in s["orientedLegs"]),
                "Unknown semantic oriented leg direction")
        require(len(source_nodes)==3 and source_nodes[1]["kind"]=="pulley",
                "Bounded M6F only: one pulley passage per authored string")
        branch_intents={i:PassageIntentSpec(node["intent"])
                        for i,node in enumerate(source_nodes)
                        if node["kind"]=="pulley"}
        oriented={i:vector_names[value] for i,value in enumerate(s["orientedLegs"])}
        result=resolve_string_route_numeric(
            scene,s["id"],branch_intents,
            oriented_segment_directions=oriented)
        if result.resolved_string is None:
            raise ValueError("Upstream refused geometry for "+s["id"]+": "+
                json.dumps({"diagnostics":[{"code":x.code,"message":x.message}
                                         for x in result.diagnostics],
                            "candidateCount":len(result.candidates),
                            "boundary":result.boundary_encountered}))
        resolved=[]
        for node in result.resolved_string.route:
            if node.type=="attachment":
                resolved.append({"kind":"attachment","ref":node.ref})
            else:
                resolved.append({"kind":"pulley","ref":node.ref,
                                 "incomingSide":node.incoming_tangent_side,
                                 "outgoingSide":node.outgoing_tangent_side,
                                 "wrap":node.wrap_orientation})
        assert len(resolved)==len(source_nodes)
        target=route_by_id[s["id"]]
        require([node["ref"] for node in target["nodes"]]==
                [node["ref"] for node in resolved],
                "Binding and authored route topology differ")
        target["nodes"]=resolved
        geom=result.numeric_geometries[0]
        radius_by_id={n:r for n,(_,r) in pulley_data.items()}
        length=sum(x.length for x in geom.segments)+sum(
            arc.sweep*radius_by_id[arc.pulley_id] for arc in geom.arcs)
        require(length>0 and len(geom.arcs)==1 and
                not result.boundary_encountered,
                "Invalid single-pulley route certificate")
        report["routes"].append({
            "id":s["id"],"authoredPassageIntent":source_nodes[1]["intent"],
            "resolved":resolved,"totalReferenceLength_m":length,
            "segments":[{"start":x.start_point,"end":x.end_point,
                         "length":x.length} for x in geom.segments],
            "arcs":[{"pulley":x.pulley_id,"start":x.start_point,"end":x.end_point,
                     "wrap":x.traversal,"sweepRadians":x.sweep} for x in geom.arcs],
            "feasibleCandidates":result.feasible_candidate_count,
            "uniqueAfterIntent":len(result.candidates)==1,
            "backend":result.backend})
    return prepared,report,g


def modelica_package(g):
    # This file is checked into the downstream branch, so OM simulation
    # remains standalone and does not need the upstream Python package.
    specs=[
      ("Modelica.Units.SI.Radius","movingRadius",g["movingRadius"]),
      ("Modelica.Units.SI.Radius","topRadius",g["topRadius"]),
      ("Modelica.Units.SI.Length","anchorSeparation",g["anchorSeparation"]),
      ("Modelica.Units.SI.Length","blockGap",g["blockGap"]),
      ("Modelica.Units.SI.Length","redirectDistance",g["redirectDistance"]),
      ("Modelica.Units.SI.Length","bInitialLeg",g["bInitialLeg"])]
    lines=["within DomelicaLab.Examples;",
           "package M6FResolvedGeometry",
           "  \"Reference geometry authored and route-certified with domelica_mecha\"",
           "  extends Modelica.Icons.Package;",
           "  constant Modelica.Units.SI.Angle slopeAngle=Modelica.Constants.pi/6;"]
    lines += [f"  constant {typ} {name}={float(value):.17g};"
              for typ,name,value in specs]
    x,y=g["cInitial"]
    lines.append("  constant Modelica.Units.SI.Position cInitial[3]={"
                 +f"{float(x):.17g},{float(y):.17g},0}};")
    lines.append("  annotation(Documentation(info=\"<html><p>Reference-only "
                 "coordinates and dimensions from pinned upstream "
                 "domelica_mecha geometry authoring; these do not "
                 "solve mechanics or make unspecified image dimensions "
                 "problem-given.</p></html>\"));")
    lines += ["end M6FResolvedGeometry;",""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--intent",type=Path,default=ROOT/"viewer/m6g-geometry-intent.json")
    p.add_argument("--binding",type=Path,default=ROOT/"viewer/m6f-routes.json")
    p.add_argument("--output-route",type=Path,required=True)
    p.add_argument("--proof",type=Path,required=True)
    p.add_argument("--modelica-package",type=Path,
                   default=ROOT/"DomelicaLab/Examples/M6FResolvedGeometry.mo")
    p.add_argument("--check-modelica",action="store_true")
    args=p.parse_args()
    routes,proof,geometry=author(args.intent,args.binding)
    modelica=modelica_package(geometry)
    if args.check_modelica:
        require(args.modelica_package.is_file() and
                args.modelica_package.read_text(encoding="utf-8")==modelica,
                "The committed Modelica geometry package diverges from "
                "upstream geometry authoring; regenerate and review it")
    else:
        args.modelica_package.parent.mkdir(parents=True,exist_ok=True)
        args.modelica_package.write_text(modelica,encoding="utf-8")
    for file,data in ((args.output_route,routes),(args.proof,proof)):
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(data,indent=2,allow_nan=False)+"\n",
                        encoding="utf-8")
    print(json.dumps({"status":"pass","upstream":UPSTREAM_SHA,
                      "outputRoute":str(args.output_route),
                      "proof":str(args.proof),
                      "routes":[{"id":x["id"],
                                 "resolved":x["resolved"],
                                 "length":x["totalReferenceLength_m"]}
                                for x in proof["routes"]]},indent=2))


if __name__=="__main__":
    main()
