"""Export OpenModelica 1.27 native animation geometry and sampled transforms.

The inputs are a compiler-generated ``*_visual.xml`` and its native CSV result.
No joint angles, link dimensions, or model names are reconstructed here.

Schema/coordinate references (OpenModelica v1.27.1):
https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMCompiler/Compiler/Template/VisualXMLTpl.tpl
https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMEdit/OMEditLIB/Animation/Visualization.cpp

``T`` is the world-to-object rotation; local vectors use its transpose. Shape
origins are ``r + transpose(T) * r_shape``. Exported frame columns include size.
Unit primitives have length coordinate x in [0, 1]; box y/z are in [-.5, .5],
cylinder/cone radius is .5, and sphere center is (.5, 0, 0), radius .5.

Supported geometry follows the native OMEdit primitive convention: box L/W/H,
circular cylinder and real cone L/W/W, sphere L/L/L. Advanced cone variants,
rotation stripes, other shapes, vectors, surfaces, CAD, and non-leaf XML
expressions are rejected, never replaced with guessed geometry.
"""

import csv
import math
from pathlib import Path
import xml.etree.ElementTree as ET


class SceneExportError(ValueError):
    """Native scene data cannot be represented without losing information."""


def _fail(context, message):
    raise SceneExportError(f"{context}: {message}")


def _finite(value, context):
    try:
        number = float(value)
    except (ValueError, TypeError):
        _fail(context, f"expected a numeric value, got {value!r}")
    if not math.isfinite(number):
        _fail(context, "non-finite numeric value")
    return number


def _scalar(node, context, references):
    """Compile leaf data only; never evaluate source text as Python code."""
    text = (node.text or "").strip()
    if len(node):
        _fail(context, f"unsupported expression <{node.tag}>")
    if node.tag == "cref":
        if not text:
            _fail(context, "empty variable reference")
        references.setdefault(text, context)
        return ("ref", text)
    if node.tag in ("exp", "enum"):
        return ("const", _finite(text, context))
    if node.tag == "bconst" and text in ("true", "false"):
        return ("const", float(text == "true"))
    _fail(context, f"unsupported expression <{node.tag}>")


def _field(shape, name, count, context, references):
    node = shape.find(name)
    if node is None or len(node) != count:
        _fail(f"{context}.{name}", f"expected {count} scalar XML children")
    return [_scalar(child, f"{context}.{name}[{i + 1}]", references)
            for i, child in enumerate(node)]


def _read_csv(path, references):
    columns = {"time": "time", **references}
    signals = {name: [] for name in columns}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        if not header or len(set(header)) != len(header):
            _fail(path, "missing or duplicate CSV column names")
        indices = {}
        for name, context in columns.items():
            if name not in header:
                _fail(context, f"missing native result column {name!r} in {path}")
            indices[name] = header.index(name)
        for line, row in enumerate(reader, 2):
            if len(row) != len(header):
                _fail(f"{path}:{line}", "CSV row length does not match header")
            for name, index in indices.items():
                signals[name].append(_finite(row[index], f"{columns[name]} at CSV line {line}"))
    times = signals["time"]
    if len(times) < 2 or times[-1] <= times[0]:
        _fail(path, "need at least two native samples spanning positive time")
    if any(b < a for a, b in zip(times, times[1:])):
        _fail(path, "native sample times are not nondecreasing")
    return signals


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    length = math.sqrt(_dot(a, a))
    return [x / length for x in a]


def _directions(length_direction, width_direction):
    # Match native direction normalization and deterministic parallel fallback.
    length = math.sqrt(_dot(length_direction, length_direction))
    ex = ([1.0, 0.0, 0.0] if length < 1e-10
          else [v / length for v in length_direction])
    normal = _cross(ex, width_direction)
    if _dot(normal, normal) <= 1e-6:
        width_direction = [0.0, 1.0, 0.0] if abs(ex[0]) > 1e-6 else [1.0, 0.0, 0.0]
    ez = _norm(_cross(ex, width_direction))
    ey = _cross(ez, ex)
    return ex, ey, ez


def _local_to_world(matrix, vector):
    return [sum(matrix[3 * row + col] * vector[row] for row in range(3))
            for col in range(3)]


def _check_rotation(matrix, context):
    rows = [matrix[i:i + 3] for i in (0, 3, 6)]
    error = max(abs(_dot(rows[i], rows[j]) - float(i == j))
                for i in range(3) for j in range(3))
    determinant = _dot(rows[0], _cross(rows[1], rows[2]))
    if error > 1e-5 or abs(determinant - 1.0) > 2e-5:
        _fail(context, f"invalid rotation (orthogonality error {error:.3g}, det {determinant:.9g})")


