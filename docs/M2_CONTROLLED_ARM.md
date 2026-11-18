# M2: native feedback control and experiment comparison

## Baseline and purpose

M2 starts from M1 revision `fa349241b57cd8fa355da4ee8426a81493e2e68a`, verified by [run 44286228183](https://github.com/physicsvigilante/domelica_lab/actions/runs/44286228183). A bounded independent review accepted the native-result and offline-browser scope. Actual OMEdit GUI animation remains uninspected; that separate item is not a prerequisite for native simulation and browser comparison.

`docs/m1-baseline.json` records immutable source hashes. `scripts/check_m1_baseline.py` requires the original models, native MAT reader, scene exporter, Three.js viewer, and pinned renderer dependencies to remain unchanged. M2 adds Modelica composition and a generic comparison wrapper.

The physical question is how shoulder-position feedback responds to a different mechanical load, different controller settings, and weaker cooling. This is an illustrative simulated machine, with an ideal motor and lossless gearbox. Its parameters are not identified from a physical robot.

## Composed system

`Components.ControlledArmPlant3D` combines standard-library rigid bodies, perpendicular revolute joints, a gearbox, dampers, thermal storage/cooling, and the existing `ThermalArmatureDrive`. A voltage input drives the plant, and a measured shoulder angle closes the feedback loop in `Examples.ControlledThermalArm3D`.

The controller is the standard-library `Modelica.Blocks.Continuous.LimPID`, configured as PID with a symmetric voltage limit, anti-windup compensation, and derivative action on the measurement. The passive elbow has no position controller. Mechanical motion, armature current, temperature feedback, and controller state evolution are all simulated natively by OpenModelica.

The initial shoulder angle is 0.25 rad. The requested angle changes at 1 s to 1.0 rad, at 10 s to −0.35 rad, and at 20 s to 0.65 rad. Each experiment runs for 30 s with 0.02 s regular output intervals, retaining additional native event samples. The derivative state is initialized consistently with the initial measurement, avoiding a derivative kick caused solely by inconsistent initialization. Starting at rest does not imply static mechanical equilibrium.

## Four isolated comparisons

| Scenario | Forearm density | PID gain | Integral time | Derivative time | Cooling conductance |
| --- | --- | --- | --- | --- | --- |
| Nominal | 850 kg/m³ | 18 | 1.2 s | 0.12 s | 0.4 W/K |
| Heavier load | 1700 kg/m³ | 18 | 1.2 s | 0.12 s | 0.4 W/K |
| Heavier load, retuned | 1700 kg/m³ | 30 | 1.2 s | 0.22 s | 0.4 W/K |
| Retuned, weaker cooling | 1700 kg/m³ | 30 | 1.2 s | 0.22 s | 0.08 W/K |

Each uses the same geometry, reference, initial conditions, 5:1 gearbox, and ±12 V motor-voltage limit. Density changes the forearm mass and inertia without changing its shape. “Retuned” denotes different illustrative settings; whether a metric improves is established by the results, not assumed in the label. This is a coupled spatial mechanism, so a heavier load need not worsen every metric.

## Native evidence and metrics

`scripts/verify_m2.py` checks the intended experiment parameters and reference, feedback wiring, output limits, armature voltage and power relations, temperature-dependent resistance, copper loss, winding heat balance, ideal gearbox constraints, and physical link geometry. Native energy outputs are compared with independent numerical integration of recorded power. Numerical integration tolerances account for finite output sampling; event timestamps are not removed from the primary results.

The script writes `artifacts/m2-metrics.json`, including metric definitions, units, scenario parameters, and native input hashes. Metrics describe tracking error, limit exposure, electrical energy, heating, temperature, and settling behavior. Electrical energy is signed: the ideal voltage source can absorb returned energy during braking. Copper heating energy is nonnegative. Settling is evaluated within the finite recorded hold windows, with unresolved cases reported explicitly.

Component and interface checks are distinct from an independent solution of the complete spatial dynamics or experimental validation against a physical machine.

## Comparison viewer

`scripts/build_preview.py` continues to build the single-view offline player and exports `artifacts/native-scenes.json`. `scripts/build_comparison.py` uses that native payload, the metrics, and `viewer/comparisons.json` to assemble `artifacts/comparison.html`.

The comparison HTML embeds two instances of the unchanged native viewer. The parent owns one physical-time clock. Each side selects its last recorded native sample at or before that time; different event grids never imply that equal sample indices correspond to equal physical times. No interpolation, dynamics, controller equations, or joint kinematics are recreated in the browser. Displayed physical values come from each selected sample; summary statistics retain their documented definitions.

Scene selectors, synchronized playback, common-scale plots, and result cards support direct comparison. Each view retains its native object inspector and camera controls. The file includes its renderer and data and works offline in a WebGL2-capable browser.

## Reproduce

Use the pinned OpenModelica CI environment, Python 3, and Node.js 22 or later. From the repository root:

```sh
python3 scripts/check_m1_baseline.py
omc scripts/install_msl.mos
omc scripts/native_smoke.mos
omc scripts/native_m2.mos
python3 scripts/export_native_csv.py m0_motorized_pendulum m0_thermal_step m0_msl_double_pendulum m1_thermal_geared_arm m2_controlled_nominal m2_controlled_heavy m2_controlled_retuned m2_controlled_cooling
python3 scripts/verify_csv.py
python3 scripts/verify_m2.py
python3 scripts/test_native_scene.py --native
npm ci --ignore-scripts --no-audit --no-fund
npm run build:runtime
python3 scripts/build_preview.py
python3 scripts/build_comparison.py
npx playwright install --with-deps chromium
node scripts/check_viewer.cjs artifacts/browser-preview.html
node scripts/check_comparison.cjs artifacts/comparison.html
```

## Acceptance scope

M2 requires native success for the four baseline and four controlled experiments, the numerical and native-scene checks, and actual browser checks for both viewer files. The comparison checks cover independent scene selection, shared physical time, native signal values, playback transitions, and responsive layout. Reports and screenshots are tied to the generated HTML hashes. CI uses software WebGL2; it does not establish hardware GPU performance.

Adding these controlled arrangements must not require changes to the physics solver, scene geometry exporter, or single-view renderer. A new primitive type or physical law would be a separately reviewed reusable library extension. A new arrangement made from supported components is a Modelica authoring and experiment-registration task.

## References

- [MSL 4.1.0 continuous blocks, including LimPID](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Blocks/Continuous.mo)
- [Modelica Standard Library 4.1.0 source](https://github.com/modelica/ModelicaStandardLibrary/tree/v4.1.0)
- [Native scene contract](NATIVE_SCENES.md)
