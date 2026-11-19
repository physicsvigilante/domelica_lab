#!/usr/bin/env python3
"""Small pure-python geometry tests: independent of OpenModelica/browser."""
import math
import unittest
from rope2d_geometry import RopeGeometryError, arc, circle_tangent, evaluate_route, point_tangent

NODES = [
    {"kind": "attachment", "ref": "left"},
    {"kind": "pulley", "ref": "P", "incomingSide": 1, "outgoingSide": -1, "wrap": "clockwise"},
    {"kind": "attachment", "ref": "right"},
]


class RopeGeometryTests(unittest.TestCase):
    def test_fixed_atwood_wrap_and_length(self):
        data = evaluate_route(NODES, {"left": (-.6, 2.1), "right": (.6, 2.1)},
                              {"P": {"center": (0, 4), "radius": .6}})
        self.assertEqual(len(data["segments"]), 2)
        self.assertEqual(len(data["arcs"]), 1)
        self.assertAlmostEqual(data["arcs"][0]["sweep"], math.pi)
        self.assertAlmostEqual(data["segments"][0]["length"], 1.9)
        self.assertAlmostEqual(data["segments"][1]["length"], 1.9)
        self.assertAlmostEqual(data["length"], 3.8 + math.pi * .6)
        self.assertEqual(data["points"][0], (-.6, 2.1))
        self.assertEqual(data["points"][-1], (.6, 2.1))

    def test_moving_pulley_and_attached_ends(self):
        static = evaluate_route(NODES, {"left": (-.6, 1), "right": (.6, 1)},
                                {"P": {"center": (0, 3), "radius": .6}})
        shifted = evaluate_route(NODES, {"left": (-.6, 1.4), "right": (.6, 1.4)},
                                 {"P": {"center": (0, 3.4), "radius": .6}})
        self.assertAlmostEqual(static["length"], shifted["length"])
        self.assertAlmostEqual(shifted["arcs"][0]["center"][1] -
                               static["arcs"][0]["center"][1], .4)
        self.assertAlmostEqual(shifted["points"][0][1] - static["points"][0][1], .4)

    def test_common_tangent_external_and_internal(self):
        for sides in ((1, -1), (1, 1)):
            a, b = circle_tangent((0, 0), (4, 0), .7, .4, *sides)
            self.assertAlmostEqual(math.dist(a, (0, 0)), .7)
            self.assertAlmostEqual(math.dist(b, (4, 0)), .4)
            self.assertGreater(math.dist(a, b), 0)

    def test_tangent_geometry_refuses_inside_and_bad_branches(self):
        with self.assertRaises(RopeGeometryError):
            point_tangent((.1, .1), (0, 0), 1, 1)
        with self.assertRaises(RopeGeometryError):
            arc((0, 0), 1, (1, 0), (-1, 0), "other")
        bad = [NODES[0], {**NODES[1], "wrap": "counterclockwise"}, NODES[2]]
        with self.assertRaises(RopeGeometryError):
            evaluate_route(bad, {"left": (-.6, 2.1), "right": (.6, 2.1)},
                           {"P": {"center": (0, 4), "radius": .6}})


if __name__ == "__main__":
    unittest.main()
