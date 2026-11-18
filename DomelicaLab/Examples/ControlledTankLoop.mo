within DomelicaLab.Examples;
model ControlledTankLoop
  "Native PI level control of a closed two-tank recirculation loop"
  extends Modelica.Icons.Example;
  parameter Modelica.Units.SI.Area crossArea=0.25;
  parameter Modelica.Units.SI.Height tankHeight=1.2;
  parameter Modelica.Units.SI.Height initialLevelA=0.9;
  parameter Modelica.Units.SI.Height initialLevelB=0.5;
  parameter Real valveScale(min=0, max=1)=1;
  parameter Integer returnBranchCount(min=1, max=2)=1;
  parameter Real controllerGain=3;
  parameter Modelica.Units.SI.Time integralTime=30;

  inner Modelica.Fluid.System system(
    p_ambient=101325, T_ambient=293.15, T_start=293.15, p_start=101325,
    g=9.80665, allowFlowReversal=true,
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    massDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial);
  DomelicaLab.Components.TwoTankLoopPlant plant(
    crossArea=crossArea, tankHeight=tankHeight,
    initialLevelA=initialLevelA, initialLevelB=initialLevelB);
  Modelica.Blocks.Sources.TimeTable target(
    table=[0,0.8; 100,0.8; 100,0.9; 200,0.9; 200,0.78; 300,0.78]);
  Modelica.Blocks.Sources.TimeTable valveSchedule(
    table=[0,0.65; 140,0.65; 140,1; 240,1; 240,0.45; 300,0.45]);
  Modelica.Blocks.Math.Gain openingScale(k=valveScale);
  Modelica.Blocks.Continuous.LimPID controller(
    controllerType=Modelica.Blocks.Types.SimpleController.PI,
    k=controllerGain, Ti=integralTime, yMin=0.001, yMax=1.5,
    wp=1, Ni=0.9, initType=Modelica.Blocks.Types.Init.InitialState,
    xi_start=0.1, withFeedForward=false, strict=false);
  Modelica.Blocks.Continuous.FirstOrder speedResponse(
    T=2, initType=Modelica.Blocks.Types.Init.InitialState, y_start=0.3,
    y(stateSelect=StateSelect.always));
  Modelica.Blocks.Math.Gain rpmScale(k=1200);
  Modelica.Blocks.Continuous.Integrator shaftEnergy(k=1, y_start=0);
  Modelica.Blocks.Continuous.Integrator netTransfer(k=1, y_start=0);

  Modelica.Units.SI.Height tankALevel=plant.tankA.level;
  Modelica.Units.SI.Height tankBLevel=plant.tankB.level;
  Modelica.Units.SI.AbsolutePressure tankAPressure=plant.pressureA.p;
  Modelica.Units.SI.AbsolutePressure tankBPressure=plant.pressureB.p;
  Modelica.Units.SI.MassFlowRate supplyFlow=plant.pump.port_a.m_flow
    "Positive from tank A through the pump and supply pipe to tank B";
  Modelica.Units.SI.MassFlowRate returnFlow=plant.returnPipe.port_a.m_flow
    "Signed flow in the main return path, positive from tank B to tank A";
  Modelica.Units.SI.MassFlowRate bypassFlow=-plant.tankB.ports[3].m_flow
    "Signed optional branch flow, positive from tank B to tank A";
  Modelica.Units.NonSI.AngularVelocity_rpm pumpRPM=plant.pump.N;
  Modelica.Units.SI.PressureDifference pumpPressureRise=plant.pump.dp_pump;
  Modelica.Units.SI.Power pumpPower=plant.pump.W_total;
  Modelica.Units.SI.Energy pumpEnergy=shaftEnergy.y;
  Real valveOpening=plant.returnValve.opening;
  Modelica.Units.SI.Height targetLevel=target.y;
  Real levelError(unit="m")=target.y-plant.tankB.level
    "Signed level error; height's nonnegative bound does not apply";
  Modelica.Units.SI.Mass totalMass=plant.tankA.m+plant.tankB.m+plant.pump.m;
  Real massResidual(unit="kg")=totalMass-
    995.586*(crossArea*(initialLevelA+initialLevelB)+0.001);
  Modelica.Units.SI.Energy totalInternalEnergy=
    plant.tankA.U+plant.tankB.U+plant.pump.U
    "Modeled internal energy; tank potential/kinetic energy is outside this medium model";
  Modelica.Units.SI.Temperature tankATemperature=plant.tankA.medium.T;
  Modelica.Units.SI.Temperature tankBTemperature=plant.tankB.medium.T;
  Real tankALevelDerivative(unit="m/s")=der(plant.tankA.level);
  Real tankBLevelDerivative(unit="m/s")=der(plant.tankB.level);
  Modelica.Units.SI.Power internalEnergyDerivative=
    der(plant.tankA.U)+der(plant.tankB.U)+der(plant.pump.U);
  Real transferredMass(unit="kg")=netTransfer.y
    "Net mass entering tank B, integrated by a native Modelica block";
  Real controllerRaw=controller.gainPID.y;
  Real controllerIntegral=controller.I.y;
  Real controllerIntegralDerivative(unit="m/s")=der(controller.I.y);
  Real pumpFraction=controller.y;
  Real filteredFraction=speedResponse.y;
  Real filteredFractionDerivative(unit="1/s")=der(speedResponse.y);
equation
  connect(target.y, controller.u_s);
  connect(plant.measuredLevel, controller.u_m);
  connect(controller.y, speedResponse.u);
  connect(speedResponse.y, rpmScale.u);
  connect(rpmScale.y, plant.commandedRPM);
  connect(valveSchedule.y, openingScale.u);
  connect(openingScale.y, plant.commandedOpening);
  shaftEnergy.u=pumpPower;
  netTransfer.u=supplyFlow-returnFlow-bypassFlow;
  annotation(experiment(StartTime=0, StopTime=300, Interval=0.1, Tolerance=1e-10),
    __OpenModelica_simulationFlags(s="dassl", nls="hybrid"),
    Documentation(info="<html><p>A native MSL PI block regulates tank B level by setting pump speed. The desired level changes at 100 and 200 seconds; the return valve changes at 140 and 240 seconds. Pump speed includes a 2 second first-order actuator response and a nonzero minimum speed. Anti-windup is supplied by LimPID. Outputs are aliases and diagnostic derivatives of the native components, plus native integration blocks. The illustrative schematic layout is not solver-defined 3D geometry.</p></html>"));
end ControlledTankLoop;
