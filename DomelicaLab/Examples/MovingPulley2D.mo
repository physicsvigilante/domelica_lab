within DomelicaLab.Examples;
model MovingPulley2D
  "One moving pulley and a fixed redirect, composed from stock MSL components"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  parameter SI.Mass loadMass=4 "Translating load and carriage concentrated at the moving axle";
  parameter SI.Mass counterweightMass=3;
  parameter SI.Acceleration g=9.8;
  parameter SI.Length pulleyRadius=0.45 "Display radius, not a rotational inertia";
  parameter SI.Height fixedHeight=5;
  parameter SI.Height initialPulleyHeight=2;
  parameter SI.Height initialCounterweightHeight=3.4;

  inner Modelica.Mechanics.MultiBody.World world(
    g=g,n={0,-1,0},animateWorld=false,animateGravity=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation loadOrigin(
    r={0,initialPulleyHeight,0},animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation counterweightOrigin(
    r={3*pulleyRadius,initialCounterweightHeight,0},animation=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic loadSlide(
    n={0,1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.always,
    s(start=0,fixed=true),v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Joints.Prismatic counterweightSlide(
    n={0,-1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.prefer,
    s(start=0,fixed=false),v(start=0,fixed=false));
  Modelica.Mechanics.MultiBody.Parts.PointMass load(
    m=loadMass,sphereDiameter=0.16,sphereColor={69,184,230});
  Modelica.Mechanics.MultiBody.Parts.PointMass counterweight(
    m=counterweightMass,sphereDiameter=0.16,sphereColor={244,164,83});

  // A massless ideal transmission encodes the taut rope's 2:1 displacement
  // ratio and reciprocal force ratio. The shared auxiliary shaft has no
  // inertia and is NOT a wheel rotation. No trajectories or forces are imposed.
  // MSL 4.1.0 has IdealGearR2T, not a translational IdealGear class.
  Modelica.Mechanics.Rotational.Components.IdealGearR2T loadTransmission(
    ratio=2,useSupportR=false,useSupportT=false);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T counterweightTransmission(
    ratio=1,useSupportR=false,useSupportT=false);

  Modelica.Mechanics.MultiBody.Visualizers.FixedShape movingWheel(
    shapeType="cylinder",r_shape={0,0,-0.06},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=0.12,width=2*pulleyRadius,height=2*pulleyRadius,
    color={153,173,189});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape fixedWheel(
    shapeType="cylinder",r_shape={2*pulleyRadius,fixedHeight,-0.06},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=0.12,width=2*pulleyRadius,height=2*pulleyRadius,
    color={153,173,189});

  // Passive native observations. Geometry consumes these recorded columns.
  SI.Position anchorPosition[3]={-pulleyRadius,fixedHeight,0};
  SI.Position movingPulleyCenter[3]=loadSlide.frame_b.r_0;
  SI.Position fixedPulleyCenter[3]={2*pulleyRadius,fixedHeight,0};
  SI.Position loadPosition[3]=load.frame_a.r_0;
  SI.Position counterweightPosition[3]=counterweight.frame_a.r_0;
  SI.Velocity loadVelocity[3]=load.v_0;
  SI.Velocity counterweightVelocity[3]=counterweight.v_0;
  SI.Acceleration loadAcceleration[3]=load.a_0;
  SI.Acceleration counterweightAcceleration[3]=counterweight.a_0;
  SI.Position loadDisplacement=loadSlide.s "Upward positive";
  SI.Position counterweightDisplacement=counterweightSlide.s "Downward positive";
  SI.Velocity loadSpeed=loadSlide.v;
  SI.Velocity counterweightSpeed=counterweightSlide.v;
  SI.Force loadSupportForce=loadSlide.axis.f "Upward axle force, twice rope tension";
  SI.Force counterweightTension=-counterweightSlide.axis.f "Upward, opposite the downward joint axis";
  SI.Force ropeTension=counterweightTension;
  SI.Force loadSupportOnBody[3]={0,loadSupportForce,0};
  SI.Force counterweightStringOnBody[3]={0,counterweightTension,0};
  SI.Length stringLength=
    (anchorPosition[2]-movingPulleyCenter[2])
    +(fixedPulleyCenter[2]-movingPulleyCenter[2])
    +(fixedPulleyCenter[2]-counterweightPosition[2])
    +2*Modelica.Constants.pi*pulleyRadius
    "Diagnostic length of the three vertical legs and two semicircular wraps";
  SI.Energy kineticEnergy=
    (load.m*(loadVelocity*loadVelocity)
     +counterweight.m*(counterweightVelocity*counterweightVelocity))/2;
  SI.Energy gravitationalEnergy=
    g*(load.m*loadPosition[2]+counterweight.m*counterweightPosition[2]);
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy;

initial equation
  assert(loadMass>0 and counterweightMass>0 and g>0,
    "Positive masses and gravity are required.");
  assert(pulleyRadius>0 and fixedHeight>initialPulleyHeight
    and fixedHeight>initialCounterweightHeight,
    "Pulley radius and initial vertical rope legs must be positive.");
equation
  connect(world.frame_b,loadOrigin.frame_a);
  connect(world.frame_b,counterweightOrigin.frame_a);
  connect(loadOrigin.frame_b,loadSlide.frame_a);
  connect(counterweightOrigin.frame_b,counterweightSlide.frame_a);
  connect(loadSlide.frame_b,load.frame_a);
  connect(counterweightSlide.frame_b,counterweight.frame_a);
  connect(loadSlide.axis,loadTransmission.flangeT);
  connect(counterweightSlide.axis,counterweightTransmission.flangeT);
  connect(loadTransmission.flangeR,counterweightTransmission.flangeR);
  connect(loadSlide.frame_b,movingWheel.frame_a);
  connect(world.frame_b,fixedWheel.frame_a);

  assert(noEvent(ropeTension>0 and loadSupportForce>0),
    "This bilateral ideal transmission is valid only while the rope stays taut.");
  assert(noEvent(fixedHeight-movingPulleyCenter[2]>0.25
    and fixedHeight-counterweightPosition[2]>0.25
    and movingPulleyCenter[2]-pulleyRadius>0.2
    and counterweightPosition[2]>0.2),
    "Nominal window ended: slack, contact and floor/pulley impacts are not modeled.");

  annotation(
    experiment(StartTime=0,StopTime=1.2,Interval=0.002,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>M6C-2D-B: an ideal rope is anchored at the ceiling, wraps below a moving pulley, passes over a fixed redirect, and ends at a counterweight. The load and carriage are a point mass at the moving axle. Motion is confined to the world XY plane by vertical prismatic joints. Two stock massless MSL IdealGearR2T elements enforce counterweight displacement = 2*load displacement, with positive axes downward and upward respectively. Their connector flows supply the reciprocal force ratio. The shared auxiliary shaft is a mathematical transmission coordinate, not either wheel's physical rotation.</p><p>Gravity, inertia, motion and tension are solved natively. The declared string length and energy are observations only. The 2D route manifest describes the recorded geometry; it does not supply the physical constraint. Both wheels are ideal massless guides without modeled spin, angular inertia, friction, sag, slip, slack or collisions. The moving assembly's translational mass is loadMass. Default values are an illustrative verification case, not attributed to a textbook problem.</p></html>"));
end MovingPulley2D;
