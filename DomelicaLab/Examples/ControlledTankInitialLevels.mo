within DomelicaLab.Examples;
model ControlledTankInitialLevels
  "Same water inventory with the initial tank levels exchanged"
  extends DomelicaLab.Examples.ControlledTankLoop(initialLevelA=0.5, initialLevelB=0.9);
end ControlledTankInitialLevels;
