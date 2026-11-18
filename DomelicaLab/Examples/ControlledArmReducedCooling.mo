within DomelicaLab.Examples;
model ControlledArmReducedCooling
  "The retuned heavy arm with one fifth of its cooling conductance"
  extends ControlledArmRetuned(coolingConductance=0.08);
end ControlledArmReducedCooling;
