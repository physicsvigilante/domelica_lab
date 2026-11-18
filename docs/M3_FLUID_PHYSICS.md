# M3 fluid model and acceptance contract

M3 qualifies two existing Modelica Standard Library fluid examples and adds a
reusable closed hydraulic network. Native OpenModelica results remain the source
of every displayed level, pressure, flow, controller state, and measurement.

## Stock qualifications

| Native model | Run | What is checked |
| --- | --- | --- |
| `Modelica.Fluid.Examples.PumpingSystem` | 2000 s, 0.4 s regular output | The original demand-valve event at 200 s, on/off pressure control, nonzero pump-speed floor, finite reservoir level, and sampled mass balance over the reservoir and the finite pump volume. |
| `Modelica.Fluid.Examples.Tanks.EmptyTanks` | 50 s, 0.05 s regular output | Initial water inventory, transfer between tanks, conservation of mass, and stopping at the upstream outlet 1 mm above the bottom. |

These models are simulated without modifying their component parameters. The
output interval and solver tolerance are chosen by `scripts/native_m3.mos`.
The stock empty-tank example deliberately retains a 1 mm film. A completely
empty `OpenTank` makes its energy equation singular; this is not a simulation of
a vessel drying to exactly zero water. The receiving tank's port is initially
above its liquid level, so the example also exercises native dry-port behavior.

The pumping example uses `StandardWaterOnePhase`. Its 50 m elevation difference,
20 kPa gauge-pressure reference, 4 kPa hysteresis band, speed dynamics, and pump
check valve are retained. Its mass check includes the finite pump volume as well
as the reservoir; the source and sink are boundaries of the checked system.

Primary source, MSL 4.1.0:

- [PumpingSystem.mo](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Examples/PumpingSystem.mo)
- [Tanks.mo, including EmptyTanks](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Examples/Tanks.mo)

## Authored composition

`TwoTankLoopPlant` contains two `OpenTank` components, a `PrescribedPump`, a supply
`StaticPipe`, a return `StaticPipe`, a `ValveLinear`, and two pressure sensors.
The composing example supplies pump speed and valve opening, and receives a
native tank-level measurement. The PI controller, anti-windup, actuator response,
and integration of shaft energy all use MSL blocks.

The plant exposes two fluid branch ports. They carry zero flow when unconnected.
`ControlledTankParallelReturn` connects an additional physical `StaticPipe`
between them. This changes the equation connectivity by composing another MSL
component; it does not replace the base plant or add browser-side fluid laws.

| Parameter | Value |
| --- | --- |
| Medium | `Modelica.Media.Water.ConstantPropertyLiquidWater` |
| Density | 995.586 kg/m³, constant |
| Tank cross-sectional area | 0.25 m² each |
| Tank height | 1.2 m each |
| Initial levels, nominal | A = 0.9 m; B = 0.5 m |
| Surface pressure | 101325 Pa |
| Initial fluid temperature | 293.15 K |
| Pump stored fluid volume | 0.001 m³ |
| Supply and main return pipes | Each 2 m long, 0.03 m diameter, zero elevation change |
| Valve nominal point | 2 kg/s at 5000 Pa with full opening |
| Pump nominal speed | 1200 rev/min |
| Pump nominal flow/head points | (0 m³/s, 10 m), (0.004 m³/s, 7 m), (0.008 m³/s, 0 m) |
| Pump modeled efficiency | 0.8, constant |
| PI gain and integral time | 3 and 30 s |
| Controller speed fraction bounds | 0.001 to 1.5 |
| Pump speed response | Native first-order block, 2 s time constant |
| New parallel return pipe | 4 m long, 0.016 m diameter, zero elevation change |

The simplified constant-property medium, ideal speed actuation, pump curve,
valve coefficient, and pipe dimensions are illustrative. They are not measured
specifications of a physical installation. `ValveLinear` is a deliberately
simple pressure-flow law supplied by MSL, not a detailed valve sizing model.

The pump uses `DomelicaLab.Functions.TwoTankPumpCurve`, a native Modelica
specialization of MSL `quadraticFlow` for the three fixed nominal points above.
For nominal volume flow `Q` in m³/s, its head in metres is:

| Nominal-flow region | Head expression |
| --- | --- |
| `Q < 0` | `10 - 250*Q` |
| `0 <= Q <= 0.008` | `10 - 250*Q - 125000*Q*Q` |
| `Q > 0.008` | `-2250*(Q - 0.008)` |

These are the original quadratic coefficients and MSL's original linear
extrapolation, including the endpoint slopes. The value expression is inlineable;
an explicit derivative function also supplies the same piecewise slopes.
Seven native initialization assertions compare it with MSL `quadraticFlow` at
`Q = {-0.002, 0, 0.002, 0.004, 0.006, 0.008, 0.010}` m³/s, including both
extrapolation regions, within 1e-10 m. The specialization preserves the pump law;
it exposes the flow dependence to the pinned compiler as described below.

