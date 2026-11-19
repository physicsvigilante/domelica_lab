# M6D: two ropes, four pulleys, one prescribed acceleration

## Diagram and explicit assumptions

User-supplied image: block A accelerates **6 m/s² left** alongside four
pulleys P1–P4 and a hanging block B. The image does *not* specify
masses, initial velocities, wheel radii, friction or external drive force.
We use illustrative masses and dimensions, initial rest, ideal smooth,
massless, taut, inextensible ropes, guided translation, and a short
collision-free 1-second window.

The image contains **two different strings**:
- **S1**: left wall anchor → around moving pulley P1 → block A.
  P1 moves independently of A; its axle begins string S2.
- **S2**: P1 axle → over fixed P2 → under moving P3 →
  over fixed P4 → B. P3 is attached to B.

Let qA denote A's leftward displacement, q1 P1's leftward displacement,
and qB B/P3 upward displacement. The changing segments yield:

    delta L1 = qA - 2*q1 = 0
    delta L2 = q1 - 3*qB = 0

Thus a(P1)=a(A)/2=3 m/s² left, and
**a(B)=a(A)/6=1 m/s² upward**.
At 1 second: A goes 3 m left, P1 goes 1.5 m left, B rises 0.5 m.

## Physics layer: stock MSL, two independent constraints

The new FourPulleyTwoRope2D.mo assembles three MultiBody Prismatic joints,
PointMass bodies A/B under World gravity, one Translational.Sources.Accelerate
applying the GIVEN acceleration to A, and four standard lossless
Rotational.Components.IdealGearR2T elements arranged in two separate
shaft pairs (ratios 1:2 and 1:3). Those ideal 1D transmissions represent
the two taut-rope constraints; their shafts are **not wheel rotation**.

Only A's acceleration is prescribed; OpenModelica computes P1/B motion
and all the connector reactions. There are no custom equations of motion
and no position time series used to move P1 or B.

For illustration we choose mA=2 kg, mB=3 kg, g=9.8 m/s².
Independent force balance predicts:

    3*T2 - mB*g = mB*aB   => T2 = 10.8 N
    2*T1 = T2            => T1 = 5.4 N
    F_drive - T1 = mA*aA  => F_drive = 17.4 N

A is driven externally: total mechanical energy is *not* conserved.
For this constant-force example, its increase equals drive work.
Expected work at 1 second is **52.2 J**. The checker verifies native
positions, speeds, accelerations, flange tensions, force balance,
constraint power and work/energy at **every sampled time**.

## Geometry layer: adapted from domelica_mecha and reused unchanged

The 2D local tangent and circular-arc algorithms were previously adapted
from physicsvigilante/domelica_mecha. This milestone reuses
scripts/rope2d_geometry.py **byte-for-byte**. A small generic extension
in scripts/build_rope2d.py now supports optional native-position rigid
carrier polylines, with segment lengths verified at every recorded frame.

The route manifest viewer/m6d-four-pulleys-routes.json gives two ordered
rope routes, each pulley center and radius as a native Modelica column,
the two masses, and explicit tangent-side/wrap choices. The same generic
kernel handles P1's right semicircle; P2's upper-right quarter circle;
P3's lower semicircle; and P4's upper semicircle.

Their nominal constant routed lengths are:
- S1 = **11.12831853071796 m**
- S2 = **16.1345130209103 m**

The geometry layer does not apply physical forces or infer motion.
Changing a rope path cannot change OpenModelica's solution.

## Presentation and styling

The SVG renderer is extended only with reusable capabilities:
any number of pulley/rope labels and HUD values, edge-aware body
labels, and optional rigid-link polylines driven by native position columns.
One explicit P3-to-B carriage link is authored as three Modelica points
(P3 axle, the native elbow on B, B center) and checked for fixed segment
lengths. It makes the carried pulley-to-block connection visible. There are no P1/P2/P3/P4-specific drawing branches. The
dark/light palettes and recorded geometry remain separate.

The existing Three.js viewer, Modelica runner, native geometry exporter,
and earlier source/recording manifests are untouched.

## Qualification commands

On pinned OpenModelica 1.27.1 with MSL 4.1.0:

    omc scripts/install_msl.mos
    python3 -m unittest discover -s scripts -p 'test_*rope*geometry.py' -v
    python3 scripts/run_experiments.py run --manifest viewer/m6d-four-pulleys-experiments.json --run-dir m6d-run
    python3 scripts/check_m6d_four_pulleys.py --csv m6d-run/m6d_four_pulleys_res.csv --report artifacts/m6d-physics.json
    python3 scripts/build_rope2d.py --csv m6d-run/m6d_four_pulleys_res.csv --native-manifest m6d-run/experiments.json --routes viewer/m6d-four-pulleys-routes.json --style viewer/m6d-four-pulleys-style.json --output artifacts/m6d-four-pulleys-dark.html

Use viewer/m6d-four-pulleys-style-light.json for the light version.
The CI workflow additionally checks Chromium playback, actual SVG
coordinates against the native recording, mobile layout and no network
requests. It preserves raw MAT/CSV, source hashes, reports and screenshots.

## Explicit limitations

This does **not** prove general arbitrary-rope dynamics: each constraint
is an authored stock Modelica transmission, and a route manifest only
describes recorded geometry. There is no pulley angular inertia,
rolling friction, slack, impacts, elastic rope, 3D routing or automatic
branch selection. The axle/mass assembly of B is idealized as a guided
point mass. Default dimensions and forces are not provided by the diagram.

Work is isolated in a stacked draft PR. Do not merge earlier PRs or
regenerate accepted references before independent review.
