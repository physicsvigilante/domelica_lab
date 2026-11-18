within DomelicaLab.Examples;
model ControlledTankParallelReturn
  "Composition adds a separate pipe in parallel with the controlled return path"
  extends DomelicaLab.Examples.ControlledTankLoop(returnBranchCount=2);
  Modelica.Fluid.Pipes.StaticPipe bypassPipe(
    redeclare package Medium=Modelica.Media.Water.ConstantPropertyLiquidWater,
    length=4, diameter=0.016, height_ab=0, allowFlowReversal=true);
equation
  connect(plant.branchB, bypassPipe.port_a);
  connect(bypassPipe.port_b, plant.branchA);
  annotation(experiment(StartTime=0, StopTime=300, Interval=0.1, Tolerance=1e-10),
    __OpenModelica_simulationFlags(s="dassl", nls="hybrid"));
end ControlledTankParallelReturn;
