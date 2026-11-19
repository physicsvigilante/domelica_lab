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

## How the actual two repositories cooperate

Upstream authored geometry is performed **inside domelica_mecha**, not by
copying a whole Python resolver into domelica_lab. The pinned authoring
source and its own CI are reviewable:

- Upstream draft PR: https://github.com/physicsvigilante/domelica_mecha/pull/1
- Exact upstream run: https://github.com/physicsvigilante/domelica_mecha/actions/runs/44538814814
- Generated artifact: https://github.com/physicsvigilante/domelica_mecha/actions/runs/44538814814/artifacts/14535958890
- Authoring commit: 0b2025f5f97a11da6d4cb24c476c7c21d3967058
- Pinned upstream library origin: ede82116f3654b6c99043927f3d7a5cb69780801

The upstream run **passed** and resolved both ropes uniquely given passage
intent (both initially had two feasible branches). It produced the exact
Modelica constants package, a resolved M6F route manifest, a full numerical
contact/arc proof and their SHA-256 hashes.

A critical access boundary is deliberate: the domelica_lab GitHub Actions
GITHUB_TOKEN **cannot read the other repository**. An attempted cross-repo
checkout returned Repository not found. We therefore preserve compact
upstream-generated, pinned outputs under viewer/m6g-upstream-proof.json and
viewer/m6g-resolved-routes.json. The complete original upstream proof remains
available as the upstream workflow artifact at the pinned run above. No
cross-repo secret, fork or broad access permission is required.

The downstream qualification pipeline:

1. Checks the geometry-authoring input SHA, Modelica package SHA and the
   matching upstream resolution evidence, then checks both first-frame rope
   arc lengths with the earlier adapted local numeric kernel.
2. Runs OpenModelica **once** on the M6F physical topology, with its
   geometric defaults imported from the pinned generated Modelica package.
3. Checks native coordinates and actual rope lengths against the upstream
   reference witness, and runs the existing physics oracle.
4. Builds dark/light standalone HTML using the now **upstream-resolved**
   route JSON, not hand-selected tangent/wrap signs.
5. Runs one focused existing M6F browser smoke check.

The existing native physics runner, the 2D viewer, rope2d_geometry.py and
earlier mechanical examples remain untouched.

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
