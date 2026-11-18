# M4C cart, pendulum and wall spring

## What this composition demonstrates

`DomelicaLab.Examples.CartPendulumSpring3D` combines a sliding carriage, a hanging pendulum and a spring anchored to a fixed wall. Releasing the pendulum causes the carriage to move. The resulting spring force changes the motion of both bodies. OpenModelica solves both mechanical degrees of freedom; no trajectory, velocity, acceleration or time-dependent drive is prescribed.

This is a chosen composition exercise, rather than a transcription of a numbered PDF problem. It uses existing Modelica Standard Library components and native primitive drawings. It does not introduce a component law or alter OpenModelica, the accepted native exporter, the renderer, or any earlier example.

| Physical role | Existing MSL component | Instance |
| --- | --- | --- |
| Uniform gravity and world reference | `MultiBody.World` | `world` |
| Horizontal ideal guide | `MultiBody.Joints.Prismatic` | `cartGuide` |
| Finite carriage with density-derived mass and inertia | `MultiBody.Parts.BodyBox` | `cartBody` |
| Undriven planar hinge | `MultiBody.Joints.Revolute` | `hinge` |
| Massless rigid pendulum link | `MultiBody.Parts.FixedTranslation` | `rod` |
| Point bob with no rotational inertia | `MultiBody.Parts.PointMass` | `bob` |
| Fixed-wall elastic connection | `MultiBody.Forces.Spring` | `wallSpring` |
| Attachment offsets | `MultiBody.Parts.FixedTranslation` | `railHeight`, `pivotOffset`, `wallAnchor`, `springAttachment` |
| Stationary structure drawings | `MultiBody.Visualizers.FixedShape` | `wall`, `rail`, `railPost`, `floor` |

The native `PointMass` is mechanically suitable here: the world, prismatic joint, revolute joint and fixed rod supply its frame orientation. Its component equations provide translational Newton dynamics and zero frame torque; they deliberately omit a rotational inertia tensor. The displayed sphere therefore must not be interpreted as a solid sphere with inertia. The rod is a massless rigid link, so its cylinder diameter also does not set any mass or bending stiffness. These choices correspond exactly to the independent equations below. See the official [PointMass source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Parts/PointMass.mo) and [FixedTranslation source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Parts/FixedTranslation.mo).

## Nominal definition and geometry

| Quantity | Value |
| --- | ---: |
| Carriage mass, $M$ | 2 kg |
| Bob mass, $m$ | 1 kg |
| Pivot-to-point-bob distance, $L$ | 1 m |
| Spring stiffness, $k$ | 20 N/m |
| Unstretched spring length | 1.1 m |
| Gravity, $g$ | 10 m/s² |
| Initial carriage displacement and speed | 0 m; 0 m/s |
| Initial pendulum angle and angular speed | 35°; 0 rad/s |
| Carriage length × width × height | 0.5 × 0.32 × 0.2 m |
| Carriage mass-center height | 1.6 m |
| Pivot height | 1.5 m |
| Bob display diameter | 0.18 m |
| Rod display diameter | 0.035 m |
| Simulation interval | 0–6 s |
| Requested output spacing | 0.005 s |
| Requested solver and tolerance | DASSL; $10^{-9}$ |

All numerical values are illustrative choices. World $x$ is horizontal, $y$ is upward, and $z$ is normal to the motion plane. The carriage coordinate $x$ is positive to the right. The angle $\theta$ is measured from vertically downward; a positive rotation about world $+z$ moves the bob toward the right of its pivot.

The actual component locations are

$$
\mathbf r_c=(x,1.6,0),\qquad
\mathbf r_p=(x,1.5,0),\qquad
\mathbf r_b=(x+L\sin\theta,1.5-L\cos\theta,0).
$$

The fixed spring endpoint is $(-1.35,1.6,0)$. Its moving endpoint is $(x-0.25,1.6,0)$, on the left carriage face. Hence the spring remains horizontal, its length is $1.1+x$, and its extension is $x$ while that length stays positive.

`BodyBox` has no authored `mass=` shorthand here. Its density is $M/(\ell w h)=62.5$ kg/m³; the standard component computes the mass from its solid box geometry. The visual origin is half a carriage length left of the component frame, so the actual mass center coincides with that frame. The world-axis moments about this mass center are

$$
I_{xx}=\frac{M(w^2+h^2)}{12},\quad
I_{yy}=\frac{M(\ell^2+w^2)}{12},\quad
I_{zz}=\frac{M(\ell^2+h^2)}{12}.
$$

Here width is along world $z$ and height along world $y$. The verifier checks all nine inertia entries, the actual native mass, and the zero center offset. The ideal prismatic joint fixes the cart orientation, so its angular velocity and rotational kinetic energy are zero even though its physical inertia tensor is finite. The official [BodyBox source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Parts/BodyBox.mo) defines this density, center-of-mass and inertia construction.

