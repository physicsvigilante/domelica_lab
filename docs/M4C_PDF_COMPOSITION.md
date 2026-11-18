# M4C PDF composition: released three-block spring chain

## Source and selected motion

The source is **problem 192, PDF page 26, printed page 6.160** of
[`01_mechanics.pdf`](../01_mechanics.pdf). The problem statement and figure were
visually inspected. The repository copy has 77 PDF pages and SHA-256
`375acb3666a9abba191605a0f2e8b5568659d44917c893a1f0f0b0e03202ee4a`.

The arrangement has three identical blocks hanging in a vertical chain. Two
identical springs connect block 1 to block 2 and block 2 to block 3. A thread
initially supports the top block. The described change is cutting that thread.

[`ReleasedSpringChain3D.mo`](../DomelicaLab/Examples/ReleasedSpringChain3D.mo)
simulates **the initial-value problem immediately after the cut**. The springs
retain the extensions of the hanging equilibrium and every block starts at
rest. There is no cutting event inside the simulation and no impulse is applied
at release. The former support is a fixed visual marker with no physical
connection to the chain.

This adds a different mechanical arrangement to the lab. Unlike Q90's single
mass between two fixed springs, all three masses now move freely. Their center
of mass falls while their relative separations contain two independent
oscillation modes. The point is to observe that motion rather than select an
answer to the textbook's initial-acceleration question.

## Composition from existing components

Every physical component is an unmodified Modelica Standard Library 4.1.0 class.

| Function | Existing MSL class | Instances |
| --- | --- | --- |
| Uniform gravity and world reference | `Mechanics.MultiBody.World` | `world` |
| Free translation and rotation with zero connection force and torque | `Mechanics.MultiBody.Joints.FreeMotion` | `topFree`, `middleFree`, `bottomFree` |
| Equal masses and rigid-body inertias with native box graphics | `Mechanics.MultiBody.Parts.BodyBox` | `topBody`, `middleBody`, `bottomBody` |
| Face attachment points on the vertical center-of-mass line | `Mechanics.MultiBody.Parts.FixedTranslation` | Four attachment offsets |
| Massless, linear, undamped springs with native spring graphics | `Mechanics.MultiBody.Forces.Spring` | `upperSpring`, `lowerSpring` |
| Reference for the former support location | `Mechanics.MultiBody.Visualizers.FixedShape` | `supportMarker` |

The FreeMotion joints introduce no guide reactions. Each box can translate and
rotate in three dimensions. Collinear initial positions and spring attachments,
zero initial angular velocities, and the symmetry of the component equations
produce the nominal vertical, nonrotating trajectory. The verification checks
that native joint forces and torques vanish and that no lateral or angular
motion develops.

The relevant component APIs were checked against the official
[MSL 4.1.0 FreeMotion source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Joints/FreeMotion.mo)
and
[MSL 4.1.0 BodyBox source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Parts/BodyBox.mo).
Initialization is specified on the FreeMotion coordinates and velocities.
The BodyBox mass comes from its density and dimensions. Its `frame_a` is placed
at the center of mass by an explicit half-length shape offset.

### Orientation coordinates and observed export boundary

The first M4C CI attempt used FreeMotion's default quaternion coordinates.
Both new models compiled and completed native simulation without Modelica
warnings; the spring chain produced 802 native samples. The subsequent CSV
inventory read failed on the unquoted generated variable name
`$STATESET1.A[1,1]`. This is an observed limitation of the repository's current
export reader handling those generated names. The native simulation had
completed, and this observation does not establish an OpenModelica compiler
bug.

The chain now sets the existing MSL option `useQuaternions=false` on each
FreeMotion joint. This selects Cardan-angle coordinates while preserving all
six degrees of freedom per body, the same initial physical state, and the same
force laws and geometry. The exporter, library and compiler remain unchanged.
The nominal bodies remain at zero rotation, far from the Cardan-coordinate
singularity; the existing native orientation and angular-velocity checks
qualify this domain. This coordinate choice is not a general recommendation
for arbitrary tumbling motion.

