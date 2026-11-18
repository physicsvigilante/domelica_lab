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
| **Controlled fluid loop (M3)** | Native pump-speed PI control of two tanks, valve changes, reversed flow, and an added parallel return pipe; stock MSL fluid examples qualify the toolchain |

The armature is reusable Modelica code. `ThermalArmatureDrive` extends it by exposing the standard resistor's heat port; the original component is unchanged. The browser reads native geometry and transforms and has no physics solver or model-specific pendulum drawing.

## Open the results

From a successful [Native Modelica Lab workflow run](https://github.com/physicsvigilante/domelica_lab/actions/workflows/native-modelica.yml), download **modelica-lab-results**, extract the ZIP, and open **artifacts/browser-preview.html**. The file works offline, without OpenModelica or a web server.

Choose a scene, play or scrub time, drag to orbit, switch to XY, and click a visible object to inspect its transform. Three.js renders the native geometry with lighting, a depth buffer, and surface picking. It is bundled inside the HTML; viewing requires a browser with WebGL2, with no installation or network connection. The **modelica-browser-checks** artifact contains the browser test report and screenshots for that same HTML file.

M1 and M2 have been reviewed and merged into `main`. Check the run attached to the exact revision before treating a result as verified.

The **Publish Verified Lab** workflow can publish the selected, verified viewers directly to GitHub Pages. Its release manifest binds the source revision, successful native/browser run, and exact HTML hashes; it does not publish arbitrary latest artifacts. See [publishing setup and release selection](docs/PUBLISHING.md).

### Compare controlled experiments

The M2 build also produces **artifacts/comparison.html**. It places two native runs side by side, with one physical-time clock and common-scale signal plots. Choose nominal load, heavier load, different controller settings, or weaker cooling independently on either side. Each side reuses the accepted Three.js viewer and maps the shared time to its own recorded samples.

See [the M2 experiment and acceptance scope](docs/M2_CONTROLLED_ARM.md). M2 is developed from the accepted M1 revision; its source preservation check enforces reuse of the original models, result reader, scene exporter, and renderer.

### Explore fluid networks

M3 produces **artifacts/fluid-preview.html**, an offline engineering schematic driven by native tank levels, signed mass flows, absolute pressures, pump speed, and valve opening. Four authored cases compare nominal circulation, a restricted valve, changed initial levels, and a real parallel return branch. Two unchanged MSL examples, `PumpingSystem` and `Tanks.EmptyTanks`, qualify the fluid toolchain separately.

Schematic layout is authored presentation data, not solver-defined spatial geometry. Native Modelica equations supply every displayed physical value. See [the M3 experiment and acceptance scope](docs/M3_FLUID_SYSTEMS.md).

## Principles

- **Modelica defines physics.** Standard-library components supply the physical laws. Mechanical scenes use native geometry; fluid schematics explicitly label their authored layout.
- **New arrangements are compositions.** Add models and connections without teaching the renderer a new mechanism.
- **Playback follows native results.** No replacement JavaScript dynamics or guessed dimensions.
- **Verification has a stated scope.** Component balances, native scene alignment, browser interaction, and actual OMEdit GUI inspection are distinct forms of evidence.
- **Outputs carry provenance.** Artifacts include native results, scene XML, source/result hashes, compiler details, and revision/run identifiers.

See [the experiments and reproduction guide](docs/EXPERIMENTS.md), [the native scene format](docs/NATIVE_SCENES.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
