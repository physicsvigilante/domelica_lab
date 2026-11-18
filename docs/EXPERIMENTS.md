# M0 — Reproducible Modelica capability exploration

## Purpose
Establish evidence for a physical modeling and visualization laboratory, not an independent solver.

| Experiment | Model | Composition/feature | Verification | Visualization |
| --- | --- | --- | --- | --- |
| M0-A | Modelica.Mechanics.MultiBody.Examples.Elementary.DoublePendulum | Untouched MSL baseline, joints and bodies | Native simulation produces finite time series | Native 3D animation in OMEdit |
| M0-B | DomelicaLab.Examples.MotorizedPendulum3D | New composition: voltage source, RL armature, EMF, bearing, damper, 3D hinged body, gravity | Native simulation; finite motor current and genuine movement | Native 3D animation in OMEdit, synchronized variable plots |
| M0-C | DomelicaLab.Examples.HeatedBody | New composition: driven heater, heat capacity, conductor, fixed ambient | Native simulation; independent exponential heat-balance oracle | Temperature and heat-flow plots |

## Reproduce without Codex

From a terminal at the repository root with OpenModelica installed:

1. Run `omc scripts/install_msl.mos` to make MSL 4.1.0 available.
2. Run `omc scripts/native_smoke.mos` to generate CSV files.
3. Run `python3 scripts/verify_csv.py` to verify physical outcomes.
4. In OMEdit, open `DomelicaLab/package.mo`, select `DomelicaLab.Examples.MotorizedPendulum3D`, then choose **Simulate with Animation**.
5. Plot `angle`, `angularVelocity`, and `motorCurrent`. View the 3D motion and compare to the electrical response at t=0.5 s. Repeat for the MSL DoublePendulum.
6. For `HeatedBody`, plot `temperature` and compare against the analytical response in the model documentation.

GitHub Actions uses OpenModelica's published v1.27.1 Docker image; the image does not bundle MSL, so the workflow prepares MSL 4.1.0 separately. This workflow supplies **native solver evidence**, not evidence that the GUI has been visually inspected.

## Acceptance gates

- **Static:** Correct Modelica package structure, script arguments, reproducible versions.
- **Native:** Modelica loads, each model compiles and simulates, result files exist, and Python verifies numerical behavior.
- **Visual:** A human inspects OMEdit 3D animation and plots. This gate is **not yet passed**.
- **Composability:** Alter the model topology using existing components (for example replace a passive arm with two linked bodies) without changing engine code. This gate is **not yet passed**.

No initial benchmark or generated simulation file should be called accepted until native CI finishes successfully. Do not regenerate or overwrite verified evidence during later experiments.

## Standalone browser preview

After the CI native and numeric checks pass, the workflow builds an **offline** file named `browser-preview.html` from the actual native pendulum and thermal CSV files. Download the `modelica-m0-results` artifact from the passing GitHub Actions run and open the HTML file in a browser: no Modelica installation, local web server or JavaScript dependencies are required.

The viewer has playback, scrubbing, speed control, live angle/current readouts, electrical and mechanical plots, and the independent thermal trace. Its arm shape is a *specific, guarded XY projection* of the authored 3D model, not an automatically extracted general 3D scene. Full OMEdit animation is a separate visual acceptance gate.
