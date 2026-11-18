within DomelicaLab.Examples;
model ControlledArmRetuned
  "Heavy forearm with a different proportional and derivative tuning"
  extends ControlledArmHeavyLoad(controllerGain=30, derivativeTime=0.22);
end ControlledArmRetuned;
