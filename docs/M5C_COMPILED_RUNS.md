# M5C — Compile once, simulate many

M5C keeps the cart–pendulum–spring Modelica assembly and the M5 geometry,
observation and rendering modules unchanged. OpenModelica builds one native
executable. Four numerical parameters can then be supplied before each new run:

| Parameter | Unit | Meaning |
| --- | --- | --- |
| `cartMass` | kg | Physical cart mass, implemented through its density |
| `bobMass` | kg | Point-mass pendulum bob |
| `springStiffness` | N/m | Wall spring stiffness |
| `initialAngle` | rad | Initial release angle from downward |

The first three must be positive and finite. The release angle must be strictly
between −π/2 and π/2. The existing model also checks spring length, rail span,
floor clearance and the exclusion of cart–bob collision. Those checks can reject
a run even when its input numbers are valid. This is not qualification of every
possible combination in that numerical domain.

The generated initialization XML must mark the four parameters as changeable.
Every result is checked for the actual requested values and their propagation
to cart density, mass and inertia, bob mass, spring stiffness and the initial
hinge angle/bob pose. Geometry parameters and changes to connections or component
counts are outside this first compiled-assembly contract.

## What recipients need

The experimental package contains the Linux x86-64 executable, initialization
and visual XML, generated runtime data (including Jacobian sparsity files),
its required shared libraries and matching ELF loader, small
Python scripts, the observation declarations and the already bundled viewer.
It includes this project's Modelica sources for provenance; it does not include
the Modelica Standard Library or a Modelica/C/C++ development toolchain.

Recipients need a compatible Linux x86-64 environment and Python 3.10 or later.
The qualified CI runtime is the `python:3.12-slim-bookworm` container. The binary
is launched with the bundled loader and library directory, rather than assuming
the host provides the compiler's shared-library versions. This does not yet
provide a Windows/macOS build, a desktop installer, a web service or a browser
WebAssembly solver.

The native MAT adapter uses Python's standard library. It reads the fresh
parameter and trajectory values, resolves signed aliases and preserves all
original timestamps. It does not evaluate Modelica expressions or compute
motion. Missing parameters are never filled from old initialization defaults.
The original `export_native_csv.py` remains unchanged for existing workflows.

## Authoring/build step

This step requires the pinned OpenModelica toolchain, MSL and Node/npm to bundle
the viewer. It builds the physical model once and performs no native simulation:

```bash
omc scripts/install_msl.mos
npm ci --ignore-scripts --no-audit --no-fund
npm run build:runtime
python3 scripts/compiled_model.py build \
  --manifest viewer/compiled-experiments.json --bundle compiled-model
tar -czf compiled-model-linux-x86_64.tar.gz compiled-model
```

Use a new, empty bundle directory. The build report records the compiler,
source identity, changeability metadata, executable/XML/library hashes and
runtime notices. The tar archive preserves executable permissions.

## Run fresh simulations without a compiler

After extracting the package, run the three declared examples:

```bash
python3 compiled-model/scripts/compiled_model.py presets \
  --bundle compiled-model --output-dir observation-run
python3 compiled-model/scripts/build_observation_lab.py \
  --manifest observation-run/experiments.json --results-dir observation-run \
  --output artifacts/compiled-parameter-lab.html
```

| Example | Cart mass | Bob mass | Stiffness | Release |
| --- | ---: | ---: | ---: | ---: |
| Original parameters | 2 kg | 1 kg | 20 N/m | 35° |
| Heavier cart | 4 kg | 1 kg | 20 N/m | 35° |
| Stiffer spring, changed bob and release | 2 kg | 1.25 kg | 40 N/m | 25° |

The third example changes three inputs together. It demonstrates those runtime
inputs; it is not a controlled comparison attributing the motion to stiffness
alone. The viewer labels each recording from its actual native parameters.

The runtime also accepts numerical choices beyond these presets. For example:

```bash
python3 compiled-model/scripts/compiled_model.py run \
  --bundle compiled-model --output-dir custom-run --id custom \
  --set cartMass=3.5 --set bobMass=1.1 --set springStiffness=32 \
  --set initialAngle=0.5235987755982988
python3 compiled-model/scripts/build_observation_lab.py \
  --manifest custom-run/experiments.json --results-dir custom-run \
  --output artifacts/custom-run.html
```

This command illustrates the interface, not an additional accepted recording.
Omitted public parameters use their declared defaults. Unknown names, duplicate
overrides, nonfinite numbers and invalid domains are rejected before execution.
Each invocation requires a fresh output directory to prevent stale-result reuse.

The command uses OpenModelica's native `-overrideFile` before initialization and
reruns the same executable. It does not change parameters during a running
simulation. The resulting HTML replays the newly computed data; opening it does
not run a solver. Arbitrary user input in a browser requires a connection to this
runtime, which is a later application integration step.

## Focused acceptance

The **Compiled Parameter Lab** workflow separates four concerns:

1. **Build once:** the authoring container runs `buildModel()` and packages one
   executable. No Modelica physics or renderer changes are required.
2. **Run without the compiler:** a separate Python-only container has no `omc`,
   GCC, Clang or make on its path and installs no MSL. It runs all three examples,
   checks parameter propagation and native completion, confirms the executable
   and package hashes remain unchanged, and builds the HTML with no Node/npm.
3. **Check the result adapter:** a subsequent, separate job reads one saved MAT
   result with the established OpenModelica reader and compares the complete
   serialized values. It does not compile or simulate another model.
4. **Check playback:** the existing browser checker exercises every recording's
   native geometry, vectors, units, filters, playback, mobile layout and XY
   fallback. Its screenshot names now follow recording IDs.

The artifacts are `compiled-model-linux-x86_64`, `compiled-parameter-results`,
`compiled-data-checks` and `compiled-browser-checks`. Check the workflow on the
reviewed revision for the actual outcome. The HTML/build report and runtime
report bind each recording to its native files and the shared executable.

No independent trajectory/energy comparison or large parameter sweep is added.
The unchanged ideal-model assumptions apply. The three successful examples, if
accepted by CI, establish this bounded path; they do not prove arbitrary model
topologies, all parameter values or hard real-time execution.

## Native interfaces used

- [OpenModelica 1.27.1 `buildModel`](https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/scripting_api.html#buildmodel)
- [Native override and result flags](https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/simulationflags.html)
- [Native MAT result layout](https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/doc/UsersGuide/source/technical_details.rst)
- [Shared M5 observation mapping](OBSERVATION_MAPPING.md)
