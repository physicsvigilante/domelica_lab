# M4: Visible motion from existing Modelica components

This milestone turns two mechanics arrangements into moving, inspectable models. Its purpose is to observe their dynamics and demonstrate composition with the Modelica Standard Library (MSL). There is no optimization or multiple-choice answer workflow.

## The two arrangements

| Model | Source | What moves | Physical components |
| --- | --- | --- | --- |
| `DomelicaLab.Examples.GrooveSlide3D` | Q31, `01_mechanics.pdf`, PDF page 5 | A block released from rest in a diagonal groove on an inclined plane | MSL World, Prismatic joint, rigid body, and native visualizers |
| `DomelicaLab.Examples.TwoSpringOscillator3D` | Q90, PDF page 13 | A 4 kg block between a ceiling spring and a floor spring | MSL World, Prismatic joint, rigid body, two MultiBody Spring components, and native visualizers |

The source figures were visually inspected. Q90 has one spring above and one below the block, each attached to a fixed support. In Q31 the groove angle is measured within the plane from the horizontal cross-slope edge.

The source specifies a 5 m groove, a 30 degree plane angle, a 30 degree groove angle, and gravity of 10 m/s2 for Q31. Q90 specifies a 4 kg block, spring constants 100 and 300 N/m, gravity of 10 m/s2, and release from rest with both springs unstretched. Dimensions used to make bodies, supports, rails, and coils visible are declared modeling or display choices, rather than additional data from the problem.

## Open the motion

The **Native Motion Lab** workflow produces the **motion-lab-results** artifact. `artifacts/motion-preview.html` opens offline in a browser with WebGL2. It contains its rendering runtime and recorded native results. Choose either model, play, pause, scrub time, adjust playback speed, orbit the view, switch to XY, and select objects to inspect them. Physical parameters are edited in Modelica and require a new native simulation.

The **motion-browser-checks** artifact contains the actual-browser report and screenshots for the matching HTML. A successful check is bound to that HTML's SHA-256; an unrelated or stale file is not equivalent evidence.

The same models can be loaded in OpenModelica/OMEdit by opening `DomelicaLab/package.mo` and selecting either example. They include MultiBody animation and saved experiment settings. The scripted compiler, exported scene, and browser checks do not constitute an inspection of the OMEdit GUI.

## Where motion comes from

MSL components define the physical equations. OpenModelica compiles and integrates those equations. Its original MAT results remain the primary output. The unchanged native CSV reader expands those original samples and parameters; it does not calculate a replacement trajectory. OpenModelica's visualization XML supplies object names, dimensions, orientations, and positions. Browser code renders and replays that data.

Existing primitive rendering is preserved. A separate generic extension supports native spring graphics using OpenModelica's field and transform conventions. That extension is presentation code, not a new physical law or a solver patch. Its mesh tessellation is documented separately; visual equivalence is not a claim of pixel-identical OMEdit rendering.

## Assumptions and boundaries

- The groove is a smooth bilateral guide represented by a Prismatic joint. The nominal recording ends at arrival at the lower endpoint after 2 seconds. It does not simulate an impact, end stop, or motion after leaving the groove.
- The spring experiment uses ideal linear massless springs, rigid supports, a rigid block, and a vertical guide. There is no damping. Oscillation therefore persists in this ideal model.
- Bodies and support geometry have explicit illustrative dimensions. Rendered coils communicate spring length and position; the model does not resolve stress, coil contact, or material deformation.
- Changing playback speed changes only how quickly recorded time is displayed. New parameter values need a new Modelica run.

## Verification and provenance

The independent physical checker covers full result duration, native sample identity, initial conditions, displacement, velocity, acceleration, constraint geometry, individual spring extensions and forces, and mechanical energy. The analytical trajectories appear only in this checker, not in either Modelica model or the browser.

Separate geometry checks cover native coordinate transforms and spring dimensions. Browser checks exercise playback, pause, scrubbing, replay, camera views, selection, signals, and desktop/mobile layout while blocking external network requests. The preserved reports state exactly which checks ran and which tolerances applied.

`motion-provenance.json` records the source revision, CI run, compiler/toolchain details, input hashes, source hashes, and output HTML hash. Native MAT, CSV, animation XML, and logs are retained together. The existing 17-file frozen mechanics baseline is checked without changing its acceptance definitions. The independent fluid PR and deferred compiler diagnostic are outside this milestone.

See [physical assumptions and numerical checks](M4_MOTION_PHYSICS.md) and [native spring rendering and browser checks](M4_MOTION_VIEWER.md) for the implementation-specific verification scope.

## Reproduce

From the repository root with OpenModelica, Python 3, and Node available:

```sh
omc scripts/install_msl.mos
omc scripts/native_m4.mos
python3 scripts/export_native_csv.py m4_groove_slide m4_two_spring
python3 scripts/verify_m4.py
npm ci --ignore-scripts --no-audit --no-fund
npm run build:runtime
python3 scripts/test_native_motion_scene.py --native
python3 scripts/build_motion_preview.py
npx playwright install chromium
node scripts/check_motion.cjs artifacts/motion-preview.html
```

The workflow pins the OpenModelica container to the same 1.27.1 image used by the accepted mechanics laboratory. MSL 4.1.0 is requested; the installed maintenance package and toolchain are recorded with the results. Consult retained logs before asserting that a run was warning-free.

## Next composition

After this first delivery, Q106 is a natural next model: a block moving down a wedge that can itself slide horizontally. It can exercise coupled motion by composing two existing Prismatic joints and bodies. That extension is not included in the two-model M4 acceptance reported here.
