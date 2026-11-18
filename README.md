# Domelica Lab

A **Modelica-first multiphysics laboratory** for exploring how reusable components can be composed into complex, physically verified, visualized systems.

## Principles

- **Modelica is the physics authority.** Prefer Modelica Standard Library components and native equations over custom solvers.
- **Composition over case-specific code.** New arrangements should be authored by connecting reusable components.
- **Simulation before visualization.** Animate native simulation results; never substitute hand-written visual physics.
- **Evidence over claims.** Separate static checks, native compilation/simulation, and graphical inspection.
- **Keep experiments reproducible.** Record OpenModelica/MSL versions, parameters, outputs, and limitations.

## First milestone

Establish a native MultiBody animation baseline and an authored electric-to-mechanical 3D model, with repeatable checks and a path to a richer viewer. Development is performed in ChatGPT and proposed changes are reviewed through pull requests.

Project status: M0 native and independent numeric gates qualified in [draft PR #1](https://github.com/physicsvigilante/domelica_lab/pull/1). Full native 3D visual inspection and unfamiliar topology composition remain pending. The PR also contains a self-contained browser preview generated from Modelica results.