## Independent nonlinear equations

The bob velocity is

$$
\dot{\mathbf r}_b=
(\dot x+L\cos\theta\,\dot\theta,
 L\sin\theta\,\dot\theta,0).
$$

Consequently the kinetic energy is

$$
T=\tfrac12(M+m)\dot x^2
+mL\cos\theta\,\dot x\dot\theta
+\tfrac12mL^2\dot\theta^2.
$$

The gravitational and elastic energy, retaining the actual world-height constants, is

$$
V=Mg(1.6)+mg(1.5-L\cos\theta)+\tfrac12kx^2.
$$

Applying Lagrange's equations to the independent coordinates $(x,\theta)$ gives

$$
\begin{bmatrix}
M+m & mL\cos\theta\\
mL\cos\theta & mL^2
\end{bmatrix}
\begin{bmatrix}\ddot x\\\ddot\theta\end{bmatrix}
=
\begin{bmatrix}
mL\sin\theta\,\dot\theta^2-kx\\
-mgL\sin\theta
\end{bmatrix}.
$$

Its determinant is $mL^2(M+m\sin^2\theta)>0$ for the declared positive masses and length. The verifier solves this matrix independently in ordinary Python. These equations are not inserted into the Modelica model and never drive the viewer.

The initial spring force is zero, but the pendulum immediately pulls on the carriage. The independent equations predict

$$
\ddot x(0)=2.01738231959\ \mathrm{m/s^2},\qquad
\ddot\theta(0)=-7.38830721471\ \mathrm{rad/s^2}.
$$

The initial horizontal force on the carriage from the pendulum is $M\ddot x(0)=4.03476463918$ N. These values are explicitly checked against native initial accelerations and the native joint force. They help distinguish a freely responding carriage from an accidentally fixed or driven one.

## Force, torque, momentum and energy accounting

The rod tension toward the pivot, positive in tension, is

$$
\mathcal T=m\left(g\cos\theta-\ddot x\sin\theta+L\dot\theta^2\right).
$$

The bob reaction is $\mathbf F_b=\mathcal T(-\sin\theta,\cos\theta,0)$, and the force exerted by the pendulum on the cart is its negative. The ideal rail reaction has zero horizontal component. Its vertical component is

$$
R_y=(M+m)g+mL\left(\sin\theta\,\ddot\theta+\cos\theta\,\dot\theta^2\right).
$$

The rail also provides the constraint moment required to keep the cart from rotating under the force applied at the underside pivot. The verifier includes this lever arm, native hinge cut-torque, and spring attachment lever arm in the cart torque balance. It also checks the massless rod's local force and moment balances, the point bob's zero torque and the revolute joint's zero driving torque. The relevant native conventions are defined in the official [Revolute source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Joints/Revolute.mo) and [Body source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Parts/Body.mo).

For the cart-plus-bob subsystem,

$$
P_x=(M+m)\dot x+mL\cos\theta\,\dot\theta,
\qquad
\dot P_x=-kx.
$$

**Horizontal momentum is not conserved.** The wall spring supplies an external horizontal force. Because the initial velocities are zero, the required balance is

$$
P_x(t)=\int_0^t F_{\mathrm{spring},x}(\tau)\,d\tau.
$$

The Modelica diagnostic `springImpulse` integrates the actual spring connector force resolved in world coordinates:

```modelica
springForceOnCart = -Frames.resolve1(wallSpring.frame_b.R,
                                    wallSpring.frame_b.f);
der(springImpulse) = springForceOnCart[1];
```

This diagnostic receives native force results and has no mechanical connection back to the model. It does not reconstruct the force as `-k*x`. The verifier independently checks the spring constitutive law, connector-force signs, differential momentum balance and integrated impulse balance. Its separate Python reference integrates $-kx$ as a fifth state and compares that reference impulse with the native monitor.

The wall is fixed, the ideal guide does no work and the unactuated hinge has zero driving torque. The spring is massless and undamped. Therefore

$$
E=T+V=E(0)
$$

for this ideal system. The verifier checks all kinetic, gravitational and elastic terms; instantaneous power balances; and total energy drift. It does not assert conservation of cart-plus-bob kinetic/gravitational energy by itself. The standard spring's force, free length and visualization semantics come from the official [Spring source](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Forces/Spring.mo).

## Numerical verification method

`scripts/verify_m4c_cart.py` exposes `CASE_PREFIX`, `STOP_TIME`, `MINIMUM_SAMPLES`, `required_columns()` and `verify_cart()` to the M4C runner. It reuses `verify_m4.read_case` unchanged. That reader requires fresh native completion evidence, checks the MAT/log/XML hashes, requires successful initialization and a completed native simulation, verifies finite required CSV values, and binds the entire CSV time sequence to the native MAT sample sequence. An initialization-only or shortened result cannot pass.

