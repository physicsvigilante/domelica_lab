# M3 — Fluid networks and native level control

## Purpose

Explore Modelica.Fluid through unchanged library examples and a new reusable hydraulic composition. M3 adds fluid experiments while retaining the accepted electromechanical models, native result reader, scene exporter, and Three.js renderer.

The baseline is the accepted M2 source tree `19481574234fa6ae771ea95d600539db120e7ffd`, merged into `main` as `dacdfab933826ac0aae6741a9e3118fc6efe8346`. The subsequent publication change copies verified M2 artifacts without changing physics.

## Native models

| Experiment | Model | Purpose |
| --- | --- | --- |
| Stock pumping | `Modelica.Fluid.Examples.PumpingSystem` | Qualify the unchanged MSL demand event and pressure-based on/off pump control over 2000 s |
| Stock empty tanks | `Modelica.Fluid.Examples.Tanks.EmptyTanks` | Qualify gravity-driven transfer and the dry outlet event over 50 s |
| Nominal circulation | `DomelicaLab.Examples.ControlledTankLoop` | PI control of tank B level in a closed two-tank circulation loop |
| Restricted valve | `ControlledTankRestrictedValve` | Scale the native return-valve opening to 55% of the nominal schedule |
| Changed starting levels | `ControlledTankInitialLevels` | Swap initial tank A/B levels while retaining the same water inventory and controller |
| Parallel return | `ControlledTankParallelReturn` | Connect an additional native pipe between the plant's exposed branch ports |

The authored reusable plant is `Components.TwoTankLoopPlant`. It composes two native `OpenTank` components, a `PrescribedPump`, two `StaticPipe` components, `ValveLinear`, and pressure sensors. A native MSL `LimPID` configured as PI controls pump speed through a two-second `FirstOrder` response. Modelica connections supply all fluid and control interactions. Native integration blocks record pump shaft work and tank B mass transfer.

The parallel case adds an actual `StaticPipe` instance and connections; it is not merely a visual change. Schematic topology is declared separately as node/edge data so that the renderer can display either arrangement without implementing hydraulic equations.

## Authored experiment

Each authored run lasts 300 s with a regular 0.1 s output interval, native event samples, automatic native state selection, and solver tolerance 1e-10. Both tank bases share an elevation; each has 0.25 m² cross-sectional area and 1.2 m height. Nominal initial levels are 0.9 m in A and 0.5 m in B. The pump has 0.001 m³ storage, an illustrative quadratic head curve, and constant 80% efficiency. The water medium is MSL `ConstantPropertyLiquidWater`.

The tank B target is 0.8 m for 0–100 s, 0.9 m for 100–200 s, and 0.78 m for 200–300 s. The nominal return-valve opening is 0.65 until 140 s, 1 until 240 s, then 0.45. Changes in opening act on the Modelica valve.

Pump output is limited to a nonzero minimum and a maximum corresponding to 1800 rpm. The pump's native check valve prevents reverse pump flow. The passive return pipe can reverse: the nominal initial water levels drive flow opposite to the declared B→A return orientation before the pump raises tank B.

## Acceptance declared before execution

`scripts/verify_m3.py` checks finite, complete native timeseries; initial conditions; parameters; reference and valve event sides; actual connections; controller identities and anti-windup; the pump characteristic; storage; and native integrations.

| Authored-network check | Acceptance |
| --- | --- |
| Total modeled mass drift | ≤1e-5 kg, including both tanks and the pump |
| Each tank's differential mass balance | ≤1e-7 kg/s |
| Tank hydrostatic and connection pressures | ≤1e-5 Pa |
| Modeled internal-energy derivative minus shaft power | ≤1e-4 W |
| Independent sampled shaft-work quadrature | ≤0.05 J + 0.002 × cumulative absolute work |
| Independent sampled tank transfer quadrature | ≤0.05 kg + 0.002 × cumulative absolute transfer |
| Target tracking | Absolute level error ≤0.025 m throughout the final 20 s of each 100 s target hold |
| Wet/nonoverflow operation | Both levels strictly between 0.05 and 1.15 m |
| Native reversal/topology behavior | Nominal main return flow has both signs; the new parallel branch carries meaningful nonzero flow |

