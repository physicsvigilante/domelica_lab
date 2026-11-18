# M4: motion from existing Modelica components

M4 turns two mechanics arrangements into native simulations with visible motion.
The goal is to observe trajectories, spring deformation, speed and energy over
time. The analytical calculations below are independent acceptance checks; they
do not prescribe the motion and are not used by the viewer.

The source problems are Q31 on PDF page 5 and Q90 on PDF page 13 of
[`01_mechanics.pdf`](../01_mechanics.pdf). Their figures were inspected visually.
The PDF's SHA-256 is
`375acb3666a9abba191605a0f2e8b5568659d44917c893a1f0f0b0e03202ee4a`.

## Scope

| Model | What moves | Native physical components | Nominal run |
| --- | --- | --- | --- |
| `DomelicaLab.Examples.GrooveSlide3D` | A block travels along a diagonal groove on a tilted plane | `MultiBody.World`, `Parts.Fixed`, `Joints.Prismatic`, `Parts.BodyBox` | 0–2 s; output interval 0.005 s |
| `DomelicaLab.Examples.TwoSpringOscillator3D` | A block oscillates vertically while one spring extends and the other compresses | `MultiBody.World`, `Joints.Prismatic`, `Parts.BodyBox`, two `Forces.Spring`, fixed frames and translations | 0–6 s; output interval 0.005 s |

Both are assemblies of unchanged Modelica Standard Library components. The new
files are example models, connections, parameter values, stock visualizer
instances and output monitors. They introduce no force-law implementation,
numerical integrator, contact library or OpenModelica patch. There are no
prescribed-motion sources. Gravity, inertia and the connected spring or joint
equations determine the trajectories in OpenModelica.

Native MultiBody graphics are exported with `+d=visxml`. The browser uses those
native dimensions and transforms with the corresponding native result samples.
The spring renderer interprets the generic native spring shape; it does not
compute a restoring force or an oscillation. Browser playback is a recorded
trajectory. Parameter changes require another native simulation.

## Q31: diagonal groove on an inclined plane

### What is specified, and what was chosen

The source specifies a plane angle of 30°, groove length 5 m, groove angle 30°
to the horizontal contour OX in the plane, and gravity 10 m/s². The block starts
at A and is released from rest. The groove is not the line of steepest descent.

The model uses an illustrative block mass of 1 kg and dimensions
0.32 × 0.28 × 0.18 m. The source does not provide these dimensions or a mass.
The box density is set from the chosen mass and volume, rather than being a
claim about a particular material. The plane thickness, rail width and margins
are presentation choices. The groove is shown as a 0.004 m thick guide strip
above the plane so that its surfaces do not coincide with the plane surface.
The block's height offset includes that thickness, placing its bottom exactly
on the strip. These dimensions are declared in Modelica and exported natively.

### Coordinates and native motion

World y points upward. The x axis is the horizontal projection of the steepest
upslope direction, and z is a horizontal contour direction. For plane angle
α and groove angle β, define

\[
\mathbf u=(\cos\alpha,\sin\alpha,0),\qquad
\mathbf c=(0,0,1),\qquad
\mathbf n=(-\sin\alpha,\cos\alpha,0),
\]

\[
\mathbf d=\sin\beta\,\mathbf u+\cos\beta\,\mathbf c.
\]

Here **d** points from O to A and **n** is the plane normal. The `Prismatic`
axis is −**d**. Its displacement q starts at zero, increases toward O, and
is a native physical state. The block frame origin is its center of mass:

\[
\mathbf r_C(0)=5\mathbf d+0.094\mathbf n,\qquad
\mathbf r_C(t)=\mathbf r_C(0)-q(t)\mathbf d.
\]

The normal offset is the 0.09 m block half-height plus the 0.004 m guide strip
thickness. It places the bottom of the box on the strip. This constant normal
translation changes the gravitational-energy reference value, while travel,
speed and acceleration remain the same. The block's orientation is fixed by
the joint; it does not rotate. The fixed shapes and
rails carry no contact calculation. The prismatic joint supplies the ideal
groove constraint, including the side reaction needed for a diagonal groove.

