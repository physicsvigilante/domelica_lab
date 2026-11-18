within;
package PumpDerivativeProbe
  function explicitHead
    input Modelica.Units.SI.VolumeFlowRate q;
    output Modelica.Units.SI.Height h;
  algorithm
    h := if q < 0 then 10 - 250*q
      elseif q > 0.008 then -2250*(q - 0.008)
      else 10 - 250*q - 125000*q*q;
  end explicitHead;

  partial model ScalarBase
    "A single prescribed flow rate: no hydraulic network and no nonlinear solver"
    Modelica.Units.SI.VolumeFlowRate q(start=0.002, fixed=true);
    Real qD(unit="m3/s2")=0.0002;
    Modelica.Units.SI.Height head;
    Real headD(unit="m/s");
  equation
    der(q)=qD;
    headD=der(head);
  end ScalarBase;

  model ScalarMSL
    extends ScalarBase;
  equation
    head=Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.quadraticFlow(
      q, {0,0.004,0.008}, {10,7,0});
  end ScalarMSL;

  model ScalarExplicit
    extends ScalarBase;
  equation
    head=explicitHead(q);
  end ScalarExplicit;

  partial model DirectBase
    Modelica.Units.SI.VolumeFlowRate q(start=0.0015, fixed=true);
    Real ratio(start=0.9, fixed=true);
    Real qD(unit="m3/s2");
    Real ratioD(unit="1/s");
    Modelica.Units.SI.Height head;
    Real headD(unit="m/s");
  equation
    qD = 0.00030 + 0.00008*sin(2*time);
    ratioD = 0.07*cos(0.3*time);
    der(q) = qD;
    der(ratio) = ratioD;
    headD = der(head);
  end DirectBase;

  model DirectMSL
    extends DirectBase;
  equation
    head = ratio*ratio*
      Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.quadraticFlow(
        q/ratio, {0,0.004,0.008}, {10,7,0});
  end DirectMSL;

  model DirectExplicit
    extends DirectBase;
  equation
    head = ratio*ratio*explicitHead(q/ratio);
  end DirectExplicit;

  partial model ImplicitBase
    parameter Modelica.Units.SI.Area area=0.25;
    Modelica.Units.SI.Height tankA(start=0.55, fixed=true);
    Modelica.Units.SI.Height tankB(start=0.85, fixed=true);
    Real ratio(start=0.85, fixed=true);
    Modelica.Units.SI.VolumeFlowRate q(start=0.004);
    Real qD(unit="m3/s2");
    Real ratioD(unit="1/s");
    Modelica.Units.SI.Height head;
    Real headD(unit="m/s");
    Modelica.Units.SI.Volume waterVolume;
    parameter Real flowResistance(unit="s/m2")=250;
  equation
    der(tankA) = -q/area;
    der(tankB) = q/area;
    der(ratio) = (1.15-ratio)/2;
    ratioD = der(ratio);
    qD = der(q);
    headD = der(head);
    head = 3 + flowResistance*q + tankB-tankA;
    waterVolume = area*(tankA+tankB);
  end ImplicitBase;

  model ImplicitMSL
    extends ImplicitBase;
  equation
    head = ratio*ratio*
      Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.quadraticFlow(
        q/ratio, {0,0.004,0.008}, {10,7,0});
  end ImplicitMSL;

  model ImplicitExplicit
    extends ImplicitBase;
  equation
    head = ratio*ratio*explicitHead(q/ratio);
  end ImplicitExplicit;
end PumpDerivativeProbe;
