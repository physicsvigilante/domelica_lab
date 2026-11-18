within DomelicaLab.Components;
model ThermalArmatureDrive
  "Existing armature drive with its copper loss exposed to a thermal network"
  extends ArmatureDrive(resistor(
    final useHeatPort=true,
    T_ref=referenceTemperature,
    alpha=temperatureCoefficient));
  parameter Modelica.Units.SI.Temperature referenceTemperature=293.15;
  parameter Modelica.Units.SI.LinearTemperatureCoefficient temperatureCoefficient=0.0039;
  Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a heatPort
    "Connect to winding heat capacity and cooling; positive flow enters drive";
equation
  connect(resistor.heatPort, heatPort);
  annotation(Documentation(info="<html><p>Reuses ArmatureDrive unchanged. MSL Resistor supplies copper loss i^2 R(T) and temperature-dependent resistance through its native heat port. The enclosing system supplies thermal storage and cooling. This ideal motor omits iron losses, rotor inertia and magnetic saturation.</p></html>"));
end ThermalArmatureDrive;