Both tank bases have the same elevation. `use_portsData=false` places all tank
ports at zero height without inlet/outlet resistance. Consequently their
absolute pressure is the surface pressure plus `rho*g*level`. Separate pressure
sensor ports have zero mass flow. A drawn pipe route or tank placement in the
browser does not change these physical parameters.

## Four experiments

| ID | Model | Change |
| --- | --- | --- |
| `m3-nominal` | `ControlledTankLoop` | Nominal composition and controller |
| `m3-restricted` | `ControlledTankRestrictedValve` | Multiply the scheduled return-valve opening by 0.55 |
| `m3-initial` | `ControlledTankInitialLevels` | Exchange initial tank levels: A = 0.5 m, B = 0.9 m; preserve total water |
| `m3-parallel` | `ControlledTankParallelReturn` | Add the separate parallel return pipe |

Each simulation covers 300 s with a 0.1 s regular output interval and solver
tolerance 1e-10. Additional native event samples are preserved, including repeated
timestamps. The target is 0.8 m initially, 0.9 m at 100 s, and 0.78 m at 200 s.
The main return valve opening is 0.65 initially, 1 at 140 s, and 0.45 at 240 s,
multiplied by the case's `valveScale`.

### Selected native numerical configuration

The authored runs use DASSL, tolerance 1e-10, the explicit native curve above,
`StateSelect.always` on both tank levels and the first-order actuator output,
and OpenModelica's `-nls=hybrid` nonlinear solver option. The output interval is
0.1 s to resolve the initial shaft-power transient in independent sampled
quadrature. Stock examples retain their original component configuration and
their separately declared simulation settings.

Each of the four selectable authored examples explicitly saves this setup:

```modelica
annotation(
  experiment(StartTime=0, StopTime=300, Interval=0.1, Tolerance=1e-10),
  __OpenModelica_simulationFlags(s="dassl", nls="hybrid"));
```

The standard `experiment` annotation supplies the time range, output interval,
and tolerance; the OpenModelica-specific annotation supplies the integration
method and nonlinear solver. In OMEdit, use the C simulation target and inspect
Simulation Setup: General should show 0–300 s, interval 0.1 s (3000 intervals),
DASSL, and tolerance 1e-10; Simulation Flags should select the hybrid nonlinear
solver. Keep **Ignore __OpenModelica_simulationFlags annotation** unchecked.
OMEdit can retain model-specific session overrides, so inspect these fields
when reopening a model already simulated in that session.

