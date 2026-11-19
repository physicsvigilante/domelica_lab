# M6B: fixed-pulley Atwood composition from Mechanics I Q68

## Goal and source

Source: repository 01_mechanics.pdf, PDF page 10, chapter 6 printed page
6.144, Question 68. Two unequal masses connected by a light string over
a smooth fixed pulley begin at rest. The lighter mass ascends 1.4 m in 2 s;
find its mass ratio to the heavier mass. The answer is 13/15 for g=9.8 m/s2.

This tests a **structurally different coupling** from M6A's bob-to-bob spring:
a fixed pulley with equal and opposite displacements of two sliding masses.
The example uses 13 kg and 15 kg to implement the question's dimensionless
ratio; it does not claim that the original problem specified absolute masses.

## Modelica assembly

- Two stock Modelica.Mechanics.MultiBody.Joints.Prismatic joints, with
  opposite upward/downward positive axes, each support one freely moving
  Modelica.Mechanics.MultiBody.Parts.PointMass under native World gravity.
- Enable the standard useAxisFlange translational ports, connect them with
  stock Modelica.Mechanics.Translational.Components.Rod(L=0). Its zero
  **coordinate** offset enforces equal positive slider displacement, thus
  physical equal-and-opposite movements; it is not a zero-length spatial rod.
- This represents the **taut, massless, inextensible rope and smooth,
  inertialess fixed pulley as a bilateral 1D ideal transmission**. The native
  connector reaction determines string tension. The example asserts tensile
  reaction and stops before illustrated bob/floor or bob/pulley contact.
  It does **not** support slack rope, impact, coil or pulley dynamics.
- Dynamic native Visualizers.FixedShape cylinders show two changing-length
  straight rope legs. Another native shape shows the **non-rotating visual**
  pulley and support. The wheel does not add inertia or friction.
- No custom motion equations or prescribed kinematics. Measurements are
  read-only aliases of the standard component states and connector forces.

## Closed-form acceptance

Let light mass m=13 kg, heavy mass M=15 kg and g=9.8 m/s2.
For an ideal taut rope the expected acceleration, rising distance and
upward tension are:

    a = (M-m)g/(M+m) = 0.7 m/s2
    y_m(t)-y_m(0) = 0.5*a*t**2
    y_M(t)-y_M(0) = -0.5*a*t**2
    T = 2*m*M*g/(M+m) = 136.5 N

At t=2 s, each moves 1.4 m in opposite vertical directions.
The independent Python **analytic** consistency check compares all native
samples to this constant-acceleration reference, verifies equal and opposite
displacement, unchanging straight+arc rope length, positive connector
tension, both mass force balances and conservative mechanical energy. The
analytic comparator is not a second numerical dynamics solver.

## Reproducibility and scope

M6B is stacked on the **unmerged** M6A PR. It adds one .mo model,
a package.order entry, separate M6B experiment/observation manifests,
one focused Python check, and a distinct CI workflow. M6A and M5 original
manifests, accepted native recordings, physics components, native runner,
geometry exporter, observation layer, and Three.js runtime remain untouched.

Use OpenModelica 1.27.1, Modelica Standard Library 4.1.0 and Node 22:

    omc scripts/install_msl.mos
    python3 scripts/run_experiments.py run --manifest viewer/m6b-experiments.json --run-dir observation-run
    python3 scripts/check_m6b_atwood.py --csv observation-run/m6b_atwood_res.csv --report artifacts/m6b-physics.json
    npm ci --ignore-scripts --no-audit --no-fund
    npm run build:runtime
    python3 scripts/build_observation_lab.py --manifest observation-run/experiments.json --results-dir observation-run --output artifacts/m6b-observation-lab.html

The output HTML is **offline recorded playback**, not a browser-native solver.
Its controls do not change masses and re-simulate in real time. Arbitrary
parameter values require a separate validated parameter/runtime facility.
No assertions are made for moving pulleys, tension-only slack/recontact,
arbitrary pulley systems, friction or collision.