The official FreeMotion source fixes `w_rel_b` from `w_rel_a_start` when
`w_rel_a_fixed=true`. In its Cardan branch it computes `w_rel_b` from the angle
derivatives through `Frames.axesRotations` and `Frames.angularVelocity2`.
At the specified zero initial angles, that mapping is nonsingular, so the
fixed zero angular velocity correctly initializes all three angle rates to
zero. The unchanged translational initial conditions initialize the remaining
three velocities.

No custom physical component, spring law, motion equation, compiler patch,
exporter patch, or viewer reconstruction is introduced. The Modelica bindings
outside the stock component declarations are read-only physical observations
and energy calculations.

## Explicit illustrative values and limits

The problem specifies identical blocks and identical springs, but does not
give their numerical masses, stiffnesses, dimensions, heights, or initial
support length. These numerical choices are **illustrative**, not textbook
givens.

| Quantity | Nominal choice |
| --- | --- |
| Mass of each block | 1 kg |
| Stiffness of each spring | 100 N/m |
| Unstretched length of each spring | 0.6 m |
| Uniform downward gravitational acceleration | 9.81 m/s² |
| Each block's vertical size, width, and depth | 0.16 m, 0.28 m, 0.24 m |
| Initial top-block center height | 5 m in the chosen world coordinates |
| Initial upper/lower spring extensions | 0.1962 m / 0.0981 m |
| Initial middle/bottom center heights | 4.0438 m / 3.1857 m |
| Simulated interval | 0 to 0.8 s |
| Output interval and requested tolerance | 0.001 s; 1e-9 |

The thread is absent throughout this interval. Springs are ideal and can both
pull and push. Their compression is intentional, not rope slack. The model
does not include spring mass, damping, air drag, lateral buckling, coil contact,
ground contact, or collision. No floor is drawn. The endpoint is a selected
observation time, not an impact event or a prediction of when a physical object
would strike a surface. The y=0 plane is only a reference for limiting this
recording. The verifier requires the lowest box edge to remain more than 0.1 m
above that plane; the independent final-time prediction is about 0.12324 m.

The independent closed-form solution predicts that the upper and lower spring
lengths remain above approximately 0.4635 m and 0.4124 m over the nominal
interval. Since springs join the facing surfaces, these lengths are also the
vertical clearances between adjacent blocks. The native verifier requires both
to remain above 0.4 m at every output sample. Native Modelica assertions also
reject endpoint coincidence and body overlap. These qualifications describe
this nominal parameter set; they do not certify arbitrary parameter changes.

## Independent physical verification

[`verify_m4c_pdf.py`](../scripts/verify_m4c_pdf.py) provides `verify_pdf()`,
`required_columns()`, and the runner constants. It consumes the native MAT to
CSV export and the hash-bound successful-completion proof provided by the
existing verification infrastructure. It does not populate the viewer with
analytical samples.

Let $e_1,e_2$ be the upper and lower spring extensions, $m$ the common
mass, $k$ the common stiffness, and $a=mg/k$. Immediately before the cut,
the upper spring supports two masses and the lower spring supports one:

$$
e_1(0)=2a,\qquad e_2(0)=a,\qquad
\dot e_1(0)=\dot e_2(0)=0.
$$

Subtracting the three vertical equations of motion cancels gravity from the
relative coordinates:

$$
\begin{bmatrix}\ddot e_1\\\ddot e_2\end{bmatrix}
=-\frac{k}{m}
\begin{bmatrix}2&-1\\-1&2\end{bmatrix}
\begin{bmatrix}e_1\\e_2\end{bmatrix}.
$$

With $\omega_1=\sqrt{k/m}$ and $\omega_2=\sqrt{3k/m}$, the independent
solution is

$$
e_1(t)=\frac{3a}{2}\cos(\omega_1t)+\frac a2\cos(\omega_2t),\qquad
e_2(t)=\frac{3a}{2}\cos(\omega_1t)-\frac a2\cos(\omega_2t).
$$

