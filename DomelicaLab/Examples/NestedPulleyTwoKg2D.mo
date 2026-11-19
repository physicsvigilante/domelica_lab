within DomelicaLab.Examples;
model NestedPulleyTwoKg2D
  "A and B are 2 kg; continuous rope A-C-B-top-C axle, C carriage mass explicit"
  extends Modelica.Icons.Example;
  import SI=Modelica.Units.SI;

  parameter SI.Mass massA=2 "Block A, kg (given)";
  parameter SI.Mass massB=2 "Block B, kg (given)";
  parameter SI.Mass carrierMassC=1
    "Illustrative inertia of moving C axle/carriage: NOT specified by the image";
  parameter SI.Acceleration g=9.8;
  parameter SI.Radius radiusC=0.32;
  parameter SI.Radius radiusB=0.36;
  parameter SI.Radius radiusTop=0.52;
  parameter SI.Height topHeight=5;
  parameter SI.Height initialCHeight=2.8;
  parameter SI.Height initialAHeight=1.1;
  parameter SI.Height initialBHeight=0.9;
  parameter SI.Length pulleyAboveB=0.7;
  parameter SI.Length wheelThickness=0.12;
  final parameter SI.Position xC=-0.4;
  final parameter SI.Position xB=0.28;
  final parameter SI.Position xTop=0.12;
  final parameter SI.Position xA=xC-radiusC;

  inner Modelica.Mechanics.MultiBody.World world(
    g=g,n={0,-1,0},animateWorld=false,animateGravity=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation aOrigin(
    r={xA,initialAHeight,0},animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation bOrigin(
    r={xB,initialBHeight,0},animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation cOrigin(
    r={xC,initialCHeight,0},animation=false);

  Modelica.Mechanics.MultiBody.Joints.Prismatic aSlide(
    n={0,-1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.always,
    s(start=0,fixed=true),v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Joints.Prismatic bSlide(
    n={0,-1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.always,
    s(start=0,fixed=true),v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Joints.Prismatic cSlide(
    n={0,-1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.prefer,
    s(start=0,fixed=false),v(start=0,fixed=false));

  Modelica.Mechanics.MultiBody.Parts.PointMass bodyA(
    m=massA,sphereDiameter=0.16,sphereColor={69,184,230});
  Modelica.Mechanics.MultiBody.Parts.PointMass bodyB(
    m=massB,sphereDiameter=0.18,sphereColor={244,164,83});
  Modelica.Mechanics.MultiBody.Parts.PointMass carriageC(
    m=carrierMassC,sphereDiameter=0.12,sphereColor={155,183,201});
  DomelicaLab.Components.IdealLinearRope3 continuousRope(
    weights={1,2,-1},offset=0)
    "A down + two B down - C down = 0; single continuous rope";

  // Native MSL wheel geometry: non-rotating, massless visual sheaves.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape cPulley(
    shapeType="cylinder",r_shape={0,0,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*radiusC,height=2*radiusC,
    color={153,173,189});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape bPulley(
    shapeType="cylinder",r_shape={0,pulleyAboveB,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*radiusB,height=2*radiusB,
    color={153,173,189});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape topPulley(
    shapeType="cylinder",r_shape={xTop,topHeight,-wheelThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=wheelThickness,width=2*radiusTop,height=2*radiusTop,
    color={153,173,189});

  // Read-only native positions and signals for the generic geometry/viewer.
  SI.Position aPosition[3]=bodyA.frame_a.r_0;
  SI.Position bPosition[3]=bodyB.frame_a.r_0;
  SI.Position cPosition[3]=carriageC.frame_a.r_0;
  SI.Position bWheelCenter[3]={xB,bPosition[2]+pulleyAboveB,0};
  SI.Position fixedWheelCenter[3]={xTop,topHeight,0};
  SI.Velocity aVelocity[3]=bodyA.v_0;
  SI.Velocity bVelocity[3]=bodyB.v_0;
  SI.Velocity cVelocity[3]=carriageC.v_0;
  SI.Acceleration aAcceleration[3]=bodyA.a_0;
  SI.Acceleration bAcceleration[3]=bodyB.a_0;
  SI.Acceleration cAcceleration[3]=carriageC.a_0;
  SI.Position aDrop=aSlide.s;
  SI.Position bDrop=bSlide.s;
  SI.Position cDrop=cSlide.s;
  SI.Velocity aDownSpeed=aSlide.v;
  SI.Velocity bDownSpeed=bSlide.v;
  SI.Velocity cDownSpeed=cSlide.v;
  SI.Acceleration aDownAcceleration=aSlide.a;
  SI.Acceleration bDownAcceleration=bSlide.a;
  SI.Acceleration cDownAcceleration=cSlide.a;
  SI.Force ropeTension=continuousRope.reaction;
  SI.Force tensionOnA[3]={0,ropeTension,0};
  SI.Force tensionOnB[3]={0,2*ropeTension,0};
  SI.Force tensionOnC[3]={0,-ropeTension,0};
  SI.Length ropeLength=
    (cPosition[2]-aPosition[2])
    +(cPosition[2]-bWheelCenter[2])
    +(topHeight-bWheelCenter[2])
    +(topHeight-cPosition[2])
    +Modelica.Constants.pi*(radiusC+radiusB+radiusTop)
    "Native position diagnostic, not a second constraint";
  SI.Power ropePower= aSlide.axis.f*aSlide.v
    +bSlide.axis.f*bSlide.v+cSlide.axis.f*cSlide.v;
  SI.Energy kineticEnergy=0.5*(
    massA*(aVelocity*aVelocity)
    +massB*(bVelocity*bVelocity)
    +carrierMassC*(cVelocity*cVelocity));
  SI.Energy gravitationalEnergy=g*(
    massA*aPosition[2]+massB*bPosition[2]+carrierMassC*cPosition[2]);
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy;

initial equation
  assert(massA>0 and massB>0 and carrierMassC>0 and g>0,
    "Two 2 kg blocks and a positive illustrative C carriage mass are required.");
  assert(radiusC>0 and radiusB>0 and radiusTop>0
     and abs((xC+radiusC)-(xB-radiusB))<1e-8
     and abs((xB+radiusB)-(xTop+radiusTop))<1e-8
     and abs((xTop-radiusTop)-xC)<1e-8,
    "Native vertical tangent routing must match the chosen pulley radii.");
equation
  connect(world.frame_b,aOrigin.frame_a);
  connect(world.frame_b,bOrigin.frame_a);
  connect(world.frame_b,cOrigin.frame_a);
  connect(aOrigin.frame_b,aSlide.frame_a);
  connect(bOrigin.frame_b,bSlide.frame_a);
  connect(cOrigin.frame_b,cSlide.frame_a);
  connect(aSlide.frame_b,bodyA.frame_a);
  connect(bSlide.frame_b,bodyB.frame_a);
  connect(cSlide.frame_b,carriageC.frame_a);
  connect(aSlide.axis,continuousRope.flangeA);
  connect(bSlide.axis,continuousRope.flangeB);
  connect(cSlide.axis,continuousRope.flangeC);
  connect(cSlide.frame_b,cPulley.frame_a);
  connect(bSlide.frame_b,bPulley.frame_a);
  connect(world.frame_b,topPulley.frame_a);
  assert(noEvent(ropeTension>0),
    "Single-rope bilateral model requires positive tension; massless C limit is not tensile.");
  assert(noEvent(cPosition[2]-aPosition[2]>0.5
    and cPosition[2]-bWheelCenter[2]>0.5
    and topHeight-cPosition[2]>0.5
    and topHeight-bWheelCenter[2]>0.5
    and aPosition[2]>0.5 and bPosition[2]>0.5),
    "Nominal trajectory stops before floor, pulley or body collision.");

  annotation(experiment(StartTime=0,StopTime=0.30,Interval=0.001,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Literal single-rope tracing of user diagram: one end at A; up over movable C, down under B's movable sheave, up over the fixed top sheave, down to the axle of C. Blocks A and B are both 2 kg as supplied. The diagram omits mass of C and other geometric quantities. This runnable demonstration explicitly assigns a 1 kg ideal translational mass to the C carriage, while its sheave has no rotational inertia. The sole rope is a reusable three-coordinate ideal bilateral constraint, weights {1,2,-1} for downward-positive joint coordinates. MSL PointMass and Prismatic components compute the gravity-driven motion and tension. No trajectories or forces are prescribed.</p><p>In the limit of truly massless C, force balance at C requires zero tension for this literal string routing: one strand pulls C's axle up while two strands pull its rim down. This makes a tensile taut-rope interpretation degenerate and prevents inferring one unique positive-tension numerical answer from the picture and A/B masses alone. The 1 kg carriage mass is an explicit illustrative hypothesis, not silently inferred from the picture.</p></html>"));
end NestedPulleyTwoKg2D;
