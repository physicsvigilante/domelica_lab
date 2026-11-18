"""Independent contracts for the native spring scene extension.

Synthetic XML/CSV fixtures are parser/geometry tests, not simulation evidence.
Run with --native after M4 simulation/export to additionally compare spring
attachment axes with separately recorded physical Modelica frame positions.

The dimensional oracle follows OpenModelica v1.27.1 Visualization.cpp and
ExtraShapes.cpp: XML width is the helix centre-line radius, XML height is the
wire radius, extra is the winding count, and length is the axial length.
The browser uses its own smooth tessellation; these tests do not assert pixel
equivalence to OMEdit's coarser mesh or its end-of-helix tessellation.
"""

import csv
import hashlib
import math
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from native_motion_scene import export_scene
from native_scene import SceneExportError, export_scene as export_baseline_scene


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sample(values, index):
    return values[0] if len(values) == 1 else values[index]


class NativeMotionSceneTests(unittest.TestCase):
    def assert_vector(self, actual, expected, tolerance=1e-12):
        self.assertEqual(len(actual), len(expected))
        for observed, reference in zip(actual, expected):
            self.assertTrue(math.isfinite(observed))
            self.assertAlmostEqual(observed, reference, delta=tolerance)

    def fixture(self, folder, *, spring=True, box=False, updates=None, rows=None):
        """Explicit +90-degree world rotation with a local one-metre offset.

        The world-to-local T is deliberately not the local-to-world matrix.
        The non-orthogonal width hint tests native orthogonalization. Expected
        world axes are +Y, -X, +Z; the spring axes must remain unit vectors.
        """
        fields = {
            "T": [0, 1, 0, -1, 0, 0, 0, 0, 1],
            "r": ["positionX", 20, 30], "r_shape": [1, 0, 0],
            "lengthDir": [2, 0, 0], "widthDir": [1, 3, 0],
            "length": ["lengthValue"], "width": ["coilRadius"],
            "height": ["wireRadius"], "extra": [4],
            "color": ["redValue", 100, 200], "specCoeff": [0.7],
        }
        fields.update(updates or {})
        root = ET.Element("visualization")
        kinds = (["spring"] if spring else []) + (["box"] if box else [])
        for kind in kinds:
            element = ET.SubElement(root, "shape")
            ET.SubElement(element, "ident").text = f"fixture.{kind}"
            ET.SubElement(element, "type").text = kind
            for name, values in fields.items():
                node = ET.SubElement(element, name)
                for value in values:
                    tag = "cref" if isinstance(value, str) else "exp"
                    ET.SubElement(node, tag).text = str(value)
        xml_path = Path(folder) / "scene.xml"
        csv_path = Path(folder) / "native.csv"
        ET.ElementTree(root).write(xml_path, encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["time", "positionX", "lengthValue", "coilRadius", "wireRadius", "redValue"])
            writer.writerows(rows if rows is not None else [
                [0, 10, 0.8, 0.20, 0.03, 20],
                [0.5, 11, 1.6, 0.25, 0.04, 40],
                [0.5, 11, 1.55, 0.25, 0.04, 50],
                [1, 12, 0.6, 0.22, 0.02, 60],
            ])
        return xml_path, csv_path

    def test_native_radii_unit_axes_rotation_offsets_and_duplicate_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.fixture(folder)
            hashes = [file_hash(path) for path in paths]
            result = export_scene(*paths)
            self.assertEqual([file_hash(path) for path in paths], hashes,
                             "Export must not alter its primary XML/CSV inputs")
        self.assertEqual(result["times"], [0, 0.5, 0.5, 1])
        self.assertEqual(len(result["objects"]), 1)
        spring = result["objects"][0]
        self.assertEqual(spring["type"], "spring")
        self.assertEqual(spring["spring"], [
            [0.8, 0.20, 0.03, 4], [1.6, 0.25, 0.04, 4],
            [1.55, 0.25, 0.04, 4], [0.6, 0.22, 0.02, 4],
        ], "Width and height are native radii; neither is divided by two")
        self.assertEqual(spring["colors"], [
            [20, 100, 200], [40, 100, 200], [50, 100, 200], [60, 100, 200]])
        for index, x in enumerate([10, 11, 11, 12]):
            self.assert_vector(sample(spring["frames"], index),
                               [0, 1, 0, -1, 0, 0, 0, 0, 1, x, 21, 30])
        # Conservative transformed tube envelope, including axial wire extent.
        # These literals are calculated independently from the four fixture rows.
        self.assert_vector(result["bounds"]["min"], [9.77, 20.96, 29.71])
        self.assert_vector(result["bounds"]["max"], [12.24, 22.64, 30.29])

    def test_non_spring_shapes_retain_the_exact_accepted_export(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.fixture(folder, spring=False, box=True)
            self.assertEqual(export_scene(*paths), export_baseline_scene(*paths))
            expected_box = export_baseline_scene(*paths)["objects"][0]
            paths = self.fixture(folder, box=True)
            mixed = export_scene(*paths)
            observed_box = next(item for item in mixed["objects"] if item["type"] == "box")
            self.assertEqual(observed_box, expected_box)

    def test_missing_reference_negative_dimensions_and_invalid_rotation_fail(self):
        failures = [
            {"length": ["missingNativeLength"]},
            {"length": [-0.1]}, {"width": [-0.2]}, {"height": [-0.03]},
            {"T": [0, 1, 0, -1, 0, 0, 0, 0, -1]},
        ]
        with tempfile.TemporaryDirectory() as folder:
            for update in failures:
                with self.subTest(update=update):
                    with self.assertRaises(SceneExportError):
                        export_scene(*self.fixture(folder, updates=update))

    def test_duplicate_identifier_and_nonfinite_native_sample_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.fixture(folder)
            tree = ET.parse(paths[0])
            tree.getroot().append(ET.fromstring(ET.tostring(tree.getroot()[0])))
            tree.write(paths[0], encoding="utf-8")
            with self.assertRaises(SceneExportError):
                export_scene(*paths)
            with self.assertRaises(SceneExportError):
                export_scene(*self.fixture(folder, rows=[
                    [0, 10, 0.8, 0.2, 0.03, 20],
                    [1, 11, float("nan"), 0.2, 0.03, 20],
                ]))


def verify_native_spring_attachments(root):
    """Check exported attachment axes against native physical frame positions.

    The renderer has a helical wire around this axis. Its wire centre-line need
    not touch the axis at the ends; this check intentionally compares the axis
    attachments, not the outer wire's surface or a tessellated terminal vertex.
    """
    files = sorted(root.glob("m4_*_visual.xml"))
    if not files:
        raise AssertionError("--native requires freshly simulated m4_*_visual.xml files")
    checked_springs = checked_samples = 0
    worst_error = 0.0
    for xml_path in files:
        prefix = xml_path.name.removesuffix("_visual.xml")
        csv_path = root / f"{prefix}_res.csv"
        scene = export_scene(xml_path, csv_path)
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if [float(row["time"]) for row in rows] != scene["times"]:
            raise AssertionError(f"{prefix}: scene samples differ from native CSV")
        for shape in scene["objects"]:
            if shape["type"] != "spring":
                continue
            suffix = ".lineForce.lineShape"
            if not shape["id"].endswith(suffix):
                raise AssertionError(f"{prefix}: unexpected native MSL spring graphic {shape['id']}")
            component = shape["id"][:-len(suffix)]
            checked_springs += 1
            for index, row in enumerate(rows):
                frame = sample(shape["frames"], index)
                dimensions = sample(shape["spring"], index)
                start = frame[9:12]
                end = [start[j] + dimensions[0] * frame[j] for j in range(3)]
                native_a = [float(row[f"{component}.frame_a.r_0[{j}]"]) for j in (1, 2, 3)]
                native_b = [float(row[f"{component}.frame_b.r_0[{j}]"]) for j in (1, 2, 3)]
                error = max(abs(observed - expected)
                            for left, right in ((start, native_a), (end, native_b))
                            for observed, expected in zip(left, right))
                worst_error = max(worst_error, error)
                if error > 1e-8:
                    raise AssertionError(f"{prefix}/{component}: native attachment error {error:g} m "
                                         f"at t={row['time']}")
                checked_samples += 1
    if checked_springs != 2:
        raise AssertionError(f"M4 first delivery must contain two native springs, found {checked_springs}")
    print(f"PASS native spring attachment axes: {checked_springs} springs, "
          f"{checked_samples} sampled pairs, maximum error {worst_error:.3g} m")


if __name__ == "__main__":
    native = "--native" in sys.argv
    if native:
        sys.argv.remove("--native")
    result = unittest.main(exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)
    if native:
        verify_native_spring_attachments(Path(__file__).resolve().parent.parent)
