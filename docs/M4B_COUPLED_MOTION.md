# M4B: coupled motion on a moving wedge

This milestone explores Q106 on PDF page 14 and a separately authored spring variation. The goal is to see two interacting bodies move, using existing Modelica Standard Library components and the accepted native-result viewer.

## Experiments

| Model | Arrangement | Illustrative nominal recording |
| --- | --- | --- |
| `MovingWedge3D` | A block slides downhill on a support that can translate freely on horizontal ground | 2 kg support, 1 kg block, 30° incline, gravity 10 m/s²; released from rest for 1 s |
| `SpringWedge3D` | The same moving support and block, with a spring between a support-mounted anchor and the block | Same masses and inclination, 10 N/m initially unstretched spring; released from rest for 6 s |

Q106 supplies a symbolic arrangement, not numerical dimensions, masses, gravity, or initial conditions. The nominal values are choices made for these motion demonstrations. The spring arrangement is a new composition, not a claim about an additional feature in Q106.

The ideal wedge is drawn as a rigid inclined deck, two uprights, and a translating base. These are standard native box primitives. One `BodyBox` supplies the entire support mass; the deck and uprights are massless visualizers. The support cannot rotate, so this mass placement does not affect its translational dynamics. The block is a second `BodyBox`.

## Why both bodies move

A horizontal `Prismatic` connects the support to the world. A second `Prismatic`, attached to the support, constrains the block along the inclined deck. World gravity acts on both bodies. Modelica solves the connected system; neither body's trajectory is prescribed.

The spring variation extends the base model and adds two ordinary `FixedTranslation` attachments and one `MultiBody.Forces.Spring`. Its upper endpoint belongs to the moving support, and its lower endpoint belongs to the block. This makes the spring force internal to the combined system. The spring can return the block uphill while the support returns horizontally.

New measurement aliases and analytical verification formulas inspect the result. They do not supply physical equations to the simulation.

## Reuse and verification

The models, native MAT reader, scene exporters, Three.js runtime, spring graphics, and motion viewer from the accepted baseline remain unchanged. `docs/m4b-reused-sources.json` records 34 reused source hashes, including the existing M1 baseline. The only shared package change is registering the two new example classes.

Verification compares every original native sample with an independent analytical trajectory. It also checks each body's position, velocity and acceleration; relative geometry; Newton's force balances; horizontal momentum and horizontal center of mass; total energy; and positive support reactions. The spring case additionally checks both spring endpoints, force, extension, and elastic energy. Completion proofs reject partial native runs and bind the exact MAT, log, and scene XML files. Viewer builds reject stale or incomplete physics evidence.

Browser checks then inspect the live geometry of both moving bodies, spring attachments, playback controls, object selection, and desktop/mobile framing. They bind the delivered HTML hash and report unexpected requests and browser errors separately from native numerical verification. These checks do not establish real-world experimental accuracy.

## Reproduce

Use the **Native Coupled Motion Lab** GitHub Actions workflow in `.github/workflows/coupled-modelica.yml`. The compiler container is OpenModelica 1.27.1 pinned by digest. The requested MSL version is 4.1.0; its installed maintenance version and source path are recorded in `m4b-native-toolchain.txt`.

With that toolchain, run from the repository root:

```sh
python3 scripts/check_m4b_reuse.py
omc scripts/install_msl.mos
omc scripts/native_m4b.mos
python3 scripts/export_native_csv.py m4b_moving_wedge m4b_spring_wedge
python3 scripts/verify_m4b.py
npm ci --ignore-scripts --no-audit --no-fund
npm run build:runtime
python3 scripts/build_coupled_preview.py
node scripts/check_coupled.cjs artifacts/coupled-preview.html
```

The final browser command requires the pinned Playwright browser, installed by the workflow. Download `coupled-lab-results` to obtain the native outputs, metrics, provenance, and self-contained `artifacts/coupled-preview.html`. The `coupled-browser-checks` artifact contains the browser report and screenshots. Read the actual workflow conclusion before treating a particular build as verified.

The HTML works offline in a browser with WebGL2. It replays recorded samples; changing mass, angle, stiffness, or initial conditions requires another native run. The same physical timestamp controls all body transforms and signal readouts.

## Physical limits

- Both joints impose ideal bilateral constraints. Positive reaction checks show that the nominal recordings are compatible with compressive contact, but no contact detection, separation, friction, or impact law is implemented.
- The finite deck has footprint guards. The free-slide recording ends before the block leaves the deck; this does not stop its physical velocity.
- The spring is ideal, massless, linear, and undamped. There is no wire contact, buckling, damping, or anchor collision.
- The support is constrained against rotation; tipping is outside this model.
- Native OMEdit GUI animation has not been inspected. The delivered interactive viewer uses native simulation data and exported geometry.

This is evidence for these two compositions within the stated domain. It does not establish that every mechanics arrangement can be modeled without extending physical libraries. The earlier fluid and compiler-diagnostic work remains separate.

See [physical definitions and independent checks](M4B_PHYSICS.md), [the separately authored spring composition](M4B_COMPOSITION.md), and [viewer verification](M4B_VIEWER.md).
