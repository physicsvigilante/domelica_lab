# Domelica Lab

A **Modelica-first multiphysics laboratory** for composing physical systems, running native simulations, and exploring their geometry and signals in an offline browser viewer.

## What is here

| Experiment | What it explores |
| --- | --- |
| **ThermalGearedArm3D** | A motor, 5:1 gearbox, two perpendicular joint axes, passive elbow, winding heat capacity, cooling, and resistance that changes with temperature |
| **MotorizedPendulum3D** | Electrical armature dynamics coupled to a gravitational rigid body and rotational damper |
| **HeatedBody** | A thermal network checked against an independent analytical solution |
| **MSL DoublePendulum** | An unchanged standard-library example using the same native scene pipeline |
| **Controlled thermal arm (M2)** | Native PID feedback, voltage limits and anti-windup; four experiments isolate forearm load, controller settings and cooling |
| **Visible motion (M4)** | A block sliding through a diagonal groove on an incline, and a block oscillating between two fixed springs, composed from existing MSL components |
| **Coupled motion (M4B)** | A block on a freely translating wedge, followed by a spring carried by that wedge; two interacting bodies reuse the existing native viewer |
| **Further compositions (M4C)** | A carriage, pendulum and wall spring couple translation to rotation; three free bodies connected by two springs fall after support removal |
| **Native observations (M5)** | One reusable layer overlays force, velocity, acceleration and torque on the cart–pendulum and released chain, with explicit source, frame, units and body ownership |

The armature is reusable Modelica code. `ThermalArmatureDrive` extends it by exposing the standard resistor's heat port; the original component is unchanged. The browser reads native geometry and transforms and has no physics solver or model-specific pendulum drawing.

## Open the results

From a successful [Native Modelica Lab workflow run](https://github.com/physicsvigilante/domelica_lab/actions/workflows/native-modelica.yml), download **modelica-lab-results**, extract the ZIP, and open **artifacts/browser-preview.html**. The file works offline, without OpenModelica or a web server.

Choose a scene, play or scrub time, drag to orbit, switch to XY, and click a visible object to inspect its transform. Three.js renders the native geometry with lighting, a depth buffer, and surface picking. It is bundled inside the HTML; viewing requires a browser with WebGL2, with no installation or network connection. The **modelica-browser-checks** artifact contains the browser test report and screenshots for that same HTML file.

M1 and M2 have been reviewed and merged into `main`. Check the run attached to the exact revision before treating a result as verified.

The **Publish Verified Lab** workflow can publish the selected, verified viewers directly to GitHub Pages. Its release manifest binds the source revision, successful native/browser run, and exact HTML hashes; it does not publish arbitrary latest artifacts. See [publishing setup and release selection](docs/PUBLISHING.md).

### Compare controlled experiments

The M2 build also produces **artifacts/comparison.html**. It places two native runs side by side, with one physical-time clock and common-scale signal plots. Choose nominal load, heavier load, different controller settings, or weaker cooling independently on either side. Each side reuses the accepted Three.js viewer and maps the shared time to its own recorded samples.

See [the M2 experiment and acceptance scope](docs/M2_CONTROLLED_ARM.md). M2 is developed from the accepted M1 revision; its source preservation check enforces reuse of the original models, result reader, scene exporter, and renderer.

### Motion from the mechanics problems

The **Native Motion Lab** workflow runs `GrooveSlide3D` (Q31, PDF page 5) and `TwoSpringOscillator3D` (Q90, PDF page 13). Both use existing Modelica Standard Library bodies, constraints, forces, and visualizers. The purpose is to observe motion and explore composition.

The resulting **motion-lab-results** artifact includes `artifacts/motion-preview.html`, raw native MAT results, CSV exports, native animation XML, and verification reports. Open the HTML for offline 3D playback, time scrubbing, camera controls, object inspection, and synchronized signals. Spring coils are a generic rendering extension driven by native geometry; there is no browser physics solver.

See [the motion experiments and reproduction guide](docs/M4_MOTION.md). The original mechanics viewer, native CSV reader, and its frozen source baseline are preserved. The motion models also provide standard MultiBody animation data for OMEdit; a browser playback check is separate from an OMEdit GUI inspection.

### Coupled motion and a new spring composition

The **Native Coupled Motion Lab** workflow runs `MovingWedge3D` (the arrangement in Q106, PDF page 14) and `SpringWedge3D` (a separately authored variation). A freely translating support responds to the block's motion. In the second model, a spring fixed to that moving support returns the block uphill.

The **coupled-lab-results** artifact contains `artifacts/coupled-preview.html`, native results, independent momentum/energy/trajectory checks, and provenance. Both models reuse the accepted motion viewer and native scene exporters unchanged. See [the coupled-motion scope and reproduction guide](docs/M4B_COUPLED_MOTION.md).

### Rotation, translation and release

The **Native Composition Motion Lab** workflow adds `CartPendulumSpring3D` and `ReleasedSpringChain3D` (the arrangement in Q192, PDF page 26). Both assemble existing standard-library components. The cart and pendulum exchange motion while the wall spring acts; the released chain's center of mass falls while its internal springs oscillate.

The **composition-lab-results** artifact contains the single offline `artifacts/composition-preview.html`, native results, independent trajectory/force/energy checks and provenance. The existing native scene exporters and complete motion viewer remain unchanged. See [the composition scope and reproduction guide](docs/M4C_COMPOSITIONS.md).

### See forces and motion together

The **Native Observation Lab** workflow uses a shared experiment manifest to run
the cart–pendulum and released chain, then builds `artifacts/observation-lab.html`.
Choose a quantity and body, toggle individual arrows, inspect signed native
components and adjust a common physical display scale. Native connector values,
coordinate conversions and derived weight arrows are labeled separately.

The same observation modules serve both scenes. A Canvas XY projection keeps
recorded playback available when WebGL2 is unavailable. The workflow publishes
native results and a separate report from actual 3D/fallback browser checks.
See [the observation lab and manifest runner](docs/M5_OBSERVATION_LAB.md).

### Compile once and change numerical parameters

The **Compiled Parameter Lab** workflow builds the existing cart–pendulum–spring
assembly once. A separate runtime container without the Modelica compiler, MSL,
or C/C++ build tools runs three fresh parameter sets and produces
`artifacts/compiled-parameter-lab.html` with the existing motion and force viewer.
The experimental Linux package also accepts custom values for cart mass, bob
mass, spring stiffness and initial release angle before each new run.

The native solver remains OpenModelica-generated code. A small standard-library
MAT adapter removes the compiler dependency from result export. This is a
qualified fixed-assembly runtime, with a separate build step for new physical
arrangements. See [the package, commands and acceptance scope](docs/M5C_COMPILED_RUNS.md).

## Principles

- **Modelica defines physics and geometry.** Standard-library components supply the physical laws.
- **New arrangements are compositions.** Add models and connections without teaching the renderer a new mechanism.
- **Playback follows native results.** No replacement JavaScript dynamics or guessed dimensions.
- **Verification has a stated scope.** Component balances, native scene alignment, browser interaction, and actual OMEdit GUI inspection are distinct forms of evidence.
- **Outputs carry provenance.** Artifacts include native results, scene XML, source/result hashes, compiler details, and revision/run identifiers.

See [the experiments and reproduction guide](docs/EXPERIMENTS.md), [the native scene format](docs/NATIVE_SCENES.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
