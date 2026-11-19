#!/usr/bin/env python3
"""Pure 2D two-rope/four-pulley checks. No Modelica installation required."""
import math
import unittest
from rope2d_geometry import RopeGeometryError, evaluate_route

S1=[
 {"kind":"attachment","ref":"wall"},
 {"kind":"pulley","ref":"P1","incomingSide":1,"outgoingSide":-1,"wrap":"clockwise"},
 {"kind":"attachment","ref":"A"}
]
S2=[
 {"kind":"attachment","ref":"P1axle"},
 {"kind":"pulley","ref":"P2","incomingSide":1,"outgoingSide":1,"wrap":"clockwise"},
 {"kind":"pulley","ref":"P3","incomingSide":1,"outgoingSide":-1,"wrap":"counterclockwise"},
 {"kind":"pulley","ref":"P4","incomingSide":-1,"outgoingSide":-1,"wrap":"clockwise"},
 {"kind":"attachment","ref":"B"}
]
def configuration(qA):
 x1=-1.5-qA/2
 yB=1.25+qA/6
 return (
    {"wall":(-9,5.6),"A":(-4.5-qA,5.2),
     "P1axle":(x1,5.4),"B":(1.9,yB)},
    {"P1":{"center":(x1,5.4),"radius":.2},
     "P2":{"center":(0,5.0),"radius":.4},
     "P3":{"center":(.8,yB+1),"radius":.4},
     "P4":{"center":(1.55,6.2),"radius":.35}}
 )
class FourPulleyGeometryTests(unittest.TestCase):
 def test_1001_relative_motion_states_reuse_existing_kernel(self):
    original1=10.5+math.pi*.2
    original2=1.5+2.75+3.95+4.95+math.pi*.95
    for sample in range(1001):
      a,p=configuration(3*sample/1000)
      first=evaluate_route(S1,a,p)
      second=evaluate_route(S2,a,p)
      with self.subTest(sample=sample):
        self.assertEqual([len(first["segments"]),len(first["arcs"])],[2,1])
        self.assertEqual([len(second["segments"]),len(second["arcs"])],[4,3])
        self.assertAlmostEqual(first["length"],original1,places=10)
        self.assertAlmostEqual(second["length"],original2,places=10)
        for route,nodes in ((first,S1),(second,S2)):
          self.assertEqual(tuple(route["points"][0]),a[nodes[0]["ref"]])
          self.assertEqual(tuple(route["points"][-1]),a[nodes[-1]["ref"]])
          for arc in route["arcs"]:
            index=arc["node"]
            left=route["segments"][index-1]
            right=route["segments"][index]
            self.assertLess(math.dist(left["end"],arc["start"]),1e-9)
            self.assertLess(math.dist(right["start"],arc["end"]),1e-9)
            for point in arc["points"]:
              self.assertAlmostEqual(math.dist(point,arc["center"]),arc["radius"],places=9)
            expected=-1 if arc["clockwise"] else 1
            for contact,leg in ((arc["start"],left),(arc["end"],right)):
              radial=tuple((contact[i]-arc["center"][i])/arc["radius"] for i in range(2))
              unit=tuple((leg["end"][i]-leg["start"][i])/leg["length"] for i in range(2))
              self.assertAlmostEqual(sum(radial[i]*unit[i] for i in range(2)),0,places=9)
              self.assertAlmostEqual(radial[0]*unit[1]-radial[1]*unit[0],expected,places=9)
        self.assertEqual([a["pulley"] for a in first["arcs"]],["P1"])
        self.assertEqual([a["pulley"] for a in second["arcs"]],["P2","P3","P4"])
        self.assertEqual([a["clockwise"] for a in second["arcs"]],[True,False,True])
        self.assertAlmostEqual(first["arcs"][0]["sweep"],math.pi,places=10)
        for arc,value in zip(second["arcs"],[math.pi/2,math.pi,math.pi]):
          self.assertAlmostEqual(arc["sweep"],value,places=10)
 def test_wrong_wrap_fails_closed(self):
    a,p=configuration(1)
    for rope,index in ((S1,1),(S2,1),(S2,2),(S2,3)):
      wrong=[dict(n) for n in rope]
      wrong[index]["wrap"]="counterclockwise" if rope[index]["wrap"]=="clockwise" else "clockwise"
      with self.subTest(rope="S1" if rope is S1 else "S2",node=index):
        with self.assertRaises(RopeGeometryError):
          evaluate_route(wrong,a,p)
 def test_a_moving_without_p1_breaks_only_rope_s1(self):
    a,p=configuration(1)
    baseline=evaluate_route(S1,a,p)["length"]
    a["A"]=(a["A"][0]-.25,a["A"][1])
    self.assertAlmostEqual(evaluate_route(S1,a,p)["length"]-baseline,.25,places=10)
 def test_b_moving_without_p3_breaks_rope_s2(self):
    a,p=configuration(1)
    baseline=evaluate_route(S2,a,p)["length"]
    a["B"]=(a["B"][0],a["B"][1]+.125)
    self.assertAlmostEqual(evaluate_route(S2,a,p)["length"]-baseline,-.125,places=10)

if __name__=="__main__":
 unittest.main()