The stock examples have separate declared checks appropriate to their own boundary conditions. Pumping checks include both controller states, the demand-valve event, a broad regulated-pressure envelope, and integrated open-system mass balance. Empty-tank checks include the complete two-tank water inventory, integrated transfer, and stopped outlet flow.

Failed criteria remain failures until the cause is resolved or the unsuccessful outcome is explicitly documented. Final measurements and execution verdicts belong to the CI artifact and pull request for the exact source revision.

The native run script calls `scripts/check_fluid_completion.py` after each simulation. It requires the current native log's simulation-success marker and checks original sample count and time coverage through OpenModelica's native reader before printing a completion message. A partial MAT file is retained as failure evidence, never treated as a successful run. The numerical trials and their observed failures are documented in [M3_FLUID_PHYSICS.md](M3_FLUID_PHYSICS.md).

## Visualization and evidence

`scripts/export_fluid_csv.py` uses OpenModelica's native `filterSimulationResults` with `numberOfIntervals=0` for dynamic variables, including compiler-generated names that are not valid Modelica source references. The filter's CSV path cannot export parameters, so the adapter obtains those through the accepted native `readSimulationResult` helper. It checks exact column coverage, native row count, row-by-row time binding, and representative public signals through both native reader paths. It preserves original native timestamps and all repeated event samples. Dynamic CSV values have 15 significant digits; raw MAT remains the primary full-precision result. No custom MAT parser or replacement solver is used. The M1/M2 exporter remains unchanged.

`scripts/build_fluid_preview.py` binds the verified native CSV/MAT results and metrics to `viewer/fluid-experiments.json` and `viewer/fluid.template.html`.

- Tank fill is native level divided by native tank height.
- Flow arrows use signed native mass flow and a declared edge orientation.
- Pressure readouts are absolute pressure; free surfaces are at 101325 Pa in these authored runs.
- Pump speed, valve opening, plot curves, and time readouts follow recorded native samples.
- Diagram coordinates are authored engineering-schematic layout, not Modelica spatial geometry.
- Scenario selection replays a completed run; it does not rerun OpenModelica.

The build emits `artifacts/fluid-preview.html`, `fluid-scenes.json`, `fluid-provenance.json`, and `m3-metrics.json`. The HTML is self-contained and requires no graphics library or WebGL. Browser checks exercise actual tank fill, signed arrows, changed topology, controls, native sample selection, desktop/mobile layout, and offline operation. Native input, verifier, builder, template, and scenario identities accompany the output.

## Scope and limitations

The stock `EmptyTanks` example retains a 1 mm film at the outlet to avoid the singularity of completely empty vessels. Its name must not be interpreted as zero remaining water.

The authored plant uses an incompressible constant-property medium, static pipe pressure losses, and lossless tank-port connections (`use_portsData=false`). The mass inventory includes all storage. The reported energy check concerns **modeled fluid internal energy**; simplified tank-port kinetic/potential energy and pressure-volume-work treatment prevent interpreting it as a complete real-installation energy validation.

This milestone does not model water hammer, cavitation, pipe elasticity, detailed CFD, real pump electrical losses, or a calibrated installation. Results establish consistency of this native composition and result visualization. They do not experimentally validate a machine. Actual OMEdit GUI inspection remains separate.

## Reproduce

After the existing native baseline steps, run:

```sh
omc scripts/native_m3.mos
python3 scripts/export_fluid_csv.py m3_msl_pumping m3_msl_empty m3_tanks_nominal m3_tanks_restricted m3_tanks_initial m3_tanks_parallel
python3 scripts/verify_m3.py
python3 scripts/build_fluid_preview.py
node scripts/check_fluid.cjs artifacts/fluid-preview.html
```

The complete GitHub workflow installs the requested MSL version and also verifies the original eight native models and both existing viewers. Publication is an explicit separate selection of a successful native/browser run, described in [PUBLISHING.md](PUBLISHING.md).

Primary component definitions: [MSL PumpingSystem](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Examples/PumpingSystem.mo), [Tanks](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Examples/Tanks.mo), and [Vessels](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Vessels.mo).
