within DomelicaLab.Examples;
model SpringWedge3D
  "A spring carried by a freely sliding wedge returns the block uphill"
  extends MovingWedge3D(startAlong=2.5);
  import SI = Modelica.Units.SI;

  parameter SI.TranslationalSpringConstant springStiffness=10
    "Illustrative internal spring stiffness; not a value supplied by Q106";
  parameter SI.Length anchorAlong=3.8
    "Spring anchor position along the moving inclined deck";
  final parameter SI.Length springFreeLength=
    anchorAlong-startAlong-blockLength/2
    "Chosen so the spring is unstretched at the initial position";
  parameter SI.Length springWidth=0.06
    "Native MSL spring visualization width parameter";
  parameter SI.Length coilWidth=0.005;

  Modelica.Mechanics.MultiBody.Parts.FixedTranslation upperSpringAnchor(
    r=surfaceOrigin+anchorAlong*uphill+blockHeight/2*planeNormal,
    animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation blockUpperAttachment(
    r=blockLength/2*uphill, animation=false);
  Modelica.Mechanics.MultiBody.Forces.Spring internalSpring(
    c=springStiffness, s_unstretched=springFreeLength, m=0,
    width=springWidth, coilWidth=coilWidth, numberOfWindings=10,
    color={70,184,215});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape anchorMount(
    shapeType="box", lengthDirection=uphill, widthDirection={0,0,1},
    length=0.08, width=0.22, height=blockHeight,
    color={134,169,187})
    "Massless display of a spring mount rigidly carried by the wedge";

  SI.Length springLength=internalSpring.length;
  SI.Length springExtension=springLength-springFreeLength;
  SI.Force springForce=internalSpring.f "Positive tension in the internal spring";
  SI.Energy elasticEnergy=springStiffness*springExtension^2/2;
  SI.Energy composedEnergy=totalEnergy+elasticEnergy
    "Both bodies' kinetic and gravitational energies plus spring energy";

initial equation
  assert(springStiffness > 0 and springFreeLength > 0.05,
    "Choose a positive stiffness and an anchor uphill of the initial block face.");
  assert(anchorAlong >= 0 and anchorAlong+0.08 <= inclineLength,
    "The complete spring mount must lie on the finite moving deck.");
equation
  connect(groundGuide.frame_b, upperSpringAnchor.frame_a);
  connect(massBody.frame_a, blockUpperAttachment.frame_a);
  connect(upperSpringAnchor.frame_b, internalSpring.frame_a);
  connect(internalSpring.frame_b, blockUpperAttachment.frame_b);
  connect(upperSpringAnchor.frame_b, anchorMount.frame_a);
  assert(noEvent(internalSpring.length > 0.05),
    "This ideal spring composition excludes coincident anchors and coil contact.");

  annotation(
    experiment(StartTime=0, StopTime=6, Interval=0.005, Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>A separate composition of MovingWedge3D with two MSL FixedTranslation components and one unmodified MSL MultiBody.Forces.Spring. Both spring endpoints belong to the two-body system: the upper anchor moves with the wedge, while the lower endpoint is on the block's uphill face. The spring is initially unstretched. No force, position or velocity is prescribed.</p><p>All numerical parameters are illustrative. With the default masses, angle, gravity and spring stiffness, the block's relative motion is bounded between 0 and 1 m downhill from its initial position. The wedge moves and returns with it. This is an ideal massless linear spring without damping, detachment, buckling or wire contact. The inherited prismatic joints maintain the geometric constraints; their reactions are checked separately to confirm that the nominal motion remains compatible with compressive contact.</p></html>"));
end SpringWedge3D;
