# M4B spring–wedge composition

`DomelicaLab.Examples.SpringWedge3D` extends `MovingWedge3D` and attaches one existing `Modelica.Mechanics.MultiBody.Forces.Spring` between the moving wedge and the block. Two existing `FixedTranslation` components locate its attachment frames. A `FixedShape` box depicts the mount. The composition introduces no new physical component, force law, compiler change, native export primitive, or renderer branch.

The spring's upper anchor is connected to `groundGuide.frame_b`, which moves with the wedge. Its other endpoint is connected to the block's uphill face through `massBody.frame_a`. Neither endpoint is attached to the ground. The inherited joints and bodies determine the motion together with the added spring.

This is an independently authored variation of the Q106 arrangement, not another problem from the PDF. All numerical parameters below are illustrative.

## Nominal arrangement

| Quantity | Value |
| --- | ---: |
| Wedge mass, M | 2 kg |
| Block mass, m | 1 kg |
| Inclination, theta | 30 degrees |
| Gravity, g | 10 m/s² |
| Spring stiffness, k | 10 N/m |
| Initial block center along the incline | 2.5 m |
| Anchor position along the incline | 3.8 m |
| Block length along the incline | 0.3 m |
| Initial unstretched spring length | 1.15 m |
| Initial wedge and relative velocities | 0 m/s |
| Recording duration | 6 s |
| Requested output interval | 0.005 s |

The anchor and the block face have the same normal offset above the deck. Their separation is therefore along the incline, and the spring has no component normal to the deck. Its free length is the initial separation, `anchorAlong - startAlong - blockLength/2`. The spring is massless, linear and undamped. The MSL spring component supplies its physical force; the aliases added in this model only expose measurements and energy.

## Independent analytical expectations

Let q be the block's downhill displacement relative to the wedge and X the wedge's displacement to the right. Define the uphill unit vector u = (cos(theta), sin(theta), 0). Both prismatic joints preserve the world-parallel orientations of their frames.

The block's velocity is `Xdot*ex - qdot*u`. Conservation of horizontal momentum, with zero initial momentum, gives

```text
(M + m) Xdot - m cos(theta) qdot = 0
X = beta q
beta = m cos(theta)/(M + m).
```

Eliminating X from the two-body kinetic energy gives the effective relative mass

```text
mu = m (M + m sin(theta)^2)/(M + m).
```

Gravity and the spring give the independent scalar equation used for verification:

```text
mu qddot + k q = m g sin(theta).
```

This equation is an oracle for the native result. It is not used to prescribe motion in the Modelica source or viewer. For release from rest with the spring unstretched,

```text
qeq = m g sin(theta)/k
omega = sqrt(k/mu)
q(t) = qeq (1 - cos(omega*t))
qdot(t) = qeq omega sin(omega*t)
qddot(t) = qeq omega^2 cos(omega*t).
```

The nominal expectations are:

| Quantity | Analytical expectation |
| --- | ---: |
| Effective mass, mu | 0.75 kg |
| Equilibrium relative displacement | 0.5 m |
| Downhill displacement range | 0 to 1 m |
| Wedge displacement range | 0 to 0.2886751346 m |
| Angular frequency | 3.6514837167 rad/s |
| Period | 1.7207211629 s |
| Spring length range | 1.15 to 2.15 m |

The block returns uphill and the wedge returns left during the second half of each oscillation. The block's center remains between 1.5 and 2.5 m along the 4 m support, so its finite visual body stays on the deck throughout the nominal run.

## Force, energy, and geometry checks

The deck normal is n = (-sin(theta), cos(theta), 0). The required compressive normal reaction on the block is

```text
N = m (g cos(theta) - Xddot sin(theta)).
```

Its nominal range is approximately 7.6980 to 9.6225 N, which stays positive. The ground's upward reaction is

```text
Rground = (M + m)g - m sin(theta) qddot,
```

which ranges from approximately 26.6667 to 33.3333 N. These signs make the nominal constrained motion compatible with compressive support. The model remains a bilateral joint model and does not implement contact loss or collision.

The spring length must equal `springFreeLength + q` at every native sample. The force on the block is uphill with magnitude `k*q`, and the equal and opposite force acts on the wedge. The two ideal guide reactions together do no net work because the relative velocity along the incline is perpendicular to the normal. The spring's net power on both bodies equals the negative rate of its elastic energy.

The conserved energy includes both moving bodies and the spring:

```text
E = 0.5*M*Xdot^2
  + 0.5*m*((Xdot - qdot*cos(theta))^2 + (qdot*sin(theta))^2)
  + gravitational energy of both bodies
  + 0.5*k*q^2.
```

The inherited `totalEnergy` covers the two bodies' kinetic and gravitational energy. The extension's `composedEnergy` adds `elasticEnergy`; the inherited energy alone is not conserved in this variant. Verification must compare the native body positions, velocities and spring forces with independently calculated quantities, rather than checking only these aliases.

Native spring endpoints are `internalSpring.frame_a.r_0` and `internalSpring.frame_b.r_0`. Its existing native primitive is `internalSpring.lineForce.lineShape`. The saved scene must keep both endpoints attached to the moving components throughout playback, including duplicate native sample times. The mount is the existing box primitive `anchorMount.vis`.

## What the composition establishes

Successful native and viewer verification demonstrates this specific extension through Modelica authoring: add standard components and connections, change initial geometry parameters, and describe the desired signals. It does not establish support for arbitrary contact, friction, detachment, or spring wire collision. Parameter changes need another native simulation and renewed checks of finite support, positive spring length, and reaction signs.

The MSL component's physical interface and law are described in the [official Spring documentation](https://build.openmodelica.org/Documentation/Modelica.Mechanics.MultiBody.Forces.Spring.html). Final run identities, numerical errors and browser verification belong in the workflow artifacts and milestone report.