The independent nominal constants are fixed in the verifier; native parameter values must match them. The reference is classic fourth-order Runge–Kutta, not a copied Modelica solver. Every coarse interval is subdivided exactly in half for the refined run. Both integrations land on every requested native sample time without interpolation; maximum step sizes are 0.002 s and 0.001 s. Duplicate native timestamps are allowed and do not advance the reference state.

The verifier checks the reference's step-refinement differences, energy balance and momentum/impulse balance before using it to assess native output. A reference difference below $10^{-8}$ is required in each of the five state coordinates. This convergence comparison is evidence of numerical accuracy, not a rigorous bound on global error or a proof that every possible model parameter set is valid.

| Main native comparison | Absolute acceptance tolerance |
| --- | ---: |
| Carriage displacement against independent IVP | $2\times10^{-6}$ m |
| Pendulum angle against independent IVP | $3\times10^{-6}$ rad |
| Linear/angular speed against independent IVP | $10^{-5}$ m/s or rad/s |
| Carriage/pendulum acceleration against independent IVP | $5\times10^{-5}$ m/s²; $10^{-4}$ rad/s² |
| Native world-frame geometry | $10^{-8}$ m |
| Force and torque balances | $10^{-7}$ N or N·m |
| Native momentum versus native spring impulse | $2\times10^{-6}$ N·s |
| Native spring impulse against independent IVP | $10^{-5}$ N·s |
| Total mechanical energy drift over six seconds | $5\times10^{-5}$ J |

These bounds are deliberately looser than the independent reference refinement difference and the native solver's requested tolerance. The report records measured maximum errors rather than reporting tolerances as achieved accuracy.

The verifier also requires visible travel, rotation, repeated velocity reversals, and a measurable variation in horizontal momentum. It checks positive spring length, a full bob sphere below the cart underside, bob-floor clearance, and carriage clearance from the displayed rail endpoints at every native sample. The Modelica model has corresponding geometry guards during integration.

`python scripts/verify_m4c_cart.py --reference-only` checks only the independent numerical oracle. It explicitly reports that no native Modelica simulation has been verified. This mode predicts a carriage range of approximately −0.402 to +0.282 m and a pendulum-angle range of −0.464 to +0.611 rad over six seconds. Those predicted ranges are not native test results; the M4C native report is the authority for the actual simulated run.

## Native visual interface

The viewer consumes native results and native visual XML. The observed position aliases are direct component-frame values, not reconstructed from the independent equations.

| Native shape | Primitive | Physical observation |
| --- | --- | --- |
| `cartBody.frameTranslation.shape` | Box | Canonical local center `[0.5,0,0]` equals `cartBody.frame_a.r_0` and `cartPosition` |
| `hinge.cylinder` | Cylinder | Native axis is world $z$; its center equals `hinge.frame_a.r_0` and `pivotPosition` |
| `rod.shape` | Cylinder | Canonical local endpoints `[0,0,0]`, `[1,0,0]` equal `rod.frame_a.r_0`, `rod.frame_b.r_0` |
| `bob.sphere` | Sphere | Canonical local center `[0.5,0,0]` equals `bob.frame_a.r_0` and `bobPosition` |
| `wallSpring.lineForce.lineShape` | Spring | Native endpoints are `wallSpring.frame_a.r_0` and `wallSpring.frame_b.r_0` |
| `wall.vis`, `rail.vis`, `railPost.vis`, `floor.vis` | Boxes | Stationary scenery attached to world |

Canonical points refer to the existing renderer's normalized primitive coordinates. They are checks on the native shape transform, not replacement locations for a custom rendering path. The rotating rod gives a strong orientation test: both endpoints must match different native frame positions while their separation stays one metre.

The spring uses `width=0.06`, `coilWidth=0.005` and 12 windings. MSL passes twice the coil width as native shape height, so the exported height is 0.01 m. The accepted native renderer's existing spring geometry is reused. Native frame attachments, transform orientation and endpoint travel are verified separately from physical balances.

## Scope and limits

The rail is an ideal bilateral guide, not a simulated unilateral contact between cart and track. It may provide signed forces and moments; the verifier does not incorrectly require a compressive ground reaction. The rigid rod can also transmit compression, although its nominal force range is reported. There is no rod elasticity, joint friction, damping, spring-wire contact, end stop, collision, contact separation, aerodynamic drag or bob rotational inertia.

The overhead geometry makes the bob and rod visible beneath the carriage. Its massless scenery does not affect the dynamics. Geometry guards keep the chosen run away from the displayed obstacles, but those guards do not constitute contact physics.

Passing this verification supports this specific native composition, initial condition and six-second interval. It does not validate a broad parameter sweep, experimental hardware, real-time parameter editing, numerical behavior beyond the declared interval, or every OpenModelica feature. Native physics verification and actual browser rendering checks are distinct pieces of evidence.
