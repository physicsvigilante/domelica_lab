within DomelicaLab.Examples;
model MovingWedge3D
  "Q106 motion: a block slides on a freely translating ideal wedge"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  parameter SI.Mass wedgeMass=2 "Illustrative prism mass; Q106 is symbolic";
  parameter SI.Mass blockMass=1 "Illustrative block mass";
  parameter SI.Angle inclineAngle=Modelica.Constants.pi/6;
  parameter SI.Acceleration g=10 "Illustrative gravity";
  parameter SI.Length inclineLength=4 "Finite illustrated sliding surface";
  parameter SI.Length startAlong=3.6 "Initial block center measured uphill from surfaceOrigin";
  parameter SI.Length blockLength=0.3 "Block length along incline";
  parameter SI.Length blockHeight=0.18 "Block thickness normal to incline";
  parameter SI.Length blockWidth=0.28;
  parameter SI.Length deckThickness=0.08;
  parameter SI.Length deckWidth=0.7;
  parameter SI.Length baseHeight=0.12;
  parameter SI.Length supportWidth=0.1;
  parameter SI.Position surfaceOrigin[3]={0,0.22,0}
    "Lower endpoint of the deck's upper face, in the translating wedge frame";

  final parameter Real uphill[3](each unit="1")={cos(inclineAngle),sin(inclineAngle),0};
  final parameter Real planeNormal[3](each unit="1")={-sin(inclineAngle),cos(inclineAngle),0};
  final parameter SI.Length baseLength=inclineLength*cos(inclineAngle)+0.3;
  final parameter SI.Position wedgeCenter[3]={inclineLength*cos(inclineAngle)/2,baseHeight/2,0};
  final parameter SI.Position initialBlockCenter[3]=
    surfaceOrigin+startAlong*uphill+blockHeight/2*planeNormal;
  final parameter SI.Position lowerSupportX=0.35*cos(inclineAngle);
  final parameter SI.Position upperSupportX=(inclineLength-0.2)*cos(inclineAngle);
  final parameter SI.Length lowerSupportHeight=
    surfaceOrigin[2]+lowerSupportX*tan(inclineAngle)-deckThickness/cos(inclineAngle)-baseHeight;
  final parameter SI.Length upperSupportHeight=
    surfaceOrigin[2]+upperSupportX*tan(inclineAngle)-deckThickness/cos(inclineAngle)-baseHeight;

  inner Modelica.Mechanics.MultiBody.World world(
    g=g, n={0,-1,0}, animateWorld=false, animateGravity=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic groundGuide(
    n={1,0,0}, animation=false, stateSelect=StateSelect.always,
    s(start=0,fixed=true), v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation wedgeCenterFrame(
    r=wedgeCenter, animation=false);
  Modelica.Mechanics.MultiBody.Parts.BodyBox wedgeBody(
    r={baseLength,0,0}, r_shape={-baseLength/2,0,0},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=baseLength, width=deckWidth, height=baseHeight,
    density=wedgeMass/(baseLength*deckWidth*baseHeight),
    color={75,102,127});
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation initialBlockFrame(
    r=initialBlockCenter, animation=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic relativeGuide(
    n=-uphill, animation=false, stateSelect=StateSelect.always,
    s(start=0,fixed=true), v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox massBody(
    r=blockLength*uphill, r_shape=-blockLength/2*uphill,
    lengthDirection=uphill, widthDirection={0,0,1},
    length=blockLength, width=blockWidth, height=blockHeight,
    density=blockMass/(blockLength*blockWidth*blockHeight),
    color={244,158,62});

  // The frame-shaped drawing is a rigid translating support. All of its mass
  // is represented by wedgeBody; these standard visualizers add no mass.
  // Its inertia distribution cannot affect the constrained pure translation.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape deck(
    shapeType="box", r_shape=surfaceOrigin-deckThickness/2*planeNormal,
    lengthDirection=uphill, widthDirection={0,0,1},
    length=inclineLength, width=deckWidth, height=deckThickness,
    color={75,102,127});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape lowerSupport(
    shapeType="box", r_shape={lowerSupportX,baseHeight,0},
    lengthDirection={0,1,0}, widthDirection={0,0,1},
    length=lowerSupportHeight, width=deckWidth-0.08, height=supportWidth,
    color={63,85,105});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape upperSupport(
    shapeType="box", r_shape={upperSupportX,baseHeight,0},
    lengthDirection={0,1,0}, widthDirection={0,0,1},
    length=upperSupportHeight, width=deckWidth-0.08, height=supportWidth,
    color={63,85,105});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape ground(
    shapeType="box", r_shape={-0.6,-0.04,0},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=inclineLength*cos(inclineAngle)+2.1, width=1.1, height=0.08,
    color={36,49,63});

  SI.Position displacement=relativeGuide.s "Block travel relative to wedge, positive downhill";
  SI.Velocity speed=relativeGuide.v;
  SI.Acceleration acceleration=relativeGuide.a;
  SI.Position wedgeDisplacement=groundGuide.s "Wedge displacement in world +x";
  SI.Velocity wedgeSpeed=groundGuide.v;
  SI.Acceleration wedgeAcceleration=groundGuide.a;
  SI.Position blockPosition[3]=massBody.frame_a.r_0 "Block center in world coordinates";
  SI.Position wedgePosition[3]=wedgeBody.frame_a.r_0 "Wedge mass center in world coordinates";
  SI.Velocity blockVelocity[3]=massBody.v_0;
  SI.Velocity wedgeVelocity[3]=wedgeBody.v_0;
  SI.Force guideForceOnBlock[3]=-relativeGuide.frame_b.f;
  SI.Force guideForceOnWedge[3]=-relativeGuide.frame_a.f;
  SI.Force normalReaction=guideForceOnBlock*planeNormal;
  SI.Force groundReaction[3]=-groundGuide.frame_b.f;
  SI.Power guidePower=guideForceOnBlock*blockVelocity+guideForceOnWedge*wedgeVelocity
    "Net power of the internal ideal relative-motion constraint";
  SI.Momentum horizontalMomentum=
    wedgeBody.m*wedgeVelocity[1]+massBody.m*blockVelocity[1];
  SI.Position centerOfMass[3]=
    (wedgeBody.m*wedgePosition+massBody.m*blockPosition)/(wedgeBody.m+massBody.m);
  SI.Energy kineticEnergy=
    (wedgeBody.m*(wedgeVelocity*wedgeVelocity)+massBody.m*(blockVelocity*blockVelocity))/2;
  SI.Energy gravitationalEnergy=g*(wedgeBody.m*wedgePosition[2]+massBody.m*blockPosition[2]);
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy
    "Mechanical energy of the two bodies; extensions add their own elastic energy monitor";

initial equation
  assert(wedgeMass>0 and blockMass>0 and g>0,
    "Positive masses and gravity are required.");
  assert(inclineAngle>0 and inclineAngle<Modelica.Constants.pi/2,
    "The incline must lie strictly between zero and 90 degrees.");
  assert(inclineLength>blockLength and blockLength>0 and blockHeight>0 and blockWidth>0
    and deckThickness>0 and deckWidth>=blockWidth and baseHeight>0 and supportWidth>0,
    "Positive display dimensions and a block narrower than the deck are required.");
  assert(startAlong>=blockLength/2 and startAlong<=inclineLength-blockLength/2,
    "The initial complete block footprint must lie on the finite deck.");
  assert(lowerSupportHeight>0 and upperSupportHeight>0 and abs(surfaceOrigin[1])<1e-12 and abs(surfaceOrigin[3])<1e-12,
    "The illustrated ramp requires positive upright lengths and a lower surface origin on its centerline.");
equation
  connect(world.frame_b,groundGuide.frame_a);
  connect(groundGuide.frame_b,wedgeCenterFrame.frame_a);
  connect(wedgeCenterFrame.frame_b,wedgeBody.frame_a);
  connect(groundGuide.frame_b,initialBlockFrame.frame_a);
  connect(initialBlockFrame.frame_b,relativeGuide.frame_a);
  connect(relativeGuide.frame_b,massBody.frame_a);
  connect(groundGuide.frame_b,deck.frame_a);
  connect(groundGuide.frame_b,lowerSupport.frame_a);
  connect(groundGuide.frame_b,upperSupport.frame_a);
  connect(world.frame_b,ground.frame_a);
  assert(noEvent(startAlong-displacement>=blockLength/2-1e-6 and
    startAlong-displacement<=inclineLength-blockLength/2+1e-6),
    "The block footprint has left the finite deck; no end impact or exit motion is modeled.");
  assert(noEvent(normalReaction>=-1e-6 and groundReaction[2]>=-1e-6),
    "A contact reaction became tensile; this ideal constrained-contact example does not model separation.");

  annotation(
    experiment(StartTime=0,StopTime=1,Interval=0.0025,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Motion exploration of Q106, PDF page 14. The problem describes a block on a prism, both on frictionless surfaces, and supplies symbolic masses and angle. All numerical masses, dimensions, angle, gravity and initial conditions here are declared illustrative choices.</p><p>Two standard Prismatic joints and two BodyBox components supply the coupled dynamics. The block moves downhill relative to the wedge while the wedge recoils in world +x. No acceleration or trajectory is imposed. The visible deck, base and uprights represent one rigid support with total mass wedgeMass; its center and inertia choice cannot alter this pure translation.</p><p>The finite deck and ground have no collision behavior. The joints enforce ideal bilateral constraints; reaction and footprint guards restrict the nominal demonstration to maintained compressive contact, without modeling separation, end stops, impacts or friction. The nominal 1-second run stops before the block leaves the deck.</p></html>"));
end MovingWedge3D;
