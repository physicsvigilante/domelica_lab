#!/usr/bin/env python3
"""Focused input/identity guards for compiler-free native execution."""
import json
import math
from pathlib import Path
import tempfile
import unittest

import compiled_model as runner


class CompiledRunGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configuration = runner.load_configuration(runner.ROOT / "viewer/compiled-experiments.json")
        cls.definitions = cls.configuration["parameters"]

    def test_nonpreset_values_are_accepted(self):
        values = runner.parameters_for(self.definitions, {"cartMass": 3.14159, "initialAngle": -0.2})
        self.assertEqual(values["cartMass"], 3.14159)
        self.assertEqual(values["initialAngle"], -0.2)
        self.assertEqual(values["springStiffness"], 20)

    def test_invalid_parameters_are_rejected(self):
        invalid = [{"rodLength": 2}, {"cartMass": 0}, {"bobMass": -1}, {"cartMass": True},
                   {"springStiffness": math.nan}, {"initialAngle": math.inf},
                   {"initialAngle": math.pi / 2}, {"initialAngle": -math.pi / 2}]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(ValueError):
                runner.parameters_for(self.definitions, request)

    def test_duplicate_overrides_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            runner.parse_overrides(["cartMass=2", "cartMass=3"])

    def test_output_identity_cannot_escape_directory(self):
        for identifier in ("../result", "a/b", "_case", "case;touch", ""):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                runner.valid_id(identifier)

    def test_nonempty_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "previous-result"
            target.mkdir()
            retained = target / "data.txt"
            retained.write_text("keep")
            with self.assertRaises(ValueError):
                runner.empty_directory(target)
            self.assertEqual(retained.read_text(), "keep")

    def test_bundle_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            model = bundle / "model"
            model.write_bytes(b"original executable")
            runner.write_json(bundle / "build.json", {"schema": "domelica.compiled-model/v1",
                "compilerInvocations": 1, "filesSHA256": {"model": runner.sha(model)}})
            runner.verify_bundle(bundle)
            model.write_bytes(b"modified executable")
            with self.assertRaisesRegex(ValueError, "changed"):
                runner.verify_bundle(bundle)

    def test_missing_or_fixed_parameter_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "init.xml"
            variables = ''.join(f'<ScalarVariable name="{name}"><Real isValueChangeable="true"/></ScalarVariable>'
                                for name in runner.PARAMETERS)
            path.write_text('<fmiModelDescription><ModelVariables>' + variables + '</ModelVariables></fmiModelDescription>')
            self.assertEqual(set(runner.parameter_metadata(path)), set(runner.PARAMETERS))
            path.write_text(path.read_text().replace('isValueChangeable="true"', 'isValueChangeable="false"', 1))
            with self.assertRaisesRegex(ValueError, "not runtime-changeable"):
                runner.parameter_metadata(path)


if __name__ == "__main__":
    unittest.main()
