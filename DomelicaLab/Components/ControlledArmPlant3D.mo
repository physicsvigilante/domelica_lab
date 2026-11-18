within DomelicaLab.Components;
model ControlledArmPlant3D
  "Reusable voltage-driven spatial arm with native electrical and thermal coupling"
  parameter Real gearRatio(min=Modelica.Constants.small)=5;
  parameter Modelica.Units.SI.Length upperLength(min=Modelica.Constants.small)=0.55;
  parameter Modelica.Units.SI.Length forearmLength(min=Modelica.Constants.small)=0.45;
  parameter Modelica.Units.SI.Density forearmDensity(min=Modelica.Constants.small)=850;
  parameter Modelica.Units.SI.ThermalConductance coolingConductance(min=0)=0.4;
  parameter Modelica.Units.SI.HeatCapacity windingHeatCapacity(min=Modelica.Constants.small)=40;
  parameter Modelica.Units.SI.Temperature ambientTemperature=293.15;
  parameter Modelica.Units.SI.Angle initialShoulderAngle=0.25;
  parameter Modelica.Units.SI.Angle initialElbowAngle=-0.4;

  Modelica.Mechanics.MultiBody.Interfaces.Frame_a mountingFrame
    "Attach to the composing model's fixed world frame";
  Modelica.Blocks.Interfaces.RealInput commandedVoltage(unit="V");
  Modelica.Blocks.Interfaces.RealOutput shoulderAngle(unit="rad")
    "Native shoulder measurement for an external controller";

  Modelica.Mechanics.MultiBody.Joints.Revolute shoulder(
    n={0,0,1}, useAxisFlange=true,
    phi(start=initialShoulderAngle, fixed=true), w(start=0, fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox upperArm(
    r={0,-upperLength,0}, widthDirection={1,0,0},
    width=0.065, height=0.05, density=850, color={39,194,173});
  Modelica.Mechanics.MultiBody.Joints.Revolute elbow(
    n={1,0,0}, useAxisFlange=true,
    phi(start=initialElbowAngle, fixed=true), w(start=0, fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox forearm(
    r={0,-forearmLength,0}, widthDirection={1,0,0},
    width=0.05, height=0.04, density=forearmDensity, color={242,166,75});
  DomelicaLab.Components.ThermalArmatureDrive drive(R=2, L=0.05, k=0.5);
  Modelica.Mechanics.Rotational.Components.IdealGear gear(ratio=gearRatio);
  Modelica.Mechanics.Rotational.Components.Damper shoulderDamper(d=0.2);
  Modelica.Mechanics.Rotational.Components.Damper elbowDamper(d=0.06);
  Modelica.Thermal.HeatTransfer.Components.HeatCapacitor winding(
    C=windingHeatCapacity, T(start=ambientTemperature, fixed=true));
  Modelica.Thermal.HeatTransfer.Components.ThermalConductor cooling(G=coolingConductance);
  Modelica.Thermal.HeatTransfer.Sources.FixedTemperature ambient(T=ambientTemperature);

  Modelica.Units.SI.Angle elbowAngle=elbow.phi;
  Modelica.Units.SI.AngularVelocity shoulderSpeed=shoulder.w;
  Modelica.Units.SI.AngularVelocity elbowSpeed=elbow.w;
  Modelica.Units.SI.AngularVelocity motorSpeed=drive.emf.w;
  Modelica.Units.SI.Current motorCurrent=drive.armatureCurrent;
  Modelica.Units.SI.Temperature windingTemperature=winding.T;
  Modelica.Units.SI.Power copperLoss=drive.resistor.LossPower;
  Modelica.Units.SI.Power inputPower=commandedVoltage*motorCurrent
    "Signed power supplied to the armature; negative means returned to the ideal supply";
  Real currentDerivative(unit="A/s")=der(drive.inductor.i);
  Real temperatureDerivative(unit="K/s")=der(winding.T);
  Modelica.Units.SI.Position tipPosition[3]=forearm.frame_b.r_0;
equation
  shoulderAngle=shoulder.phi;
  connect(mountingFrame, shoulder.frame_a);
  connect(shoulder.frame_b, upperArm.frame_a);
  connect(upperArm.frame_b, elbow.frame_a);
  connect(elbow.frame_b, forearm.frame_a);
  connect(commandedVoltage, drive.commandedVoltage);
  connect(drive.shaft, gear.flange_a);
  connect(gear.flange_b, shoulder.axis);
  connect(shoulder.axis, shoulderDamper.flange_b);
  connect(shoulder.support, shoulderDamper.flange_a);
  connect(elbow.axis, elbowDamper.flange_b);
  connect(elbow.support, elbowDamper.flange_a);
  connect(drive.heatPort, winding.port);
  connect(winding.port, cooling.port_a);
  connect(cooling.port_b, ambient.port);
  annotation(Documentation(info="<html><p>A plant assembled from MSL joints, rigid bodies, gear, dampers and thermal storage, reusing ThermalArmatureDrive. Voltage comes from the composing model; shoulder angle is an exposed measurement. The perpendicular elbow is passive. The supported mounting is a fixed world frame. The ideal motor has no rotor inertia, iron loss or saturation, and the gear is lossless. Joint damping dissipates energy separately from winding copper loss.</p></html>"));
end ControlledArmPlant3D;