The center-of-mass height is independently
$Y(t)=Y(0)-gt^2/2$. Writing the center spacings as
$d_1=h+L_0+e_1$ and $d_2=h+L_0+e_2$, where $h$ is the block height,
gives

$$
y_1=Y+\frac{2d_1+d_2}{3},\qquad
y_2=Y+\frac{d_2-d_1}{3},\qquad
y_3=Y-\frac{d_1+2d_2}{3}.
$$

The verifier differentiates these formulas analytically for velocities and
accelerations. For the nominal parameters the mode periods are approximately
0.6283 s and 0.3628 s. The initial accelerations, with upward positive, are
$(-29.43,0,0)$ m/s². The initial zeros for the middle and bottom blocks are
instantaneous; those blocks subsequently move.

At every native sample the checks cover:

- All three positions, velocities, and accelerations against the independent
  closed-form solution, with lateral motion and rotation also checked.
- Direct observation aliases against the actual native body and spring
  connector quantities, including native body mass, dimensions, density and
  inertia. Declared illustrative parameters and initial heights, plus each
  native spring's stiffness, free length and zero mass, are checked against
  independently specified constants.
- Native spring forces against their independently predicted values, their
  extension laws, and both connector-force signs.
- Each body's force balance and the center-of-mass free-fall law.
- Spring endpoints against the appropriate body surfaces and lengths against
  their three-dimensional endpoint distances.
- Zero FreeMotion forces and torques, positive spring lengths, separate
  bodies, clearance above the y=0 reference plane, and substantial motion in
  both internal spring coordinates.
- Total mechanical energy, reconstructed from native body velocities,
  inertias, heights and spring forces, including rotational energy.

The main tolerances are 3e-7 m for body positions, 3e-6 m/s for velocities,
3e-5 m/s² for accelerations, and 2e-5 J for total energy drift. The implementation
also checks exact identities and native force balances at tighter tolerances.
These are numerical verification tolerances, not estimates of experimental
accuracy. Measured residuals and completion status belong to the generated M4C
metrics report; this source document does not claim a run succeeded before the
report exists.

## Native observable and unchanged viewer

The native visuals are three boxes, two springs, and one fixed support marker.
FreeMotion's optional vector animation is disabled. The expected scene IDs are
`topBody.frameTranslation.shape`, `middleBody.frameTranslation.shape`,
`bottomBody.frameTranslation.shape`, `upperSpring.lineForce.lineShape`,
`lowerSpring.lineForce.lineShape`, and `supportMarker.vis`. The XML output is
the authority for the actual IDs and transforms.

Each box's canonical midpoint maps to its native center-of-mass frame.
`upperStart`, `upperEnd`, `lowerStart`, and `lowerEnd` are direct native spring
connector positions. The existing viewer can therefore check geometry without
a spring-chain-specific renderer. Useful observations include the three
heights, two spring extensions, signed spring forces, center height and speed,
and total energy. Around 0.3 s both springs are compressed and the three blocks
have visibly distinct displacements; the final sample shows the full fall.

## Other candidates kept outside this milestone

This was a bounded source review, not a classification of every problem in the
PDF. The following examples were not silently simplified into the chosen model:

| Source problem | Why its full motion was not included here |
| --- | --- |
| Q195, PDF page 26, printed 6.160 | Bullet penetration into planks needs an explicit resistance/material model and assumptions about its variation. The wording does not supply a complete force law for a faithful penetration animation. |
| Q198, PDF page 26, printed 6.160 | A ball struck by a bat supplies an average contact force, not a resolved contact history or impact law. Free flight alone would omit the central interaction. |
| Q220, PDF page 29, printed 6.163 | A collar stops while the other masses keep moving, followed by a ground impact. The complete motion needs the stop/contact transition and changing constraint or support conditions. Those events are outside this unchanged continuous component composition. |

These are limits of the selected information and milestone scope, not claims
that Modelica as a language cannot represent those systems with additional
physical modeling.
