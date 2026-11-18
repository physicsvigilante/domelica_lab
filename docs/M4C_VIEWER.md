# M4C native composition playback

M4C adds two new assemblies of existing Modelica Standard Library components:
a spring-mounted cart with an unactuated pendulum, and the three-block,
two-spring chain in Q192 immediately after its supporting thread is cut.
OpenModelica supplies the motion. The accepted motion viewer displays native
animation shapes and sampled transforms without changes to its renderer.

## What is new and what is reused

| Part | M4C treatment |
| --- | --- |
| Physical assemblies | New `CartPendulumSpring3D` and `ReleasedSpringChain3D` models, using existing MSL components |
| Physical acceptance | New independent cart and chain checks, coordinated by `verify_m4c.py` |
| Experiment titles, plot columns and observations | New `viewer/composition-experiments.json` |
| Packaging and acceptance entry points | New `build_composition_preview.py` and `check_composition.cjs` |
| Primitive export | Unchanged `native_scene.py` |
| Spring export | Unchanged `native_motion_scene.py` |
| Native CSV export and time handling | Existing exporter and `build_preview.add_series` |
| Input hashes and ordinary native probes | Existing `build_coupled_preview.digest`, `validate_hashes` and `attach_observations` |
| HTML, browser geometry, interaction and playback | Unchanged `motion.template.html`, `motion-spring.js` and `three-runtime.js` |

The reuse manifest and its gate compare the frozen accepted sources byte for
byte. New model names do not appear in the reused geometry exporter or browser
renderer. The new browser checker also has no cart or chain equation of motion.

## Native input and output contract

| Experiment ID | Model | Native prefix | Nominal interval |
| --- | --- | --- | --- |
| `cart-pendulum-spring` | `DomelicaLab.Examples.CartPendulumSpring3D` | `m4c_cart_pendulum` | 0–6 s, 0.005 s output interval |
| `released-spring-chain` | `DomelicaLab.Examples.ReleasedSpringChain3D` | `m4c_pdf_composition` | 0–0.8 s, 0.001 s output interval |

Each prefix supplies a native MAT result, exported CSV, `_visual.xml`, compiler
log and completion record. The builder first requires a passing
`artifacts/m4c-metrics.json`, with the matching model, sample count and start/end
times for each case. It validates every bound input and source hash. The required
source set includes both `verify_m4c_cart.py` and `verify_m4c_pdf.py`, their
orchestrator, the common completion checker `verify_m4.py`, the native runner,
CSV exporter, package files and both physical model files.

The native exporter preserves the original sample sequence, including duplicate
event timestamps. Plot values and observation probes must match that complete
time sequence exactly. Neither the new builder nor the browser acceptance code
resamples a native trajectory. Constant geometry fields may be represented by
one row only when every row is exactly equal.

The outputs are:

- `artifacts/composition-preview.html`: one self-contained offline HTML file.
- `artifacts/composition-scenes.json`: the exact data payload embedded in it.
- `artifacts/composition-provenance.json`: source/input hashes, toolchain and
  renderer details, run URL and the delivered HTML SHA-256.
- `artifacts/composition-checks/report.json`: browser observations and the
  SHA-256 of the actual HTML opened by Chromium.
- Four non-initial screenshots in `artifacts/composition-checks/`: desktop and
  390 px mobile views for each experiment.

The build also binds its new metadata, packaging/checking scripts, reuse
manifest, workflow, M4C documents, reused exporter/viewer files, package lock and
renderer runtime. Changing a bound native input or physical verification source
requires rerunning native acceptance before the preview can be packaged.

## How native positions become visible

The unchanged exporters read each native animation shape's dimensions,
orientation and origin. A scene frame has three scaled world-space axes followed
by its world-space origin. The unchanged browser uses that frame directly as the
mesh transform. Its primitive geometry supports native boxes, circular
cylinders, real cones and spheres; the existing spring extension supports an
ideal helix. Unsupported native geometry fails export instead of receiving a
substitute drawing.

Model coordinates and shape coordinates need not have the same origin. The new
metadata therefore declares **fixed points within the canonical unit geometry**
for acceptance observations. These are coordinate descriptions of a shape,
not a calculation of where the moving body should be.

| Observation | Native object and fixed local point | Independent native position |
| --- | --- | --- |
| Cart center | `cartBody.frameTranslation.shape`, `[0.5,0,0]` | `cartPosition`, an alias of the cart's `frame_a.r_0` |
| Pendulum bob center | `bob.sphere`, `[0.5,0,0]` | `bobPosition`, an alias of the PointMass frame position |
| Rod start/end | `rod.shape`, `[0,0,0]` and `[1,0,0]` | `rod.frame_a.r_0` and `rod.frame_b.r_0` |
| Each chain block center | Its `BodyBox` shape, `[0.5,0,0]` | `topPosition`, `middlePosition` or `bottomPosition`, each a native frame alias |
| Spring attachment axis | Local `[0,0,0]` and `[native length,0,0]` | The spring's native `frame_a.r_0` and `frame_b.r_0`, through direct aliases |

