within DomelicaLab.Examples;
model ControlledTankRestrictedValve
  "Same loop and controller with reduced opening of the scheduled return valve"
  extends DomelicaLab.Examples.ControlledTankLoop(valveScale=0.55);
  annotation(experiment(StartTime=0, StopTime=300, Interval=0.1, Tolerance=1e-10),
    __OpenModelica_simulationFlags(s="dassl", nls="hybrid"));
end ControlledTankRestrictedValve;
