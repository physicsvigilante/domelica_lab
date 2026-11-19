within DomelicaLab.Examples;
model SevenPulleyTwoRopes2D
  "Native gravity-driven motion of seven ideal pulleys, two independent taut ropes"
  extends Modelica.Icons.Example;
  import SI=Modelica.Units.SI;

  // This diagram specifies no masses or dimensions. These are explicitly
  // illustrative: the geometry scale/radii are the prior native mecha result.
  parameter SI.Mass massA=2;
  parameter SI.Mass massB=7 "Large pulley plus B carriage";
  parameter SI.Mass massX=0.5 "Small moving pulley X carriage";
  parameter SI.Mass massY=0.5 "Small moving pulley Y carriage";
  parameter SI.Mass massP=4 "Middle pulley P carriage";
  parameter SI.Acceleration gravity=10;
  parameter SI.Radius radiusSmall=1
    "Reference radius from mecha's M6J seven-pulley geometry run";
  parameter SI.Radius radiusP=2 "Mecha-resolved P radius";
  parameter SI.Radius radiusBigB=2.5 "Mecha-resolved B radius";

  // Five independent vertical body positions. Positive q is UP.
  // The two separate *ideal inextensible rope* constraints are exact
  // length derivatives of the mecha-verified nine vertical rope legs.
  // Two unilateral tensions distribute ideal reciprocal rope forces.
  SI.Position qA(start=0,fixed=true);
  SI.Position qB(start=0,fixed=false);
  SI.Position qX(start=0,fixed=true);
  SI.Position qY(start=0,fixed=true);
  SI.Position qP(start=0,fixed=false);
  SI.Velocity vA(start=0,fixed=true);
  SI.Velocity vB(start=0,fixed=false);
  SI.Velocity vX(start=0,fixed=true);
  SI.Velocity vY(start=0,fixed=true);
  SI.Velocity vP(start=0,fixed=false);
  SI.Force tensionMain;
  SI.Force tensionInner;

  SI.Position f1Center[2]={0,16};
  SI.Position f2Center[2]={4,16};
  SI.Position f3Center[2]={8,16};
  SI.Position xCenter[2]={2,12+qX};
  SI.Position yCenter[2]={6,12+qY};
  SI.Position pCenter[2]={4,7+qP};
  SI.Position bCenter[2]={1.5,qB};
  SI.Position aBlock[2]={9,11+qA};
  SI.Position bBlock[2]={1.5,qB-3.5}
    "Display-only rigidly suspended B block below the large pulley";
  SI.Position xAxle[2]={2,12+qX};
  SI.Position yAxle[2]={6,12+qY};
  SI.Position pAxle[2]={4,7+qP};

  SI.Acceleration aA=der(vA);
  SI.Acceleration aB=der(vB);
  SI.Acceleration aX=der(vX);
  SI.Acceleration aY=der(vY);
  SI.Acceleration aP=der(vP);

  SI.Length mainRopeLength=
       (pCenter[2]-bCenter[2])+(f1Center[2]-bCenter[2])
      +(f1Center[2]-xCenter[2])+(f2Center[2]-xCenter[2])
      +(f2Center[2]-yCenter[2])+(f3Center[2]-yCenter[2])
      +(f3Center[2]-aBlock[2])
      +Modelica.Constants.pi*(radiusBigB+radiusSmall*5);
  SI.Length innerRopeLength=(xCenter[2]-pCenter[2])
                            +(yCenter[2]-pCenter[2])
                            +Modelica.Constants.pi*radiusP;
  SI.Energy kineticEnergy=0.5*(
       massA*vA^2+massB*vB^2+massX*vX^2+massY*vY^2+massP*vP^2);
  SI.Energy gravitationalEnergy=gravity*(
       massA*aBlock[2]+massB*bCenter[2]+massX*xCenter[2]
      +massY*yCenter[2]+massP*pCenter[2]);
  SI.Energy totalEnergy=kineticEnergy+gravitationalEnergy;

equation
  der(qA)=vA;
  der(qB)=vB;
  der(qX)=vX;
  der(qY)=vY;
  der(qP)=vP;

  // Reciprocal ideal-rope forces are -T*gradient(string length).
  massA*der(vA)=-massA*gravity+tensionMain;
  massB*der(vB)=-massB*gravity+2*tensionMain;
  massX*der(vX)=-massX*gravity+2*tensionMain-tensionInner;
  massY*der(vY)=-massY*gravity+2*tensionMain-tensionInner;
  massP*der(vP)=-massP*gravity-tensionMain+2*tensionInner;

  // main: P axle -> under large B -> over F1 -> under X -> over
  // F2 -> under Y -> over F3 -> A
  0=qP-2*qB-2*qX-2*qY-qA;
  // inner: X axle -> under P -> Y axle
  0=qX+qY-2*qP;

  assert(noEvent(tensionMain>1e-6 and tensionInner>1e-6),
         "An ideal rope became compressive; chosen motion is not taut");
  assert(noEvent(xCenter[2]<14 and yCenter[2]<14
          and pCenter[2]+radiusP<xCenter[2]-radiusSmall
          and bCenter[2]+radiusBigB<pCenter[2]-radiusP
          and aBlock[2]<15),
         "Pulley disks would collide or an ideal rope leg would collapse");

  annotation(
    experiment(StartTime=0,StopTime=1,Interval=0.005,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Two ideal inextensible ropes with seven ideal pulleys, five translating mass assemblies, and 2 independent linear length constraints. Rope coefficients follow mecha's M6J certified vertical/tangent geometry. The diagram has no masses or dimensions, so mA=2, mB=7, mX=mY=.5, mP=4, g=10 and the reference scale are illustrative. Pulleys have no rotational inertia or friction. Motion is computed natively by OpenModelica; the HTML only replays recorded positions and routed tangents/arcs using existing geometry. This is an idealized schematic with no slack or collisions.</p></html>"));
end SevenPulleyTwoRopes2D;
