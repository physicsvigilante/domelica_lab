within DomelicaLab.Examples;
model ThermalGearedArm3D
  "A geared motor drives a spatial two-link arm while copper loss heats its winding"
  extends Modelica.Icons.Example;

  parameter Real gearRatio=5;
  parameter Modelica.Units.SI.Length upperLength=0.55;
  parameter Modelica.Units.SI.Length forearmLength=0.45;
  parameter Modelica.Units.SI.Temperature ambientTemperature=293.15;

  inner Modelica.Mechanics.MultiBody.World world(n={0,-1,0});
  Modelica.Mechanics.MultiBody.Joints.Revolute shoulder(
    n={0,0,1}, useAxisFlange=true,
    phi(start=0.25, fixed=true), w(start=0, fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox upperArm(
    r={0,-upperLength,0}, widthDirection={1,0,0},
    width=0.065, height=0.05, density=850, color={39,194,173});
  Modelica.Mechanics.MultiBody.Joints.Revolute elbow(
    n={1,0,0}, useAxisFlange=true,
    phi(start=-0.4, fixed=true), w(start=0, fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox forearm(
    r={0,-forearmLength,0}, widthDirection={1,0,0},
    width=0.05, height=0.04, density=850, color={242,166,75});

  DomelicaLab.Components.ThermalArmatureDrive drive(R=2, L=0.05, k=0.5);
  Modelica.Mechanics.Rotational.Components.IdealGear gear(ratio=gearRatio);
  Modelica.Mechanics.Rotational.Components.Damper shoulderDamper(d=0.2);
  Modelica.Mechanics.Rotational.Components.Damper elbowDamper(d=0.06);
  Modelica.Blocks.Sources.TimeTable command(
    table=[0,0; 0.5,0; 1,6; 3,6; 3.5,0; 8,0]);

  Modelica.Thermal.HeatTransfer.Components.HeatCapacitor winding(
    C=40, T(start=ambientTemperature, fixed=true));
  Modelica.Thermal.HeatTransfer.Components.ThermalConductor cooling(G=0.4);
  Modelica.Thermal.HeatTransfer.Sources.FixedTemperature ambient(T=ambientTemperature);

  Modelica.Units.SI.Angle shoulderAngle=shoulder.phi;
  Modelica.Units.SI.Angle elbowAngle=elbow.phi;
  Modelica.Units.SI.AngularVelocity shoulderSpeed=shoulder.w;
  Modelica.Units.SI.AngularVelocity elbowSpeed=elbow.w;
  Modelica.Units.SI.AngularVelocity motorSpeed=drive.emf.w;
  Modelica.Units.SI.Current motorCurrent=drive.armatureCurrent;
  Modelica.Units.SI.Temperature windingTemperature=winding.T;
  Modelica.Units.SI.Power copperLoss=drive.resistor.LossPower;
  Modelica.Units.SI.Voltage appliedVoltage=command.y;
  Real currentDerivative(unit="A/s")=der(drive.inductor.i);
  Real temperatureDerivative(unit="K/s")=der(winding.T);
  Modelica.Units.SI.Position tipPosition[3]=forearm.frame_b.r_0;
equation
  connect(world.frame_b, shoulder.frame_a);
  connect(shoulder.frame_b, upperArm.frame_a);
  connect(upperArm.frame_b, elbow.frame_a);
  connect(elbow.frame_b, forearm.frame_a);
  connect(command.y, drive.commandedVoltage);
  connect(drive.shaft, gear.flange_a);
  connect(gear.flange_b, shoulder.axis);
  connect(shoulder.axis, shoulderDamper.flange_b);
  connect(shoulder.support, shoulderDamper.flange_a);
  connect(elbow.axis, elbowDamper.flange_b);
  connect(elbow.support, elbowDamper.flange_a);
  connect(drive.heatPort, winding.port);
  connect(winding.port, cooling.port_a);
  connect(cooling.port_b, ambient.port);
  annotation(
    experiment(StartTime=0, StopTime=8, Interval=0.01, Tolerance=1e-7),
    Documentation(info="<html><p>A different topology composed entirely from MSL components and the existing armature. The two joint axes are perpendicular, so the passive elbow moves out of the shoulder's plane. A 5:1 ideal gear transmits motor torque to the shoulder. Copper loss heats a lumped winding, increasing its resistance; conduction cools it to the ambient. The voltage ramps up and down. Zero applied voltage leaves the armature circuit closed, allowing electrical damping and continued copper heating. This is an open-loop experiment, not a position-controlled robot.</p></html>"));
end ThermalGearedArm3D;
