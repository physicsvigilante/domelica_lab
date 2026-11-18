within DomelicaLab.Examples;
model ControlledTankInitialLevels
  "Same water inventory with the initial tank levels exchanged"
  extends DomelicaLab.Examples.ControlledTankLoop(initialLevelA=0.5, initialLevelB=0.9);
  annotation(experiment(StartTime=0, StopTime=300, Interval=0.1, Tolerance=1e-10),
    __OpenModelica_simulationFlags(s="dassl", nls="hybrid"));
end ControlledTankInitialLevels;
