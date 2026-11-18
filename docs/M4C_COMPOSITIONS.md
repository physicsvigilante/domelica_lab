# M4C: coupled rotation and a released spring chain

This milestone adds two motion demonstrations using existing Modelica Standard Library components and the accepted native-result viewer. It builds from merged M4B revision `63d96aa9e6e32012de4b480a0542f3d48b487a40` (tree `5f85fed76200f7906d0a1d016887d6d8e5ebf3c3`).

## What moves

| Model | Arrangement | Nominal recording |
| --- | --- | --- |
| `CartPendulumSpring3D` | A spring connects a fixed wall to a horizontal carriage; an unactuated pendulum hangs below the carriage | 2 kg carriage, 1 kg point bob, 1 m massless rod, 20 N/m spring, gravity 10 m/s²; released from 35° for 6 s |
| `ReleasedSpringChain3D` | Three equal bodies hang in series on two equal springs, then their top support is removed | PDF Q192, page 26; 1 kg per body, 100 N/m springs, 0.6 m free length, gravity 9.81 m/s²; 0.8 s immediately after release |

These are illustrative numerical choices. The PDF supplies identical blocks and identical springs, without those numerical values or dimensions. Its initial-acceleration question motivates the arrangement; this project follows the subsequent motion. The spring chain is a previously unmodeled arrangement in this repository, selected after the existing viewer was frozen. This is a composition exercise, not a blind benchmark of general problem solving.

The carriage uses a standard `BodyBox`, `Prismatic`, `Revolute`, massless `FixedTranslation` rod, `PointMass`, and `Forces.Spring`. The chain uses three standard `BodyBox` bodies with `FreeMotion` joints and two `Forces.Spring` components. The free joints apply zero cut force and torque; symmetry, initial conditions and spring forces keep the nominal chain vertical. No hidden vertical guides constrain the chain.

The chain begins at the instant just after the thread is cut. Its initial spring stretches are those of the pre-cut static equilibrium. The former support is only a stationary visual marker. There is no thread-fracture component or topology-switching event. The recording ends before any body reaches the reference plane y=0; no ground collision is modeled.

## What is authored and what is reused

New work consists of the two assembly models, measurement aliases, nominal experiment metadata, independent physical verification, native-run orchestration, and additional viewer acceptance checks. The component connections and initial conditions define the experiment; they do not prescribe its trajectory.

The accepted Modelica models, native MAT reader, CSV export, native scene exporters, Three.js entry, spring renderer and complete motion-viewer template are reused unchanged. `docs/m4c-reused-sources.json` freezes 49 accepted files, including the PDF and prior verification. The only shared Modelica package edit adds the new class names to `Examples/package.order`.

Rendered meshes use OpenModelica's native animation XML and the complete original simulation time sequence. Observation metadata identifies component positions, rod endpoints, spring attachments and dimensions for verification only. It never drives geometry. There is no browser physics solver and no cart-specific or chain-specific renderer branch.

## Independent checks

The cart verifier integrates an independently written nonlinear two-degree-of-freedom equation with RK4. A second run with half the reference step checks numerical convergence before comparison with native DASSL results. Every native sample is checked for trajectory, component geometry, force and torque balances, energy, and the impulse of the external wall spring. Horizontal momentum of the carriage and bob is allowed to change by that impulse.

The chain verifier uses closed-form internal normal modes plus free fall of the center of mass. It checks every native body's position, velocity and acceleration, actual spring forces and extensions, zero free-joint constraint force, symmetry, and total mechanical energy. The initially different body accelerations provide a useful check independent of a static drawing.

Both verifiers bind the exact MAT, CSV, animation XML, simulation log and native-completion evidence. The viewer builder rejects stale physical reports. Browser checks exercise the delivered HTML using Chromium and real WebGL, inspect actual mesh matrices and spring attachments, check rotation and translation, exercise playback and picking, and inspect mobile framing. Reports include the exact delivered HTML hash. Browser checks do not establish actual OMEdit GUI behavior or experimental accuracy.

## Reproduce and open the result

Use the [Native Composition Motion Lab workflow](../.github/workflows/composition-modelica.yml). It pins the OpenModelica 1.27.1 container by digest and requests MSL 4.1.0. The installed MSL maintenance version and source path are recorded separately; its maintenance package revision is not independently locked.

With that toolchain, run from the repository root:

```sh
python3 scripts/check_m4c_reuse.py
omc scripts/install_msl.mos
omc scripts/native_m4c.mos
python3 scripts/export_native_csv.py m4c_cart_pendulum m4c_pdf_composition
python3 scripts/verify_m4c.py
npm ci --ignore-scripts --no-audit --no-fund
npm run build:runtime
python3 scripts/build_composition_preview.py
node scripts/check_composition.cjs artifacts/composition-preview.html
```

The final command requires the pinned Playwright Chromium installation, which the workflow prepares. Read the workflow's actual conclusion for the exact revision before treating its results as verified.

The `composition-lab-results` artifact contains the native data, metrics, provenance and `artifacts/composition-preview.html`. That single HTML file works offline in a browser with WebGL2. It supports scene selection, play/pause, time scrubbing, speed selection, camera controls, object inspection and synchronized native signals. Changing physical parameters requires another native simulation. The separate `composition-browser-checks` artifact contains the browser report and screenshots.

## Limits of this milestone

The carriage's horizontal guide and pivot are ideal. Its bob is an ideal point mass; the displayed sphere does not add rotational inertia. The rod has no mass, flexibility or damping. Finite carriage inertia is present, but the guide prevents its rotation.

The chain bodies are genuinely free to move in three dimensions. This recording tests symmetric vertical initial conditions, not arbitrary lateral perturbations. Both systems use ideal massless linear springs without coil contact, spring inertia, material deformation, damping or extension stops. Physical assertions and independent checks qualify the nominal clearance and positive-length domain. No general collision or contact engine is implied by the displayed shapes.

Two nominal recordings establish reuse for these arrangements only. No broad parameter sweep, experimental validation or compiler patch is part of this milestone. Earlier fluid and compiler-diagnostic work remains separate.

See [cart physics and oracle](M4C_CART_PHYSICS.md), [PDF selection and chain physics](M4C_PDF_COMPOSITION.md), and [viewer acceptance](M4C_VIEWER.md).
