within DomelicaLab.Functions;
function TwoTankPumpCurveDerivative
  "Derivative of the fixed two-tank pump curve, including linear extrapolation"
  input Modelica.Units.SI.VolumeFlowRate V_flow;
  input Real der_V_flow(unit="m3/s2");
  output Real der_head(unit="m/s");
algorithm
  der_head := (if V_flow < 0 then -250
    elseif V_flow > 0.008 then -2250
    else -250 - 250000*V_flow)*der_V_flow;
end TwoTankPumpCurveDerivative;
