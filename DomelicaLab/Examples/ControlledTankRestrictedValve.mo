within DomelicaLab.Examples;
model ControlledTankRestrictedValve
  "Same loop and controller with reduced opening of the scheduled return valve"
  extends DomelicaLab.Examples.ControlledTankLoop(valveScale=0.55);
end ControlledTankRestrictedValve;