The authored boxes use `r_shape` offsets that place their geometric centers at
the chosen physical frame. The PointMass sphere similarly has its canonical
center at local `[0.5,0,0]`. A `FixedTranslation` rod has a start and end along its
canonical local x axis. The checker transforms these fixed local points through
the exported native frame and compares them with the separately copied native
physical coordinates at every sample.

For the cart, the rod's two native endpoints also establish rotation: their
direction must change substantially while the pivot and bob both translate.
The check cannot pass by showing the cart, rod and bob as one translated group.
For the falling chain, the block positions must move relative to one another,
and both endpoints of each spring must fall with their attached bodies. The
wall spring in the cart experiment instead has a fixed first attachment. These
are metadata observations; the checker does not assume every spring has a
fixed anchor or that every scene contains exactly two boxes.

The helix's attachment **axis** endpoints are the physical spring frames. A
coil's wire centerline lies at the native coil radius around that axis; its first
and last vertices are not asserted to lie on the axis. The ideal display does
not add modeled end hooks or coil contact.

## Geometry evidence without duplicated trajectories

The payload adds only four raw native XML dimension fields per shape: `length`,
`width`, `height` and `extra`. It reuses the accepted XML leaf parser and CSV
reader to obtain their values. Most are constant and occupy one row. It does not
copy all raw transformation, orientation and position columns a second time.

These fields are observations only. They are never used to create the displayed
meshes. They let acceptance verify the length of each scaled frame axis for all
samples, accounting for the native dimension conventions:

- Box: length, width and height.
- Circular cylinder or real cone: length, width and width.
- Sphere: length on all three axes.
- Spring: unit orientation axes plus separate length, coil radius, wire radius
  and winding count. Native `width` is the coil radius; native `height` is the
  wire radius under the accepted OMEdit 1.27.1 interpretation.

The checker also requires orthogonal, right-handed geometry axes. Every native
spring's dimension tuple is compared directly with the raw fields, preserving
the renderer's radius interpretation. The actual rendered helix is checked
separately: centerline length/radius/turn count and circular wire radius must
agree with those native values.

## Browser acceptance

After the native and reuse gates pass, the CI entry points are:

```sh
python scripts/build_composition_preview.py
node scripts/check_composition.cjs artifacts/composition-preview.html
```

The browser gate opens the exact packaged file with networking disabled and
requires functioning WebGL2 and a depth buffer. It verifies the embedded payload
against `composition-scenes.json` and the HTML bytes against the provenance
manifest. The report records Chromium's version and the tested artifact hash.

For each experiment, the gate checks:

1. Native dimensions, axis constraints, body positions, relative motion, fixed
   reference objects and every spring attachment over the complete run.
2. Four distinct native sample indices, selected by metadata. At each index it
   reads the actual rendered mesh matrices for every object, verifies canonical
   primitive vertices or spring geometry, and checks plot/scrubber/time agreement.
3. Conservative native geometry bounds throughout the run against the live
   camera's viewport and depth range. It requires a visible pixel change from
   the initial frame before capturing each non-initial screenshot.
4. XY view, actual canvas pointer selection of a moving body, component
   inspection, 3D orbit, playback to the recorded end, replay, speed selection,
   pause and scrub.
5. Both 360 px and 390 px mobile layouts, including complete trajectory framing,
   controls without horizontal overflow and component selection.

It also checks the existing explicit WebGL-unavailable state and requires no
unexpected page errors, console errors or network requests in normal playback.
The designed checks are not evidence that a particular build passed: the
generated report, run URL and matching artifact hash establish that result.

## Scope of the result

The viewer provides playback of a completed OpenModelica simulation. Camera,
selection, speed and scrub controls operate on the recording. A new mass,
spring stiffness, initial angle or physical arrangement requires a new native
simulation. The browser never integrates a substitute JavaScript physics model.

The pendulum's rod is massless and its bob is a point mass. The falling chain is
initialized immediately after release; the thread-cutting event itself is not
simulated. Springs and joints are ideal, with no damping, collision or coil
contact. Physical validity is assessed by the separate native acceptance modules;
the browser gate establishes faithful visible playback and interaction.
Headless Chromium evidence does not establish that the OMEdit GUI was run.
