# M6G: use real upstream domelica_mecha to author pulley geometry

## Why this is a meaningful integration

M6F used a good numeric tangent/arc kernel, previously **adapted** from
domelica_mecha, but the LLM manually selected its two tangent branches,
circular wrap directions and schematic coordinates. M6G upgrades a
bounded part of this workflow to use the **actual upstream repository**.

The pinned source is physicsvigilante/domelica_mecha, commit
ede82116f3654b6c99043927f3d7a5cb69780801.

The local authoring script uses its real
\`physics_sandbox.route_resolution.resolve_string_route_numeric\` and
\`PassageIntentSpec\`, which in turn call the upstream numeric
tangent/arc/branch admissibility and orientation algorithms.

One small input, \`viewer/m6g-geometry-intent.json\`, contains:
- the **given** 30° incline;
- illustrative, explicitly marked initial C position, two pulley
  radii and four relative clearances;
- two *ordered*, **high-level** rope routes, no explicit tangent sides
  or clockwise/counterclockwise wraps;
- semantic straight-leg travel directions (up/down slope; down).

The upstream resolver chooses **unique feasible branch incidences**
and wrap orientations or refuses ambiguous/inconsistent geometry.
It constructs actual reference contact points and arc sweeps, not
only visually styled segments.

The authored output consists of:

1. \`artifacts/m6g-resolved-routes.json\` — a valid input for the
   unchanged domelica_lab 2D recording adapter.
2. \`artifacts/m6g-geometry-proof.json\` — a small audited numeric
   reference with actual tangents, arcs, lengths, repo source SHA and
   model-authoring input SHA-256.
3. \`DomelicaLab/Examples/M6FResolvedGeometry.mo\` — committed and
   mechanically read-only Modelica constants for the *illustrative*
   physical dimensions. The new authoring CI job verifies that this
   standalone package is an exact function of the intent JSON.

The M6F model now reads its physical geometry defaults from the
generated Modelica package. It still derives actual body/pulley
world locations using the same Modelica rigid-frame formulas and
simulates mechanics using stock World/Prismatic/PointMass/
IdealGearR2T. No external Python or second solver is required for
someone opening the compiled Modelica package.

**This is geometry authoring, NOT dynamic solving** by domelica_mecha.
The physical shape and ropes remain governed by OpenModelica.
The upstream resolver does not decide the system's mass, friction,
force laws, 3D geometry, or change the native equations.

## Qualification boundary

The new CI workflow:

- checks out **exact upstream commit** into an isolated sibling
  directory and imports its Python package without copying it into
  domelica_lab;
- runs its numeric route resolver and exports a route/witness artifact;
- runs one existing M6F OpenModelica setup with the generated
  Modelica geometry constants;
- verifies native first-frame coordinates and both *physical* rope
  lengths match the upstream numeric geometry witness;
- reuses the existing standalone dark/light HTML generator and
  browser smoke test, using the newly **authored** route rather than
  the old hand-picked branch JSON.

The core \`rope2d_geometry.py\`, \`build_rope2d.py\`,
\`rope2d.template.html\`, native runner and all earlier models are
untouched. The full upstream source is a **build-time authoring
dependency only**, not bundled into the standalone HTML or users'
OpenModelica environment.

## Limits

Input still specifies an illustrative reference center and relative
distances. The upstream solver **does not automatically reconstruct a
unique physical dimensioned layout from a schematic that has only
a 30° angle**; that would be a false claim of physical authority.
Nor does it derive mechanics from a route JSON. This slice resolves
discrete tangent/wrap choices and certifies the chosen geometry.

The next enhancement—only if further problems require it—is to
use upstream reference embedding for partial geometry, reducing
the number of authored coordinates while retaining provenance
of any arbitrary schematic choices. Do not add this until a
specific unfamiliar topology benefits from it.
