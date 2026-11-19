# Native observations viewer

This viewer replays the existing native geometry and observations. It does not
integrate equations of motion or calculate new mechanical trajectories.

## Build markers

Replace each marker once in `observation.template.html`:

| Marker | Input |
| --- | --- |
| `__THREE_RUNTIME__` | Existing bundled Three.js runtime |
| `__SPRING_RENDERER__` | Existing `motion-spring.js` |
| `__OBSERVATION_LAYER__` | `observation-layer.js` |
| `__NATIVE_CANVAS__` | `native-canvas.js` |
| `__NATIVE_MODEL_DATA__` | Native scene JSON, with observations attached |

The wrapper schema is `domelica.observation-lab/v1`; native scene geometry
keeps the original affine primitive and spring contracts. Each scene also carries `bodies`, `overlays`, and optionally `observationNotes` or `notes`.
The `overlays` array follows the declarative observation exporter contract.
Existing `scene.observations` metadata has a different purpose and is preserved.

## Shared observation layer

```javascript
const layer = DomelicaObservationLayer.create({
  THREE: null,       // or bundled THREE
  parent: null,      // or a Three.js Group
  controls: null,    // or a DOM element for full controls
  onChange(reason) {}
});
layer.loadScene(scene);
layer.setKind("force");
layer.setBody("all");
layer.setScale(0.02);  // metres per quantity unit; common to all active arrows
layer.setEnabled(observationId, true);
layer.select(observationId);
layer.update(nativeSampleIndex);
const samples = layer.getActiveSamples();
const bounds = layer.extendBounds(scene.bounds);
const state = layer.getState();
```

Available quantities are discovered from metadata. The layer does not contain
cart, chain, spring, mass, or force-law special cases. Each active sample has an
explicit world point, vector, receiving or observed body, quantity kind, units,
source metadata, scaled endpoint, and magnitude.

All vectors for one quantity share the same scale. Different physical
quantities use separate scales: force `m/N`, velocity `s`, acceleration `s²`,
and torque `m/(N·m)`. The scale is a display setting, not a change to the model.
An exactly zero vector has no arrow. Near-zero values remain unchanged, including
scientific-notation readouts. Arrow length is never given a minimum or normalized
separately per vector. Torque uses a double arrow along its axis and the
right-hand convention.

`extendBounds` includes every active arrow's attachment point and scaled endpoint
over the complete native recording, plus arrowhead allowance. Filters and scale
changes trigger a fit; ordinary playback does not move the camera.

## Optional XY renderer

```javascript
const view = DomelicaNativeCanvas.create(canvas);
view.resize(width, height, devicePixelRatio);
view.render({
  scene,
  index: nativeSampleIndex,
  overlays: layer.getActiveSamples(),
  bounds: layer.extendBounds(scene.bounds),
  zoom: 1,
  selected: null,
  theme: null
});
```

Optional `theme` keys are `foreground`, `muted`, `grid`, `bodyFill`, and
`bodyStroke`. A caller can also replace each sample's `color`. These are viewing
choices only. `grid` is reserved for future use; this renderer draws no grid.
`project(point)`, `pick(x,y)`, and `getState()` expose projection and selection.

The Canvas renderer reads the same native affine matrices and spring dimensions.
It is an orthographic XY projection with tessellated primitive surfaces; it is
not a second physics model. Projected in-plane arrow lengths retain the common
scale. An out-of-plane component is shown by a direction symbol at the exact
attachment point: circle-dot for +Z and circle-cross for −Z, with a double ring
for torque. Symbol size does not encode out-of-plane magnitude; the numerical
readout retains the complete XYZ vector.

The standalone template uses Three.js when WebGL2 is available and explicitly
labels the XY fallback otherwise. The same reusable modules support a compact
chat playback without Three.js.

## Runtime interfaces

- `window.__domelica`: existing scene playback, camera, picking, native transform,
  and diagnostics interface; state also reports observation selection and that
  this is playback of the named native recording. Its origin comes from the
  recording manifest, whether an earlier result or a newly completed run.
- `window.__domelicaObservations`: the shared observation-layer instance.

The initial local API check exercised first/final native samples and fit bounds.
The repository's `scripts/check_observation_lab.cjs` exercises the completed HTML
in Chromium. Its report binds the rendered file hash and native recording to the
check outcome; these presentation checks are separate from physical accuracy
validation or an OMEdit GUI inspection.
