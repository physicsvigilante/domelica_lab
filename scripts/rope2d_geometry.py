#!/usr/bin/env python3
"""Pure planar rope geometry; no forces, dynamics, layout or visual styling.

Numeric tangent and arc constructions adapted from the user's
domelica_mecha/src/physics_sandbox/local_geometry.py. Input world XY is metres.
The route fixes incidence sides and wrap directions; ambiguous branches fail.
"""
from __future__ import annotations
from math import atan2, cos, hypot, isfinite, pi, sin, sqrt


class RopeGeometryError(ValueError):
    pass


def point(value):
    if len(value) != 2:
        raise RopeGeometryError("Expected XY pair")
    p = tuple(float(x) for x in value)
    if not all(isfinite(x) for x in p):
        raise RopeGeometryError("Nonfinite XY point")
    return p


def positive_radius(value):
    radius = float(value)
    if not isfinite(radius) or radius <= 0:
        raise RopeGeometryError("Pulley radius must be finite and positive")
    return radius


def segment(start, end):
    start, end = point(start), point(end)
    length = hypot(end[0] - start[0], end[1] - start[1])
    if length <= 1e-9:
        raise RopeGeometryError("Degenerate straight rope segment")
    return {"start": start, "end": end, "length": length}


def point_tangent(source, center, radius, side):
    source, center = point(source), point(center)
    radius = positive_radius(radius)
    if side not in (-1, 1):
        raise RopeGeometryError("Tangent side must be -1 or +1")
    dx, dy = center[0] - source[0], center[1] - source[1]
    d2 = dx * dx + dy * dy
    if d2 <= radius * radius + 1e-12:
        raise RopeGeometryError("Attachment must be outside pulley")
    length = sqrt(d2 - radius * radius)
    ux = (length * dx - side * radius * dy) / d2
    uy = (length * dy + side * radius * dx) / d2
    contact = (source[0] + length * ux, source[1] + length * uy)
    return contact


def circle_tangent(c0, c1, r0, r1, side0, side1):
    c0, c1 = point(c0), point(c1)
    r0, r1 = positive_radius(r0), positive_radius(r1)
    if side0 not in (-1, 1) or side1 not in (-1, 1):
        raise RopeGeometryError("Common tangent sides must be -1 or +1")
    dx, dy = c1[0] - c0[0], c1[1] - c0[1]
    d2 = dx * dx + dy * dy
    if d2 <= 1e-18:
        raise RopeGeometryError("Coincident pulley centers")
    d = sqrt(d2)
    end_sign = -side0 * side1
    offset = r0 - end_sign * r1
    if d2 <= offset * offset + 1e-12:
        raise RopeGeometryError("Selected common tangent is infeasible")
    leg = sqrt(d2 - offset * offset)
    nx = offset * dx / d2 - side0 * leg * dy / d2
    ny = offset * dy / d2 + side0 * leg * dx / d2
    return ((c0[0] + r0 * nx, c0[1] + r0 * ny),
            (c1[0] + end_sign * r1 * nx, c1[1] + end_sign * r1 * ny))


def arc(center, radius, start, end, wrap, steps=24):
    center, start, end = point(center), point(start), point(end)
    radius = positive_radius(radius)
    if wrap not in ("clockwise", "counterclockwise"):
        raise RopeGeometryError("Wrap must be clockwise or counterclockwise")
    for contact in (start, end):
        if abs(hypot(contact[0] - center[0], contact[1] - center[1]) - radius) > 1e-7 * max(1, radius):
            raise RopeGeometryError("Arc contact is not on pulley")
    first = atan2(start[1] - center[1], start[0] - center[0])
    last = atan2(end[1] - center[1], end[0] - center[0])
    clockwise = wrap == "clockwise"
    sweep = ((first - last) if clockwise else (last - first)) % (2 * pi)
    if not 1e-7 < sweep < 2 * pi - 1e-7:
        raise RopeGeometryError("Degenerate or full-circle wrap")
    count = max(4, int(steps))
    direction = -1 if clockwise else 1
    samples = [(center[0] + radius * cos(first + direction * sweep * j / count),
                center[1] + radius * sin(first + direction * sweep * j / count))
               for j in range(count + 1)]
    samples[0], samples[-1] = start, end
    return {"center": center, "radius": radius, "start": start, "end": end,
            "clockwise": clockwise, "sweep": sweep, "length": radius * sweep,
            "points": samples}


def evaluate_route(nodes, attachments, pulleys):
    """Return joined straight legs, tangent-continuous arcs, total length, XY path.

    nodes: ordered attachment/pulley entries. Explicit tangent sides and
    wrap orientation are branch choices, not guessed from camera positions.
    """
    if len(nodes) < 2 or nodes[0]["kind"] != "attachment" or nodes[-1]["kind"] != "attachment":
        raise RopeGeometryError("Route must start and end at attachments")
    if any(node["kind"] not in ("attachment", "pulley") for node in nodes):
        raise RopeGeometryError("Unsupported rope route node")
    if any(a["ref"] == b["ref"] and a["kind"] == b["kind"] for a, b in zip(nodes, nodes[1:])):
        raise RopeGeometryError("Repeated consecutive route endpoint")
    def position(node):
        if node["kind"] == "attachment":
            return point(attachments[node["ref"]])
        return point(pulleys[node["ref"]]["center"])
    def radius(node):
        return positive_radius(pulleys[node["ref"]]["radius"])

    segments = []
    for left, right in zip(nodes, nodes[1:]):
        a, b = position(left), position(right)
        if left["kind"] == right["kind"] == "attachment":
            start, end = a, b
        elif left["kind"] == "attachment":
            start, end = a, point_tangent(a, b, radius(right), right["incomingSide"])
        elif right["kind"] == "attachment":
            start, end = point_tangent(b, a, radius(left), left["outgoingSide"]), b
        else:
            start, end = circle_tangent(a, b, radius(left), radius(right),
                                       left["outgoingSide"], right["incomingSide"])
        segments.append(segment(start, end))
    arcs = []
    by_node = {}
    for index, node in enumerate(nodes[1:-1], start=1):
        if node["kind"] != "pulley":
            continue
        a = segments[index - 1]
        b = segments[index]
        center = position(node)
        r = radius(node)
        arc_data = arc(center, r, a["end"], b["start"], node["wrap"])
        expected = -1 if arc_data["clockwise"] else 1
        for contact, leg in ((a["end"], a), (b["start"], b)):
            ux = (leg["end"][0] - leg["start"][0]) / leg["length"]
            uy = (leg["end"][1] - leg["start"][1]) / leg["length"]
            rx, ry = (contact[0] - center[0]) / r, (contact[1] - center[1]) / r
            cross = rx * uy - ry * ux
            if expected * cross < 1 - 1e-6:
                raise RopeGeometryError("Rope tangent contradicts selected wrap")
        arcs.append({"node": index, "pulley": node["ref"], **arc_data})
        by_node[index] = arc_data

    polyline = [segments[0]["start"], segments[0]["end"]]
    for index in range(1, len(segments)):
        current = segments[index]
        if index in by_node:
            polyline.extend(by_node[index]["points"][1:])
        elif hypot(polyline[-1][0] - current["start"][0],
                   polyline[-1][1] - current["start"][1]) > 1e-7:
            raise RopeGeometryError("Route discontinuity at attachment")
        polyline.append(current["end"])
    total = sum(s["length"] for s in segments) + sum(a["length"] for a in arcs)
    return {"segments": segments, "arcs": arcs, "points": polyline, "length": total}
