# Native observation mapping

These mappings were first exercised with the accepted OpenModelica run at commit
`2391387201f6d4feffbcd4e8cafdf0d6430fdfc1`, recorded in
[run 44370469180](https://github.com/physicsvigilante/domelica_lab/actions/runs/44370469180).
The mappings also apply to fresh recordings produced by the manifest runner.
The observation exporter itself never solves a new trajectory or changes
Modelica equations. Each built viewer names the native recording it actually uses.

## What the metadata declares

`observations.json` defines each arrow's quantity, unit, receiving body,
application or reference point, source columns, coordinate frame, and sign
meaning. The generic exporter contains no model names or mechanics equations.
It accepts direct native vector columns, constant vectors, a native frame
rotation plus an explicit sign, and a labeled uniform-gravity calculation.
It rejects unsupported operations and missing/nonfinite inputs.

Positions always come from native world-coordinate position columns. The
export keeps every sample, including the duplicate final timestamp. The two
output scenes have exactly the same timestamp arrays as the accepted native
geometry, so an animation must use one shared sample index for both geometry
and overlays. No interpolation or numerical differentiation is performed here.

### Cart–pendulum

| Quantity | Native source | Receiving body / reference point | Interpretation |
|---|---|---|---|
| Spring force | `springForceOnCart[1:3]` | Cart / `springCartPosition` | Already world-resolved and signed as force on cart in the Modelica model. |
| Hinge force | `pendulumForceOnCart[1:3]` | Cart / `pivotPosition` | Pendulum reaction at the hinge; do not move it to the cart COM without an accompanying moment change. |
| Guide force | `railReaction[1:3]` | Cart / `cartPosition` | Bilateral ideal-guide reaction, not a contact-only normal. |
| Rod force | `rodForceOnBob[1:3]` | Bob / `bobPosition` | Force into the point-mass bob connector. |
| Guide couple | `railTorque[1:3]` | Cart / guide frame at `cartPosition` | Native torque vector, world-resolved; right-hand-rule direction, units N·m. |
| Cart velocity | `cartVelocity[1:3]` | Cart / `cartPosition` | Native world velocity. |
| Bob velocity | `bobVelocity[1:3]` | Bob / `bobPosition` | Native world velocity. |
| Cart acceleration | `cartBody.a_0[1:3]` | Cart / `cartPosition` | Full native vector, not reconstructed from displacement. |
| Bob acceleration | `bobAcceleration[1:3]` | Bob / `bobPosition` | Native world acceleration. |
| Two weights | `cartBody.m`, `bob.m`, `world.g`, `world.n` | Respective centers of mass | Explicitly derived as mass × gravity, not stored force-output columns. |

The cart body's reference frame coincides with its center of mass in this
authored model. That relationship is established by the model geometry and
native `r_CM` values; the exporter does not assume it for arbitrary bodies.
The guide couple is necessary when interpreting the full cart free body,
because the hinge force is applied below the center of mass.

### Released spring chain

| Quantity | Native source | Receiving body / application point |
|---|---|---|
| Upper spring → top | `upperSpring.frame_a.f`, `.R.T` | Top block / `upperStart` |
| Upper spring → middle | `upperSpring.frame_b.f`, `.R.T` | Middle block / `upperEnd` |
| Lower spring → middle | `lowerSpring.frame_a.f`, `.R.T` | Middle block / `lowerStart` |
| Lower spring → bottom | `lowerSpring.frame_b.f`, `.R.T` | Bottom block / `lowerEnd` |
| Three velocities | `topVelocity`, `middleVelocity`, `bottomVelocity` | Corresponding native COM positions |
| Three accelerations | `topAcceleration`, `middleAcceleration`, `bottomAcceleration` | Corresponding native COM positions |
| Three weights | Each `Body.m`, plus `world.g`, `world.n` | Corresponding native COM positions |

A Modelica connector flow force points **into its component**. At each spring
connection the display therefore uses `−transpose(R.T) × frame.f` for the force
**on the attached block**. MultiBody's `R.T` maps world vectors into the local
frame, so its transpose resolves a saved connector force back into world
coordinates. These channels are labeled **native-transform** to distinguish
the frame/sign conversion from a force vector already saved in world axes.
The exporter reads the complete native rotation matrix at every sample even
though this particular accepted run is nonrotating.

The weights are separately labeled **derived**. They use the native body mass
and uniform world gravity parameters: `mass * g * n / length(n)`. A different
gravity law would need a different explicit source mapping; this operation
must not be applied to a point-gravity model by assumption.

Each chain body has full FreeMotion freedom. The drawn upper support marker
is disconnected scenery and contributes no support force. No extra rail or
contact force is added to the display.

## Lightweight checks completed

- All 24 overlays have finite three-component vectors and positions for every
  sample: 11 cart overlays over 1,202 samples; 13 chain overlays over 802.
- Both timestamp arrays match the accepted native geometry arrays exactly.
  One duplicate final timestamp is preserved in each scene.
- All declared source columns exist. Input CSV hashes are recorded in the
  exported provenance, and the source manifest has its own SHA-256 binding.
- Initial force directions agree with connector ownership. The upper spring
  pulls the top block down and the middle block up; the lower spring pulls the
  middle block down and the bottom block up. The cart guide couple starts in
  the negative world-z direction.
- One nonidentity rotation fixture checks the transpose direction that the
  nonrotating chain data alone cannot exercise.

These checks establish the observation mapping and data alignment. They do
not constitute a new simulation, a new numerical accuracy study, or browser
render acceptance. The viewer needs its own focused interaction/render checks.

## Rebuild

```bash
python3 scripts/observation_data.py viewer/observations.json PATH_TO_NATIVE_RESULTS observation-scenes.json
```

The native results directory must contain the two filenames declared by the
manifest. Add a new model by declaring its saved columns and ownership in a
new scene entry; do not add a model-name branch to the exporter.
