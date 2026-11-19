# M6E: two 2 kg masses in user's nested-pulley image

## Literal image interpretation

One continuous rope: A -> over moving pulley C -> under moving pulley
attached to B -> over the fixed ceiling pulley -> terminates at C's
moving axle. The last strand is **not a second independent rope**.

Given by user: mass(A) = mass(B) = **2 kg**. The image does not specify
the mass of the moving C axle/carriage. This is material because its
resultant rope force is downward: two downward strands on wheel C and
one upward strand attached to C's axle.

For strictly massless C, the force balance demands zero rope tension,
which makes a positive-tension taut-string model degenerate. To produce
a bounded nondegenerate native simulation without concealing this gap,
the example sets **C carriage mass = 1 kg (illustrative only)**.
Its wheel itself remains nonrotating and massless. A/B are the only
2 kg blocks. Gravity g=9.8 m/s2, dimensions and initial rest are also
declared choices.

## Physical law / independent oracle

Positive displacements are downward. The single ideal rope imposes:

    q_A + 2 q_B - q_C = 0

A new 20-line **reusable ideal three-flange Modelica component** represents
this massless lossless bilateral constraint, with signed weights 1,2,-1.
It is not a browser physics solver. The source does not prescribe any
position, velocity, acceleration or tension. Stock MSL PointMass and
Prismatic joints supply inertias and native gravity.

With T the single-string tension:

    m_A*g - T   = m_A*a_A
    m_B*g - 2*T = m_B*a_B
    m_C*g + T   = m_C*a_C

Therefore:

    T = 2*g / (1/m_A + 4/m_B + 1/m_C)

For the **illustrative** C mass 1 kg:
T=5.6 N, a_A=7.0 m/s2 down, a_B=4.2 down,
a_C=15.4 down. The 0.3-second run stops before a geometry/contact
violation. Changing mC changes the solution; no unique numerical
accelerations can be inferred solely from the two 2 kg block masses
and the single-rope diagram.

## How both repositories are used

- **domelica_lab**: new Modelica composition and reusable three-flange
  constraint, existing frozen native runner/export and standalone SVG
  recording/presentation pipeline.
- **domelica_mecha**: same previously adapted and tested tangent/arc
  kernel (scripts/rope2d_geometry.py) and ordered rope route representation.
  No mechanics engine or dynamics code is imported from domelica_mecha.
- A small *new declarative* rope route references C, Bwheel and Top's
  **native recorded centers/radii**, the native A and C axle endpoints,
  plus the rigid Bwheel-to-B link. The core 2D geometry and viewer
  implementations are not modified.

## Focused verification and scope

One pinned OpenModelica native run, 31 analytic geometric configurations
as a smoke test, and a focused Playwright check of the two resulting
offline HTML files. The native checker compares gravity, rope tension,
q_A+2q_B-q_C, rope length and mechanical energy against the analytic
oracle. All previous pull requests remain unmerged.

No arbitrary-parameter UI, 3D changes, comprehensive scene graph,
friction, wheel spin/inertia, rope slack, self-contact or collision.
