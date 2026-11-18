within DomelicaLab.Examples;
model CartPendulumSpring3D
  "A spring-mounted sliding carriage responds to an undriven hanging pendulum"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;
  import Frames = Modelica.Mechanics.MultiBody.Frames;

  parameter SI.Mass cartMass=2;
  parameter SI.Mass bobMass=1;
  parameter SI.Length rodLength=1;
  parameter SI.TranslationalSpringConstant springStiffness=20;
  parameter SI.Length springFreeLength=1.1;
  parameter SI.Acceleration g=10;
  parameter SI.Angle initialAngle=35*Modelica.Constants.pi/180
    "Release angle from vertically downward, positive toward world +x";
  parameter SI.Length cartLength=0.5;
  parameter SI.Length cartWidth=0.32;
  parameter SI.Length cartHeight=0.2;
  parameter SI.Position cartCenterHeight=1.6;
  parameter SI.Diameter bobDiameter=0.18
    "Display diameter only: PointMass has zero rotational inertia";
  parameter SI.Diameter rodDiameter=0.035
    "Display diameter only: FixedTranslation has no mass or inertia";

  inner Modelica.Mechanics.MultiBody.World world(
    g=g, n={0,-1,0}, animateWorld=false, animateGravity=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation railHeight(
    r={0,cartCenterHeight,0}, animation=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic cartGuide(
    n={1,0,0}, animation=false, stateSelect=StateSelect.always,
    s(start=0,fixed=true), v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox cartBody(
    r={cartLength,0,0}, r_shape={-cartLength/2,0,0},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=cartLength, width=cartWidth, height=cartHeight,
    density=cartMass/(cartLength*cartWidth*cartHeight),
    color={75,137,173});
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation pivotOffset(
    r={0,-cartHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Joints.Revolute hinge(
    n={0,0,1}, useAxisFlange=false, stateSelect=StateSelect.always,
    phi(start=initialAngle,fixed=true), w(start=0,fixed=true),
    cylinderLength=0.42, cylinderDiameter=0.1, cylinderColor={204,218,228});
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation rod(
    r={0,-rodLength,0}, shapeType="cylinder",
    lengthDirection={0,-1,0}, widthDirection={0,0,1},
    length=rodLength, width=rodDiameter, height=rodDiameter,
    color={210,223,232});
  Modelica.Mechanics.MultiBody.Parts.PointMass bob(
    m=bobMass, sphereDiameter=bobDiameter, sphereColor={245,163,62});

  Modelica.Mechanics.MultiBody.Parts.FixedTranslation wallAnchor(
    r={-cartLength/2-springFreeLength,cartCenterHeight,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation springAttachment(
    r={-cartLength/2,0,0}, animation=false);
  Modelica.Mechanics.MultiBody.Forces.Spring wallSpring(
    c=springStiffness, s_unstretched=springFreeLength, m=0,
    width=0.06, coilWidth=0.005, numberOfWindings=12, color={68,192,186});

  // These native drawings are stationary, massless scenery. The Prismatic
  // joint supplies a bilateral ideal guide; these shapes add no contact law.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape wall(
    shapeType="box", r_shape={-cartLength/2-springFreeLength-0.04,0,0},
    lengthDirection={0,1,0}, widthDirection={0,0,1},
    length=1.84, width=0.6, height=0.08, color={68,84,101});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape rail(
    shapeType="box", r_shape={-1.43,cartCenterHeight,-0.25},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=2.63, width=0.08, height=0.08, color={85,102,120});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape railPost(
    shapeType="box", r_shape={1.16,0,-0.25},
    lengthDirection={0,1,0}, widthDirection={0,0,1},
    length=1.64, width=0.08, height=0.08, color={68,84,101});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape floor(
    shapeType="box", r_shape={-1.65,-0.03,0},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=3.0, width=0.9, height=0.06, color={35,48,63});

  // All visual observations below are aliases of native component results.
  SI.Position cartDisplacement=cartGuide.s;
  SI.Velocity cartSpeed=cartGuide.v;
  SI.Acceleration cartAcceleration=cartGuide.a;
  SI.Angle pendulumAngle=hinge.phi;
  SI.AngularVelocity pendulumSpeed=hinge.w;
  SI.AngularAcceleration pendulumAcceleration=hinge.a;
  SI.Position cartPosition[3]=cartBody.frame_a.r_0;
  SI.Position pivotPosition[3]=hinge.frame_a.r_0;
  SI.Position bobPosition[3]=bob.frame_a.r_0;
  SI.Velocity cartVelocity[3]=cartBody.v_0;
  SI.Velocity bobVelocity[3]=bob.v_0;
  SI.Acceleration bobAcceleration[3]=bob.a_0;
  SI.AngularVelocity cartAngularVelocity[3]=cartBody.body.w_a;
  SI.Position springAnchorPosition[3]=wallSpring.frame_a.r_0;
  SI.Position springCartPosition[3]=wallSpring.frame_b.r_0;
  SI.Length springLength=wallSpring.length;
  SI.Length springExtension=wallSpring.length-wallSpring.s_unstretched;
  SI.Force springForce=wallSpring.f "Positive extension force; cart force is its negative";
  SI.Force springForceOnCart[3]=-Frames.resolve1(wallSpring.frame_b.R,wallSpring.frame_b.f);
  SI.Force rodForceOnBob[3]=Frames.resolve1(bob.frame_a.R,bob.frame_a.f);
  SI.Force pendulumForceOnCart[3]=-Frames.resolve1(hinge.frame_a.R,hinge.frame_a.f);
  SI.Force railReaction[3]=-Frames.resolve1(cartGuide.frame_b.R,cartGuide.frame_b.f);
  SI.Torque railTorque[3]=-Frames.resolve1(cartGuide.frame_b.R,cartGuide.frame_b.t);
  SI.Force rodTension=rodForceOnBob*
    Frames.resolve1(rod.frame_a.R,{0,1,0})
    "Axial reaction toward the pivot; the rigid rod can transmit either sign";
  SI.Power rodPower=rodForceOnBob*bobVelocity+pendulumForceOnCart*cartVelocity;
  SI.Power guidePower=railReaction*cartVelocity+railTorque*cartAngularVelocity;
  SI.Power springPower=springForceOnCart*cartVelocity;
  SI.Momentum horizontalMomentum=cartBody.m*cartVelocity[1]+bob.m*bobVelocity[1];
  SI.Momentum springImpulse(start=0,fixed=true)
    "Diagnostic integral of the external spring force; does not drive the mechanics";
  SI.Position centerOfMass[3]=(cartBody.m*cartPosition+bob.m*bobPosition)/(cartBody.m+bob.m);
  SI.Energy kineticEnergy=(cartBody.m*(cartVelocity*cartVelocity)+bob.m*(bobVelocity*bobVelocity))/2;
  SI.Energy gravitationalEnergy=g*(cartBody.m*cartPosition[2]+bob.m*bobPosition[2]);
  SI.Energy elasticEnergy=wallSpring.c*springExtension^2/2;
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy+elasticEnergy;

initial equation
  assert(cartMass>0 and bobMass>0 and rodLength>0 and springStiffness>0 and springFreeLength>0 and g>0,
    "Positive masses, rod length, spring stiffness, free length and gravity are required.");
  assert(cartLength>0 and cartWidth>0 and cartHeight>0 and bobDiameter>0 and rodDiameter>0,
    "Positive visual dimensions are required.");
  assert(cartCenterHeight-cartHeight/2-rodLength-bobDiameter/2>0,
    "The bob's full downward swing must clear the illustrated floor.");
  assert(abs(initialAngle)<Modelica.Constants.pi/2,
    "This displayed release is below the pivot; no cart collision is modeled.");
equation
  connect(world.frame_b,railHeight.frame_a);
  connect(railHeight.frame_b,cartGuide.frame_a);
  connect(cartGuide.frame_b,cartBody.frame_a);
  connect(cartGuide.frame_b,pivotOffset.frame_a);
  connect(pivotOffset.frame_b,hinge.frame_a);
  connect(hinge.frame_b,rod.frame_a);
  connect(rod.frame_b,bob.frame_a);
  connect(world.frame_b,wallAnchor.frame_a);
  connect(wallAnchor.frame_b,wallSpring.frame_a);
  connect(cartGuide.frame_b,springAttachment.frame_a);
  connect(springAttachment.frame_b,wallSpring.frame_b);
  connect(world.frame_b,wall.frame_a);
  connect(world.frame_b,rail.frame_a);
  connect(world.frame_b,railPost.frame_a);
  connect(world.frame_b,floor.frame_a);
  der(springImpulse)=springForceOnCart[1];
  assert(noEvent(springLength>0.05),
    "The spring endpoints approached each other; this demonstration excludes zero-length line forces.");
  assert(noEvent(bobPosition[2]+bobDiameter/2<cartPosition[2]-cartHeight/2),
    "The visible bob entered the cart height region; collision physics is not modeled.");
  assert(noEvent(cartPosition[1]-cartLength/2>-1.35 and cartPosition[1]+cartLength/2<1.12),
    "The carriage left the displayed rail span; no endpoint impacts are modeled.");

  annotation(
    experiment(StartTime=0,StopTime=6,Interval=0.005,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>A new composition of standard MSL MultiBody components: a BodyBox carriage constrained by a horizontal Prismatic joint, an unactuated Revolute joint, a massless FixedTranslation rod, an ideal PointMass bob, and a massless wall-anchored Spring. The carriage is released at spring equilibrium while the pendulum starts 35 degrees from downward. Both mechanical degrees of freedom are solved by OpenModelica; no position or acceleration is prescribed.</p><p>World x is horizontal, y is upward and z is normal to the motion plane. Positive hinge angle carries the downward rod toward world +x. The bob's sphere and the rod cylinder are native drawings; their display diameters add neither bob rotational inertia nor rod mass. The finite cart has its actual density-derived mass and inertia, but its ideal guide prevents rotation.</p><p>The overhead rail is a bilateral guide, not a unilateral contact surface. Its constraint reactions may act in either direction. The spring is ideal, massless and undamped and has no coil contact or extension stop. No friction, collision, rod flexibility or rod mass is modeled. The illustrative geometry and release are guarded to keep the bob below the cart and the carriage within the displayed span.</p><p>The wall spring exerts an external horizontal force on the cart-plus-bob subsystem. Horizontal momentum changes by its impulse; it is not conserved. Total mechanical energy, including spring energy, is conserved because the wall is fixed and the guide does no work. springImpulse is only a diagnostic integral and does not impose a mechanical law.</p></html>"));
end CartPendulumSpring3D;
