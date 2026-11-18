# Native scene playback contract

## Pipeline

1. `native_smoke.mos` enables `+d=visxml` and simulates with native MAT output.
2. `export_native_csv.py` uses supported OpenModelica batch commands to read the original result variables and sample arrays, including parameters and signed aliases. It serializes those values without interpolation.
3. `native_scene.export_scene()` reads each XML field as a constant or an exact reference into the corresponding CSV. Missing values and unsupported constructs fail explicitly.
4. `build_preview.py` attaches selected native signals from `viewer/experiments.json` and embeds everything in one HTML file, with source/result hashes.
5. The viewer projects the exported meshes and replays recorded samples. Camera operations change the view, not the system dynamics.

## Coordinates

The XML rotation `T` maps world vectors into the local object frame. A local point is placed in the world as:

`worldPoint = r + transpose(T) * (r_shape + primitivePoint)`

The exporter derives an orthonormal length/width/height basis from the native `lengthDir` and `widthDir`. It validates rotation orthogonality and determinant. It then stores each shape's affine transform as:

`[axisX_xyz, axisY_xyz, axisZ_xyz, origin_xyz]`

These axes include dimensions. A unit box spans X from 0 to 1 and Y/Z from -0.5 to 0.5; its origin is the center of its starting face, not the box center. A unit cylinder/cone has radius 0.5 and spans X from 0 to 1. The unit sphere has center (0.5, 0, 0) and radius 0.5.

## Supported subset

The current implementation follows OpenModelica 1.27.1's native primitive conventions:

| Shape | Dimensions and restrictions |
| --- | --- |
| `box` | Native length, width, height |
| `cylinder` | Length and circular diameter `width`; rotation stripes unsupported |
| `cone` | Real cone, `extra=0`; length and base diameter `width` |
| `sphere` | Diameter `length`, following the native OMEdit convention |

Dynamic transforms, dimensions and colors are supported. Constant transforms are stored once. Bounds conservatively enclose every primitive over every native sample, so camera Fit includes the full trajectory.

CAD files, pipes, springs, gearwheel graphics, surfaces, vectors, advanced cone variants and non-leaf XML expressions are deliberately unsupported. The exporter reports the native object/field instead of substituting a decorative placeholder. The browser uses shaded polygons and depth sorting; intersecting shapes can show ordering artifacts. Specular coefficients are read for reference validity, but the browser uses its own simple lighting.

## Adding a system

Add a new Modelica model and compose its components normally. Add a native simulation entry and a viewer configuration entry naming the result prefix and signals to plot. For models whose visualizers fall within the supported subset, no geometry-specific renderer or physics-engine change is needed. Add verification appropriate to the new experiment's physical question.

This contract is not a claim that every possible Modelica visualizer is supported. Adding a new primitive type requires implementing and verifying that type's geometry once; adding a different mechanism made from supported primitives does not.

## Reference implementations

- [OpenModelica 1.27.1 animation guide](https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/omedit.html#d-visualization)
- [Native scene XML template](https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMCompiler/Compiler/Template/VisualXMLTpl.tpl)
- [Native geometry/transform rendering](https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMEdit/OMEditLIB/Animation/Visualization.cpp)
- [Native result-reading API](https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/scripting_api.html#readsimulationresult)
