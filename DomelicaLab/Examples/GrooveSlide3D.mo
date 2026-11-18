within DomelicaLab.Examples;
model GrooveSlide3D
  "Q31: gravity-driven motion along a diagonal groove on an inclined plane"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  parameter SI.Angle planeAngle=Modelica.Constants.pi/6
    "Plane inclination to horizontal (Q31: 30 degrees)";
  parameter SI.Angle grooveAngle=Modelica.Constants.pi/6
    "Groove angle to the horizontal contour OX within the plane";
  parameter SI.Length grooveLength=5 "Distance A to O";
  parameter SI.Acceleration g=10 "Gravity specified in Q31";
  parameter SI.Mass blockMass=1
    "Illustrative mass; Q31 does not specify it and ideal acceleration is independent of it";
  parameter SI.Length blockLength=0.32 "Illustrative block length along groove";
  parameter SI.Length blockWidth=0.28 "Illustrative block width";
  parameter SI.Length blockHeight=0.18 "Illustrative block thickness normal to plane";
  parameter SI.Length plateThickness=0.08 "Visual plate thickness";
  parameter SI.Length grooveThickness=0.004 "Raised guide strip thickness for distinct native surfaces";
  parameter SI.Length margin=0.35 "Visual margin around the finite groove";

  final parameter Real uphill[3](each unit="1")={cos(planeAngle),sin(planeAngle),0};
  final parameter Real across[3](each unit="1")={0,0,1};
  final parameter Real planeNormal[3](each unit="1")={-sin(planeAngle),cos(planeAngle),0};
  final parameter Real grooveDirection[3](each unit="1")=
    sin(grooveAngle)*uphill + cos(grooveAngle)*across
    "Unit vector O to A; groove lies in the inclined plane";
  final parameter Real grooveSide[3](each unit="1")=cross(planeNormal,grooveDirection);
  final parameter SI.Position startPosition[3]=
    grooveLength*grooveDirection + (blockHeight/2+grooveThickness)*planeNormal;
  final parameter SI.Length plateLength=grooveLength*sin(grooveAngle)+2*margin;
  final parameter SI.Length plateWidth=grooveLength*cos(grooveAngle)+2*margin;

  inner Modelica.Mechanics.MultiBody.World world(
    g=g, n={0,-1,0}, animateWorld=false, animateGravity=false);
  Modelica.Mechanics.MultiBody.Parts.Fixed startFrame(
    r=startPosition, animation=false);
  Modelica.Mechanics.MultiBody.Joints.Prismatic guide(
    n=-grooveDirection, animation=false,
    stateSelect=StateSelect.always,
    s(start=0, fixed=true), v(start=0, fixed=true));
  Modelica.Mechanics.MultiBody.Parts.BodyBox massBody(
    r=blockLength*grooveDirection,
    r_shape=-blockLength/2*grooveDirection,
    lengthDirection=grooveDirection, widthDirection=grooveSide,
    length=blockLength, width=blockWidth, height=blockHeight,
    density=blockMass/(blockLength*blockWidth*blockHeight),
    color={244,158,62});

  // These stock visualizers describe the fixed plane and guide. The stock
  // Prismatic supplies the ideal mechanical constraint; there is no contact solver.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape plane(
    shapeType="box", lengthDirection=uphill, widthDirection=across,
    r_shape=-margin*uphill + (plateWidth/2-margin)*across
      - plateThickness/2*planeNormal,
    length=plateLength, width=plateWidth, height=plateThickness,
    color={75,102,127});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape groove(
    shapeType="box", lengthDirection=grooveDirection, widthDirection=grooveSide,
    r_shape=grooveThickness/2*planeNormal,
    length=grooveLength, width=0.4, height=grooveThickness,
    color={36,49,63});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape railLeft(
    shapeType="box", lengthDirection=grooveDirection, widthDirection=grooveSide,
    r_shape=0.19*grooveSide+0.03*planeNormal,
    length=grooveLength, width=0.04, height=0.06,
    color={144,173,195});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape railRight(
    shapeType="box", lengthDirection=grooveDirection, widthDirection=grooveSide,
    r_shape=-0.19*grooveSide+0.03*planeNormal,
    length=grooveLength, width=0.04, height=0.06,
    color={144,173,195});

  SI.Position displacement=guide.s "Travel from A toward O, positive downhill";
  SI.Velocity speed=guide.v "Signed velocity from A toward O";
  SI.Acceleration acceleration=guide.a;
  SI.Position position[3]=massBody.frame_a.r_0 "Block center in world coordinates";
  SI.Velocity velocity[3]=massBody.v_0;
  SI.Force guideReaction[3]=-guide.frame_b.f
    "Constraint force on the block, resolved in the world-parallel joint frame";
  SI.Force normalReaction=guideReaction*planeNormal;
  SI.Force sideReaction=guideReaction*grooveSide;
  SI.Power reactionPower=guideReaction*velocity;
  SI.Energy kineticEnergy=massBody.m*(velocity*velocity)/2;
  SI.Energy potentialEnergy=massBody.m*g*position[2]
    "Gravitational energy relative to world y=0";
  SI.Energy totalEnergy=kineticEnergy+potentialEnergy;

initial equation
  assert(planeAngle > 0 and planeAngle < Modelica.Constants.pi/2,
    "The demonstration requires an upward inclined plane.");
  assert(grooveAngle > 0 and grooveAngle < Modelica.Constants.pi/2,
    "The demonstration requires a descending groove with both in-plane components.");
  assert(grooveLength > 0 and g > 0 and blockMass > 0,
    "Length, gravity and block mass must be positive.");
equation
  connect(startFrame.frame_b, guide.frame_a);
  connect(guide.frame_b, massBody.frame_a);
  connect(world.frame_b, plane.frame_a);
  connect(world.frame_b, groove.frame_a);
  connect(world.frame_b, railLeft.frame_a);
  connect(world.frame_b, railRight.frame_a);
  assert(noEvent(displacement >= -1e-6 and displacement <= grooveLength+1e-6),
    "Outside finite groove: stop at arrival or extend the guide explicitly; no end impact is modeled.");

  annotation(
    experiment(StartTime=0, StopTime=2, Interval=0.005, Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Motion demonstration of Q31, PDF page 5. The plane is inclined 30 degrees to horizontal; the groove is 30 degrees from a horizontal contour within the plane. The Prismatic joint and BodyBox determine motion under World gravity. No trajectory is imposed.</p><p>The nominal run ends when the block center has travelled 5 m, at 2 s. This is the end of the valid trajectory, not an impact or an inelastic stop. Change the run stop time if changing the geometry. Body mass and rendering dimensions are illustrative because the problem does not give them. The fixed plane and rail shapes have no collision behavior.</p></html>"));
end GrooveSlide3D;