def _compress(samples):
    return samples[:1] if all(row == samples[0] for row in samples[1:]) else samples


def export_scene(xml_path: Path, csv_path: Path) -> dict:
    """Return generic scene objects, native times, and an all-time world AABB.

    A frame is [axisX_xyz, axisY_xyz, axisZ_xyz, origin_xyz], with scaled axis
    columns. Frames and optional dynamic colors have either one element or one
    element per native time. Bounds conservatively enclose the oriented box
    around each primitive at every sample, including cylinders/cones/spheres.
    Duplicate event times are preserved. Unsupported or missing data fails.
    """
    root = ET.parse(xml_path).getroot()
    if root.tag != "visualization":
        _fail(xml_path, "expected <visualization> root")
    references, shapes, identifiers = {}, [], set()
    for element in root:
        if element.tag != "shape":
            _fail(xml_path, f"unsupported scene object <{element.tag}>")
        ident = (element.findtext("ident") or "").strip()
        kind = (element.findtext("type") or "").strip()
        if not ident or ident in identifiers:
            _fail(xml_path, f"empty or duplicate shape identifier {ident!r}")
        identifiers.add(ident)
        if kind not in {"box", "cylinder", "cone", "sphere"}:
            _fail(ident, f"unsupported primitive {kind!r}")
        counts = {"T": 9, "r": 3, "r_shape": 3, "lengthDir": 3,
                  "widthDir": 3, "length": 1, "width": 1, "height": 1,
                  "extra": 1, "color": 3, "specCoeff": 1}
        fields = {name: _field(element, name, size, ident, references)
                  for name, size in counts.items()}
        shapes.append((ident, kind, fields))
    if not shapes:
        _fail(xml_path, "native scene contains no supported shapes")
    signals = _read_csv(csv_path, references)
    times = signals["time"]
    bounds_min, bounds_max = [math.inf] * 3, [-math.inf] * 3
    objects = []
    for ident, kind, fields in shapes:
        frames, colors = [], []
        for i, time in enumerate(times):
            values = {name: [value if tag == "const" else signals[value][i]
                             for tag, value in expression]
                      for name, expression in fields.items()}
            context = f"{ident} at t={time:g}"
            rotation = values["T"]
            _check_rotation(rotation, context)
            dimensions = [values[name][0] for name in ("length", "width", "height")]
            if any(size < 0 for size in dimensions):
                _fail(context, "negative primitive dimension")
            if kind == "cone" and values["extra"][0] != 0:
                _fail(context, "only real cones (extra=0) are supported")
            if kind == "cylinder" and values["extra"][0] > 0:
                _fail(context, "cylinder rotation stripes (extra>0) are unsupported")
            if kind in {"cylinder", "cone"}:
                dimensions[2] = dimensions[1]
            elif kind == "sphere":
                dimensions = [dimensions[0]] * 3
            basis = _directions(values["lengthDir"], values["widthDir"])
            axes = [[v * size for v in _local_to_world(rotation, direction)]
                    for direction, size in zip(basis, dimensions)]
            offset = _local_to_world(rotation, values["r_shape"])
            origin = [v + shift for v, shift in zip(values["r"], offset)]
            frame = [*axes[0], *axes[1], *axes[2], *origin]
            if not all(math.isfinite(value) for value in frame):
                _fail(context, "transform overflow")
            frames.append(frame)
            color = values["color"]
            if any(c < 0 or c > 255 for c in color):
                _fail(context, "color lies outside native RGB range 0..255")
            colors.append(color)
            # All supported unit primitives lie in x:[0,1], y/z:[-.5,.5].
            for coordinate in range(3):
                center = origin[coordinate] + 0.5 * axes[0][coordinate]
                radius = 0.5 * sum(abs(axis[coordinate]) for axis in axes)
                bounds_min[coordinate] = min(bounds_min[coordinate], center - radius)
                bounds_max[coordinate] = max(bounds_max[coordinate], center + radius)
        item = {"id": ident, "type": kind, "color": colors[0], "frames": _compress(frames)}
        colors = _compress(colors)
        if len(colors) != 1:
            item["colors"] = colors
        objects.append(item)
    return {"times": times, "objects": objects,
            "bounds": {"min": bounds_min, "max": bounds_max}}
