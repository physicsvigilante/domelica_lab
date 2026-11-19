#!/usr/bin/env python3
"""Fail-closed, styling-only symbols: independent of Modelica installation."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import unittest
from build_rope2d import validate_style

ROOT = Path(__file__).resolve().parents[1]
DARK = json.loads((ROOT / "viewer/m6d-four-pulleys-style.json").read_text())
LIGHT = json.loads((ROOT / "viewer/m6d-four-pulleys-style-light.json").read_text())


class DeclarativeStyleTests(unittest.TestCase):
    def valid(self, value):
        validate_style(value, ["A", "B"], {"wall", "A", "P1axle", "B"},
                       {"P1", "P2", "P3", "P4"})

    def test_both_styles_use_same_decorative_geometry(self):
        self.valid(DARK)
        self.valid(LIGHT)
        self.assertEqual(DARK["bodySymbols"], LIGHT["bodySymbols"])
        self.assertEqual(DARK["supportMarks"], LIGHT["supportMarks"])
        self.assertNotEqual(DARK["background"], LIGHT["background"])
        self.assertEqual(set(DARK["bodySymbols"]), {"A", "B"})
        self.assertEqual({x["kind"] for x in DARK["supportMarks"]}, {"wall", "ceiling"})

    def test_backwards_compatible_circle_styles(self):
        # Earlier accepted examples do not need symbol configuration.
        minimal = copy.deepcopy(DARK)
        del minimal["bodySymbols"]
        del minimal["supportMarks"]
        self.valid(minimal)

    def test_refuse_physics_in_a_style_file(self):
        for name, value in [("mass", 2), ("radius", 0.4),
                            ("pulleyCenter", [1, 2]), ("gravity", 9.8)]:
            with self.subTest(name=name):
                bad = copy.deepcopy(DARK)
                bad[name] = value
                with self.assertRaises(ValueError):
                    self.valid(bad)

    def test_invalid_owner_and_mechanical_geometry_are_refused(self):
        cases = []
        bad = copy.deepcopy(DARK)
        bad["bodySymbols"]["C"] = bad["bodySymbols"].pop("A")
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["bodySymbols"]["A"]["mass"] = 100
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["bodySymbols"]["A"]["widthPx"] = -1
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["bodySymbols"]["A"]["widthPx"] = float("nan")
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["bodySymbols"]["A"]["widthPx"] = 7
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["supportMarks"][0]["ref"] = "unknown"
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["supportMarks"][0]["kind"] = "ceiling"
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["supportMarks"][1]["ref"] = "wall"
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["supportMarks"].append(copy.deepcopy(bad["supportMarks"][0]))
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["supportMarks"][0]["position"] = [1, 2]
        cases.append(bad)
        bad = copy.deepcopy(DARK)
        bad["supportMarks"][0]["sizePx"] = True
        cases.append(bad)
        for i, case in enumerate(cases):
            with self.subTest(case=i):
                with self.assertRaises(ValueError):
                    self.valid(case)


if __name__ == "__main__":
    unittest.main()
