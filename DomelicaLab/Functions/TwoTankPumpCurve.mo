within DomelicaLab.Functions;
function TwoTankPumpCurve
  "MSL quadraticFlow specialized to the fixed two-tank pump points"
  extends Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.baseFlow;
algorithm
  head := if V_flow < 0 then 10 - 250*V_flow
    elseif V_flow > 0.008 then -2250*(V_flow - 0.008)
    else 10 - 250*V_flow - 125000*V_flow*V_flow;
  annotation(derivative=DomelicaLab.Functions.TwoTankPumpCurveDerivative, Inline=true,
    Documentation(info="<html><p>This native Modelica function is algebraically identical to MSL quadraticFlow with V_flow_nominal={0,0.004,0.008} and head_nominal={10,7,0}, including its linear extrapolation outside the nominal interval. Exposing the fixed one-input expression avoids the omitted flow derivative observed when the pinned OpenModelica toolchain differentiated the partially applied generic MSL function. The plant compares seven values against the native MSL function during initialization. This is an illustrative pump curve, not a fit to measured equipment.</p></html>"));
end TwoTankPumpCurve;
