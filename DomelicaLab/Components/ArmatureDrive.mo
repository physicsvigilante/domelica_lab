within DomelicaLab.Components;
model ArmatureDrive
  "Reusable voltage-driven DC armature with an electromechanical shaft"
  parameter Modelica.Units.SI.Resistance R = 2 "Armature resistance";
  parameter Modelica.Units.SI.Inductance L = 0.05 "Armature inductance";
  parameter Real k(unit="N.m/A") = 2 "Ideal electromechanical conversion constant";

  Modelica.Blocks.Interfaces.RealInput commandedVoltage(unit="V")
    "Applied voltage, supplied by the composing model";
  Modelica.Mechanics.Rotational.Interfaces.Flange_b shaft
    "Mechanical output shaft";

  Modelica.Electrical.Analog.Sources.SignalVoltage supply;
  Modelica.Electrical.Analog.Basic.Resistor resistor(R=R);
  Modelica.Electrical.Analog.Basic.Inductor inductor(L=L, i(start=0, fixed=true));
  Modelica.Electrical.Analog.Basic.RotationalEMF emf(k=k);
  Modelica.Electrical.Analog.Basic.Ground ground;

  Modelica.Units.SI.Current armatureCurrent = resistor.i
    "Current through the armature";
equation
  connect(commandedVoltage, supply.v);
  connect(supply.p, resistor.p);
  connect(resistor.n, inductor.p);
  connect(inductor.n, emf.p);
  connect(emf.n, supply.n);
  connect(supply.n, ground.p);
  connect(emf.flange, shaft);
  annotation(Documentation(info="<html><p>An ideal DC armature assembled from MSL resistor, inductor, EMF, source and electrical ground. The EMF mechanical support is fixed internally (useSupport=false). No motor dynamics are hand-coded.</p></html>"));
end ArmatureDrive;
