within DomelicaLab.Components;
model IdealLinearRope3
  "Massless bilateral lossless three-flange linear rope constraint"
  import SI = Modelica.Units.SI;
  parameter Real weights[3]={1,2,-1}
    "Signed dimensionless rope leg counts in positive flange directions";
  parameter SI.Position offset=0 "Fixed signed length offset";
  Modelica.Mechanics.Translational.Interfaces.Flange_a flangeA;
  Modelica.Mechanics.Translational.Interfaces.Flange_a flangeB;
  Modelica.Mechanics.Translational.Interfaces.Flange_a flangeC;
  SI.Force reaction "Single ideal constraint multiplier; positive is tensile for {1,2,-1}";
equation
  weights[1]*flangeA.s+weights[2]*flangeB.s+weights[3]*flangeC.s=offset;
  flangeA.f=weights[1]*reaction;
  flangeB.f=weights[2]*reaction;
  flangeC.f=weights[3]*reaction;
  annotation(Documentation(info="<html><p>An ideal massless, power-conserving, bilateral 1D constraint for three translational coordinates. The signed coefficient vector represents length derivatives, not a rendered rope. Virtual-work reactions are distributed according to the same coefficients, ensuring zero net constraint power. The caller is responsible for testing positive tension and geometric feasibility. No slack, friction, impact, contact or elasticity is represented.</p></html>"));
end IdealLinearRope3;
