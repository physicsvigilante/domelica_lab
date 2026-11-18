within DomelicaLab.Components;
model TwoTankLoopPlant
  "Reusable closed hydraulic loop assembled from Modelica.Fluid components"
  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater
    constrainedby Modelica.Media.Interfaces.PartialMedium;
  parameter Modelica.Units.SI.Area crossArea=0.25;
  parameter Modelica.Units.SI.Height tankHeight=1.2;
  parameter Modelica.Units.SI.Height initialLevelA=0.9;
  parameter Modelica.Units.SI.Height initialLevelB=0.5;
  parameter Modelica.Units.SI.Temperature initialTemperature=293.15;
  parameter Modelica.Units.SI.Length supplyLength=2;
  parameter Modelica.Units.SI.Diameter supplyDiameter=0.03;
  parameter Modelica.Units.SI.Length returnLength=2;
  parameter Modelica.Units.SI.Diameter returnDiameter=0.03;

  Modelica.Blocks.Interfaces.RealInput commandedRPM(unit="rev/min");
  Modelica.Blocks.Interfaces.RealInput commandedOpening(min=0, max=1);
  Modelica.Blocks.Interfaces.RealOutput measuredLevel(unit="m");
  Modelica.Fluid.Interfaces.FluidPort_a branchA(redeclare package Medium=Medium)
    "Optional branch connection to tank A; an unconnected port has zero flow";
  Modelica.Fluid.Interfaces.FluidPort_b branchB(redeclare package Medium=Medium)
    "Optional branch connection to tank B";

  Modelica.Fluid.Vessels.OpenTank tankA(
    redeclare package Medium=Medium, nPorts=4, use_portsData=false,
    crossArea=crossArea, height=tankHeight, level_start=initialLevelA,
    T_start=initialTemperature,
    massDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial);
  Modelica.Fluid.Vessels.OpenTank tankB(
    redeclare package Medium=Medium, nPorts=4, use_portsData=false,
    crossArea=crossArea, height=tankHeight, level_start=initialLevelB,
    T_start=initialTemperature,
    massDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial);
  Modelica.Fluid.Machines.PrescribedPump pump(
    redeclare package Medium=Medium, use_N_in=true, N_nominal=1200,
    checkValve=true,
    checkValveHomotopy=Modelica.Fluid.Types.CheckValveHomotopyType.NoHomotopy,
    V=0.001, m_flow_start=1, p_a_start=108000, p_b_start=118000,
    T_start=initialTemperature,
    massDynamics=Modelica.Fluid.Types.Dynamics.SteadyState,
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    redeclare function flowCharacteristic =
      Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.quadraticFlow(
        V_flow_nominal={0,0.004,0.008}, head_nominal={10,7,0}),
    redeclare function efficiencyCharacteristic =
      Modelica.Fluid.Machines.BaseClasses.PumpCharacteristics.constantEfficiency(
        eta_nominal=0.8));
  Modelica.Fluid.Pipes.StaticPipe supplyPipe(
    redeclare package Medium=Medium, length=supplyLength,
    diameter=supplyDiameter, height_ab=0, allowFlowReversal=true);
  Modelica.Fluid.Pipes.StaticPipe returnPipe(
    redeclare package Medium=Medium, length=returnLength,
    diameter=returnDiameter, height_ab=0, allowFlowReversal=true);
  Modelica.Fluid.Valves.ValveLinear returnValve(
    redeclare package Medium=Medium, dp_nominal=5000,
    m_flow_nominal=2, allowFlowReversal=true);
  Modelica.Fluid.Sensors.Pressure pressureA(redeclare package Medium=Medium);
  Modelica.Fluid.Sensors.Pressure pressureB(redeclare package Medium=Medium);

equation
  measuredLevel=tankB.level;
  connect(commandedRPM, pump.N_in);
  connect(commandedOpening, returnValve.opening);
  connect(tankA.ports[1], pump.port_a);
  connect(pump.port_b, supplyPipe.port_a);
  connect(supplyPipe.port_b, tankB.ports[1]);
  connect(tankB.ports[2], returnPipe.port_a);
  connect(returnPipe.port_b, returnValve.port_a);
  connect(returnValve.port_b, tankA.ports[2]);
  connect(tankA.ports[3], branchA);
  connect(tankB.ports[3], branchB);
  connect(tankA.ports[4], pressureA.port);
  connect(tankB.ports[4], pressureB.port);
  annotation(Documentation(info="<html><p>Both tank bases share one elevation. Native MSL components supply the hydraulic and thermal equations. Static pipes and the valve have no storage; both tanks and the 1 litre pump volume store fluid internal energy. The incompressible medium makes pump mass constant. All tank ports are at the bottom with use_portsData=false, so port pressure is hydrostatic and no inlet/outlet loss is added. The optional branch ports allow another model to add a physical return path without changing this plant. This is an illustrative hydraulic network, not a calibrated pump installation.</p></html>"));
end TwoTankLoopPlant;
