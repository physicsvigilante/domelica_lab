#!/usr/bin/env python3
"""Independent geometric invariants over moving configurations, not a simulation.

The Modelica/native CSV checks live in check_m6c_moving_pulley.py. These tests
exercise the unchanged rope kernel with a stationary anchor and redirect while
the load pulley moves relative to them, including a circle-to-circle tangent.
"""
import math
import unittest

from rope2d_geometry import RopeGeometryError, evaluate_route


NODES = [
    {"kind": "attachment", "ref": "anchor"},
    {"kind": "pulley", "ref": "moving", "incomingSide": -1,
     "outgoingSide": -1, "wrap": "counterclockwise"},
    {"kind": "pulley", "ref": "fixed", "incomingSide": -1,
     "outgoingSide": -1, "wrap": "clockwise"},
    {"kind": "attachment", "ref": "counterweight"},
]


def configuration(q):
    radius = .45
    return ({"anchor": (-radius, 5), "counterweight": (3*radius, 3.4-2*q)},
            {"moving": {"center": (0, 2+q), "radius": radius},
             "fixed": {"center": (2*radius, 5), "radius": radius}})


class MovingRopeGeometryTests(unittest.TestCase):
    def assert_point(self, actual, expected):
        self.assertLess(math.dist(actual, expected), 1e-11)

    def test_relative_motion_preserves_contacts_wraps_and_length(self):
        initial_length = 2*(5-2)+(5-3.4)+2*math.pi*.45
        for index in range(1001):
            q = .882*index/1000
            with self.subTest(sample=index):
                attachments, pulleys = configuration(q)
                route = evaluate_route(NODES, attachments, pulleys)
                segments, arcs = route["segments"], route["arcs"]
                self.assertEqual(len(segments), 3)
                self.assertEqual(len(arcs), 2)
                self.assert_point(route["points"][0], attachments["anchor"])
                self.assert_point(route["points"][-1], attachments["counterweight"])
                expected = [(attachments["anchor"], (-.45, 2+q)),
                            ((.45, 2+q), (.45, 5)),
                            ((1.35, 5), attachments["counterweight"])]
                for segment, (start, end) in zip(segments, expected):
                    self.assert_point(segment["start"], start)
                    self.assert_point(segment["end"], end)
                    self.assertAlmostEqual(segment["length"], math.dist(start, end), places=11)
                for i, arc in enumerate(arcs):
                    self.assertEqual(arc["clockwise"], i == 1)
                    self.assertAlmostEqual(arc["sweep"], math.pi, places=11)
                    self.assert_point(arc["start"], segments[i]["end"])
                    self.assert_point(arc["end"], segments[i+1]["start"])
                    self.assert_point(arc["points"][0], arc["start"])
                    self.assert_point(arc["points"][-1], arc["end"])
                    for point in arc["points"]:
                        self.assertAlmostEqual(math.dist(point, arc["center"]), arc["radius"], places=11)
                        # The movable wrap is below its axle; the redirect is above.
                        self.assertGreaterEqual((1 if i else -1)*(point[1]-arc["center"][1]), -1e-11)
                    for contact, leg in [(arc["start"], segments[i]),
                                         (arc["end"], segments[i+1])]:
                        radial = [(contact[k]-arc["center"][k])/arc["radius"] for k in (0, 1)]
                        tangent = [(leg["end"][k]-leg["start"][k])/leg["length"] for k in (0, 1)]
                        self.assertAlmostEqual(sum(a*b for a, b in zip(radial, tangent)), 0, places=11)
                        cross = radial[0]*tangent[1]-radial[1]*tangent[0]
                        self.assertAlmostEqual(cross, -1 if i else 1, places=11)
                self.assertAlmostEqual(route["length"], initial_length, places=11)

    def test_wrong_movable_wrap_is_rejected(self):
        attachments, pulleys = configuration(.4)
        wrong = [dict(node) for node in NODES]
        wrong[1]["wrap"] = "clockwise"
        with self.assertRaises(RopeGeometryError):
            evaluate_route(wrong, attachments, pulleys)

    def test_independent_endpoint_motion_changes_geometric_length(self):
        # The geometry kernel observes the constraint; it cannot enforce motion.
        attachments, pulleys = configuration(.4)
        baseline = evaluate_route(NODES, attachments, pulleys)["length"]
        attachments["counterweight"] = (1.35, attachments["counterweight"][1]-.1)
        changed = evaluate_route(NODES, attachments, pulleys)["length"]
        self.assertAlmostEqual(changed-baseline, .1, places=11)


if __name__ == "__main__":
    unittest.main()
