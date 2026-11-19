# M6F: 30-degree incline, massless moving pulley and hanging block

## Diagram interpretation

The user image shows an incline of **30°**, a block A on the incline,
a smaller pulley C free to move along it, a fixed pulley at the top, a
left wall/string anchor and hanging block B. Close inspection identifies
**two independent ropes**:

- S1: left anchor → around moving pulley C → attached to A
- S2: attached to axle of C → over fixed top pulley → attached to B

No masses, friction coefficient, initial velocities or external forces
are specified in the image. The *demonstration* explicitly assumes
mA=2 kg, mB=3 kg, g=9.8 m/s², initial rest, massless pulleys, frictionless
guides, massless taut inextensible ropes, and no collision during 0–1 s.
These values are illustrative and should not be presented as original
problem data.

## Physics by existing Modelica Standard Library components

New **one** Modelica model (InclineMovablePulley2D.mo), no new law or
custom component. It composes:
- MultiBody.World gravity and two MSL PointMass components,
- three MultiBody.Prismatic joints (A,C follow 30° slope, B descends),
- two pairs of stock Rotational.Components.IdealGearR2T (one per rope).

C's pulley and guide are **massless**; no arbitrary carriage mass has
been added. Its force balance imposes T2=2*T1 automatically. The first
lossless transmission enforces sA=2*sC (upslope); the second sC=sB
(B downward). OpenModelica solves motion and tensions. No prescribed
trajectories, accelerations or custom equations of motion.

Independent textbook benchmark for incline angle theta:

    2*T1 = T2
    T1 - mA*g*sin(theta) = mA*aA
    mB*g - T2 = mB*aB
    aA = 2*aC, aC = aB

So

    aB = (mB - 2*mA*sin(theta))*g/(mB+4*mA).
    aA = 2*aB.
    T1 = mA*(g*sin(theta) + aA), T2=2*T1.

For the stated illustrative 2/3 kg masses and 30°, expected acceleration
of B is **0.890909... m/s² downward**, A is **1.781818... m/s² upslope**,
and T1=13.363636... N, T2=26.727272... N.

## Reuse of domelica_mecha and the existing 2D stack

The rope geometry routines were already adapted from
physicsvigilante/domelica_mecha, especially local_geometry.py and
prepared_display_routes.py. The exact same **unmodified**
scripts/rope2d_geometry.py computes both the tangent contact points
and arc lengths:
- S1: two inclined parallel tangent legs and clockwise moving pulley arc
- S2: inclined leg to upper-left tangent of fixed wheel, clockwise
  wrap over the top, then a vertical hanging leg to B.

The Modelica model supplies every physical XY center, attachment
and radius through the native CSV; viewer/m6f-routes.json merely binds
those native columns to two ordered paths. The existing 2D HTML
builder and SVG viewer are reused without any changes. The incline
triangle is a native-grounded, **display-only** rigid polyline using
the existing rigidLinks contract. Style JSON controls only appearance.

## Focused qualification

Only one pinned OpenModelica 1.27.1/MSL4.1.0 simulation, one small
native physics oracle and one short Chromium smoke test across dark
and light standalone HTML files. The geometry builder verifies constant
rope length at every sample. Existing protected native/3D sources are
not edited, and prior PRs stay unmerged.

The result proves *this particular idealized composition*, not friction
or arbitrary pulley contact. No pulley rotation/inertia, slack, moving
wedge dynamics, collisions, or generic force-from-JSON compiler.
