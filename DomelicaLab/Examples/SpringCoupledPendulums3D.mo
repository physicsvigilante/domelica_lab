within DomelicaLab.Examples;
model SpringCoupledPendulums3D
  "Two independent pendulums exchange energy through a spring joining their bobs"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;
  import Frames = Modelica.Mechanics.MultiBody.Frames;

  parameter SI.Mass leftMass=1 "Left bob has no rotational inertia";
  parameter SI.Mass rightMass=1.3 "Right bob has no rotational inertia";
  parameter SI.Length pendulumLength=1.05 "Equal massless rigid rods";
  parameter SI.Length pivotSeparation=2.2 "Horizontal distance between fixed hinges";
  parameter SI.Height pivotHeight=1.75;
  parameter SI.TranslationalSpringConstant couplingStiffness=12;
  parameter SI.Length springFreeLength=pivotSeparation
    "The spring is unstrained when both rods point vertically downward";
  parameter SI.Acceleration g=9.81;
  parameter SI.Angle leftInitialAngle=24*Modelica.Constants.pi/180
    "Angle from downward toward world +x";
  parameter SI.Angle rightInitialAngle=-12*Modelica.Constants.pi/180;
  parameter SI.Diameter bobDiameter=0.18 "Visual only";
  parameter SI.Diameter rodDiameter=0.032 "Visual only";

  inner Modelica.Mechanics.MultiBody.World world(
    g=g, n={0,-1,0}, animateWorld=false, animateGravity=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation leftSupport(
    r={-pivotSeparation/2,pivotHeight,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation rightSupport(
    r={pivotSeparation/2,pivotHeight,0}, animation=false);

  Modelica.Mechanics.MultiBody.Joints.Revolute leftHinge(
    n={0,0,1}, useAxisFlange=false, stateSelect=StateSelect.always,
    phi(start=leftInitialAngle,fixed=true), w(start=0,fixed=true),
    cylinderLength=0.22, cylinderDiameter=0.085, cylinderColor={210,225,237});
  Modelica.Mechanics.MultiBody.Joints.Revolute rightHinge(
    n={0,0,1}, useAxisFlange=false, stateSelect=StateSelect.always,
    phi(start=rightInitialAngle,fixed=true), w(start=0,fixed=true),
    cylinderLength=0.22, cylinderDiameter=0.085, cylinderColor={210,225,237});

  Modelica.Mechanics.MultiBody.Parts.FixedTranslation leftRod(
    r={0,-pendulumLength,0}, shapeType="cylinder",
    lengthDirection={0,-1,0}, widthDirection={0,0,1},
    length=pendulumLength, width=rodDiameter, height=rodDiameter,
    color={119,189,235});
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation rightRod(
    r={0,-pendulumLength,0}, shapeType="cylinder",
    lengthDirection={0,-1,0}, widthDirection={0,0,1},
    length=pendulumLength, width=rodDiameter, height=rodDiameter,
    color={233,162,125});
  Modelica.Mechanics.MultiBody.Parts.PointMass leftBob(
    m=leftMass, sphereDiameter=bobDiameter, sphereColor={63,181,225});
  Modelica.Mechanics.MultiBody.Parts.PointMass rightBob(
    m=rightMass, sphereDiameter=bobDiameter, sphereColor={242,158,95});
  Modelica.Mechanics.MultiBody.Forces.Spring couplingSpring(
    c=couplingStiffness, s_unstretched=springFreeLength, m=0,
    width=0.062, coilWidth=0.004, numberOfWindings=14,
    color={116,220,153});

  // These are world-fixed native geometric references only, with no
  // contacts, impacts or extra mechanical forces.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape supportBeam(
    shapeType="box", r_shape={-pivotSeparation/2-0.2,pivotHeight+0.12,-0.03},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=pivotSeparation+0.4, width=0.13, height=0.09,
    color={92,116,139});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape floor(
    shapeType="box", r_shape={-pivotSeparation/2-0.5,-0.05,-0.12},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=pivotSeparation+1.0, width=0.28, height=0.1,
    color={45,62,77});

  // Read-only native observations; they never impose a motion law.
  SI.Angle leftAngle=leftHinge.phi;
  SI.Angle rightAngle=rightHinge.phi;
  SI.AngularVelocity leftAngularSpeed=leftHinge.w;
  SI.AngularVelocity rightAngularSpeed=rightHinge.w;
  SI.Position leftPivotPosition[3]=leftHinge.frame_a.r_0;
  SI.Position rightPivotPosition[3]=rightHinge.frame_a.r_0;
  SI.Position leftPosition[3]=leftBob.frame_a.r_0;
  SI.Position rightPosition[3]=rightBob.frame_a.r_0;
  SI.Velocity leftVelocity[3]=leftBob.v_0;
  SI.Velocity rightVelocity[3]=rightBob.v_0;
  SI.Acceleration leftAcceleration[3]=leftBob.a_0;
  SI.Acceleration rightAcceleration[3]=rightBob.a_0;
  SI.Length springLength=couplingSpring.length;
  SI.Length springExtension=springLength-springFreeLength;
  SI.Force leftSpringOnBob[3]=
    -Frames.resolve1(couplingSpring.frame_a.R,couplingSpring.frame_a.f)
    "Spring force ON left bob, opposite the native force INTO the spring";
  SI.Force rightSpringOnBob[3]=
    -Frames.resolve1(couplingSpring.frame_b.R,couplingSpring.frame_b.f);
  SI.Force leftRodOnBob[3]=
    -Frames.resolve1(leftRod.frame_b.R,leftRod.frame_b.f)
    "Rod force ON bob, opposite the native force INTO the rod";
  SI.Force rightRodOnBob[3]=
    -Frames.resolve1(rightRod.frame_b.R,rightRod.frame_b.f);

  SI.Position centerOfMass[3]=
    (leftBob.m*leftPosition+rightBob.m*rightPosition)/(leftBob.m+rightBob.m);
  SI.Energy kineticEnergy=
    (leftBob.m*(leftVelocity*leftVelocity)
      +rightBob.m*(rightVelocity*rightVelocity))/2;
  SI.Energy gravitationalEnergy=
    g*(leftBob.m*leftPosition[2]+rightBob.m*rightPosition[2]);
  SI.Energy springEnergy=couplingSpring.c*springExtension^2/2;
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy+springEnergy;

initial equation
  assert(leftMass>0 and rightMass>0 and pendulumLength>0
    and pivotSeparation>0 and pivotHeight>0 and springFreeLength>0
    and couplingStiffness>0 and g>0,
    "This two-pendulum demonstration requires positive physical parameters.");
  assert(abs(leftInitialAngle)<Modelica.Constants.pi/3
    and abs(rightInitialAngle)<Modelica.Constants.pi/3,
    "The nominal example is restricted to releases within 60 degrees.");
  assert(bobDiameter>0 and rodDiameter>0
    and pivotHeight-pendulumLength-bobDiameter/2>0.3,
    "The drawn bobs must clear the illustrated floor.");

equation
  connect(world.frame_b,leftSupport.frame_a);
  connect(world.frame_b,rightSupport.frame_a);
  connect(leftSupport.frame_b,leftHinge.frame_a);
  connect(rightSupport.frame_b,rightHinge.frame_a);
  connect(leftHinge.frame_b,leftRod.frame_a);
  connect(rightHinge.frame_b,rightRod.frame_a);
  connect(leftRod.frame_b,leftBob.frame_a);
  connect(rightRod.frame_b,rightBob.frame_a);
  connect(leftBob.frame_a,couplingSpring.frame_a);
  connect(rightBob.frame_a,couplingSpring.frame_b);
  connect(world.frame_b,supportBeam.frame_a);
  connect(world.frame_b,floor.frame_a);

  assert(noEvent(springLength>2*bobDiameter),
    "The bob endpoints approached; this ideal model excludes collision and spring coil contact.");

  annotation(
    experiment(StartTime=0,StopTime=5,Interval=0.005,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>An unfamiliar compositional test, not a verbatim question from 01_mechanics.pdf. Two massless rods with point-mass bobs swing on separate fixed, ideal revolute hinges. One MSL MultiBody.Forces.Spring joins their bobs and transmits equal-and-opposite forces. Both pendulum angles are native dynamic states; no drive, prescribed trajectory or mechanism-specific physics routine is used.</p><p>The world x axis is horizontal, y points up, and the hinges rotate about z. At release the bobs have unequal initial angles and zero velocities. The spring is initially compressed, then exchanges energy between both pendulums. The rods and bobs use stock native animation primitives. The displayed bob diameters do not add rotational inertia; the rods are strictly massless. Supports and floor are disconnected visual references, not collision objects.</p><p>The model assumes uniform gravity, a massless undamped spring, point masses, rigid massless rods, and frictionless hinges, with no contact or coil limits. Every observed force is evaluated from native connector flow variables with explicit sign conventions. The mechanical energy readout includes both bobs and their spring and is diagnostic only.</p></html>"));
end SpringCoupledPendulums3D;
