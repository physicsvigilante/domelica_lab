within DomelicaLab.Examples;
model SpringPulleyFloorLiftOff2D
  "8 kg A on an inelastic hard floor, 4.5 kg B, one spring and fixed pulley"
  extends Modelica.Icons.Example;
  import SI=Modelica.Units.SI;

  parameter SI.Mass massA=8 "Given block A mass";
  parameter SI.Mass massB=4.5 "Given hanging B mass";
  parameter SI.Acceleration gravity=9.8;
  parameter SI.TranslationalSpringConstant springK=20
    "Illustrative spring stiffness; unspecified in the picture";
  parameter SI.Length springFreeLength=1.3
    "Illustrative natural spring length; initially unstretched";
  parameter SI.Height floorY=0;
  parameter SI.Height aRestHeight=0.30
    "A center when its lower face touches the floor; display convention";
  parameter SI.Height bInitialHeight=5.5;
  parameter SI.Height pulleyY=7.5;
  parameter SI.Radius pulleyRadius=0.45;
  final parameter SI.Position aX=-pulleyRadius;
  final parameter SI.Position bX=pulleyRadius;

  // MassWithStopAndFriction provides a genuine unilateral HARD stop and
  // event reinit(v,0) on impact. With its friction coefficients all zero,
  // the lower stop absorbs normal impact without imparting upward bounce.
  // It can release when the spring's upward force exceeds the weight.
  Modelica.Mechanics.Translational.Components.MassWithStopAndFriction aFloor(
    m=massA,L=0,smin=0,smax=1.5,
    F_prop=0,F_Coulomb=0,F_Stribeck=0,
    s(start=0,fixed=true),v(start=0,fixed=true))
    "A is the only moving mass with hard inelastic ground contact";
  Modelica.Mechanics.Translational.Components.Mass bMass(
    m=massB,s(start=0,fixed=true),v(start=0,fixed=true))
    "B is freely translating downward under gravity";
  Modelica.Mechanics.Translational.Components.Spring liftSpring(
    c=springK,s_rel0=0)
    "A to the massless left rope end, along common upward axis";
  Modelica.Mechanics.Translational.Sources.ConstantForce weightA(
    f_constant=-massA*gravity);
  Modelica.Mechanics.Translational.Sources.ConstantForce weightB(
    f_constant=massB*gravity);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T leftRope(
    ratio=1,useSupportR=false,useSupportT=false);
  Modelica.Mechanics.Rotational.Components.IdealGearR2T rightRope(
    ratio=1,useSupportR=false,useSupportT=false);

  // Flanges: A and spring top use UP-positive coordinates, B DOWN-positive.
  // The ideal transmission gives q_left = q_B, i.e. the left rope end
  // rises as B falls. No prescribed trajectory or browser dynamics.
  SI.Position aPosition[3]={aX,aRestHeight+aFloor.s,0};
  SI.Position bPosition[3]={bX,bInitialHeight-bMass.s,0};
  SI.Position ropeLeftPosition[3]={aX,aRestHeight+springFreeLength+leftRope.flangeT.s,0};
  SI.Position pulleyCenter[3]={0,pulleyY,0};
  SI.Position floorAnchor[3]={aX,floorY,0};
  SI.Velocity aUpSpeed=aFloor.v;
  SI.Velocity bDownSpeed=bMass.v;
  SI.Acceleration aUpAcceleration=aFloor.a;
  SI.Acceleration bDownAcceleration=bMass.a;
  SI.Position aLift=aFloor.s;
  SI.Position bDrop=bMass.s;
  SI.Position ropeLeftRise=leftRope.flangeT.s;
  SI.Length springLength=ropeLeftPosition[2]-aPosition[2];
  SI.Length springExtension=liftSpring.s_rel;
  SI.Force springForce=liftSpring.f
    "Upward tension on A from spring";
  SI.Force ropeTension=springForce
    "Ideal massless rope tension";
  SI.Force floorNormal=-aFloor.f
    "Upward normal on A; opposite MSL hard-stop internal friction reaction";
  Boolean onFloor=aFloor.stopped == -1
    "Native hard-stop geometric status, not a browser threshold";
  SI.Length routedRopeLength=(pulleyY-ropeLeftPosition[2])
    +(pulleyY-bPosition[2])+Modelica.Constants.pi*pulleyRadius;
  SI.Energy kineticEnergy=0.5*(massA*aUpSpeed*aUpSpeed+massB*bDownSpeed*bDownSpeed);
  SI.Energy springEnergy=0.5*springK*springExtension*springExtension;
  SI.Energy gravitationalEnergy=gravity*(massA*aPosition[2]+massB*bPosition[2]);
  SI.Energy totalEnergy=kineticEnergy+springEnergy+gravitationalEnergy;

initial equation
  assert(massA>0 and massB>0 and springK>0
    and springFreeLength>0 and gravity>0,
    "Masses, stiffness, natural length and gravity must be positive");
  assert(aRestHeight>floorY and bInitialHeight>floorY
    and pulleyY>bInitialHeight and
    pulleyY>aRestHeight+springFreeLength,
    "Initially valid floor, spring and fixed pulley geometry");

equation
  connect(aFloor.flange_b,liftSpring.flange_a);
  connect(weightA.flange,aFloor.flange_a);
  connect(liftSpring.flange_b,leftRope.flangeT);
  connect(leftRope.flangeR,rightRope.flangeR);
  connect(rightRope.flangeT,bMass.flange_a);
  connect(bMass.flange_b,weightB.flange);

  assert(noEvent(aPosition[2]>=aRestHeight-1e-5
      and bPosition[2]>floorY+0.2
      and bPosition[2]<pulleyY-pulleyRadius-0.2
      and ropeLeftPosition[2]<pulleyY-0.2
      and springLength>0.1),
    "Model exceeded the collision-free rope/spring/contact domain");
  assert(noEvent(ropeTension>=-1e-7),
    "Nominal ideal rope would be compressive; slack physics not modeled");

  annotation(experiment(StartTime=0,StopTime=10,Interval=0.01,Tolerance=1e-8),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Image: a fixed pulley with hanging B and an intermediate spring on the opposite strand connected to A, initially supported on the ground. Masses A=8kg, B=4.5kg are given. The spring stiffness 20 N/m, natural length 1.3m, gravity 9.8m/s2, initial rest and dimensions are illustrative assumptions, because the image supplies no stiffness or length. A is an MSL MassWithStopAndFriction with zero friction and a hard lower stop: the library resets velocity to zero at impact (coefficient of restitution zero) and allows later release when the spring upward force exceeds A's weight. B uses a standard MSL translating Mass, the vertical ideal spring uses MSL Spring, and an ideal pulley is represented by two MSL IdealGearR2T transmissions without wheel inertia. Recorded motion, contact state, energy and spring force all come from OpenModelica. There is no prescribed motion, no browser physics, and no added custom contact law. Inelastic floor impacts dissipate energy; total mechanical energy is not conserved at impact.</p></html>"));
end SpringPulleyFloorLiftOff2D;