The independent trajectory oracle uses the gravitational projection

\[
a=g\sin\alpha\sin\beta=2.5\;\mathrm{m/s^2},\qquad
q(t)=\tfrac12at^2,\qquad v(t)=at.
\]

This gives 5 m of travel in the chosen 2 s run. The nominal run ends at O with
nonzero velocity. Ending playback does not mean that the block hit an end stop,
bounced or became stationary. No such mechanism is specified or modeled.
The model rejects output outside the finite groove's qualified displacement
range. If geometry or gravity is changed, the run stop time must be changed too.

### Independent acceptance

`verify_m4.py` checks every native sample against the analytical displacement,
speed, acceleration and three-dimensional center position. It also checks the
world-resolved guide reaction, the positive plane-normal reaction, the side
reaction and zero constraint power. Energy is recomputed from native velocity
and height, then compared with the initial value; the exported energy monitors
are checked separately.

For the nominal mass the normal reaction is \(mg\cos\alpha\), which stays
positive throughout the run. This qualifies the selected constrained motion;
it is not a general contact or separation model.

## Q90: block between an upper and a lower spring

### The connections in the figure

The figure places the 4 kg block **between** two fixed supports: the upper
100 N/m spring connects the ceiling to the block, and the lower 300 N/m spring
connects the block to the floor. Both are initially unstretched. When the block
moves downward, the upper spring stretches and the lower spring compresses.
Both exert an upward restoring force on the block in this motion.

The two stock `MultiBody.Forces.Spring` components have zero spring mass. The
`BodyBox` has exactly 4 kg of mass, while the `Prismatic` joint permits vertical
motion and prevents sideways translation and rotation. The guide has no axial
drive or damping.

### Dimensions and initial conditions

The source gives mass, stiffnesses, gravity and initial release conditions.
It does not specify free lengths or block dimensions. The demonstration chooses:

| Quantity | Chosen value | Purpose |
| --- | --- | --- |
| Each spring's unstretched length | 0.6 m | Gives room for the complete nominal motion |
| Block height × width × depth | 0.2 × 0.3 × 0.24 m | Defines the native rigid-body shape |
| Initial block center | (0, 0, 0) m | Coordinate origin |
| Upper anchor / lower anchor height | +0.7 m / −0.7 m | Matches free spring lengths and block half-height |
| Native spring `width` input | 0.08 m | Native visualization parameter |
| Native spring `coilWidth` input | 0.006 m | Native visualization parameter |
| Windings | 7 | Native visualization parameter |

The spring shape parameters follow the native visualization convention; in the
pinned OpenModelica renderer, XML `width` is the coil centerline radius and XML
`height` is the wire radius. MSL supplies XML `height = 2*coilWidth`, so this
configuration has a 0.08 m centerline radius and 0.012 m rendered wire radius.
The resulting outer radius 0.092 m fits within the block's attachment faces.
Those dimensions are not a claim about manufactured spring dimensions. Physical spring
stiffness is supplied separately by `c`. The ideal linear components do not
infer stiffness from the rendered coil geometry.

The block starts at rest with both spring extensions zero. The initial
conditions deliberately are not static equilibrium: gravity immediately
accelerates the block downward. No release impulse is added.

### Independent trajectory and force checks

Take q as downward displacement from the initial position. The independently
derived nominal equation and solution are

\[
m\ddot q=mg-(k_1+k_2)q,\quad
\omega=\sqrt{(k_1+k_2)/m}=10\;\mathrm{rad/s},
\]

\[
q(t)=\frac{mg}{k_1+k_2}(1-\cos\omega t),\qquad
\dot q(t)=\frac{mg\omega}{k_1+k_2}\sin\omega t.
\]

The analytical reference has equilibrium drop 0.1 m, displacement range
0–0.2 m, and period \(2\pi/10\) s. These are checks on the native solution,
not equations injected into the model or viewer.

