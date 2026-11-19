within DomelicaLab.Examples;
model FreeRodElasticBallImpact2D
  "One perfectly elastic end impact: equal-mass ball and freely moving slender rod"
  extends Modelica.Icons.Example;
  import SI = Modelica.Units.SI;

  parameter SI.Mass mass=1 "Same mass for ball and rod; illustrative 1 kg";
  parameter SI.Length rodLength=2 "Illustrative rod length";
  parameter SI.Length rodWidth=0.04 "Schematic contact thickness";
  parameter SI.Radius ballRadius=0.10 "Schematic ball radius";
  parameter SI.Velocity v0=2 "Illustrative ball initial horizontal speed";
  parameter Real restitution=1 "Perfectly elastic: e=1";
  final parameter SI.MomentOfInertia I=mass*rodLength^2/12
    "Uniform slender rod about its center";
  final parameter SI.Length h=rodLength/2;

  SI.Position ballX(start=-1.2,fixed=true);
  SI.Velocity ballV(start=v0,fixed=true,stateSelect=StateSelect.always);
  SI.Position rodX(start=0,fixed=true);
  SI.Velocity rodVx(start=0,fixed=true,stateSelect=StateSelect.always);
  SI.Angle rodAngle(start=0,fixed=true);
  SI.AngularVelocity rodOmega(start=0,fixed=true,stateSelect=StateSelect.always);
  discrete Boolean impacted(start=false,fixed=true);
  discrete SI.Time impactTime(start=-1,fixed=true);

  // A frictionless horizontal blow at the rod's lower end. The impulse
  // equation uses restitution and the rod's actual central moment of inertia,
  // not a prescribed post-collision velocity or animation trajectory.
  SI.Velocity relativeContactSpeed=ballV-rodVx-h*rodOmega;
  Real candidateImpulse(unit="N.s")=
    (1+restitution)*relativeContactSpeed/
    (1/mass+1/mass+h*h/I);

  // All geometry exposed by Modelica itself: the HTML only projects these.
  SI.Position ballCenter[2]={ballX,0};
  SI.Position rodCenter[2]={rodX,h};
  SI.Position rodLower[2]={rodX+h*sin(rodAngle),h-h*cos(rodAngle)};
  SI.Position rodUpper[2]={rodX-h*sin(rodAngle),h+h*cos(rodAngle)};
  SI.Energy kineticEnergy=0.5*mass*ballV^2
    +0.5*mass*rodVx^2+0.5*I*rodOmega^2;

initial equation
  assert(mass>0 and rodLength>0 and v0>0
    and ballRadius>0 and rodWidth>0 and restitution==1,
    "This demo requires positive parameters and e=1");
equation
  der(ballX)=ballV;
  der(rodX)=rodVx;
  der(rodAngle)=rodOmega;
  der(ballV)=0;
  der(rodVx)=0;
  der(rodOmega)=0;

  when ballX+ballRadius >= rodX-rodWidth/2 and not pre(impacted) then
    impacted=true;
    impactTime=time;
    reinit(ballV,ballV-candidateImpulse/mass);
    reinit(rodVx,rodVx+candidateImpulse/mass);
    reinit(rodOmega,rodOmega+h*candidateImpulse/I);
  end when;

  annotation(
    experiment(StartTime=0,StopTime=1.5,Interval=0.0025,Tolerance=1e-9),
    __OpenModelica_simulationFlags(s="dassl"),
    Documentation(info="<html><p>Minimal OpenModelica demonstration of the supplied picture: a ball hits the lower end of an initially vertical, uniform rod. Ball and rod have equal mass, both nominally 1 kg. No pivot is present, so the rod translates and rotates freely in a horizontal frictionless plane. A single event handles a perfectly elastic impact, applying the equal-and-opposite impulse to the ball linear velocity, rod center translation and rod angular velocity. Modelica integrates all post-impact motion and exports endpoints at each time sample. No scripted post-impact motion. No gravity, later contact/recontact, ball spin or force-duration model; collision is instantaneous and idealized.</p></html>"));
end FreeRodElasticBallImpact2D;
