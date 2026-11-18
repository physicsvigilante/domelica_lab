"""Add native OpenModelica spring primitives without changing the M1 exporter.

All ordinary primitives are delegated to the accepted native_scene exporter.
Spring frames contain unit orientation columns, then the native origin. Their
separate sampled geometry is [length, coilRadius, wireRadius, windingCount].
This follows OMEdit v1.27.1 Visualization.cpp's Spring(width,height,extra,length)
call, not the cylinder interpretation of width/height. The browser tessellates
an ideal helix; it does not reproduce OMEdit's coarse surface triangulation.
"""
from pathlib import Path
import copy
import math
import tempfile
import xml.etree.ElementTree as ET

import native_scene as base


def export_scene(xml_path: Path, csv_path: Path) -> dict:
    root = ET.parse(xml_path).getroot()
    if root.tag != "visualization":
        base._fail(xml_path, "expected <visualization> root")
    ordinary, spring_elements, identifiers, order = ET.Element("visualization"), [], set(), []
    for element in root:
        if element.tag != "shape":
            base._fail(xml_path, f"unsupported scene object <{element.tag}>")
        ident = (element.findtext("ident") or "").strip()
        if not ident or ident in identifiers:
            base._fail(xml_path, f"empty or duplicate shape identifier {ident!r}")
        identifiers.add(ident)
        order.append(ident)
        if (element.findtext("type") or "").strip() == "spring":
            spring_elements.append(element)
        else:
            ordinary.append(copy.deepcopy(element))
    if not spring_elements:
        return base.export_scene(xml_path, csv_path)

    # The unchanged exporter remains the authority for its supported subset.
    if len(ordinary):
        with tempfile.TemporaryDirectory(prefix="domelica-motion-scene-") as tmp:
            subset = Path(tmp) / "ordinary.xml"
            ET.ElementTree(ordinary).write(subset, encoding="utf-8")
            result = base.export_scene(subset, csv_path)
    else:
        result = {"times": None, "objects": [],
                  "bounds": {"min": [math.inf] * 3, "max": [-math.inf] * 3}}

    references, definitions = {}, []
    counts = {"T": 9, "r": 3, "r_shape": 3, "lengthDir": 3,
              "widthDir": 3, "length": 1, "width": 1, "height": 1,
              "extra": 1, "color": 3, "specCoeff": 1}
    for element in spring_elements:
        ident = element.findtext("ident").strip()
        fields = {name: base._field(element, name, count, ident, references)
                  for name, count in counts.items()}
        definitions.append((ident, fields))
    signals = base._read_csv(csv_path, references)
    times = signals["time"]
    if result["times"] is not None and result["times"] != times:
        base._fail(xml_path, "spring and ordinary native times differ")
    result["times"] = times

    for ident, fields in definitions:
        frames, geometry, colors = [], [], []
        for index, time in enumerate(times):
            values = {name: [value if tag == "const" else signals[value][index]
                             for tag, value in expression]
                      for name, expression in fields.items()}
            context = f"{ident} at t={time:g}"
            rotation = values["T"]
            base._check_rotation(rotation, context)
            length, radius, wire, windings = [values[key][0]
                                             for key in ("length", "width", "height", "extra")]
            if not (length > 0 and radius > 0 and wire > 0 and 0 < windings <= 128):
                base._fail(context, "spring needs positive length/radii and 0 < windings <= 128")
            if wire >= radius:
                base._fail(context, "spring wire radius must be smaller than coil radius")
            basis = base._directions(values["lengthDir"], values["widthDir"])
            axes = [base._local_to_world(rotation, direction) for direction in basis]
            offset = base._local_to_world(rotation, values["r_shape"])
            origin = [v + shift for v, shift in zip(values["r"], offset)]
            frame = [*axes[0], *axes[1], *axes[2], *origin]
            if not all(math.isfinite(v) for v in frame):
                base._fail(context, "spring transform overflow")
            color = values["color"]
            if any(c < 0 or c > 255 for c in color):
                base._fail(context, "color lies outside native RGB range 0..255")
            frames.append(frame)
            geometry.append([length, radius, wire, windings])
            colors.append(color)
            # Conservative envelope includes the circular wire cross-section.
            for coordinate in range(3):
                center = origin[coordinate] + 0.5 * length * axes[0][coordinate]
                extent = ((0.5 * length + wire) * abs(axes[0][coordinate])
                          + (radius + wire) * (abs(axes[1][coordinate]) + abs(axes[2][coordinate])))
                result["bounds"]["min"][coordinate] = min(result["bounds"]["min"][coordinate], center - extent)
                result["bounds"]["max"][coordinate] = max(result["bounds"]["max"][coordinate], center + extent)
        item = {"id": ident, "type": "spring", "color": colors[0],
                "frames": base._compress(frames), "spring": base._compress(geometry)}
        colors = base._compress(colors)
        if len(colors) != 1:
            item["colors"] = colors
        result["objects"].append(item)
    positions = {ident: index for index, ident in enumerate(order)}
    result["objects"].sort(key=lambda item: positions[item["id"]])
    return result
