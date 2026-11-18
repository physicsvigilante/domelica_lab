within DomelicaLab.Examples;
model MotorizedPendulum3D
  "Electric armature drives a gravitational 3D multibody pendulum"
  extends Modelica.Icons.Example;

  parameter Modelica.Units.SI.Length armLength = 0.7
    "Joint-to-tip length";
  inner Modelica.Mechanics.MultiBody.World world(n={0,-1,0});
  Modelica.Mechanics.MultiBody.Joints.Revolute hinge(
    n={0,0,1},
    useAxisFlange=true,
    phi(start=0.3, fixed=true),
    w(start=0, fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox arm(
    r={0,-armLength,0},
    widthDirection={1,0,0},
    width=0.06,
    height=0.05,
    density=850,
    color={40,140,220});
  DomelicaLab.Components.ArmatureDrive drive(R=2,L=0.05,k=2);
  Modelica.Mechanics.Rotational.Components.Damper damper(d=0.15);
  Modelica.Blocks.Sources.Step command(height=18,startTime=0.5);

  Modelica.Units.SI.Angle angle = hinge.phi
    "Hinge angle in rad";
  Modelica.Units.SI.AngularVelocity angularVelocity = hinge.w;
  Modelica.Units.SI.Current motorCurrent = drive.armatureCurrent;
equation
  connect(world.frame_b, hinge.frame_a);
  connect(hinge.frame_b, arm.frame_a);
  connect(hinge.axis, drive.shaft);
  connect(hinge.axis, damper.flange_b);
  connect(damper.flange_a, hinge.support);
  connect(command.y, drive.commandedVoltage);
  annotation(
    experiment(StartTime=0, StopTime=4, Interval=0.01, Tolerance=1e-6),
    Documentation(info="<html><p>New composition of electrical, rotational and 3D multibody components. Open in OMEdit and use Simulate with Animation. Plot angle, angularVelocity and motorCurrent; the voltage step occurs at 0.5 s. The arm is a geometrically and inertially meaningful MSL BodyBox, not a decorative animation.</p></html>"));
end MotorizedPendulum3D;
