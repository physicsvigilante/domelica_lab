# M6A: Two spring-coupled pendulums with existing components

## The composability question

Can an unfamiliar mechanical topology be authored solely by a new Modelica
assembly and experiment/observation declarations, without editing the physics
engine, native runner, geometry exporter or force/motion renderer?

M6A adds SpringCoupledPendulums3D. Two fixed, independent ideal revolute
hinges each hold a massless rod ending in a point-mass bob. One standard MSL
MultiBody.Forces.Spring joins the two bobs. Both angles are native dynamic
states solved by OpenModelica; neither motion is prescribed. This is a
separately constructed JEE-relevant example, not a verbatim question from
01_mechanics.pdf.

Nominal illustrative parameters:

| Quantity | Value |
| --- | --- |
| Left bob mass | 1 kg |
| Right bob mass | 1.3 kg |
| Rod length | 1.05 m each |
| Fixed hinge separation | 2.2 m |
| Spring stiffness | 12 N/m |
| Spring free length | 2.2 m |
| Release angles | +24 and -12 degrees from vertically downward |
| Initial angular speeds | 0 rad/s |
| Gravity | 9.81 m/s2 downward |
| Native run | 0-5 s, 1,000 output intervals, DASSL |

The spring begins compressed. Its force couples the two independent
pendulum degrees of freedom and transfers energy between the bobs.

## Scope of changes

The physical arrangement is entirely in the new Modelica source, registered
in Examples/package.order. New files m6a-experiments.json and
m6a-observations.json describe the arrangement and ten native/derived
observations: each bob receives spring, rod and weight forces, velocity
and acceleration overlays.

The rod and spring arrows are forces ON the bobs, explicitly opposite to
the native connector flow forces into the corresponding spring or rod,
resolved to world coordinates by OpenModelica. Weight is derived from saved
native masses, gravity and world direction. The renderer does not guess
ownership or sign conventions.

The two previously accepted M5 assemblies are declared as fresh runs
alongside the new one in the M6 manifest. Original M5 manifests, native
recording hashes, physics models, exporters and the entire browser viewer
remain unchanged. The M6 browser workflow reuses the same generic
multi-arrangement acceptance checker. There are no new mechanism-specific
equations, Python branches or scene-graph objects.

## Reproduction

In the pinned OpenModelica 1.27.1 plus MSL 4.1.0 environment:

    omc scripts/install_msl.mos
    python3 scripts/run_experiments.py run --manifest viewer/m6a-experiments.json --run-dir observation-run
    python3 scripts/check_m6a_physics.py --csv observation-run/m6a_coupled_pendulums_res.csv --report artifacts/m6a-physics-check.json
    npm ci --ignore-scripts --no-audit --no-fund
    npm run build:runtime
    python3 scripts/build_observation_lab.py --manifest observation-run/experiments.json --results-dir observation-run --output artifacts/m6a-observation-lab.html

Open the resulting standalone HTML offline. It replays recorded Modelica
motion, forces, velocities and accelerations; viewing does not solve.

The native workflow checks unchanged accepted sources and fresh solution
completion, all original time samples, source/result hashes, rigid-rod
lengths, spring action/reaction, both point-mass Newton force balances,
nominal bob separation and modest undamped energy drift. The browser
workflow checks geometry, glyphs, source labels, controls, mobile and
Canvas fallback at several timestamps for all three arrangements.
No independent trajectory solver or broad numerical sweep is added.

## Limitations and next gate

The ideal rods and spring are massless; bobs are point masses whose visible
spheres add no rotational inertia. Hinges are frictionless. Fixed
visualizers and floor are not physical contact constraints. There is no
friction, damping, collision, coil contact, rope or prescribed drive.

One successful unfamiliar topology does not prove all possible JEE
mechanisms work; M6B should select a contrasting new composition and
record any reusable component or rendering gap without hardcoding it.
