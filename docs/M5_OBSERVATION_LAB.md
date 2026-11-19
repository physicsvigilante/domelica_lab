# M5 — Reusable observations over native motion

M5 adds a shared presentation layer for forces, velocities, accelerations and
torques. The same code displays the cart–pendulum and the released spring chain.
The Modelica assemblies, their physical laws, the native MAT reader and the
native geometry exporters are unchanged.

## Open the result

The **Native Observation Lab** workflow publishes **observation-lab-results**.
Open `artifacts/observation-lab.html` for self-contained offline playback. It
contains both scenes, all original native timestamps and the bundled renderer.
No OpenModelica installation or web server is required to view a recording.

Choose a system, a quantity and a body. Individual observations can be hidden.
The scale is shared by all visible arrows of that quantity; numerical readouts
show the unscaled world-coordinate values. Select an observation to inspect its
source expression, sign convention and application/reference point. Physical
parameter changes require a new native simulation.

The default 3D path uses Three.js/WebGL2. If the browser does not supply WebGL2,
the same native data can be viewed in an explicitly labeled Canvas XY
projection. This fallback has no 3D orbit. It projects the native affine shapes
and sampled vectors; it does not run another mechanics solver.

## What is observed

| Recording | Observations | Native sample count in the original M4C run |
| --- | ---: | ---: |
| Cart–pendulum | 6 forces including 2 derived weights, 2 velocities, 2 accelerations, 1 guide torque | 1,202 |
| Released spring chain | 7 forces including 3 derived weights, 3 velocities, 3 accelerations | 802 |

New runs retain whatever original timestamp array OpenModelica produces,
including duplicate event/final timestamps. No fixed sample count is imposed
on a future model.

Each observation declares a receiving/observed body, world-coordinate
application/reference point, quantity, units, sign convention and source.
Ownership and application points are authored metadata; the renderer never
guesses them from a variable name or assumes every body-frame origin is its
center of mass.

Sources have three distinct meanings:

- `native`: directly read from saved native columns, including model-authored
  force aliases evaluated by OpenModelica.
- `native-transform`: a native connector vector resolved into world coordinates
  with the saved rotation matrix and an explicitly declared sign. The chain's
  spring forces use `-transpose(frame.R.T) * frame.f`, so the arrows are forces
  **on the blocks**, opposite the connector forces into the spring.
- `derived`: a declared calculation using saved native data. Weight is computed
  from native body mass and uniform-gravity parameters; it is not described as
  an independently exported force column.

The native guide couple is included for the cart. Force and torque are separate
quantities. A torque glyph is a double axial arrow with right-hand-rule
direction, not a force at the tip of a lever. In XY, positive/negative Z is
marked by a dot/cross symbol; symbol radius is not a magnitude scale.

Exactly zero vectors have no directional glyph. Small nonzero native values
remain unchanged and use scientific notation when needed. Camera fitting
includes active arrow endpoints throughout the trajectory. Changing arrow
scale changes display geometry only.

See [the complete observation mapping](OBSERVATION_MAPPING.md) and
[the renderer interface](INTEGRATION.md).

## A manifest instead of another milestone-specific runner

`viewer/observation-experiments.json` declares model class, prefix, solver interval/options,
native recording identity, chart signals and the observation-manifest path.
`viewer/observations.json` declares the body and vector bindings. The shared
commands are:

```bash
# Show the generated native script without running a simulation.
python3 scripts/run_experiments.py plan --run-dir observation-plan

# Run in a fresh, empty directory using installed OpenModelica and MSL.
omc scripts/install_msl.mos
python3 scripts/run_experiments.py run --run-dir observation-run

# Bundle the pinned renderer and package that completed native recording.
npm ci --ignore-scripts --no-audit --no-fund
npm run build:runtime
python3 scripts/build_observation_lab.py \
  --manifest observation-run/experiments.json \
  --results-dir observation-run \
  --output artifacts/observation-lab.html
```

The runner freezes a copy of the Modelica package inside the run directory,
keeps native logs, requires an explicit native success message for each model,
checks the saved time interval, and uses the existing native MAT-to-CSV reader.
It records model/source hashes and generated input hashes. It does not run an
independent dynamics solver or an energy/trajectory comparison campaign.

The builder requires matching native input hashes, source bindings when
available, matching geometry/observation timestamps, finite values, supported
units and declared bodies. It rejects missing columns and unknown observation
operations. The copied recording is playback; `newSimulationDuringBuild` and
`newSimulationDuringExport` describe those stages separately from the origin
of the native run.

For replaying the original accepted M4C artifacts, use the checked-in manifest
and point `--results-dir` at that extracted artifact. Its known hashes prevent
silently mixing old geometry with another result file.

## Adding another arrangement

1. Compose its `.mo` model from supported Modelica components and add its class
   to the package as usual.
2. Add an experiment entry with its model, solver settings and signals.
3. Add body and observation bindings to the observation manifest. Use actual
   result-column names and explicitly identify point, frame, sign and units.
4. Run the same native command and build the same viewer.

No model-name branch is needed in the observation renderer. This is a contract
for the supported geometry/observation operations, not a claim that every
Modelica component or native visualizer is already supported. The existing
geometry exporters support boxes, cylinders, cones, spheres and springs. Other
primitive types still require a generic exporter/renderer extension.

## Validation scope and limitations

The workflow performs fresh native simulations, data/schema checks and focused
browser checks on the exact generated HTML. Its separate
**observation-browser-checks** artifact records the actual outcome, backend,
HTML hash and screenshots. Consult the run on the revision being reviewed;
documentation is not a substitute for a successful run.

The local chat environment blocked Chromium at process startup. JavaScript
syntax, generic overlay API and direct Canvas raster inspection were possible
there; those checks alone were not reported as a browser pass. The initial
chat preview reused the original M4C native run, before repository write
authorization was clarified. The new workflow supplies its own native source
and run provenance.

The physical scope is inherited from M4C: a point-mass bob, massless rod, ideal
guide/joints/springs, no contact or damping, and a chain initialized immediately
after support removal. Six nonfatal state-selection warnings were present for
the original nominal, nonrotating chain; logs are retained. This work does not
qualify arbitrary tumbling or establish an OpenModelica compiler defect.

Earlier fluid/compiler diagnostics remain separate.