The CLI acceptance path is `omc scripts/native_m3.mos`; that script passes the
same settings explicitly through `simulate(..., method="dassl", simflags="-nls=hybrid")`
and the numeric experiment arguments. The recorded evidence comes from scripted
native runs. An OMEdit GUI run has not been performed or claimed.
These annotations follow the official
[OpenModelica 1.27.1 OMEdit guide](https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/omedit.html#openmodelica-simulationflags-annotation)
and [C runtime flag reference](https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/simulationflags.html).

This configuration was selected after retaining and rejecting failed native
results. The first automatic-state trial at tolerance 1e-7 completed and met
the tracking criterion, but conserved mass drifted by up to approximately
0.0016 kg. Selecting physical states with the default nonlinear solver improved
conservation but produced event-iteration failures when the pump check valve
closed. Partial results from that trial were rejected. Returning to automatic
selection at 1e-10 completed, but still failed mass conservation and an added
independent actuator trajectory check.

The generated OpenModelica 1.27.1 equations explained why tightening tolerance
alone was insufficient: differentiation of the partially applied generic pump
curve omitted its flow-dependent contribution. In the automatic-state
configuration, this incorrect derivative fed the transformed integration
states. Physical-state selection with the hybrid nonlinear solver gave correct
primary trajectories, but still exported incorrect auxiliary derivatives.
The explicit one-input curve value exposes the polynomial and extrapolation
before differentiation. A wrapper that merely delegated the value to MSL and
supplied a derivative annotation did not correct this observed transformation.

The combined explicit-curve, physical-state, hybrid configuration completed the
300 s initial-high-B experiment in
[diagnostic run 44315234663, job 134839455353](https://github.com/physicsvigilante/domelica_lab/actions/runs/44315234663/job/134839455353).
It passed all original physical gates, all three tracking windows, the new exact
and integrated actuator checks, the seven native curve comparisons, and the
full pump-head derivative chain rule. The exact first-second actuator error was
at most 4.96e-10; the head-derivative residual was at most 2.45e-15 m/s across
1936 open-valve samples. The explicit curve with automatic selection did not
pass. This diagnostic qualifies the selected configuration for that experiment;
production acceptance additionally requires all four experiments and both stock
qualifications to pass the complete native CI run.

All original physical acceptance tolerances remain unchanged. Before printing
PASS, the native script invokes
`check_fluid_completion.py`, which requires the current run's native success log
marker, complete sample count, and actual final native time. The time check uses
the supported native batch result reader. Stale result files and logs are removed
before the run; the presence of a partially written MAT file is insufficient.

An attempted completion guard using stored `SimulationResult` record fields was
rejected by the OMC 1.27.1 script interpreter before the authored simulations
ran. The separate native-reader helper avoids that scripting limitation.

`supplyFlow` is positive from A through the pump to B. `returnFlow` and
`bypassFlow` are positive from B to A. These are signed mass flow rates in kg/s;
a negative value means actual native flow reversal. The nominal initial level
difference is intended to demonstrate reversal of the main return path.

## Acceptance contracts

The original physical limits below were declared before the first native run.
The additional temporal and derivative checks were declared before comparing
the diagnostic solver candidates. `scripts/verify_m3.py` checks these
independently specified contracts:

- All required native columns are finite, time is monotone, the regular sample
  grid is complete, and the requested final simulation time is reached.
- Initial conditions, intended case parameters, density, controller connections,
  reference events, and valve events match their declared values.
- Tank levels stay between 0.05 m and 1.15 m for the authored cases.
- Both tank inventories and the pump inventory sum to the constant initial mass,
  within 1e-5 kg. Individual tank mass derivatives equal the signed net flow at
  their four ports within 1e-7 kg/s.
- Native pressure connections, hydrostatic tank pressures, two-port flow signs,
  valve conductance, pump similarity curve, pump check-valve condition, and
  shaft-power relation satisfy their specified numerical tolerances.
- Native PI proportional/integral contributions, limits, anti-windup, and the
  first-order pump response agree with their component identities.
- Recorded speed-fraction change agrees with independent sampled integration of
  `(pumpFraction-filteredFraction)/2`, within 0.0001 plus 0.002 times its
  cumulative absolute integral. The initial-high-B case also agrees with the
  exact first-second response `0.001 + 0.299*exp(-t/2)` within 1e-6, after
  verifying its constant input and initial-state premises.
- When native pump-head and flow derivative columns are exported, the complete
  speed/flow chain rule holds within 1e-5 m/s on open-valve samples with
  `supplyFlow > 1e-5 kg/s`. Availability, sample count, and the maximum residual
  are recorded. Missing native derivative columns are reported explicitly.
- Absolute level error is at most **0.025 m throughout the final 20 s of each
  target hold**: 80–100 s, 180–200 s, and 280–300 s. The sample immediately after
  a new target event belongs to the new hold, not the preceding window.
- The added branch carries nonzero flow; the nominal main return path exercises
  both signs. Base cases retain zero branch flow.

The criteria are not relaxed to accommodate observed results. A failed criterion
requires investigating the model, numerical setup, or verifier and recording
the resulting correction.

[M3_TEMPORAL_ACCEPTANCE.md](M3_TEMPORAL_ACCEPTANCE.md) explains why pointwise
component identities also need independent checks of the recorded trajectories.

### What the energy check means

Both tanks and the finite pump volume store native fluid internal energy. The
static pipes and valve do not store energy or mass. In this closed, horizontal,
adiabatic network, the sum of the **modeled internal-energy derivatives** equals
native pump shaft power. The verifier checks that identity, and checks change
in stored internal energy against a native integral of shaft power.

This medium and tank configuration omit tank kinetic/potential energy from the
energy states. The check therefore establishes consistency of the modeled
internal-energy equations, not complete real-machine energy conservation.
`pumpEnergy` is signed shaft energy, not electrical consumption.

Independent trapezoidal quadrature uses the original native output samples.
Its authored-case energy tolerance is 0.05 J plus 0.002 times cumulative absolute
shaft work. Its transferred-mass tolerance is 0.05 kg plus 0.002 times cumulative
absolute net transfer. Repeated event timestamps contribute zero duration.
These sampled quadrature tolerances are distinct from algebraic residual gates.

Primary source for the modeled component equations:

- [Vessels.mo](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Vessels.mo)
- [Machines.mo](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Machines.mo)
- [Pipes.mo](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Pipes.mo)
- [Valves.mo](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Valves.mo)
- [Fluid/Interfaces.mo](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Fluid/Interfaces.mo)
- [ConstantPropertyLiquidWater](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Media/Water/package.mo)

## Evidence and visualization boundary

The verifier writes `artifacts/m3-metrics.json` only after all six cases pass.
Each result identifies its model, native MAT and CSV hashes, measurements, and
verification status; the report also records the verifier's own SHA-256 hash.
This binds displayed measurements to the checked native input files.

The fluid viewer is an engineering schematic driven by those native signals.
The layout is illustrative; it is not inferred 3D vessel or pipe geometry.
Flow direction, tank fill, pressure readings, valve opening, and pump speed must
come from the current recorded sample. Changing the selected case replays a
different completed simulation; it does not run OpenModelica in the browser.
