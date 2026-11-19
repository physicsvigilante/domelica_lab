# M6C-2D-B: a moving pulley through the same 2D layers

## Scope and result to verify

Add one native Modelica composition: a ceiling anchor, a load-bearing moving
pulley, a fixed redirect, and a counterweight. The load and moving carriage are
represented by one point mass at the moving axle. This is an illustrative
verification problem, not an attributed textbook question.

The existing fixed-pulley example remains a regression case. Both examples use
one numeric geometry kernel, one native-recording adapter, and one SVG template.
The native runner, MAT/CSV exporter, previous Modelica examples, original
manifests, and the 3D viewer remain unchanged.

| Layer | This slice |
| --- | --- |
| Physics | Add `DomelicaLab/Examples/MovingPulley2D.mo`, composed from stock MSL components |
| Recording | Add one experiment manifest and explicit native observation mappings; reuse the runner |
| Geometry | Add a route manifest with a moving center and two pulley passages; reuse `rope2d_geometry.py` and `build_rope2d.py` byte for byte |
| Presentation | Reuse the SVG template with generic wording, one axle per pulley, and readable labels for a mass at an axle |
| Styling | Bind the existing dark/light palettes to the new body IDs; neither style changes physical data |
| Validation | Independent native Newton/energy checks, tangent/arc invariants, and actual SVG playback checks; retain fixed-pulley regression |

The template required a small generalization because the first pilot contained
fixed-pulley wording and only one axle marker. There is no moving-pulley branch
or equation of motion in the renderer. The earlier aspiration of an entirely
unchanged template was therefore too strong; the geometry kernel and recording
adapter are unchanged.

## Native mechanical composition

`MovingPulley2D` confines two MSL MultiBody PointMass components to vertical
Prismatic joints. The load coordinate q is upward positive; the counterweight
coordinate s is downward positive. Two stock
`Modelica.Mechanics.Rotational.Components.IdealGearR2T` components share a
massless auxiliary rotational flange, with ratios 2 and 1 respectively.
Their constitutive equations enforce s = 2q and reciprocal connector forces.
The auxiliary angle is a transmission coordinate, not either wheel's spin.

This is a compact composition of existing MSL laws. No trajectory, acceleration,
or force is prescribed; native inertia, gravity and connector reactions
produce the motion. The route JSON only describes how to depict that physical
model's recorded geometry. It does not define or solve a general rope constraint.

Official MSL 4.1.0 source:

- [IdealGearR2T](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/Rotational/Components/IdealGearR2T.mo)
- [Grounded support implementation](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/Rotational/Interfaces/PartialElementaryRotationalToTranslational.mo)
- [Prismatic joint](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Joints/Prismatic.mo)

## Independent physical oracle

For load mass M, counterweight mass m, upward load acceleration a, and one-strand
tension T, Newton's equations are:

    2T - M g = M a
    m g - T = 2m a

Therefore:

    a = (2m - M) g / (M + 4m)
    T = 3 M m g / (M + 4m)

Starting from rest, the load rises a t^2 / 2 and the counterweight drops a t^2.
For M=4 kg, m=3 kg, g=9.8 m/s², and t=1.2 s:

| Quantity | Analytical expectation |
| --- | ---: |
| Load acceleration upward | 1.225 m/s² |
| Counterweight acceleration downward | 2.45 m/s² |
| Load rise | 0.882 m |
| Counterweight drop | 1.764 m |
| One-strand rope tension | 22.05 N |
| Upward load support from two strands | 44.1 N |

The checker compares every saved native sample against these independent
relations, both bodies' Newton balances, the displacement/speed/acceleration
constraints, zero net constraint power, and total mechanical energy. Native
force-vector aliases are checked as well as scalar connector reactions.

## Route and geometry contract

The fixed anchor is (-r,H); the moving center is (0,y); the fixed redirect
center is (2r,H); the counterweight is (3r,z). Defaults are r=0.45 m, H=5 m,
y(0)=2 m and z(0)=3.4 m. The ordered route is:

