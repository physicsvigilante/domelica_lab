#!/usr/bin/env node
"use strict";
// Validate the delivered SVG at every recorded sample, including both wraps.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {pathToFileURL}=require("node:url"),{createHash}=require("node:crypto");
const {chromium}=require("playwright");
const args=process.argv.slice(2);
if(args.length!==3)throw new Error("Pass dark HTML, light HTML, output directory");
const [darkPath,lightPath,outPath]=args.map(x=>path.resolve(x));
fs.mkdirSync(outPath,{recursive:true});
const read=file=>{
 const html=fs.readFileSync(file,"utf8");
 const match=html.match(/<script id="recording" type="application\/json">([\s\S]*?)<\/script>/);
 assert.ok(match,"Standalone HTML requires the native recording payload");
 return {payload:JSON.parse(match[1]),sha256:createHash("sha256").update(html).digest("hex")};
};
const dark=read(darkPath),light=read(lightPath);
const report={passed:false,darkSHA256:dark.sha256,lightSHA256:light.sha256,
 steps:[],screenshots:[],errors:[],externalRequests:[]};
const pass=name=>{report.steps.push(name);console.log("PASS",name);};
const save=()=>fs.writeFileSync(path.join(outPath,"report.json"),JSON.stringify(report,null,2));

(async()=>{
 for(const key of ["schema","times","frames","bounds","metrics","maxRopeLengthDrift_m"])
   assert.deepEqual(dark.payload[key],light.payload[key],"Style changed "+key);
 const physicalProvenance=payload=>{
   const {styleSHA256,...rest}=payload.provenance;return rest;
 };
 assert.deepEqual(physicalProvenance(dark.payload),physicalProvenance(light.payload));
 assert.notEqual(dark.payload.provenance.styleSHA256,light.payload.provenance.styleSHA256);
 assert.notDeepEqual(dark.payload.style,light.payload.style);
 assert.equal(dark.payload.schema,"domelica.rope-playback-2d/v1");
 assert.ok(dark.payload.times.length>=1000);
 assert.ok(dark.payload.maxRopeLengthDrift_m.rope<1e-6);
 const first=dark.payload.frames[0],last=dark.payload.frames.at(-1);
 const near=(a,b,tol=1e-7)=>assert.ok(Math.abs(a-b)<tol,`${a} != ${b}`);
 const pulleyNames=Object.keys(first.pulleys);
 assert.equal(pulleyNames.length,2);
 const moving=pulleyNames.find(id=>Math.hypot(...first.pulleys[id].center.map((v,k)=>v-first.bodies.load.position[k]))<1e-8);
 assert.ok(moving,"A physical load must be at the movable axle");
 const fixed=pulleyNames.find(id=>id!==moving);
 const rise=last.bodies.load.position[1]-first.bodies.load.position[1];
 assert.ok(rise>.5,"The pulley must actually move relative to its fixed support");
 near(rise,.882,2e-5);
 near(first.bodies.counterweight.position[1]-last.bodies.counterweight.position[1],2*rise);
 for(const frame of dark.payload.frames){
   const rope=frame.ropes.rope;
   assert.equal(rope.arcs.length,2);
   near(rope.length,first.ropes.rope.length);
   assert.deepEqual(frame.pulleys[fixed],first.pulleys[fixed]);
   assert.deepEqual(rope.points[0],first.ropes.rope.points[0]);
   frame.bodies.load.position.forEach((v,k)=>near(v,frame.pulleys[moving].center[k]));
   frame.bodies.counterweight.position.forEach((v,k)=>near(v,rope.points.at(-1)[k]));
   const q=frame.bodies.load.position[1]-first.bodies.load.position[1];
   near(first.bodies.counterweight.position[1]-frame.bodies.counterweight.position[1],2*q);
 }
 pass("Both styles retain identical native motion, geometry and non-style provenance; movable pulley has 2:1 travel");
 const browser=await chromium.launch({headless:true});
 try{
  for(const [tag,file] of [["dark",darkPath],["light",lightPath]]){
   const page=await browser.newPage({viewport:{width:1000,height:800}}),uri=pathToFileURL(file).href;
   page.on("pageerror",error=>report.errors.push(String(error)));
   page.on("console",message=>{if(message.type()==="error")report.errors.push(message.text());});
   page.on("request",request=>{if(request.url()!==uri&&!/^(data|blob):/.test(request.url()))report.externalRequests.push(request.url());});
   await page.goto(uri,{waitUntil:"load"});
   await page.waitForFunction(()=>!!window.__rope2d);
   const checked=await page.evaluate(({moving,fixed})=>{
     const D=JSON.parse(document.getElementById("recording").textContent),api=window.__rope2d;
     const [x0,y0,x1,y1]=D.bounds;
     const close=(a,b,message)=>{if(Math.abs(a-b)>1e-6)throw new Error(message+`: ${a} != ${b}`);};
     const check=(condition,message)=>{if(!condition)throw new Error(message);};
     const pos=element=>[Number(element.getAttribute("cx")),Number(element.getAttribute("cy"))];
     const circle=id=>document.querySelector(`[data-pulley="${id}"]`);
     check(document.querySelectorAll("[data-axle]").length===2,"Every pulley has an axle");
     let firstMovingY,lastMovingY;
     for(let i=0;i<D.times.length;i++){
       api.seek(i);
       const state=api.getState(),frame=state.frame;
       close(state.time,D.times[i],"Frame time");
       check(state.index===i,"Native sample index");
       const project=point=>[440+(point[0]-(x0+x1)/2)*state.scale,260-(point[1]-(y0+y1)/2)*state.scale];
       const points=document.querySelector('[data-rope="rope"]').getAttribute("points").trim()
         .split(/\s+/).map(point=>point.split(",").map(Number));
       check(points.length===frame.ropes.rope.points.length,"Every recorded rope point is rendered");
       points.forEach((point,j)=>point.forEach((value,k)=>close(value,project(frame.ropes.rope.points[j])[k],"Projected rope point")));
       for(const [id,pulley] of Object.entries(frame.pulleys)){
         const element=circle(id),center=pos(element),radius=Number(element.getAttribute("r"));
         center.forEach((v,k)=>close(v,project(pulley.center)[k],"Projected native pulley center"));
         close(radius,pulley.radius*state.scale,"Physical radius uses the same XY scale");
         pos(document.querySelector(`[data-axle="${id}"]`)).forEach((v,k)=>close(v,center[k],"Axle follows its pulley"));
         const indices=points.map((p,j)=>Math.abs(Math.hypot(p[0]-center[0],p[1]-center[1])-radius)<1e-6?j:-1).filter(j=>j>=0);
         check(indices.length>4,"A sampled circular wrap must be present");
         const start=indices[0],end=indices.at(-1);
         check(end-start+1===indices.length&&start>0&&end<points.length-1,"Connected wrap and straight legs");
         close(points[start][0],center[0]-radius,"Left tangent contact");
         close(points[end][0],center[0]+radius,"Right tangent contact");
         close(points[start][1],center[1],"Incoming contact height");
         close(points[end][1],center[1],"Outgoing contact height");
         for(const j of indices){
           close(Math.hypot(points[j][0]-center[0],points[j][1]-center[1]),radius,"SVG arc radius");
           check((id===moving?1:-1)*(points[j][1]-center[1])>=-1e-6,"Lower movable / upper fixed wrap after Y inversion");
         }
         for(const [j,a,b] of [[start,start-1,start],[end,end,end+1]]){
           const radial=points[j].map((v,k)=>(v-center[k])/radius);
           const length=Math.hypot(points[b][0]-points[a][0],points[b][1]-points[a][1]);
           const tangent=points[b].map((v,k)=>(v-points[a][k])/length);
           close(radial[0]*tangent[0]+radial[1]*tangent[1],0,"Straight leg is orthogonal to contact radius");
           close(radial[0]*tangent[1]-radial[1]*tangent[0],id===moving?-1:1,"Tangent orientation matches SVG wrap");
         }
       }
       for(const [id,body] of Object.entries(frame.bodies)){
         const position=pos(document.querySelector(`[data-body="${id}"]`));
         position.forEach((v,k)=>close(v,project(body.position)[k],"Rendered native body"));
         const target=id==="load"?pos(circle(moving)):points.at(-1);
         position.forEach((v,k)=>close(v,target[k],"Load/rope attachment follows native position"));
         const box=document.querySelector(`[data-body-label="${id}"]`).getBBox();
         check(box.x>=0&&box.x+box.width<=880&&box.y>=0&&box.y+box.height<=520,"Body label stays inside diagram");
       }
       if(i===0)firstMovingY=pos(circle(moving))[1];
       if(i===D.times.length-1)lastMovingY=pos(circle(moving))[1];
     }
     check(lastMovingY<firstMovingY,"Native upward pulley travel appears upward in SVG");
     return {samples:D.times.length,moving,fixed};
   },{moving,fixed});
   report[tag]=checked;
   pass(`${tag}: actual SVG centers, radii, both tangent wraps, body attachments and labels checked at all ${checked.samples} samples`);
   const screenshot=async(name,index)=>{
     await page.evaluate(i=>window.__rope2d.seek(i),index);
     await page.screenshot({path:path.join(outPath,name),fullPage:true});report.screenshots.push(name);
   };
   const middle=Math.floor(dark.payload.times.length/2);
   if(tag==="dark"){
     await screenshot("dark-first.png",0);
     await screenshot("dark-last.png",dark.payload.times.length-1);
   }
   await screenshot(tag+"-middle.png",middle);
   await page.evaluate(()=>window.__rope2d.seek(0));
   await page.locator("#play").click();
   await page.waitForFunction(()=>window.__rope2d.getState().index>0,null,{timeout:4000});
   await page.locator("#play").click();
   assert.equal((await page.evaluate(()=>window.__rope2d.getState())).playing,false);
   await page.evaluate(index=>{
     const scrub=document.getElementById("scrub");scrub.value=String(index);
     scrub.dispatchEvent(new Event("input",{bubbles:true}));
   },middle);
   assert.equal((await page.evaluate(()=>window.__rope2d.getState())).index,middle);
   pass(tag+": play, pause and scrub update recorded geometry");
   await page.setViewportSize({width:360,height:740});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,"Mobile overflow");
   await screenshot(tag+"-mobile.png",middle);
   pass(tag+": 360 px mobile layout has no horizontal overflow");
   await page.close();
  }
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.externalRequests,[]);
  pass("Both standalone files run without browser errors or external requests");
  report.passed=true;
 }finally{await browser.close();}
 save();
})().catch(error=>{report.error=String(error);save();console.error(error);process.exitCode=1;});