The expected spring lengths are 0.6 + q and 0.6 − q. Their native signed
extensions are +q and −q. The aliases `upperForce` and `lowerForce` both mean
**upward force on the block**, so they have the same sign in the downward
excursion. The native axial spring signals `upperSpring.f` and `lowerSpring.f`
use positive extension and negative compression instead. The checker verifies
both conventions against the native component connector forces.

Energy is independently recomputed as

\[
E=\tfrac12m|\mathbf v_C|^2+mgy_C
 +\tfrac12k_1\Delta l_1^2+\tfrac12k_2\Delta l_2^2.
\]

Its initial value is zero with this gravitational reference. The undamped
linear model should preserve it. Every native sample is checked for trajectory,
position, force balance, spring extensions and lengths, native force signs,
zero guide force and energy conservation. The verifier also requires the
intended displacement range and at least 18 velocity reversals in 6 s, so a
stationary or prematurely truncated output cannot pass as a motion demo.

The spring lengths remain at least 0.4 m in the nominal motion. This avoids
anchor coincidence. The model does not include coil contact, buckling,
detachment, damping or collision with the support plates.

## Native acceptance and artifact identity

The saved models and the batch script request DASSL with tolerance 1e-9. The
output interval is 0.005 s. The output interval is a sampling request, not a
fixed integration step. Native event samples, including repeated event times,
are preserved.

`scripts/native_m4.mos` removes this suite's old MAT, CSV, scene and log files
before each run. After each simulation it invokes the completion mode of
`verify_m4.py`. That mode requires fresh initialization and simulation-success
log messages, reads the MAT through the official OpenModelica result APIs,
checks native sample count and exact time coverage, and binds those results to
SHA-256 identities of the MAT, log and scene XML. A partial MAT or initialization
success alone is insufficient.

The unchanged native exporter reads all variables and parameters from MAT with
OpenModelica. Normal verification checks the exact CSV time sequence against
the native completion evidence and verifies the input hashes before checking
physics. `artifacts/m4-metrics.json` records the measured errors and hashes of
native inputs, source models, package definitions, runner, exporter and verifier.
The browser build binds itself to those successful acceptance inputs.

| Acceptance quantity | Nominal absolute limit |
| --- | ---: |
| Q31 displacement, center position, speed, acceleration | 5×10⁻⁷ in the corresponding SI unit |
| Q31 guide reaction | 1×10⁻⁶ N |
| Q31 energy drift | 1×10⁻⁵ J |
| Q90 displacement / center position | 5×10⁻⁷ m |
| Q90 velocity | 5×10⁻⁶ m/s |
| Q90 acceleration | 5×10⁻⁵ m/s² |
| Q90 spring force / force balance residual | 1×10⁻⁶ N |
| Q90 energy drift | 5×10⁻⁵ J |

These are acceptance limits, not a claim that every run has passed. Consult the
workflow run and its measured report for the exact source revision. Native
physics verification, browser interaction tests, native shape export tests and
an inspected OMEdit GUI animation are separate forms of evidence. Passing one
does not imply that the others were performed.

## Reproduction

From the repository root with OpenModelica and the requested MSL available:

```sh
omc scripts/install_msl.mos
omc scripts/native_m4.mos
python3 scripts/export_native_csv.py m4_groove_slide m4_two_spring
python3 scripts/verify_m4.py
```

For OMEdit, load `DomelicaLab/package.mo`, open either example and use the saved
experiment settings with **Simulate with Animation**. OpenModelica must have
its animation support installed. This is a reproduction path, not evidence
that the GUI has been exercised in the automated workflow.

## Primary references

- [MSL 4.1.0 Prismatic source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Joints/Prismatic.mo)
- [MSL 4.1.0 BodyBox source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Parts/BodyBox.mo)
- [MSL 4.1.0 Spring source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Forces/Spring.mo)
- [MSL 4.1.0 native line-force visualization](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Forces/LineForceWithMass.mo)
- [OpenModelica 1.27.1 scripting API](https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/scripting_api.html)
