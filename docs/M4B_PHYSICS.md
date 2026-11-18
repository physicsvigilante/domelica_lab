# M4B coupled-motion physics

## Source problem and scope

Q106 on page 14 of `01_mechanics.pdf` describes a block of mass `m` sliding on a prism of mass `M`, with the prism free to translate on a frictionless horizontal surface. The question supplies symbolic masses and incline angle. The numerical choices below are illustrative motion experiments, not additional data from the question.

`MovingWedge3D` composes two unmodified MSL `MultiBody.Joints.Prismatic` components and two `Parts.BodyBox` components. The first joint admits horizontal translation of the wedge. The second, attached to the moving wedge, admits downhill translation of the block. Gravity acts on both bodies. Four initial conditions fix the two joint coordinates and their velocities to zero; no body trajectory or acceleration is imposed.

The nominal choices are `M=2 kg`, `m=1 kg`, inclination 30 degrees, and `g=10 m/s²`. The finite incline is 4 m long. The initial block center lies 3.6 m uphill from its lower endpoint. A 1 s run ends before its complete 0.3 m footprint leaves the deck. It does not simulate arrival, impact or separation.

## Coordinate and geometry contract

World `y` is upward. Let `q` denote positive downhill travel relative to the wedge, and `X` denote wedge translation in world `+x`. Define

\[
u=(\cos\theta,\sin\theta,0),\qquad
n=(-\sin\theta,\cos\theta,0).
\]

The deck top starts at `surfaceOrigin={0,0.22,0}` in the translating wedge frame. Its native box is centered half a deck thickness below that top plane. The block center starts at `surfaceOrigin + startAlong*u + blockHeight/2*n`, and evolves as that vector plus `(X,0,0)-q*u`. Its bottom face therefore stays on the deck top. The standard `BodyBox` center-of-mass expression is `r_shape + normalize(lengthDirection)*length/2`; the explicit negative half-length offsets make each body's `frame_a` its center of mass. This follows the [MSL 4.1.0 BodyBox source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Parts/BodyBox.mo).

The wedge is drawn as a rigid frame with a base, inclined deck and two uprights, using native box primitives already handled by the renderer. Its total mass is represented by the base `BodyBox`; the other shapes are massless visualizers. Because the entire support undergoes constrained pure translation, its inertia distribution and fixed center-of-mass offset do not affect the translational dynamics. The appearance is not a solid triangular prism or a contact mesh.

## Independent analytical reference

Horizontal momentum conservation from the zero-velocity initial state gives

\[
(M+m)\dot X-m\cos\theta\,\dot q=0,
\qquad X=\beta q,
\qquad \beta=\frac{m\cos\theta}{M+m}.
\]

Eliminating `X` gives the effective mass for the relative coordinate,

\[
\mu=\frac{m(M+m\sin^2\theta)}{M+m}.
\]

For the unforced slide, `μ q̈ = mg sinθ`, so the nominal relative acceleration is `20/3 m/s²`. The expected 1 s motion is `q=10/3 m`, `X≈0.962250449 m`.

The independently authored `SpringWedge3D` adds an internal, initially unstretched MSL spring between the wedge and the block, with `k=10 N/m` and initial center coordinate 2.5 m. Both ends move with the two-body system, preserving horizontal momentum. The relative equation becomes

\[
\mu\ddot q+kq=mg\sin\theta,
\qquad q(t)=q_e(1-\cos\omega t),
\quad q_e=\frac{mg\sin\theta}{k},
\quad \omega=\sqrt{k/\mu}.
\]

Here `μ=0.75 kg`, `q_e=0.5 m`, and the period is approximately `1.720721163 s`. The block's relative excursion is 0–1 m; the wedge's is 0–0.288675135 m. The 6 s nominal run contains several reversals. The spring length is `1.15 m + q`.

For both models, the expected block normal reaction and total vertical ground reaction are

\[
N=m(g\cos\theta-\ddot X\sin\theta),
\qquad R_y=(M+m)g-m\ddot q\sin\theta.
\]

The nominal spring case has `N≈7.698–9.623 N` and `R_y≈26.667–33.333 N`, both compressive throughout. The relative constraint transfers power between bodies but does zero net work on the pair. The internal spring transfers momentum between them but supplies no external horizontal force.

## Verification and limitations

`scripts/native_m4b.mos` runs the two native models with DASSL tolerance `1e-9` and exports native visual XML. Completion requires fresh files, successful native initialization and simulation logs, full native MAT time coverage, and a hash-bound proof. `verify_m4b.py` then checks every original native sample against independently written constants and trajectories. It checks both body positions and velocities, joint aliases and relative geometry, horizontal momentum and center of mass, action/reaction forces, each body's force balance, positive reactions, finite deck footprint, constraint power, and total energy. The spring case includes elastic energy; the base model's bodies-only energy is not conserved separately in that case.

`artifacts/m4b-metrics.json` records the observed errors and binds the native inputs and verification sources. Results are accepted only when the actual native workflow succeeds; the analytical reference is not a substitute for execution evidence or the source of viewer motion.

These are ideal bilateral joint constraints, checked to remain compatible with compressive contact. They do not implement a unilateral contact solver, loss of contact, floor or endpoint impacts, friction, damping, spring wire contact or experimental validation. Only two nominal parameter sets are qualified by this milestone. The separate browser workflow checks visible geometry and playback; it does not constitute an OMEdit GUI test.
