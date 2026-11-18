# Domelica Lab

A **Modelica-first multiphysics laboratory** for composing physical systems, running native simulations, and exploring their geometry and signals in an offline browser viewer.

## What is here

| Experiment | What it explores |
| --- | --- |
| **ThermalGearedArm3D** | A motor, 5:1 gearbox, two perpendicular joint axes, passive elbow, winding heat capacity, cooling, and resistance that changes with temperature |
| **MotorizedPendulum3D** | Electrical armature dynamics coupled to a gravitational rigid body and rotational damper |
| **HeatedBody** | A thermal network checked against an independent analytical solution |
| **MSL DoublePendulum** | An unchanged standard-library example using the same native scene pipeline |

The armature is reusable Modelica code. `ThermalArmatureDrive` extends it by exposing the standard resistor's heat port; the original component is unchanged. The browser reads native geometry and transforms and has no physics solver or model-specific pendulum drawing.

## Open the results

From a successful [Native Modelica Lab workflow run](https://github.com/physicsvigilante/domelica_lab/actions/workflows/native-modelica.yml), download **modelica-lab-results**, extract the ZIP, and open **artifacts/browser-preview.html**. The file works offline, without OpenModelica or a web server.

Choose a scene, play or scrub time, drag to orbit, switch to XY, and click a visible object to inspect its transform. Three.js renders the native geometry with lighting, a depth buffer, and surface picking. It is bundled inside the HTML; viewing requires a browser with WebGL2, with no installation or network connection. The **modelica-browser-checks** artifact contains the browser test report and screenshots for that same HTML file.

Development is proposed in [draft PR #1](https://github.com/physicsvigilante/domelica_lab/pull/1). Check the run attached to the exact revision before treating a result as verified.

## Principles

- **Modelica defines physics and geometry.** Standard-library components supply the physical laws.
- **New arrangements are compositions.** Add models and connections without teaching the renderer a new mechanism.
- **Playback follows native results.** No replacement JavaScript dynamics or guessed dimensions.
- **Verification has a stated scope.** Component balances, native scene alignment, browser interaction, and actual OMEdit GUI inspection are distinct forms of evidence.
- **Outputs carry provenance.** Artifacts include native results, scene XML, source/result hashes, compiler details, and revision/run identifiers.

See [the experiments and reproduction guide](docs/EXPERIMENTS.md), [the native scene format](docs/NATIVE_SCENES.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
