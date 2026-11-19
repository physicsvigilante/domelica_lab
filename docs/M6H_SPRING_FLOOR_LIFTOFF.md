# M6H: 8 kg A on a non-rebounding floor, spring + 4.5 kg B, 10 s

## Source and explicit assumptions

User image: fixed smooth pulley, vertical rope, spring between the rope's
left end and A, block A standing on a floor, hanging block B. Requested
physical values: **mA=8 kg, mB=4.5 kg**, duration **10 seconds** and
**A does not rebound on hitting the ground**.

The image does NOT specify spring stiffness/natural length, dimensions,
gravity or initial conditions. This bounded demonstration explicitly
assumes **k=20 N/m**, initial spring natural length **1.3 m**, gravity
**9.8 m/s²**, A at rest on floor, B initially at rest, pulley radius
0.45 m and fixed pulley center height 7.5 m. The spring and rope are
ideal; no rope slack, pulley spin, friction or floor penetration.

## Physics: use stock Modelica, including a real inelastic hard stop

New \`SpringPulleyFloorLiftOff2D.mo\` uses only standard MSL:
- \`Modelica.Mechanics.Translational.Components.MassWithStopAndFriction\`
  for A, m=8kg, hard lower stop smin=0 and **all friction coefficients
  zero**. In MSL 4.1.0 this component explicitly reinitializes
  velocity with \`reinit(v,0)\` at a hard-stop impact. This represents
  an ideal inelastic normal collision **coefficient of restitution 0**.
  Its unilateral stop reaction can release when the spring overcomes
  A's weight.
- \`Translational.Components.Mass\` for freely moving B, m=4.5 kg.
- \`Translational.Components.Spring(c=20,s_rel0=0)\`, connecting A
  to a *massless* left rope endpoint.
- Two stock \`Rotational.Components.IdealGearR2T(ratio=1)\` constraints
  connect left rope endpoint upward travel to B's downward travel.
- Two stock constant gravity force components, one for each axis.

There is no hardcoded A trajectory, lift-off time, contact force, or
external browser motion. Spring force, pulley coupling, floor reaction
and transitions are computed by the OpenModelica/Modelica components.

**Important difference:** restitution zero means the floor gives no
upward *impact bounce*. If the spring later stretches enough again,
A can **lift off anew**; that later motion is not an impact rebound.

With A held on the floor, B's initial spring oscillation has maximum
spring force \`2*mB*g = 88.2 N\`, which exceeds A's weight \`mA*g=78.4N\`.
Thus lift-off is possible for this initially unstretched ideal setup.

## Visual: minimum reusable addition to current 2D viewer

The previously accepted \`domelica_lab\` native CSV → 2D adapter and
\`rope2d_geometry.py\` already handle a fixed pulley, one semicircular
arc and two moving rope legs. The only missing visual pieces are:

- An optional **spring** in route JSON, with two XY endpoints and
  rest length read from actual Modelica recorded CSV columns.
- A strictly decorative spring style (line color, stroke width, zigzag
  turns and amplitude in **pixels**, never physical units).
- An optional **floor** support marker anchored to native XY position,
  reusing the previously introduced support-marker convention.

The SVG draws a coil-like zigzag between recorded spring endpoints,
but has **no spring force law or impact detection**. Earlier
route/style files without optional springs/floor symbols retain the
existing meaning. The original 3D viewer is untouched.

## Focused acceptance

One native OpenModelica 1.27.1 / MSL 4.1.0 run covering 0–10 s with
1000 time intervals (plus native event samples). A native checker
verifies the following from recorded output:

- A begins on the floor with a relaxed spring, lifts above it and
  later impacts the floor.
- A's downward pre-impact velocity is reset to **zero at contact**,
  and A remains at rest immediately afterward (no restitution bounce).
- Rope length and B's Newton equation are consistent with native
  force/position signals; no floor penetration or tensile rope failure.
- The total mechanical energy does not increase spontaneously and
  drops across inelastic collisions.

One lightweight Chromium test checks dark/light standalone HTML,
rope arcs, floor and spring glyph positions, and play/pause at the
lift-off and impact frames. It reuses the already-tested recording
viewer instead of repeating all older mechanisms' CI suites.

## Limits

The floor is an ideal vertical hard stop, not a finite-stiffness
contact surface. Other collisions and slack-rope scenarios are not
modeled. The spring has no mass or nonlinearity and its damping is
zero; irreversible loss occurs at ground impacts. Do not infer
numerical lift-off times from the diagram alone without a spring k.
Keep this PR draft and all earlier PRs unmerged until reviewed.
