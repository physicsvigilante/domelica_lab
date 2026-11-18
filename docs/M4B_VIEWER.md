# Coupled motion playback

The coupled viewer uses the accepted M4 template, Three.js runtime, spring mesh
code, ordinary geometry exporter, and spring geometry exporter without changing
their bytes. `viewer/coupled-experiments.json` selects the new native examples,
camera poses, and recorded signals. No example identifier enters the renderer.

`scripts/build_coupled_preview.py` accepts only successful, current native
physics reports. It checks the exact source and input hashes, native model name,
sample count, and time coverage before creating:

- `artifacts/coupled-preview.html`, a complete offline WebGL2 viewer;
- `artifacts/coupled-scenes.json`, the native scene payload;
- `artifacts/coupled-provenance.json`, the HTML identity and source/input hashes.

The artifact contains all native samples, including duplicate timestamps. The
existing viewer clock chooses recorded frames. Changing physical parameters
requires another native simulation; scrubbing and playback speed only change
how the result is viewed.

## Coupled behavior checks

`scripts/check_coupled.cjs` opens the exact delivered HTML in Chromium offline.
It verifies two moving body meshes, their distinct relative motion, the rigid
support assembly, fixed ground, synchronized native plots, camera and pointer
selection, playback controls, and desktop/mobile layout. Spring attachment axes
are compared with both physical component frames at every native sample, and
the moving spring anchor is checked to ensure it follows the wedge.

Additional native observation columns used by these checks are copied from CSV
without interpolation or recomputation. They do not feed the renderer or any
force law. Browser mesh matrices are compared with exported transforms at four
representative samples; spring mesh cross-sections are checked there too. Full
trajectory corner projections check framing. Screenshots use nonzero simulation
times and canvas image hashes must change when the recorded bodies move.

This is browser rendering validation. OMEdit's desktop GUI is not inspected.
The support is depicted by native rigid boxes; the bodies' ideal prismatic
constraints, rather than the drawing surfaces, supply their mechanical guides.
