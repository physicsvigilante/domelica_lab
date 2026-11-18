within DomelicaLab.Examples;
model ControlledThermalArm3D
  "Native position feedback around a reusable electromechanical and thermal arm"
  extends Modelica.Icons.Example;
  parameter Modelica.Units.SI.Density forearmDensity=850;
  parameter Modelica.Units.SI.ThermalConductance coolingConductance=0.4;
  parameter Real controllerGain=18 "Illustrative voltage per radian gain";
  parameter Modelica.Units.SI.Time integralTime=1.2;
  parameter Modelica.Units.SI.Time derivativeTime=0.12;
  parameter Modelica.Units.SI.Voltage voltageLimit=12;
  parameter Modelica.Units.SI.Angle initialShoulderAngle=0.25;

  inner Modelica.Mechanics.MultiBody.World world(n={0,-1,0});
  DomelicaLab.Components.ControlledArmPlant3D plant(
    forearmDensity=forearmDensity,
    coolingConductance=coolingConductance,
    initialShoulderAngle=initialShoulderAngle);
  Modelica.Blocks.Sources.TimeTable reference(
    table=[0,0.25; 1,0.25; 1,1.0; 10,1.0; 10,-0.35;
           20,-0.35; 20,0.65; 30,0.65]);
  Modelica.Blocks.Continuous.LimPID controller(
    controllerType=Modelica.Blocks.Types.SimpleController.PID,
    k=controllerGain, Ti=integralTime, Td=derivativeTime,
    yMax=voltageLimit, yMin=-voltageLimit,
    wp=1, wd=0, Ni=0.9, Nd=10,
    initType=Modelica.Blocks.Types.Init.InitialState,
    xi_start=0, xd_start=-initialShoulderAngle,
    strict=false, withFeedForward=false);
  Modelica.Blocks.Sources.RealExpression electricalPowerSignal(y=plant.inputPower);
  Modelica.Blocks.Sources.RealExpression copperPowerSignal(y=plant.copperLoss);
  Modelica.Blocks.Continuous.Integrator electricalWork(
    k=1, initType=Modelica.Blocks.Types.Init.InitialState, y_start=0);
  Modelica.Blocks.Continuous.Integrator copperHeat(
    k=1, initType=Modelica.Blocks.Types.Init.InitialState, y_start=0);

  Modelica.Units.SI.Angle desiredAngle=reference.y;
  Modelica.Units.SI.Angle shoulderAngle=plant.shoulderAngle;
  Modelica.Units.SI.Angle elbowAngle=plant.elbowAngle;
  Modelica.Units.SI.Angle trackingError=desiredAngle-shoulderAngle;
  Modelica.Units.SI.AngularVelocity shoulderSpeed=plant.shoulderSpeed;
  Modelica.Units.SI.AngularVelocity elbowSpeed=plant.elbowSpeed;
  Modelica.Units.SI.AngularVelocity motorSpeed=plant.motorSpeed;
  Modelica.Units.SI.Current motorCurrent=plant.motorCurrent;
  Modelica.Units.SI.Voltage appliedVoltage=controller.y;
  Modelica.Units.SI.Temperature windingTemperature=plant.windingTemperature;
  Modelica.Units.SI.Power copperLoss=plant.copperLoss;
  Modelica.Units.SI.Power inputPower=plant.inputPower;
  Modelica.Units.SI.Energy electricalEnergy=electricalWork.y
    "Signed net energy delivered by the ideal voltage supply";
  Modelica.Units.SI.Energy copperEnergy=copperHeat.y
    "Cumulative irreversible winding copper loss";
  Real currentDerivative(unit="A/s")=plant.currentDerivative;
  Real temperatureDerivative(unit="K/s")=plant.temperatureDerivative;
  Modelica.Units.SI.Position tipPosition[3]=plant.tipPosition;
  Real controllerIntegral=controller.I.y;
  Real controllerDerivative=controller.D.y;
  Real controllerDerivativeState=controller.D.x;
  Real integratorDerivative=der(controller.I.y);
  Modelica.Units.SI.Voltage rawControlVoltage=controller.limiter.u;
equation
  connect(world.frame_b, plant.mountingFrame);
  connect(reference.y, controller.u_s);
  connect(plant.shoulderAngle, controller.u_m);
  connect(controller.y, plant.commandedVoltage);
  connect(electricalPowerSignal.y, electricalWork.u);
  connect(copperPowerSignal.y, copperHeat.u);
  annotation(
    experiment(StartTime=0, StopTime=30, Interval=0.02, Tolerance=1e-7),
    Documentation(info="<html><p>Position feedback is implemented by MSL LimPID with a +/-12 V output limit and native anti-windup. Its derivative acts on the measurement (wd=0), so reference steps do not cause derivative kick. The derivative state initially equals minus the measured angle, while the integral state starts at zero; the plant is allowed a physical startup transient. Requested shoulder angles are 0.25 rad initially, 1.0 rad at 1 s, -0.35 rad at 10 s and 0.65 rad at 20 s. The elbow remains passive. Native Integrator blocks accumulate signed supply energy and winding copper heat. Parameters are illustrative, not identified from a real machine.</p></html>"));
end ControlledThermalArm3D;
