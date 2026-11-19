/* Canvas XY presentation of native affine primitives and sampled observations.
 * This is a projection renderer, never a second physics engine.
 * Optional theme colors let the same renderer fit a chat light/dark surface.
 */
"use strict";
const DomelicaNativeCanvas = (() => {
  const at=(rows,i)=>rows[rows.length===1?0:i];
  const transform=(f,p)=>[f[9]+f[0]*p[0]+f[3]*p[1]+f[6]*p[2],f[10]+f[1]*p[0]+f[4]*p[1]+f[7]*p[2],f[11]+f[2]*p[0]+f[5]*p[1]+f[8]*p[2]];
  const rgb=a=>`rgb(${a.map(v=>Math.round(v)).join(",")})`;
  function create(canvas) {
    const ctx=canvas.getContext("2d");
    if(!ctx) throw new Error("A Canvas2D context is required for the XY view");
    let width=1,height=1,pixel=1,scale=1,center=[0,0,0],boxes=[],last=null;
    function resize(w,h,dpr=1) {
      width=Math.max(1,w);height=Math.max(1,h);pixel=Math.max(1,Math.min(2,dpr));
      canvas.width=Math.round(width*pixel);canvas.height=Math.round(height*pixel);
    }
    function project(p) {return {x:width/2+(p[0]-center[0])*scale,y:height/2-(p[1]-center[1])*scale,z:p[2]};}
    function path(points,close=false) {
      ctx.beginPath();points.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(q.x,q.y):ctx.moveTo(q.x,q.y);});if(close)ctx.closePath();
    }
    function polygon(points,fill,stroke) {path(points,true);ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1;ctx.stroke();}}
    function register(object,points) {
      const a=points.map(project);boxes.push({id:object.id,minX:Math.min(...a.map(p=>p.x)),maxX:Math.max(...a.map(p=>p.x)),minY:Math.min(...a.map(p=>p.y)),maxY:Math.max(...a.map(p=>p.y))});
    }
    function shape(object,index,selected,theme) {
      const f=at(object.frames,index),color=object.colors?at(object.colors,index):object.color;
      const fill=theme?.bodyFill||rgb(color),stroke=selected===object.id?(theme?.foreground||"#b9ffe5"):(theme?.bodyStroke||"#7594a2");
      const p=q=>transform(f,q),end0=p([0,0,0]),end1=p([1,0,0]);
      if(object.type==="box") {
        const corners=[];for(const x of [0,1])for(const y of [-.5,.5])for(const z of [-.5,.5])corners.push(p([x,y,z]));
        const faces=[[0,4,6,2],[1,3,7,5],[0,1,5,4],[2,6,7,3],[0,2,3,1],[4,5,7,6]].map(ids=>ids.map(i=>corners[i]));
        faces.sort((a,b)=>a.reduce((s,q)=>s+q[2],0)-b.reduce((s,q)=>s+q[2],0));
        for(const face of faces) polygon(face,fill,stroke);register(object,corners);
      } else if(object.type==="sphere") {
        const c=project(p([.5,0,0]));
        // Orthographic projection of an affine unit sphere is an ellipse.
        const aa=(f[0]*f[0]+f[3]*f[3]+f[6]*f[6])*.25;
        const bb=(f[1]*f[1]+f[4]*f[4]+f[7]*f[7])*.25;
        const ab=-(f[0]*f[1]+f[3]*f[4]+f[6]*f[7])*.25;
        const disc=Math.sqrt((aa-bb)*(aa-bb)+4*ab*ab),r1=Math.sqrt(Math.max(0,(aa+bb+disc)/2)),r2=Math.sqrt(Math.max(0,(aa+bb-disc)/2));
        ctx.beginPath();ctx.ellipse(c.x,c.y,r1*scale,r2*scale,.5*Math.atan2(2*ab,aa-bb),0,2*Math.PI);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=stroke;ctx.lineWidth=selected===object.id?2:1;ctx.stroke();
        boxes.push({id:object.id,minX:c.x-r1*scale,maxX:c.x+r1*scale,minY:c.y-r1*scale,maxY:c.y+r1*scale});
      } else if(object.type==="cylinder"||object.type==="cone") {
        const segments=24,rings=[[],[]],sides=[];
        for(let k=0;k<segments;k++){const a=k*2*Math.PI/segments;rings[0].push(p([0,.5*Math.cos(a),.5*Math.sin(a)]));rings[1].push(p([1,object.type==="cone"?0:.5*Math.cos(a),object.type==="cone"?0:.5*Math.sin(a)]));}
        for(let k=0;k<segments;k++) sides.push([rings[0][k],rings[0][(k+1)%segments],rings[1][(k+1)%segments],rings[1][k]]);
        sides.push(rings[0],rings[1]);sides.sort((a,b)=>a.reduce((s,q)=>s+q[2],0)/a.length-b.reduce((s,q)=>s+q[2],0)/b.length);
        for(const face of sides)polygon(face,fill,null);
        path([end0,end1]);ctx.strokeStyle=stroke;ctx.lineWidth=selected===object.id?1.8:.6;ctx.stroke();register(object,rings.flat());
      } else if(object.type==="spring") {
        const [len,radius,wire,turns]=at(object.spring,index),steps=Math.max(24,Math.ceil(turns*24)),points=[];
        for(let k=0;k<=steps;k++){const u=k/steps,a=u*turns*2*Math.PI;points.push(p([len*u,radius*Math.sin(a),radius*Math.cos(a)]));}
        path(points);ctx.strokeStyle=theme?.bodyStroke||fill;ctx.lineWidth=2*wire*scale;ctx.lineCap="round";ctx.lineJoin="round";ctx.stroke();ctx.lineCap="butt";register(object,points);
      }
    }
    function arrow(sample,theme) {
      if(sample.magnitude===0) return;
      const p=project(sample.point),e=project(sample.end),dx=e.x-p.x,dy=e.y-p.y,dist=Math.hypot(dx,dy);
      const color=sample.color||theme?.foreground||"#79e5cb";
      ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;
      function head(at,fraction) {
        const h=Math.min(12,dist*.26)*fraction,w=h*.55,ux=dx/dist,uy=dy/dist;
        ctx.beginPath();ctx.moveTo(at.x,at.y);ctx.lineTo(at.x-ux*h-uy*w,at.y-uy*h+ux*w);ctx.lineTo(at.x-ux*h+uy*w,at.y-uy*h-ux*w);ctx.closePath();ctx.fill();
      }
      if(dist>0) {
        ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(e.x,e.y);ctx.stroke();head(e,1);
        if(sample.kind==="torque") head({x:p.x+.78*dx,y:p.y+.78*dy},.85);
      }
      // Out-of-plane direction is a symbol, not a fabricated projected length.
      if(sample.vector[2]!==0) {
        const r=8;ctx.beginPath();ctx.arc(p.x,p.y,r,0,2*Math.PI);ctx.stroke();
        if(sample.kind==="torque"){ctx.beginPath();ctx.arc(p.x,p.y,r+3,0,2*Math.PI);ctx.stroke();}
        if(sample.vector[2]>0){ctx.beginPath();ctx.arc(p.x,p.y,2,0,2*Math.PI);ctx.fill();}
        else {ctx.beginPath();ctx.moveTo(p.x-3,p.y-3);ctx.lineTo(p.x+3,p.y+3);ctx.moveTo(p.x-3,p.y+3);ctx.lineTo(p.x+3,p.y-3);ctx.stroke();}
      }
      // A small anchor marker identifies the exact application point only.
      if(sample.vector[2]===0){ctx.beginPath();ctx.arc(p.x,p.y,2.5,0,2*Math.PI);ctx.fill();}
    }
    function render(options) {
      const {scene,index=0,overlays=[],bounds=scene.bounds,zoom=1,selected=null,theme=null}=options;
      center=bounds.min.map((v,k)=>(v+bounds.max[k])/2);
      const spanX=Math.max(.1,bounds.max[0]-bounds.min[0]),spanY=Math.max(.1,bounds.max[1]-bounds.min[1]);
      scale=Math.min(Math.max(1,width-64)/spanX,Math.max(1,height-64)/spanY)*zoom;
      ctx.setTransform(pixel,0,0,pixel,0,0);ctx.clearRect(0,0,width,height);boxes=[];
      const shapes=scene.objects.slice().sort((a,b)=>at(a.frames,index)[11]-at(b.frames,index)[11]);
      for(const object of shapes) shape(object,index,selected,theme);
      for(const sample of overlays) arrow(sample,theme);
      // Scale bar describes world distance. It does not change native geometry.
      const target=80/scale,power=Math.pow(10,Math.floor(Math.log10(target))),bar=[1,2,5,10].map(a=>a*power).filter(a=>a<=target).at(-1)||power;
      const left=20,base=height-18;
      ctx.strokeStyle=theme?.muted||"#a4bac7";ctx.fillStyle=theme?.muted||"#a4bac7";ctx.lineWidth=1;
      ctx.beginPath();ctx.moveTo(left,base);ctx.lineTo(left+bar*scale,base);ctx.moveTo(left,base-3);ctx.lineTo(left,base+3);ctx.moveTo(left+bar*scale,base-3);ctx.lineTo(left+bar*scale,base+3);ctx.stroke();
      ctx.font="12px system-ui";ctx.textAlign="left";ctx.fillText(Number(bar.toPrecision(3))+" m",left,base-7);
      ctx.textAlign="right";ctx.fillText("X →   Y ↑",width-18,base);ctx.textAlign="left";
      last={projection:"XY",index,width,height,scale,center:center.slice(),overlayCount:overlays.length,zeroCount:overlays.filter(o=>o.magnitude===0).length};
    }
    function pick(x,y) {return boxes.slice().reverse().find(b=>x>=b.minX&&x<=b.maxX&&y>=b.minY&&y<=b.maxY)?.id||null;}
    return {resize,render,project,pick,getState:()=>last?{...last}:null};
  }
  return {create};
})();
