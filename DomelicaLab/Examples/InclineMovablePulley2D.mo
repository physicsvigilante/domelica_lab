within DomelicaLab.Examples;
model InclineMovablePulley2D
  "Inclined block A, massless moving pulley C, fixed redirect and hanging block B"
  extends Modelica.Icons.Example;
  import SI=Modelica.Units.SI;

  // The picture gives 30 degrees, but no masses/friction values.
  // The chosen values are an explicitly illustrative, frictionless case.
  parameter SI.Mass massA=2 "Illustrative block A mass";
  parameter SI.Mass massB=3 "Illustrative block B mass";
  parameter SI.Acceleration g=9.8;
  parameter SI.Angle slopeAngle=DomelicaLab.Examples.M6FResolvedGeometry.slopeAngle;
  parameter SI.Radius movingRadius=DomelicaLab.Examples.M6FResolvedGeometry.movingRadius;
  parameter SI.Radius topRadius=DomelicaLab.Examples.M6FResolvedGeometry.topRadius;
  parameter SI.Length anchorSeparation=DomelicaLab.Examples.M6FResolvedGeometry.anchorSeparation;
  parameter SI.Length blockGap=DomelicaLab.Examples.M6FResolvedGeometry.blockGap;
  parameter SI.Length redirectDistance=DomelicaLab.Examples.M6FResolvedGeometry.redirectDistance;
  parameter SI.Length bInitialLeg=DomelicaLab.Examples.M6FResolvedGeometry.bInitialLeg;
  parameter SI.Length schematicRampOffset=0.25;
  parameter SI.Length wheelThickness=0.1;
  final parameter Real u[3]={cos(slopeAngle),sin(slopeAngle),0};
  final parameter Real n[3]={-sin(slopeAngle),cos(slopeAngle),0};
  final parameter SI.Position cInitial[3]=DomelicaLab.Examples.M6FResolvedGeometry.cInitial;
  final parameter SI.Position aInitial[3]=cInitial-blockGap*u;
  final parameter SI.Position anchorInitial[3]=cInitial-anchorSeparation*u+movingRadius*n;
  final parameter SI.Position topInitial[3]=cInitial+redirectDistance*u-topRadius*n;
  final parameter SI.Position bInitial[3]={topInitial[1]+topRadius,topInitial[2]-bInitialLeg,0};
  final parameter SI.Position rampStart[3]=cInitial-3*u-schematicRampOffset*n;
  final parameter SI.Position rampEnd[3]=cInitial+1.6*u-schematicRampOffset*n;
  final parameter SI.Position rampFoot[3]={rampEnd[1],rampStart[2],0};

  inner Modelica.Mechanics.MultiBody.World world(
    g=g,n={0,-1,0},animateWorld=false,animateGravity=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation aOrigin(
    r=aInitial,animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation cOrigin(
    r=cInitial,animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation bOrigin(
    r=bInitial,animation=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic aSlide(
    n=u,useAxisFlange=true,animation=false,
    stateSelect=StateSelect.always,s(start=0,fixed=true),v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Joints.Prismatic cSlide(
    n=u,useAxisFlange=true,animation=false,
    stateSelect=StateSelect.prefer,s(start=0,fixed=false),v(start=0,fixed=false));
  Modelica.Mechanics.MultiBody.Joints.Prismatic bSlide(
    n={0,-1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.prefer,s(start=0,fixed=false),v(start=0,fixed=false));
  Modelica.Mechanics.MultiBody.Parts.PointMass blockA(
    m=massA,sphereDiameter=0.18,sphereColor={72,185,225});
  Modelica.Mechanics.MultiBody.Parts.PointMass blockB(
    m=massB,sphereDiameter=0.20,sphereColor={241,169,109});

  // Two independent, massless, ideal ropes:
  // S1: left anchor -> around moving C pulley -> block A.
  // The changing straight legs give s_A=2*s_C (upslope).
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s1A(
    ratio=1,useSupportR=false,useSupportT=false);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s1C(
    ratio=2,useSupportR=false,useSupportT=false);
  // S2: C axle -> over fixed top pulley -> block B.
  // The changing legs give s_C=s_B (C upslope, B downward).
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s2C(
    ratio=1,useSupportR=false,useSupportT=false);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T s2B(
    ratio=1,useSupportR=false,useSupportT=false);

  // Native rigid guide geometry for rendering, not an incline contact solver.
  // The prismatic axis keeps A on the inclined guide; the ground triangle is
  // only an explicitly schematic outline, owned by the native model.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape cWheel(
    shapeType="cylinder",r_shape={0,0,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*movingRadius,height=2*movingRadius,
    color={155,173,190});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape topWheel(
    shapeType="cylinder",r_shape={topInitial[1],topInitial[2],-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*topRadius,height=2*topRadius,
    color={155,173,190});

  // Passive geometry/kinematics exported to the existing 2D route adapter.
  SI.Position aPosition[3]=blockA.frame_a.r_0;
  SI.Position bPosition[3]=blockB.frame_a.r_0;
  SI.Position cPosition[3]=cSlide.frame_b.r_0;
  SI.Position aRopeEndpoint[3]=aPosition-movingRadius*n;
  SI.Position anchorPosition[3]=anchorInitial;
  SI.Position fixedPulleyCenter[3]=topInitial;
  SI.Position rampOutlineStart[3]=rampStart;
  SI.Position rampOutlineEnd[3]=rampEnd;
  SI.Position rampOutlineFoot[3]=rampFoot;
  SI.Velocity aVelocity[3]=blockA.v_0;
  SI.Velocity bVelocity[3]=blockB.v_0;
  SI.Acceleration aAcceleration[3]=blockA.a_0;
  SI.Acceleration bAcceleration[3]=blockB.a_0;
  SI.Position aRise=aSlide.s;
  SI.Position cRise=cSlide.s;
  SI.Position bDrop=bSlide.s;
  SI.Velocity aUpSpeed=aSlide.v;
  SI.Velocity cUpSpeed=cSlide.v;
  SI.Velocity bDownSpeed=bSlide.v;
  SI.Acceleration aUpAcceleration=aSlide.a;
  SI.Acceleration cUpAcceleration=cSlide.a;
  SI.Acceleration bDownAcceleration=bSlide.a;
  SI.Force tensionS1=aSlide.axis.f;
  SI.Force tensionS2=-bSlide.axis.f;
  SI.Force cNetRopeForce=tensionS2-2*tensionS1;
  SI.Force aRopeForce[3]=tensionS1*u;
  SI.Force bRopeForce[3]={0,tensionS2,0};
  SI.Length ropeS1Length=
    sum((cPosition-anchorPosition).*u)
    +sum((cPosition-aRopeEndpoint).*u)
    +Modelica.Constants.pi*movingRadius;
  SI.Length ropeS2Length=
    sum((fixedPulleyCenter-cPosition).*u)
    +(fixedPulleyCenter[2]-bPosition[2])
    +(2*Modelica.Constants.pi/3)*topRadius;
  SI.Energy kineticEnergy=
    (massA*(aVelocity*aVelocity)+massB*(bVelocity*bVelocity))/2;
  SI.Energy gravitationalEnergy=g*(massA*aPosition[2]+massB*bPosition[2]);
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy;

initial equation
  assert(massA>0 and massB>0 and g>0,
    "Illustrative masses and gravity must be positive.");
  assert(abs(slopeAngle-Modelica.Constants.pi/6)<1e-8,
    "This bounded display route is authored for a 30-degree incline.");
  assert(redirectDistance>0 and blockGap>0 and anchorSeparation>0
      and movingRadius>0 and topRadius>0,
    "Valid separated pulley geometry is required.");
equation
  connect(world.frame_b,aOrigin.frame_a);
  connect(world.frame_b,cOrigin.frame_a);
  connect(world.frame_b,bOrigin.frame_a);
  connect(aOrigin.frame_b,aSlide.frame_a);
  connect(cOrigin.frame_b,cSlide.frame_a);
  connect(bOrigin.frame_b,bSlide.frame_a);
  connect(aSlide.frame_b,blockA.frame_a);
  connect(bSlide.frame_b,blockB.frame_a);
  connect(aSlide.axis,s1A.flangeT);
  connect(cSlide.axis,s1C.flangeT);
  connect(cSlide.axis,s2C.flangeT);
  connect(bSlide.axis,s2B.flangeT);
  connect(s1A.flangeR,s1C.flangeR);
  connect(s2C.flangeR,s2B.flangeR);
  connect(cSlide.frame_b,cWheel.frame_a);
  connect(world.frame_b,topWheel.frame_a);

  assert(noEvent(tensionS1>0 and tensionS2>0),
    "The nominal bilateral rope model excludes slack and compression.");
  assert(noEvent(blockGap+cSlide.s-aSlide.s>0.25
    and bInitialLeg+bSlide.s>0.35
    and redirectDistance-cSlide.s>0.35
    and anchorSeparation+cSlide.s>0.35),
    "Stop before an inadmissible straight-leg or wheel-contact geometry.");
  annotation(
    experiment(StartTime=0,StopTime=1.0,Interval=0.002,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>30-degree incline figure. Two ropes: one is anchored at the left, wraps around a moving massless pulley C and ends on block A. A second rope is attached to C's axle, passes over the fixed pulley at the summit and ends on block B. Ideal inextensible ropes create sA=2 sC along the slope and sB=sC downward. Two stock MSL IdealGearR2T pairs encode these ratios and reciprocal reaction forces, while MSL Prismatic joints and PointMass components supply gravitational dynamics. No trajectories or accelerations are prescribed.</p><p>Model demonstration masses 2kg (A) and 3kg (B) are explicitly illustrative because the diagram only gives 30 degrees. No pulley inertia, rope mass, friction, collision, slack, rolling, wheel spin or contact-switching is modeled. The incline triangle is recorded display geometry; guide motion is native.</p></html>"));
end InclineMovablePulley2D;
