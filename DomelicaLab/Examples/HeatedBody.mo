within DomelicaLab.Examples;
model HeatedBody
  "A heat capacity heated by a commanded source and cooled by conduction"
  extends Modelica.Icons.Example;
  parameter Modelica.Units.SI.Temperature ambientTemperature = 293.15;
  parameter Modelica.Units.SI.HeatCapacity C = 15;
  parameter Modelica.Units.SI.ThermalConductance G = 1.2;
  parameter Modelica.Units.SI.HeatFlowRate commandedHeat = 90;

  Modelica.Thermal.HeatTransfer.Components.HeatCapacitor body(
    C=C, T(start=ambientTemperature, fixed=true));
  Modelica.Thermal.HeatTransfer.Components.ThermalConductor conductor(G=G);
  Modelica.Thermal.HeatTransfer.Sources.FixedTemperature ambient(T=ambientTemperature);
  Modelica.Thermal.HeatTransfer.Sources.PrescribedHeatFlow heater;
  Modelica.Blocks.Sources.Step heatCommand(
    height=commandedHeat, startTime=0.5);

  Modelica.Units.SI.Temperature temperature = body.T
    "Physical temperature, not visualization-derived";
equation
  connect(heatCommand.y, heater.Q_flow);
  connect(heater.port, body.port);
  connect(body.port, conductor.port_a);
  connect(conductor.port_b, ambient.port);
  annotation(
    experiment(StartTime=0, StopTime=5, Interval=0.01, Tolerance=1e-7),
    Documentation(info="<html><p>Uses only standard thermal components. Following the heat step at t=0.5 s, T(t) = T_ambient + (Q/G)*(1-exp(-G*(t-0.5)/C)); this independent analytic solution is used as a verification oracle.</p></html>"));
end HeatedBody;
