within DomelicaLab.Examples;
model FourPulleyTwoRope2D
  "Diagram: A drives P1 through rope S1; P1 drives P2-P3-P4 and B through rope S2"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  // The diagram gives a_A = 6 m/s2 left. Other masses and dimensions below
  // are explicit illustrative choices, not values inferred from the picture.
  parameter SI.Mass massA=2 "Illustrative mass for horizontally guided block A";
  parameter SI.Mass massB=3 "Illustrative vertically guided block B";
  parameter SI.Acceleration g=9.8;
  parameter SI.Acceleration givenLeftAcceleration=6
    "Diagram-prescribed acceleration of A, positive toward the left";
  parameter SI.Position wallX=-9;
  parameter SI.Position initialAX=-4.5;
  parameter SI.Position initialP1X=-1.5;
  parameter SI.Position p2X=0;
  parameter SI.Height p2Y=5;
  parameter SI.Height p4Y=6.2;
  parameter SI.Height initialBY=1.25;
  parameter SI.Length p3HeightAboveB=1;
  parameter SI.Radius r1=0.2;
  parameter SI.Radius r2=0.4;
  parameter SI.Radius r3=0.4;
  parameter SI.Radius r4=0.35;
  parameter SI.Length wheelThickness=0.1 "Display only";
  final parameter SI.Position p3X=p2X+r2+r3;
  final parameter SI.Position p4X=p3X+r3+r4;
  final parameter SI.Position bX=p4X+r4;
  final parameter SI.Height p1Y=p2Y+r2;
  final parameter SI.Height aY=p1Y-r1;

  inner Modelica.Mechanics.MultiBody.World world(
    g=g,n={0,-1,0},animateWorld=false,animateGravity=false);

  // A and P1 slide left on horizontal guides, B moves vertically upward.
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation aOrigin(
    r={initialAX,aY,0},animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation p1Origin(
    r={initialP1X,p1Y,0},animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation bOrigin(
    r={bX,initialBY,0},animation=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic aSlide(
    n={-1,0,0},useAxisFlange=true,animation=false,
    s(start=0,fixed=false),v(start=0,fixed=false));
  Modelica.Mechanics.MultiBody.Joints.Prismatic p1Slide(
    n={-1,0,0},useAxisFlange=true,animation=false,
    s(start=0,fixed=false),v(start=0,fixed=false));
  Modelica.Mechanics.MultiBody.Joints.Prismatic bSlide(
    n={0,1,0},useAxisFlange=true,animation=false,
    s(start=0,fixed=false),v(start=0,fixed=false));
  Modelica.Mechanics.MultiBody.Parts.PointMass bodyA(
    m=massA,sphereDiameter=0.19,sphereColor={81,186,226});
  Modelica.Mechanics.MultiBody.Parts.PointMass bodyB(
    m=massB,sphereDiameter=0.22,sphereColor={242,160,89});

  // Only A is driven: the textbook specifies its acceleration.
  // This stock source integrates prescribed acceleration using initial
  // zero position/velocity. The remaining two motions are solved by
  // the massless rope transmissions, not by trajectory tables.
  Modelica.Blocks.Sources.Constant accelerationCommand(k=givenLeftAcceleration);
  Modelica.Mechanics.Translational.Sources.Accelerate prescribedA;

  // Rope S1: world anchor -> *moving* P1 -> block A.
  // Horizontal lengths: (xP1-xWall)+(xP1-xA), giving sA=2*sP1.
  // Rope S2: P1 axle -> fixed P2 -> *moving* P3 -> fixed P4 -> block B.
  // Its horizontal extension cancels three upward-moving vertical legs:
  // sP1=3*sB. The shafts are abstract massless transmission coordinates,
  // NOT physical wheel rotation. All four elements are stock MSL.
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s1AtA(
    ratio=1,useSupportR=false,useSupportT=false);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s1AtP1(
    ratio=2,useSupportR=false,useSupportT=false);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s2AtP1(
    ratio=1,useSupportR=false,useSupportT=false);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s2AtB(
    ratio=3,useSupportR=false,useSupportT=false);

  // The four wheels contribute visual geometry only; P1 follows its own
  // massless slider, P3 follows the B frame with a fixed spatial offset.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape wheelP1(
    shapeType="cylinder",r_shape={0,0,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*r1,height=2*r1,color={143,171,188});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape wheelP2(
    shapeType="cylinder",r_shape={p2X,p2Y,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*r2,height=2*r2,color={143,171,188});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape wheelP3(
    shapeType="cylinder",
    r_shape={p3X-bX,p3HeightAboveB,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*r3,height=2*r3,color={143,171,188});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape wheelP4(
    shapeType="cylinder",r_shape={p4X,p4Y,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*r4,height=2*r4,color={143,171,188});

  // All following aliases are passive native observations.
  SI.Position wallAnchor[3]={wallX,p1Y+r1,0};
  SI.Position aPosition[3]=bodyA.frame_a.r_0;
  SI.Position bPosition[3]=bodyB.frame_a.r_0;
  SI.Position p1Center[3]=p1Slide.frame_b.r_0;
  SI.Position p2Center[3]={p2X,p2Y,0};
  SI.Position p3Center[3]={p3X,bPosition[2]+p3HeightAboveB,0};
  SI.Position p4Center[3]={p4X,p4Y,0};
  SI.Velocity aVelocity[3]=bodyA.v_0;
  SI.Velocity bVelocity[3]=bodyB.v_0;
  SI.Acceleration aAcceleration[3]=bodyA.a_0;
  SI.Acceleration bAcceleration[3]=bodyB.a_0;

  SI.Position aLeftDisplacement=aSlide.s;
  SI.Position p1LeftDisplacement=p1Slide.s;
  SI.Position bRise=bSlide.s;
  SI.Velocity aLeftSpeed=aSlide.v;
  SI.Velocity p1LeftSpeed=p1Slide.v;
  SI.Velocity bUpSpeed=bSlide.v;
  SI.Acceleration aLeftAcceleration=aSlide.a;
  SI.Acceleration p1LeftAcceleration=p1Slide.a;
  SI.Acceleration bUpAcceleration=bSlide.a;

  // Flange flow signs are checked against an independent Newton oracle.
  // Rope S1 pulls A right. Rope S2 pulls the P1 axle right and provides
  // three upward supporting legs to B/P3 considered as one guided assembly.
  SI.Force tensionS1=s1AtA.flangeT.f;
  SI.Force tensionS2=s2AtP1.flangeT.f;
  SI.Force leftDriveForce=-prescribedA.flange.f;
  SI.Force aRopeForce[3]={tensionS1,0,0};
  SI.Force aExternalForce[3]={-leftDriveForce,0,0};
  SI.Force bRopeForce[3]={0,3*tensionS2,0};
  SI.Force p1NetRopeForce=tensionS2-2*tensionS1;

  SI.Length ropeS1Length=
    (p1Center[1]-wallAnchor[1])+(p1Center[1]-aPosition[1])
    +Modelica.Constants.pi*r1;
  SI.Length ropeS2Length=
    (p2Center[1]-p1Center[1])
    +(p2Center[2]-p3Center[2])
    +(p4Center[2]-p3Center[2])
    +(p4Center[2]-bPosition[2])
    +Modelica.Constants.pi*(r2/2+r3+r4);
  SI.Energy kineticEnergy=
    (massA*(aVelocity*aVelocity)+massB*(bVelocity*bVelocity))/2;
  SI.Energy potentialEnergy=
    g*(massA*aPosition[2]+massB*bPosition[2]);
  SI.Energy totalEnergy=kineticEnergy+potentialEnergy;
  SI.Power externalPower=leftDriveForce*aLeftSpeed;
  SI.Energy driveWork=leftDriveForce*aLeftDisplacement
    "For this constant-force nominal run; observation, not an actuator law";

initial equation
  assert(massA>0 and massB>0 and givenLeftAcceleration>0 and g>0,
    "This example requires positive masses, gravity and given leftward acceleration.");
  assert(r1>0 and r2>0 and r3>0 and r4>0 and wheelThickness>0,
    "Pulley display dimensions must be positive.");
  assert(wallX<initialAX and initialAX<initialP1X and initialP1X<p2X
      and p4Y>p2Y and p2Y>initialBY+p3HeightAboveB,
    "Initial anchored rope routes must be nondegenerate.");

equation
  connect(world.frame_b,aOrigin.frame_a);
  connect(world.frame_b,p1Origin.frame_a);
  connect(world.frame_b,bOrigin.frame_a);
  connect(aOrigin.frame_b,aSlide.frame_a);
  connect(p1Origin.frame_b,p1Slide.frame_a);
  connect(bOrigin.frame_b,bSlide.frame_a);
  connect(aSlide.frame_b,bodyA.frame_a);
  connect(bSlide.frame_b,bodyB.frame_a);

  connect(accelerationCommand.y,prescribedA.a_ref);
  connect(prescribedA.flange,aSlide.axis);
  connect(aSlide.axis,s1AtA.flangeT);
  connect(p1Slide.axis,s1AtP1.flangeT);
  connect(p1Slide.axis,s2AtP1.flangeT);
  connect(bSlide.axis,s2AtB.flangeT);
  connect(s1AtA.flangeR,s1AtP1.flangeR);
  connect(s2AtP1.flangeR,s2AtB.flangeR);

  connect(p1Slide.frame_b,wheelP1.frame_a);
  connect(world.frame_b,wheelP2.frame_a);
  connect(bSlide.frame_b,wheelP3.frame_a);
  connect(world.frame_b,wheelP4.frame_a);

  assert(noEvent(tensionS1>0 and tensionS2>0),
    "This nominal bilateral transmission excludes slack/compression.");
  assert(noEvent(aPosition[1]-wallX>0.25
      and p1Center[1]-aPosition[1]>r1+0.25
      and p1Center[1]-wallX>r1+0.25
      and p2X-p1Center[1]>r2+0.25
      and p2Y-p3Center[2]>r2+r3+0.25
      and p4Y-p3Center[2]>r3+r4+0.25
      and p4Y-bPosition[2]>r4+0.25
      and bPosition[2]>0.25),
    "Nominal trajectory exceeded the ideal route/contact-free window.");

  annotation(
    experiment(StartTime=0,StopTime=1,Interval=0.001,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Multi-pulley textbook diagram, interpreted as two independently taut massless ropes. Rope S1 is anchored at the left wall and runs around moving pulley P1 to block A. Rope S2 is attached to P1's axle, redirected by fixed P2, wrapped around moving P3 (rigidly attached to block B), over fixed P4, and ends at block B. The given acceleration of A is 6 m/s2 left, imposed by an MSL Translational.Sources.Accelerate. All other accelerations and native connector reactions follow from two pairs of MSL IdealGearR2T with ratios 1:2 and 1:3, encoding the separate rope-length constraints. Expected a_B=1 m/s2 upward. No custom equations of motion, prescribed B trajectory, or geometry-derived forces.</p><p>Masses, wheel radii, locations and recording duration are explicitly illustrative. The wheels do not rotate or contribute mass/inertia. Each taut rope is represented by a bilateral ideal lossless transmission; no slack, slips, impacts, friction, wheel torques or elasticity. Point masses and prismatic guides suppress body rotation. The 2D rope paths and arcs are derived from the native positions/radii in a separate visualization layer, not used by the solver.</p></html>"));
end FourPulleyTwoRope2D;
