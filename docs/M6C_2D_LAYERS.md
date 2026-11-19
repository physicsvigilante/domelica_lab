# M6C-2D-A: minimal geometry / styling layers for Modelica recordings

## Decision

Start in **2D**. Reuse the already-proved fixed-pulley Q68 simulation before
attempting a moving pulley. Avoid a general scene graph, 3D renderer extension,
live solver connection, variable parameter UI, or a second mechanics engine.

Three independently replaceable responsibilities:

1. **Physical model and recording (OpenModelica).** The \`AtwoodFixedPulley3D.mo\`
   model supplies native positions, pulley center/radius, masses and tension.
   M6C adds only a read-only \`pulleyCenter[3]\` alias. No dynamics, topology,
   constraint, exporter or existing viewer has been modified.
2. **2D rope geometry (pure Python).** \`scripts/rope2d_geometry.py\` calculates
   point-to-circle tangents, circle-to-circle tangents, straight legs, wrapped
   circular arcs and total rope length from numbers, never forces or motion.
   \`viewer/m6c-2d-routes.json\` provides a small ordered route with explicit
   tangent-side and wrap choices, using named native CSV columns. The
   \`build_rope2d.py\` adapter binds real recorded samples and verifies native
   input hashes and the optional constant-length rope contract.
3. **Presentation (standalone SVG).** \`viewer/rope2d.template.html\` draws the
   precomputed geometry; \`viewer/m6c-2d-style.json\` and
   \`m6c-2d-style-light.json\` control only colors and decorative pixel widths.
   The same recording and geometry can be rendered twice with different styles
   without another simulation. No browser physics or geometry solver.

The route and style files are deliberately separate. A style file cannot change
mass, pulley radius, attachment positions, tension, or rope length. A route
file cannot specify arbitrary physical motion or forces.

## Reuse and ownership

The numeric tangent and arc formulas are a bounded adaptation of
\`physicsvigilante/domelica_mecha/src/physics_sandbox/local_geometry.py\`
(the same author's repository). The small ordered route vocabulary draws on
\`prepared_display_routes.py\`. No symbolic dependencies or other physics
engine code are imported. Explicitly reject invalid tangent branches, degenerate
segments, coincident pulley centers, invalid wrap direction, nonfinite inputs,
or a violated nominal rope-length constraint.

In this first trial the Modelica frame is world XY. The historical M6B model
uses a **massless, non-rotating ideal fixed pulley** with a visual radius. Rope
length includes two straight legs plus the upper semicircular wrap; the
underlying physics is still the existing taut-string bilateral constraint.
The radius is read from the Modelica run, not invented in the renderer.

## Reproduce

On OpenModelica 1.27.1 with MSL 4.1.0:

    omc scripts/install_msl.mos
    python3 -m unittest discover -s scripts -p test_rope2d_geometry.py
    python3 scripts/run_experiments.py run --manifest viewer/m6c-2d-experiments.json --run-dir observation-run
    python3 scripts/check_m6b_atwood.py --csv observation-run/m6b_atwood_res.csv --report artifacts/m6c-physics.json
    python3 scripts/build_rope2d.py --csv observation-run/m6b_atwood_res.csv --native-manifest observation-run/experiments.json --output artifacts/m6c-2d-dark.html
    python3 scripts/build_rope2d.py --csv observation-run/m6b_atwood_res.csv --native-manifest observation-run/experiments.json --style viewer/m6c-2d-style-light.json --output artifacts/m6c-2d-light.html

The standalone HTML files open offline. With Node 22 and Playwright installed,
\`node scripts/check_rope2d.cjs artifacts/m6c-2d-dark.html
artifacts/m6c-2d-light.html artifacts/m6c-2d-browser\` checks both versions
in Chromium, including real SVG endpoints, pulley radius, playback, scrubbing,
mobile width, source identity and no network requests.

## Narrow acceptance / next slice

This slice must demonstrate:

- One freshly computed fixed-pulley native run matches the existing analytical
  Q68 checks. Geometry at all native time samples conserves routed rope length.
- Tangency, arc radius and join continuity are correct; invalid branches refuse.
- Both dark and light animations carry **bit-for-bit identical geometry,
  trajectories, forces and source hashes**; only style differs.
- No modifications to M5/M6A/M6B original manifests, historical recordings,
  the core native runner, exported source locks or the existing Three.js viewer.

**Next M6C-2D-B:** author one actual *moving-pulley* arrangement in Modelica,
bind its moving pulley-center column into the same route grammar, and reuse the
geometry builder and SVG renderer unchanged. If extra geometry primitives are
needed, extend only the reusable kernel, not the per-mechanism renderer.
