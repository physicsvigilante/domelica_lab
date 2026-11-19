within DomelicaLab.Examples;
model AtwoodFixedPulley3D
  "JEE Mechanics chapter 6 Q68: two freely moving masses on an ideal taut string"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  // The PDF specifies only the ratio; these particular kilogram values are illustrative.
  parameter SI.Mass lightMass=13 "Light mass, kg";
  parameter SI.Mass heavyMass=15 "Heavy mass, kg";
  parameter SI.Acceleration g=9.8 "Uniform downward gravity";
  parameter SI.Length pulleyRadius=0.6 "Radius of fixed visual pulley";
  parameter SI.Height pulleyHeight=4.0;
  parameter SI.Height initialBobHeight=2.1 "Common release height";
  parameter SI.Diameter bobDiameter=0.18 "Display only, point masses have no rotational inertia";
  parameter SI.Diameter stringDiameter=0.026 "Display only";
  parameter SI.Length pulleyThickness=0.16 "Display only";

  inner Modelica.Mechanics.MultiBody.World world(
    g=g,n={0,-1,0},animateWorld=false,animateGravity=false);

  Modelica.Mechanics.MultiBody.Parts.FixedTranslation lightOrigin(
    r={-pulleyRadius,initialBobHeight,0},animation=false);
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation heavyOrigin(
    r={pulleyRadius,initialBobHeight,0},animation=false);

  // Coordinate s is UP for the light bob and DOWN for the heavy bob.
  // A stock zero-offset translational Rod couples these two positive
  // displacements. It is an ideal taut/inextensible string constraint,
  // NOT a physical bar between the bobs or a slack-string/contact law.
  Modelica.Mechanics.MultiBody.Joints.Prismatic lightSlide(
    n={0,1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.always,
    s(start=0,fixed=true),v(start=0,fixed=true));
  Modelica.Mechanics.MultiBody.Joints.Prismatic heavySlide(
    n={0,-1,0},useAxisFlange=true,animation=false,
    stateSelect=StateSelect.prefer,
    s(start=0,fixed=false),v(start=0,fixed=false));
  Modelica.Mechanics.Translational.Components.Rod tautStringConstraint(L=0)
    "Massless bilateral 1D kinematic constraint; tensile force checked during nominal run";

  Modelica.Mechanics.MultiBody.Parts.PointMass lightBob(
    m=lightMass,sphereDiameter=bobDiameter,sphereColor={69,184,230});
  Modelica.Mechanics.MultiBody.Parts.PointMass heavyBob(
    m=heavyMass,sphereDiameter=bobDiameter,sphereColor={244,164,83});

  // The display pulley does not rotate or supply mass/inertia; its sole
  // mechanical counterpart is the ideal taut-string transmission above.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape pulley(
    shapeType="cylinder",
    r_shape={0,pulleyHeight,-pulleyThickness/2},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=pulleyThickness,width=2*pulleyRadius,height=2*pulleyRadius,
    color={153,173,189});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape axle(
    shapeType="cylinder",
    r_shape={0,pulleyHeight,-pulleyThickness},
    lengthDirection={0,0,1},widthDirection={1,0,0},
    length=2*pulleyThickness,width=0.16,height=0.16,
    color={76,99,120});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape supportBeam(
    shapeType="box",
    r_shape={-0.15,pulleyHeight+pulleyRadius+0.12,0},
    lengthDirection={0,1,0},widthDirection={0,0,1},
    length=0.65,width=0.23,height=0.16,color={79,104,126});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape floor(
    shapeType="box",r_shape={-1.05,0,-0.12},
    lengthDirection={1,0,0},widthDirection={0,0,1},
    length=2.1,width=0.3,height=0.08,color={47,63,80});

  // Genuine time-varying native MSL visualizers (not renderer branches).
  // These two straight cable sections end at their actual bob frames.
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape lightStringVisual(
    shapeType="cylinder",r_shape={-pulleyRadius,pulleyHeight,0},
    lengthDirection={0,-1,0},widthDirection={0,0,1},
    length=lightStringLength,width=stringDiameter,height=stringDiameter,
    color={165,211,217});
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape heavyStringVisual(
    shapeType="cylinder",r_shape={pulleyRadius,pulleyHeight,0},
    lengthDirection={0,-1,0},widthDirection={0,0,1},
    length=heavyStringLength,width=stringDiameter,height=stringDiameter,
    color={165,211,217});

  // Passive observations, not equations of motion.
  // Read-only pulley-center geometry exposed for the generic 2D display
  // adapter. This alias does not add a physical constraint or trajectory.
  SI.Position pulleyCenter[3]={0,pulleyHeight,0};
  SI.Position lightPosition[3]=lightBob.frame_a.r_0;
  SI.Position heavyPosition[3]=heavyBob.frame_a.r_0;
  SI.Velocity lightVelocity[3]=lightBob.v_0;
  SI.Velocity heavyVelocity[3]=heavyBob.v_0;
  SI.Acceleration lightAcceleration[3]=lightBob.a_0;
  SI.Acceleration heavyAcceleration[3]=heavyBob.a_0;
  SI.Position lightDisplacement=lightSlide.s "Upward-positive displacement";
  SI.Position heavyDisplacement=heavySlide.s "Downward-positive displacement";
  SI.Velocity lightSpeed=lightSlide.v;
  SI.Velocity heavySpeed=heavySlide.v;
  SI.Force lightTension=lightSlide.axis.f
    "Positive upward force on light point mass from the 1D constraint";
  SI.Force heavyTension=-heavySlide.axis.f
    "Positive upward force on heavy point mass; opposite its downward axis";
  SI.Force lightStringOnBob[3]={0,lightTension,0};
  SI.Force heavyStringOnBob[3]={0,heavyTension,0};
  SI.Length lightStringLength=pulleyHeight-lightPosition[2];
  SI.Length heavyStringLength=pulleyHeight-heavyPosition[2];
  SI.Length stringLength=lightStringLength+heavyStringLength
    +Modelica.Constants.pi*pulleyRadius "Diagnostic, not an imposed constraint";
  SI.Energy kineticEnergy=
    (lightBob.m*(lightVelocity*lightVelocity)
     +heavyBob.m*(heavyVelocity*heavyVelocity))/2;
  SI.Energy gravitationalEnergy=
    g*(lightBob.m*lightPosition[2]+heavyBob.m*heavyPosition[2]);
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy;

