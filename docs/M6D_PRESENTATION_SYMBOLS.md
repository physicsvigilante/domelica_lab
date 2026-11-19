# M6D presentation follow-up: native-anchored schematic symbols

## Motivation

The four-pulley image has two rectangular blocks, a left wall anchor and a
ceiling support for P4. The verified M6D 2D HTML initially drew point-mass
circles with no wall/ceiling symbols. The measured motions, forces and rope
geometry were already correct; this change improves display fidelity **only**.

## Contract

The existing style schema gains two optional, strictly decorative fields:

- bodySymbols: maps known native body IDs to "box" glyphs with widthPx and
  heightPx. These are explicitly **screen pixels**, not physical body sizes.
  Omission leaves the original circular glyph and old manifests unchanged.
- supportMarks: an ordered list of "wall" marks referencing named native
  attachment IDs and "ceiling" marks referencing named native pulley IDs.
  sizePx sets the mark's visual span. It never sets a physical coordinate,
  force, contact condition, or length.

The recording adapter includes native XY attachment positions in each
frame. The renderer projects those positions with the same native XY scale
used for ropes and pulleys, then draws the specified symbols. Ceiling
stems terminate at the physical wheel rim (native radius projected by the
same scale). No support is movable by styling-only world coordinates.

The geometry kernel (rope2d_geometry.py), Modelica physical models, native
runner/exporter, rope constraints, and recorded physics are untouched.

## Independent validation

- Style validation rejects unrecognized fields (including mass, radius,
  gravity or arbitrary position), unknown body IDs, unknown support refs,
  duplicated support IDs, nonfinite dimensions, and invalid glyph kinds.
- Dark and light styles use identical symbol dimensions and support identities,
  while choosing different colors.
- The actual SVG tests check rectangle centers against native body positions,
  decorative pixel dimensions against style, the wall support against the
  native wallAnchor column, the ceiling against P4's native center/radius,
  and every rope/control sample for all 1,002 native frames.
- Existing one-fixed-pulley and one-moving-pulley playback/browser checks
  remain unchanged and pass as regressions.

**Interpretation:** blocks are still Modelica PointMass bodies. Their
rectangular outlines are intentionally schematic; no translational or
rotational inertia is inferred from the picture. The supported symbols are
not a generic geometry compiler or CAD scene graph.

## Next

If needed, the next strictly separate slice can add **native-bound 2D
acceleration/force arrows** using the existing observation manifest. It
should not prescribe motion or inject forces into the geometry layer.
