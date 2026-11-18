within DomelicaLab.Examples;
model ReleasedSpringChain3D
  "Q192: three equal blocks and two equal springs, immediately after the top thread is cut"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  parameter SI.Mass blockMass=1 "Illustrative; Q192 specifies identical masses only";
  parameter SI.TranslationalSpringConstant stiffness=100
    "Illustrative; Q192 specifies identical ideal springs only";
  parameter SI.Acceleration g=9.81 "Illustrative uniform gravity";
  parameter SI.Length freeLength=0.6 "Illustrative unstretched length of each spring";
  parameter SI.Length blockHeight=0.16 "Illustrative vertical box dimension";
  parameter SI.Length blockWidth=0.28;
  parameter SI.Length blockDepth=0.24;
  parameter SI.Height topInitialHeight=5 "Illustrative world-coordinate origin";
  parameter SI.Length springWidth=0.065 "Native spring coil centerline radius";
  parameter SI.Length coilWidth=0.004 "MSL spring coil-width rendering parameter";
  final parameter SI.Length upperInitialExtension=2*blockMass*g/stiffness
    "Pre-cut upper spring supported two blocks";
  final parameter SI.Length lowerInitialExtension=blockMass*g/stiffness
    "Pre-cut lower spring supported one block";
  final parameter SI.Height middleInitialHeight=
    topInitialHeight-blockHeight-freeLength-upperInitialExtension;
  final parameter SI.Height bottomInitialHeight=
    middleInitialHeight-blockHeight-freeLength-lowerInitialExtension;

  inner Modelica.Mechanics.MultiBody.World world(
    g=g, n={0,-1,0}, animateWorld=false, animateGravity=false);
  Modelica.Mechanics.MultiBody.Joints.FreeMotion topFree(
    animation=false, enforceStates=true,
    r_rel_a(start={0,topInitialHeight,0}, each fixed=true),
    v_rel_a(start={0,0,0}, each fixed=true),
    angles_fixed=true, angles_start={0,0,0},
    w_rel_a_fixed=true, w_rel_a_start={0,0,0});
  Modelica.Mechanics.MultiBody.Joints.FreeMotion middleFree(
    animation=false, enforceStates=true,
    r_rel_a(start={0,middleInitialHeight,0}, each fixed=true),
    v_rel_a(start={0,0,0}, each fixed=true),
    angles_fixed=true, angles_start={0,0,0},
    w_rel_a_fixed=true, w_rel_a_start={0,0,0});
  Modelica.Mechanics.MultiBody.Joints.FreeMotion bottomFree(
    animation=false, enforceStates=true,
    r_rel_a(start={0,bottomInitialHeight,0}, each fixed=true),
    v_rel_a(start={0,0,0}, each fixed=true),
    angles_fixed=true, angles_start={0,0,0},
    w_rel_a_fixed=true, w_rel_a_start={0,0,0});

  Modelica.Mechanics.MultiBody.Parts.BodyBox topBody(
    r={0,-blockHeight,0}, r_shape={0,blockHeight/2,0},
    lengthDirection={0,-1,0}, widthDirection={1,0,0},
    length=blockHeight, width=blockWidth, height=blockDepth,
    density=blockMass/(blockHeight*blockWidth*blockDepth),
    color={244,158,62});
  Modelica.Mechanics.MultiBody.Parts.BodyBox middleBody(
    r={0,-blockHeight,0}, r_shape={0,blockHeight/2,0},
    lengthDirection={0,-1,0}, widthDirection={1,0,0},
    length=blockHeight, width=blockWidth, height=blockDepth,
    density=blockMass/(blockHeight*blockWidth*blockDepth),
    color={76,180,220});
  Modelica.Mechanics.MultiBody.Parts.BodyBox bottomBody(
    r={0,-blockHeight,0}, r_shape={0,blockHeight/2,0},
    lengthDirection={0,-1,0}, widthDirection={1,0,0},
    length=blockHeight, width=blockWidth, height=blockDepth,
    density=blockMass/(blockHeight*blockWidth*blockDepth),
    color={124,201,147});

  Modelica.Mechanics.MultiBody.Parts.FixedTranslation topLowerAttachment(
    r={0,-blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation middleUpperAttachment(
    r={0,blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation middleLowerAttachment(
    r={0,-blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation bottomUpperAttachment(
    r={0,blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Forces.Spring upperSpring(
    c=stiffness, s_unstretched=freeLength, m=0,
    width=springWidth, coilWidth=coilWidth, numberOfWindings=8,
    color={110,164,236});
  Modelica.Mechanics.MultiBody.Forces.Spring lowerSpring(
    c=stiffness, s_unstretched=freeLength, m=0,
    width=springWidth, coilWidth=coilWidth, numberOfWindings=8,
    color={173,141,229});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape supportMarker(
    shapeType="box", r_shape={-0.45,topInitialHeight+0.35,0},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=0.9, width=0.4, height=0.06, color={96,119,141});

  // Read-only observations. The unmodified MSL components supply every equation
  // of motion; these bindings do not constrain a force or trajectory.
  SI.Position topPosition[3]=topBody.frame_a.r_0;
  SI.Position middlePosition[3]=middleBody.frame_a.r_0;
  SI.Position bottomPosition[3]=bottomBody.frame_a.r_0;
  SI.Velocity topVelocity[3]=topBody.v_0;
  SI.Velocity middleVelocity[3]=middleBody.v_0;
  SI.Velocity bottomVelocity[3]=bottomBody.v_0;
  SI.Acceleration topAcceleration[3]=topBody.a_0;
  SI.Acceleration middleAcceleration[3]=middleBody.a_0;
  SI.Acceleration bottomAcceleration[3]=bottomBody.a_0;
  SI.AngularVelocity topAngularVelocity[3]=
    Modelica.Mechanics.MultiBody.Frames.angularVelocity2(topBody.frame_a.R);
  SI.AngularVelocity middleAngularVelocity[3]=
    Modelica.Mechanics.MultiBody.Frames.angularVelocity2(middleBody.frame_a.R);
  SI.AngularVelocity bottomAngularVelocity[3]=
    Modelica.Mechanics.MultiBody.Frames.angularVelocity2(bottomBody.frame_a.R);
  SI.Position upperStart[3]=upperSpring.frame_a.r_0;
  SI.Position upperEnd[3]=upperSpring.frame_b.r_0;
  SI.Position lowerStart[3]=lowerSpring.frame_a.r_0;
  SI.Position lowerEnd[3]=lowerSpring.frame_b.r_0;
  SI.Height topHeight=topPosition[2];
  SI.Height middleHeight=middlePosition[2];
  SI.Height bottomHeight=bottomPosition[2];
  SI.Length upperExtension=upperSpring.length-freeLength;
  SI.Length lowerExtension=lowerSpring.length-freeLength;
  SI.Force upperTension=upperSpring.f "Signed force: negative means ideal spring compression";
  SI.Force lowerTension=lowerSpring.f "Signed force: negative means ideal spring compression";
  SI.Position centerOfMass[3]=
    (topBody.m*topPosition+middleBody.m*middlePosition+bottomBody.m*bottomPosition)
      /(topBody.m+middleBody.m+bottomBody.m);
  SI.Velocity centerVelocity[3]=
    (topBody.m*topVelocity+middleBody.m*middleVelocity+bottomBody.m*bottomVelocity)
      /(topBody.m+middleBody.m+bottomBody.m);
  SI.Acceleration centerAcceleration[3]=
    (topBody.m*topAcceleration+middleBody.m*middleAcceleration+bottomBody.m*bottomAcceleration)
      /(topBody.m+middleBody.m+bottomBody.m);
  SI.Height centerHeight=centerOfMass[2];
  SI.Velocity centerSpeed=centerVelocity[2] "Signed upward center-of-mass speed";
  SI.Energy translationalEnergy=
    (topBody.m*(topVelocity*topVelocity)+middleBody.m*(middleVelocity*middleVelocity)
      +bottomBody.m*(bottomVelocity*bottomVelocity))/2;
  SI.Energy rotationalEnergy=
    (topAngularVelocity*(topBody.I*topAngularVelocity)
      +middleAngularVelocity*(middleBody.I*middleAngularVelocity)
      +bottomAngularVelocity*(bottomBody.I*bottomAngularVelocity))/2;
  SI.Energy kineticEnergy=translationalEnergy+rotationalEnergy;
  SI.Energy gravitationalEnergy=
    g*(topBody.m*topHeight+middleBody.m*middleHeight+bottomBody.m*bottomHeight);
  SI.Energy elasticEnergy=stiffness*(upperExtension^2+lowerExtension^2)/2;
  SI.Energy potentialEnergy=gravitationalEnergy+elasticEnergy;
  SI.Energy totalEnergy=kineticEnergy+potentialEnergy;

initial equation
  assert(blockMass > 0 and stiffness > 0 and g > 0,
    "Q192 illustrative mass, stiffness and gravity must be positive.");
  assert(blockHeight > 0 and blockWidth > 0 and blockDepth > 0,
    "Illustrative body dimensions must be positive.");
  assert(freeLength > 2*blockMass*g/stiffness+0.1,
    "The selected normal-mode amplitude must leave separated spring endpoints.");
equation
  connect(world.frame_b, topFree.frame_a);
  connect(world.frame_b, middleFree.frame_a);
  connect(world.frame_b, bottomFree.frame_a);
  connect(topFree.frame_b, topBody.frame_a);
  connect(middleFree.frame_b, middleBody.frame_a);
  connect(bottomFree.frame_b, bottomBody.frame_a);
  connect(topBody.frame_a, topLowerAttachment.frame_a);
  connect(middleBody.frame_a, middleUpperAttachment.frame_a);
  connect(middleBody.frame_a, middleLowerAttachment.frame_a);
  connect(bottomBody.frame_a, bottomUpperAttachment.frame_a);
  connect(topLowerAttachment.frame_b, upperSpring.frame_a);
  connect(middleUpperAttachment.frame_b, upperSpring.frame_b);
  connect(middleLowerAttachment.frame_b, lowerSpring.frame_a);
  connect(bottomUpperAttachment.frame_b, lowerSpring.frame_b);
  connect(world.frame_b, supportMarker.frame_a);
  assert(noEvent(upperSpring.length > 0.1 and lowerSpring.length > 0.1),
    "This post-cut demonstration excludes spring endpoint coincidence and coil contact.");
  assert(noEvent(topHeight-middleHeight > blockHeight
                 and middleHeight-bottomHeight > blockHeight),
    "This nominal vertical demonstration must stop before any body overlap.");

  annotation(
    experiment(StartTime=0, StopTime=0.8, Interval=0.001, Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Post-cut motion of Q192, PDF page 26 (printed page 6.160). Three identical blocks hang in series from two identical springs. At t=0 the top thread has already been cut. Initial spring extensions are those of the pre-cut hanging equilibrium, and all initial velocities vanish. The cutting event itself is outside this initial-value model.</p><p>All physical components are unmodified Modelica Standard Library classes. Three FreeMotion joints exert exactly zero force and torque and allow each body full free motion. Vertical motion follows from collinear initial conditions and spring attachments through the centers of mass, not from a prescribed trajectory or a vertical guide. The ideal, massless, linear springs permit both tension and compression; there is no damping, coil contact, buckling, air drag, ground contact or impact law.</p><p>All numerical masses, stiffnesses, dimensions, gravity and heights are explicitly illustrative because the problem supplies only identical masses and identical springs. The 0.8 s nominal run preserves separate bodies and positive spring lengths. The fixed support marker is only a visual reference; no thread or physical support remains connected to the falling chain. Native BodyBox and Spring animation supplies all moving geometry.</p></html>"));
end ReleasedSpringChain3D;
