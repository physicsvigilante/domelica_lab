# Standalone test of OpenModelica differentiation of MSL quadraticFlow

No M3 production models are modified. The direct models prescribe q and r by
ODEs with exact integrated solutions. The implicit models impose a pump-head
flow constraint while exchanging a conserved volume between two tank levels.

The MSL function and the explicitly specialized one-input Modelica function
have the same quadratic head and original linear extrapolation. Native
der(head) and trajectories are independently compared with an analytical
chain-rule oracle and the control model. Full logs, sample grids and compiler
versions are preserved even on failure.

A passing minimal test would not refute failures seen in the full M3 fluid
DAE. Failures must be checked for mistakes in this test before being reported
upstream. No external issue is filed or production code changed by this work.