1. Fixed anchor.
2. Below the moving pulley: sides -1/-1, counterclockwise wrap.
3. Above the fixed redirect: sides -1/-1, clockwise wrap.
4. Counterweight.

The common tangent is the vertical internal tangent at x=r. Both wraps are
semicircles. Three straight legs and two arcs give:

    L = (H-y) + (H-y) + (H-z) + 2 pi r
      = 3H - 2y - z + 2 pi r
      = 10.427433388230813 m

The native ratio 2 delta-y + delta-z = 0 conserves this geometric length.
The existing geometry evaluator consumes actual native center/end positions at
every recorded time; it is not told the expected trajectory. Tests independently
check contact-circle membership, perpendicular tangents, arc orientation,
continuity, and invariant length while the pulley moves relative to fixed points.
The SVG displays the precomputed sampled arc polyline; analytic arc length is
used for the length check.

## Reproduce and inspect

Use the project's pinned OpenModelica 1.27.1 / MSL 4.1.0 toolchain. In an empty
`observation-run` directory:

```bash
omc scripts/install_msl.mos
python3 scripts/run_experiments.py run --manifest viewer/m6c-2d-moving-experiments.json --run-dir observation-run/moving
python3 scripts/check_m6c_moving_pulley.py --csv observation-run/moving/m6c_moving_res.csv --report artifacts/m6c-moving-physics.json
python3 scripts/observation_data.py observation-run/moving/observations.json observation-run/moving artifacts/m6c-moving-observations.json
python3 scripts/build_rope2d.py --csv observation-run/moving/m6c_moving_res.csv --native-manifest observation-run/moving/experiments.json --routes viewer/m6c-2d-moving-routes.json --style viewer/m6c-2d-moving-style.json --output artifacts/m6c-2d-moving-dark.html
python3 scripts/build_rope2d.py --csv observation-run/moving/m6c_moving_res.csv --native-manifest observation-run/moving/experiments.json --routes viewer/m6c-2d-moving-routes.json --style viewer/m6c-2d-moving-style-light.json --output artifacts/m6c-2d-moving-light.html
python3 -m unittest discover -s scripts -p test_rope2d_geometry.py -v
python3 -m unittest discover -s scripts -p test_m6c_moving_rope_geometry.py -v
npm ci --ignore-scripts --no-audit --no-fund
npx playwright install chromium
node scripts/check_m6c_moving_pulley.cjs artifacts/m6c-2d-moving-dark.html artifacts/m6c-2d-moving-light.html artifacts/m6c-2d-moving-browser
```

The existing `M6C 2D Rope Geometry Layers` workflow runs this case and the
fixed-pulley regression at the same source commit. Artifacts retain frozen
Modelica source, native MAT/CSV/XML, logs, completed manifests, physics reports,
all four offline HTML files, and browser screenshots/reports. Dark/light files
must have identical times, geometry, metrics and native CSV/source identity;
the style and its own hash differ. The displayed mass and one-strand tension
must not be confused with the moving axle's two-strand support force.

## Bounded capability

This demonstrates one moving pulley and one fixed redirect with vertical legs
and constant wrap angles. It does not establish arbitrary multi-pulley physics,
branch discovery, wheel inertia/rolling contact, slack/recontact, sag, friction,
collisions, or a general scene graph. Radius is recorded from Modelica and sets
the display path; it does not add angular inertia. The nominal run checks for
positive tension and clearances and stops before contacts.

The 2D viewer remains offline recorded playback. Parameter changes require a
new native simulation. Its observation HUD shows scalar rope tension; the full
native force/velocity/acceleration mapping is exported separately. Dark/light
styles affect the SVG diagram; the surrounding HTML controls retain their
existing dark appearance. Validation of this slice is evidence for this bounded
composition, not a claim that every arrangement is supported.
