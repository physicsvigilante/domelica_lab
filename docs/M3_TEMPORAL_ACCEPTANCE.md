## Independent actuator trajectory acceptance

The native first-order pump response satisfies the declared equation

`der(filteredFraction) = (pumpFraction - filteredFraction) / 2`.

Checking this equation against an exported derivative alias checks a pointwise
identity. It does not independently establish that the recorded state followed
that derivative over time. A diagnostic native run exposed this distinction:
the pointwise identity passed while the reconstructed pump-speed trajectory was
incorrect. The acceptance verifier therefore includes two additional checks.

For every authored case, it independently integrates the right-hand side from
the recorded controller output and speed fraction using trapezoidal quadrature.
The allowed residual is 0.0001 plus 0.002 times the cumulative absolute integral.
Native event samples are preserved; repeated timestamps contribute zero time.
The maximum observed residual is recorded as `speedTrajectoryFraction`.

For the initial-high-B case, the verifier first requires that the controller
output stays at 0.001 over the first second and that the initial speed fraction
is 0.3. With the declared 2 s time constant, the independent exact solution is

`filteredFraction(t) = 0.001 + 0.299 * exp(-t/2)`.

Every native sample in that first second must agree within 1e-6. Its maximum
error is recorded as `initialSpeedOracleFraction`. These tolerances were declared
before evaluating the diagnostic solver candidates.

These checks strengthen acceptance without changing any existing mass, energy,
controller, geometry, or tracking limits. They do not alter or correct the
native results, and they are not used to generate the visualization.

## Native pump-curve derivative acceptance

The diagnostic also exposed a missing flow contribution in the generated
derivative of the original partially applied pump curve. Production acceptance
retains the same 1e-5 m/s chain-rule limit declared for the diagnostic candidates.
For open-valve samples with `supplyFlow > 1e-5 kg/s`, write the pump similarity
law as `H = r*r*F(q/r)`, where `r = pumpRPM/1200`, `q = supplyFlow/995.586`, and
`F` is the fixed native head curve, including MSL's linear extrapolation. Its
complete derivative is

`der(H) = 2*r*der(r)*F(q/r) + F'(q/r)*(r*der(q) - q*der(r))`.

The verifier compares this expression with native `der(plant.pump.head)` when
that column and a native flow derivative are exported. It records availability,
the columns used, the number of checked samples, and the maximum residual under
`verification.nativePumpHeadDerivative`. Availability is explicit because these
auxiliary columns depend on compiler transformations. This check complements
the independent actuator trajectory checks; it does not replace them.
