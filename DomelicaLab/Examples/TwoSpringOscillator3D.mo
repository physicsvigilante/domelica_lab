within DomelicaLab.Examples;
model TwoSpringOscillator3D
  "Q90: a vertical block between two fixed, initially unstretched springs"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  parameter SI.Mass blockMass=4 "Mass specified in Q90";
  parameter SI.TranslationalSpringConstant kUpper=100;
  parameter SI.TranslationalSpringConstant kLower=300;
  parameter SI.Acceleration g=10;
  parameter SI.Length upperFreeLength=0.6
    "Illustrative free length; Q90 gives stiffness but no spring dimensions";
  parameter SI.Length lowerFreeLength=0.6 "Illustrative free length";
  parameter SI.Length blockHeight=0.2 "Illustrative vertical block dimension";
  parameter SI.Length blockWidth=0.3;
  parameter SI.Length blockDepth=0.24;
  parameter SI.Length springWidth=0.08 "Native MSL spring visualization width parameter";
  parameter SI.Length coilWidth=0.006 "Spring rendering coil width";

  inner Modelica.Mechanics.MultiBody.World world(
    g=g, n={0,-1,0}, animateWorld=false, animateGravity=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic guide(
    n={0,-1,0}, animation=false,
    stateSelect=StateSelect.always,
    s(start=0, fixed=true), v(start=0, fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox massBody(
    r={0,-blockHeight,0}, r_shape={0,blockHeight/2,0},
    lengthDirection={0,-1,0}, widthDirection={1,0,0},
    length=blockHeight, width=blockWidth, height=blockDepth,
    density=blockMass/(blockHeight*blockWidth*blockDepth),
    color={244,158,62});
  Modelica.Mechanics.MultiBody.Parts.Fixed upperAnchor(
    r={0,upperFreeLength+blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.Fixed lowerAnchor(
    r={0,-lowerFreeLength-blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation upperAttachment(
    r={0,blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation lowerAttachment(
    r={0,-blockHeight/2,0}, animation=false);
  Modelica.Mechanics.MultiBody.Forces.Spring upperSpring(
    c=kUpper, s_unstretched=upperFreeLength, m=0,
    width=springWidth, coilWidth=coilWidth, numberOfWindings=7,
    color={63,174,224});
  Modelica.Mechanics.MultiBody.Forces.Spring lowerSpring(
    c=kLower, s_unstretched=lowerFreeLength, m=0,
    width=springWidth, coilWidth=coilWidth, numberOfWindings=7,
    color={112,206,155});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape ceiling(
    shapeType="box", r_shape={-0.3,0.025,0},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=0.6, width=0.42, height=0.05, color={96,119,141});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape floor(
    shapeType="box", r_shape={-0.3,-0.025,0},
    lengthDirection={1,0,0}, widthDirection={0,0,1},
    length=0.6, width=0.42, height=0.05, color={96,119,141});

  SI.Position displacement=guide.s "Downward travel from initial unstretched position";
  SI.Velocity speed=guide.v "Signed downward velocity";
  SI.Acceleration acceleration=guide.a "Signed downward acceleration";
  SI.Position position[3]=massBody.frame_a.r_0 "Block center in world coordinates";
  SI.Velocity velocity[3]=massBody.v_0;
  SI.Length upperExtension=upperSpring.length-upperFreeLength;
  SI.Length lowerExtension=lowerSpring.length-lowerFreeLength
    "Negative values mean compression";
  SI.Force upperForce=-upperSpring.frame_b.f[2]
    "Upward force exerted by upper spring on block";
  SI.Force lowerForce=-lowerSpring.frame_a.f[2]
    "Upward force exerted by lower spring on block";
  SI.Force guideReaction[3]=-guide.frame_b.f;
  SI.Energy kineticEnergy=massBody.m*(velocity*velocity)/2;
  SI.Energy gravitationalEnergy=massBody.m*g*position[2];
  SI.Energy elasticEnergy=kUpper*upperExtension^2/2+kLower*lowerExtension^2/2;
  SI.Energy potentialEnergy=gravitationalEnergy+elasticEnergy;
  SI.Energy totalEnergy=kineticEnergy+potentialEnergy;

initial equation
  assert(blockMass > 0 and kUpper > 0 and kLower > 0 and g > 0,
    "Mass, spring constants and gravity must be positive.");
  assert(upperFreeLength > 0 and lowerFreeLength > 2*blockMass*g/(kUpper+kLower),
    "Choose free lengths that keep the nominal undamped motion away from anchor coincidence.");
equation
  connect(world.frame_b, guide.frame_a);
  connect(guide.frame_b, massBody.frame_a);
  connect(massBody.frame_a, upperAttachment.frame_a);
  connect(massBody.frame_a, lowerAttachment.frame_a);
  connect(upperAnchor.frame_b, upperSpring.frame_a);
  connect(upperSpring.frame_b, upperAttachment.frame_b);
  connect(lowerAttachment.frame_b, lowerSpring.frame_a);
  connect(lowerSpring.frame_b, lowerAnchor.frame_b);
  connect(upperAnchor.frame_b, ceiling.frame_a);
  connect(lowerAnchor.frame_b, floor.frame_a);
  assert(noEvent(upperSpring.length > 0.05 and lowerSpring.length > 0.05),
    "This ideal spring demonstration excludes anchor coincidence and coil contact.");

  annotation(
    experiment(StartTime=0, StopTime=6, Interval=0.005, Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Motion demonstration of Q90, PDF page 13. The figure has one spring above and one below the 4 kg block. Both are initially unstretched. The upper spring stretches and the lower spring compresses as gravity moves the block downward.</p><p>Two unmodified MSL MultiBody.Forces.Spring components supply the forces. A Prismatic joint restricts the intended vertical motion without adding axial force. Spring free lengths and box dimensions are declared illustrative choices; they do not replace the stated mass, stiffnesses or gravity. Springs are ideal, massless, linear and undamped; there is no coil-contact, buckling, floor collision or spring detachment model.</p></html>"));
end TwoSpringOscillator3D;
