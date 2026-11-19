#!/usr/bin/env python3
"""Fast unit proof of the literal image route using the existing geometry kernel."""
import json
import math
from pathlib import Path
import unittest
from rope2d_geometry import evaluate_route, RopeGeometryError

ROOT=Path(__file__).resolve().parents[1]
ROUTE=json.loads((ROOT/"viewer/m6e-routes.json").read_text())["ropes"][0]["nodes"]


class NestedTwoKgGeometry(unittest.TestCase):
    def test_native_analytical_positions_keep_one_string_length(self):
        first=None
        for i in range(31):
            t=.30*i/30
            yA=1.1-.5*7*t*t
            yB=.9-.5*4.2*t*t
            yC=2.8-.5*15.4*t*t
            attachments={"A":(-.72,yA),"Caxle":(-.4,yC),"B":(.28,yB)}
            pulleys={
                "C":{"center":(-.4,yC),"radius":.32},
                "Bwheel":{"center":(.28,yB+.7),"radius":.36},
                "Top":{"center":(.12,5),"radius":.52}}
            result=evaluate_route(ROUTE,attachments,pulleys)
            if first is None:first=result["length"]
            self.assertAlmostEqual(result["length"],first,places=9)
            self.assertEqual(len(result["arcs"]),3)
            self.assertEqual(len(result["segments"]),4)
            self.assertEqual([x["pulley"] for x in result["arcs"]],
                             ["C","Bwheel","Top"])
            self.assertEqual([x["clockwise"] for x in result["arcs"]],
                             [True,False,False])
            for arc in result["arcs"]:
                self.assertAlmostEqual(arc["sweep"],math.pi,places=8)
    def test_wrong_wrap_refused(self):
        nodes=[dict(x) for x in ROUTE]
        nodes[2]["wrap"]="clockwise"
        attachments={"A":(-.72,1.1),"Caxle":(-.4,2.8),"B":(.28,.9)}
        pulleys={"C":{"center":(-.4,2.8),"radius":.32},
          "Bwheel":{"center":(.28,1.6),"radius":.36},
          "Top":{"center":(.12,5),"radius":.52}}
        with self.assertRaises(RopeGeometryError):
            evaluate_route(nodes,attachments,pulleys)

if __name__=="__main__":
    unittest.main()