initial equation
  assert(lightMass>0 and heavyMass>lightMass and g>0,
    "The example requires unequal positive masses with the chosen light side rising.");
  assert(pulleyRadius>0 and pulleyHeight>initialBobHeight
    and bobDiameter>0 and stringDiameter>0 and pulleyThickness>0,
    "The visual pulley/string geometry needs positive dimensions.");
equation
  connect(world.frame_b,lightOrigin.frame_a);
  connect(world.frame_b,heavyOrigin.frame_a);
  connect(lightOrigin.frame_b,lightSlide.frame_a);
  connect(heavyOrigin.frame_b,heavySlide.frame_a);
  connect(lightSlide.frame_b,lightBob.frame_a);
  connect(heavySlide.frame_b,heavyBob.frame_a);
  connect(lightSlide.axis,tautStringConstraint.flange_a);
  connect(heavySlide.axis,tautStringConstraint.flange_b);

  connect(world.frame_b,pulley.frame_a);
  connect(world.frame_b,axle.frame_a);
  connect(world.frame_b,supportBeam.frame_a);
  connect(world.frame_b,floor.frame_a);
  connect(world.frame_b,lightStringVisual.frame_a);
  connect(world.frame_b,heavyStringVisual.frame_a);

  assert(noEvent(lightStringLength>0.25 and heavyStringLength>0.25
    and lightPosition[2]>0.2 and heavyPosition[2]>0.2),
    "Nominal window ended: this model does not simulate bob-pulley or floor impacts.");
  assert(noEvent(lightTension>0 and heavyTension>0),
    "Taut-string approximation excludes slack or compression.");

  annotation(
    experiment(StartTime=0,StopTime=2,Interval=0.002,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Mechanics I, Newton's Laws, chapter 6 Q68 (PDF page 10, printed 6.144). Two unequal freely translating point masses are linked by a light inextensible string over a massless smooth fixed pulley. Positive slider directions are opposite: lighter bob up, heavier bob down. A stock MSL Translational.Components.Rod with zero offset joins their translational drive flanges and enforces equal positive slider displacements; neither trajectory or tension is prescribed. This is a bilateral ideal constraint, valid only while its reaction remains tensile. No mechanism-specific equations of motion are introduced.</p><p>The chosen 13 kg and 15 kg masses and g=9.8 m/s2 reproduce the problem's 13/15 ratio and a 1.4 m rise of the light bob after 2 seconds. Only the mass ratio is given in the question; kilogram scale, heights, radii and visual diameters are illustrative. The wheel and changing-length string shapes are true native Modelica visual objects, but wheel rotation, string material, angular inertia, sag, slip, slack, collisions, and friction are not modeled. Stop before a bob reaches the wheel or ground. Weight overlays derive from saved native masses and gravity; tension comes from native prismatic axis connector flows.</p></html>"));
end AtwoodFixedPulley3D;
