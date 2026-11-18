"""Synthetic geometry checks, plus optional comparisons with real native results.

Run with --native after simulation to require all three mechanical result pairs.
The synthetic fixtures themselves are not native simulation evidence.
"""

import csv
from pathlib import Path
import tempfile
import unittest
import sys

from native_scene import SceneExportError, export_scene


def verify_native_endpoints(root):
    """Compare rendered box endpoints with separately exported physical frames.

    These named fixtures use BodyBox's default length=norm(r), r_shape=0. They
    exercise the generic exporter; no fixture names are embedded in that code.
    """
    fixtures = {
        "m0_motorized_pendulum": ["arm"],
        "m0_msl_double_pendulum": ["boxBody1", "boxBody2"],
        "m1_thermal_geared_arm": ["upperArm", "forearm"],
    }
    for prefix, bodies in fixtures.items():
        csv_path = root / f"{prefix}_res.csv"
        scene = export_scene(root / f"{prefix}_visual.xml", csv_path)
        objects = {shape["id"]: shape for shape in scene["objects"]}
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        max_error = 0.0
        for body in bodies:
            shape = objects[f"{body}.frameTranslation.shape"]
            if shape["type"] != "box":
                raise AssertionError(f"{prefix}: {body} is no longer the box geometry fixture")
            frames = shape["frames"]
            for index, row in enumerate(rows):
                frame = frames[0] if len(frames) == 1 else frames[index]
                origin, tip = frame[9:12], [frame[9 + j] + frame[j] for j in range(3)]
                native_a = [float(row[f"{body}.frame_a.r_0[{j}]"]) for j in (1, 2, 3)]
                native_b = [float(row[f"{body}.frame_b.r_0[{j}]"]) for j in (1, 2, 3)]
                error = max(abs(x - y) for a, b in ((origin, native_a), (tip, native_b))
                            for x, y in zip(a, b))
                max_error = max(max_error, error)
                if error > 1e-8:
                    raise AssertionError(f"{prefix}: {body} scene/physical frame error {error:g} m "
                                         f"at native t={row['time']}")
        print(f"PASS native scene endpoints: {prefix}, {len(bodies)} boxes, "
              f"{len(rows)} samples, max coordinate error {max_error:.3g} m")


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
    check_native = "--native" in sys.argv
    if check_native:
        sys.argv.remove("--native")
    result = unittest.main(exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)
    if check_native:
        verify_native_endpoints(Path(__file__).resolve().parent.parent)
