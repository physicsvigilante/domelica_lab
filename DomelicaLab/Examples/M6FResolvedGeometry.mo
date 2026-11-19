within DomelicaLab.Examples;
package M6FResolvedGeometry
  "Reference geometry authored and route-certified with domelica_mecha"
  extends Modelica.Icons.Package;
  constant Modelica.Units.SI.Angle slopeAngle=Modelica.Constants.pi/6;
  constant Modelica.Units.SI.Radius movingRadius=0.22;
  constant Modelica.Units.SI.Radius topRadius=0.32000000000000001;
  constant Modelica.Units.SI.Length anchorSeparation=3;
  constant Modelica.Units.SI.Length blockGap=1.3;
  constant Modelica.Units.SI.Length redirectDistance=2.3999999999999999;
  constant Modelica.Units.SI.Length bInitialLeg=1.75;
  constant Modelica.Units.SI.Position cInitial[3]={1.5,2.6000000000000001,0};
  annotation(Documentation(info="<html><p>Reference-only coordinates and dimensions from pinned upstream domelica_mecha geometry authoring; these do not solve mechanics or make unspecified image dimensions problem-given.</p></html>"));
end M6FResolvedGeometry;
