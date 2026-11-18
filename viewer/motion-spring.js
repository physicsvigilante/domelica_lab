/* Generic geometry only: no dynamics, forces, or model-specific dimensions.
 * Native spring dimensions follow OMEdit 1.27.1 Spring(width,height,extra,length).
 * An ideal helix is tessellated with circular wire sections. Unlike affine
 * stretching of a prebuilt coil, changing native length preserves wire radius.
 */
"use strict";
const DomelicaSpring = {
 createGeometry(spec) {
  const [length,radius,wire,turns]=spec;
  if(!spec.every(Number.isFinite)||length<=0||radius<=0||wire<=0||wire>=radius||turns<=0||turns>128)throw new Error("Invalid native spring dimensions");
  const segments=Math.max(24,Math.ceil(turns*24)),radial=12,positions=[],indices=[],centers=[];
  const frequency=2*Math.PI*turns,tangentNorm=Math.hypot(length,frequency*radius);
  for(let i=0;i<=segments;i++){
   const u=i/segments,a=frequency*u,s=Math.sin(a),c=Math.cos(a),center=[length*u,radius*s,radius*c];
   const tangent=[length/tangentNorm,frequency*radius*c/tangentNorm,-frequency*radius*s/tangentNorm];
   const normal=[0,s,c],binormal=[tangent[1]*c-tangent[2]*s,-tangent[0]*c,tangent[0]*s];
   centers.push(...center);
   for(let j=0;j<=radial;j++){
    const b=2*Math.PI*j/radial,cb=Math.cos(b),sb=Math.sin(b);
    positions.push(...center.map((v,k)=>v+wire*(normal[k]*cb+binormal[k]*sb)));
   }
  }
  for(let i=0;i<segments;i++)for(let j=0;j<radial;j++){
   const a=i*(radial+1)+j,b=a+radial+1;
   indices.push(a,b,a+1,b,b+1,a+1);
  }
  // End caps are local surface details and carry no force or contact behavior.
  for(const end of [0,segments]){
   const ci=positions.length/3;positions.push(...centers.slice(end*3,end*3+3));
   const start=end*(radial+1);
   for(let j=0;j<radial;j++)end===0?indices.push(ci,start+j+1,start+j):indices.push(ci,start+j,start+j+1);
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute("position",new THREE.Float32BufferAttribute(positions,3));
  geometry.setIndex(indices);geometry.computeVertexNormals();geometry.computeBoundingBox();geometry.computeBoundingSphere();
  geometry.userData={nativeSpring:spec.slice(),segments,radial,centers};return geometry;
 }
};
