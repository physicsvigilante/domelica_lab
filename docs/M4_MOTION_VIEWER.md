# M4 motion playback

The M4 viewer replays Q31 and Q90 from the native OpenModelica result files.
Its physics is entirely in the Modelica Standard Library components assembled
in `GrooveSlide3D` and `TwoSpringOscillator3D`. There is no JavaScript integrator
or hand-authored motion path.

## Reproduction

After native simulation, export and physical acceptance have completed:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run build:runtime
python3 scripts/test_native_motion_scene.py --native
python3 scripts/build_motion_preview.py
node scripts/check_motion.cjs artifacts/motion-preview.html
```

Open `artifacts/motion-preview.html` in a WebGL2 browser. It includes its renderer
and recorded data and makes no network requests. Choose a scene and press Play.
Play, pause, speed and the time slider all use the same native sample clock.
The animation stops at the last recorded sample; Replay explicitly starts over.
Drag to orbit, use XY for a planar view, and click a native part to inspect it.
Changing physical parameters requires a fresh native simulation.

## Source and result identity

`motion-provenance.json` records source revision, native run, compiler details,
source hashes and MAT/CSV/XML input hashes, plus the delivered HTML hash.
`motion-scenes.json` is the exact payload embedded in that HTML. The browser
report names the tested HTML hash and preserves desktop and mobile screenshots.
The builder refuses to package a failed physical-acceptance report.

The accepted M1 exporter, native CSV reader, Three.js runtime, and original
viewer template are unchanged. M4 uses a separate template based on the accepted
one, and delegates ordinary primitives to the unchanged exporter. The generic
spring extension is the only additional geometry family.

## Native spring dimensional convention

OpenModelica 1.27.1's `Visualization.cpp` creates a spring using the arguments
`Spring(width, height, extra, length)`. Its `ExtraShapes.cpp` interprets those
arguments as coil centerline radius, wire radius, winding count and length.
The native XML values are retained with this exact interpretation. They are
not treated as a cylinder's diameter and height.

References:

- [OMEdit 1.27.1 shape construction](https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMEdit/OMEditLIB/Animation/Visualization.cpp)
- [OMEdit 1.27.1 spring dimensions](https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMEdit/OMEditLIB/Animation/ExtraShapes.cpp)
- [MSL 4.1.0 spring component](https://github.com/modelica/ModelicaStandardLibrary/blob/v4.1.0/Modelica/Mechanics/MultiBody/Forces/Spring.mo)

Spring objects have unit orientation columns and a native origin. A separate
sampled geometry field stores `[length, coilRadius, wireRadius, windingCount]`.
Every value comes from native XML constants or native CSV variables. Ordinary
objects keep the M1 convention of dimension-scaled orientation columns.

The browser draws an ideal helix with 24 segments per turn and 12 around each
wire cross-section. The wire remains circular with constant native radius when
the spring length changes. This is a smoother surface tessellation than OMEdit's
coarser spring mesh; it is not a claim of identical OMEdit pixels or vertices.
Spring pose, length, radius and winding count are native. Light, grid, surface
tessellation and selection highlights are viewer presentation choices.

The helix does not detect wire contact, spring solid height, collisions or
separation. Only positive lengths and radii, wire radius below coil radius, and
positive winding counts up to 128 are supported. Unsupported native objects
or malformed fields fail explicitly.

## Verification scope

- Independent synthetic geometry fixtures cover rotation, offsets, variable
  dimensions, duplicate native event times, bounds and invalid data rejection.
- Native checks compare spring-axis attachment points to the native component
  frame positions at every sample.
- Browser checks compare actual Three.js mesh transforms and spring vertices
  to native payloads at multiple times, including circular wire radius as the
  spring stretches and compresses.
- Controls, actual pointer picking, offline operation, mobile layout and the
  unavailable-WebGL state are exercised in Chromium.

These checks verify native result playback and the stated geometry subset.
They do not establish an inspected OMEdit GUI session or experimental validation
of a physical apparatus. Q31 ends at the groove's end; the model has no end stop.
