"""Synthetic geometry contract checks; these are not native simulation evidence."""

import csv
from pathlib import Path
import tempfile
import unittest

from native_scene import SceneExportError, export_scene


class NativeSceneContractTests(unittest.TestCase):
    def fixture(self, folder, *, kind="box", missing=False, reflection=False):
        # A +90 degree object-to-world rotation about Z has this world-to-object T.
        # Explicit offset exercises both the transpose and object-frame r_shape.
        fields = {
            "T": [0, 1, 0, -1, 0, 0, 0, 0, -1 if reflection else 1],
            "r": [10, 20, 30], "r_shape": [1, 0, 0],
            "lengthDir": [1, 0, 0], "widthDir": [1, 2, 0],
            "length": [2], "width": [4], "height": [6],
            "extra": [0], "color": [20, 100, 200], "specCoeff": [0.7],
        }
        parts = [f"<visualization><shape><ident>synthetic.fixture</ident><type>{kind}</type>"]
        for name, vector in fields.items():
            body = "".join(f"<exp>{value}</exp>" for value in vector)
            if name == "r":
                body = "<cref>synthetic.x</cref><exp>20</exp><exp>30</exp>"
            if name == "color":
                body = "<cref>synthetic.red</cref><exp>100</exp><exp>200</exp>"
            parts.append(f"<{name}>{body}</{name}>")
        parts.append("</shape></visualization>")
        xml_path, csv_path = Path(folder) / "scene.xml", Path(folder) / "result.csv"
        xml_path.write_text("".join(parts), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["time", "wrong.x" if missing else "synthetic.x", "synthetic.red"])
            writer.writerows([[0, 10, 20], [1, 11, 40]])
        return xml_path, csv_path

    def test_rotation_offset_dimensions_color_and_all_time_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            result = export_scene(*self.fixture(folder))
        shape = result["objects"][0]
        # Unit x moves +world Y; unit y moves -world X; r_shape moves +world Y.
        self.assertEqual(shape["frames"][0], [0, 2, 0, -4, 0, 0, 0, 0, 6, 10, 21, 30])
        self.assertEqual(shape["frames"][1][-3:], [11, 21, 30])
        self.assertEqual(shape["colors"], [[20, 100, 200], [40, 100, 200]])
        self.assertEqual(result["bounds"], {"min": [8, 21, 27], "max": [13, 23, 33]})

    def test_rejects_missing_native_data_and_unsupported_shapes(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(SceneExportError, "synthetic.fixture.r.*missing native result"):
                export_scene(*self.fixture(folder, missing=True))
            with self.assertRaisesRegex(SceneExportError, "unsupported primitive 'gearwheel'"):
                export_scene(*self.fixture(folder, kind="gearwheel"))

    def test_rejects_reflection_as_a_rotation(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(SceneExportError, "invalid rotation"):
                export_scene(*self.fixture(folder, reflection=True))


if __name__ == "__main__":
    unittest.main()
