#!/usr/bin/env node
"use strict";
// Generic 2D presentation acceptance of a *native* two-rope / four-pulley run.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {pathToFileURL}=require("node:url"),{createHash}=require("node:crypto");
const {chromium}=require("playwright");
if(process.argv.length!==5)throw new Error("Pass dark.html light.html output_dir");
const [darkPath,lightPath,outPath]=process.argv.slice(2).map(x=>path.resolve(x));
fs.mkdirSync(outPath,{recursive:true});
function read(file){
 const html=fs.readFileSync(file,"utf8");
 const match=html.match(/<script id="recording" type="application\/json">([\s\S]*?)<\/script>/);
 assert.ok(match,"Standalone payload absent");
 return {payload:JSON.parse(match[1]),sha256:createHash("sha256").update(html).digest("hex")};
}
const dark=read(darkPath),light=read(lightPath);
const D=dark.payload,report={passed:false,darkSHA256:dark.sha256,lightSHA256:light.sha256,
 steps:[],screenshots:[],errors:[],externalRequests:[]};
const record=name=>{report.steps.push(name);console.log("PASS",name)};
const save=()=>fs.writeFileSync(path.join(outPath,"report.json"),JSON.stringify(report,null,2));
const close=(a,b,tol=1e-6)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tol,String(a)+" != "+String(b));
(async()=>{
 assert.equal(D.schema,"domelica.rope-playback-2d/v1");
 for(const name of ["schema","times","frames","bounds","metrics","maxRopeLengthDrift_m"])
   assert.deepEqual(D[name],light.payload[name],"Style changed "+name);
 const stableSource=({styleSHA256,...rest})=>rest;
 assert.deepEqual(stableSource(D.provenance),stableSource(light.payload.provenance));
 assert.notDeepEqual(D.style,light.payload.style);
 assert.equal(D.provenance.experimentId,"four-pulley-two-rope");
 assert.equal(D.times.length,1002);
 for(const name of ["S1","S2"])assert.ok(D.maxRopeLengthDrift_m[name]<=1e-6);
 assert.deepEqual(Object.keys(D.frames[0].pulleys),["P1","P2","P3","P4"]);
 assert.deepEqual(Object.keys(D.frames[0].ropes),["S1","S2"]);
 assert.deepEqual(Object.keys(D.frames[0].bodies),["A","B"]);
 assert.deepEqual(D.style.bodySymbols,light.payload.style.bodySymbols);
 assert.deepEqual(D.style.supportMarks,light.payload.style.supportMarks);
 assert.deepEqual(Object.keys(D.style.bodySymbols),["A","B"]);
 assert.ok(D.style.supportMarks.length===2);
 assert.ok(D.style.supportMarks.every(mark=>["wall","ceiling"].includes(mark.kind)));
 assert.deepEqual(Object.keys(D.frames[0].rigidLinks),["P3-to-B"]);
 const baseLink=D.frames[0].rigidLinks["P3-to-B"];
 assert.equal(baseLink.length,3);
 assert.deepEqual(baseLink[0],D.frames[0].pulleys.P3.center);
 assert.deepEqual(baseLink.at(-1),D.frames[0].bodies.B.position);
 const first=D.frames[0],last=D.frames.at(-1);
 assert.ok(last.pulleys.P1.center[0]<first.pulleys.P1.center[0]-1);
 assert.ok(last.pulleys.P3.center[1]>first.pulleys.P3.center[1]+.3);
 assert.deepEqual(last.pulleys.P2,first.pulleys.P2);
 assert.deepEqual(last.pulleys.P4,first.pulleys.P4);
 close(first.bodies.A.position[0]-last.bodies.A.position[0],3);
 close(first.pulleys.P1.center[0]-last.pulleys.P1.center[0],1.5);
 close(last.bodies.B.position[1]-first.bodies.B.position[1],.5);
 close(first.bodies.A.position[0]-last.bodies.A.position[0],
       2*(first.pulleys.P1.center[0]-last.pulleys.P1.center[0]));
 close(first.pulleys.P1.center[0]-last.pulleys.P1.center[0],
       3*(last.bodies.B.position[1]-first.bodies.B.position[1]));
 close(first.ropes.S1.arcs[0].sweep,Math.PI);
 assert.deepEqual(first.ropes.S2.arcs.map(x=>x.pulley),["P2","P3","P4"]);
 for(const [sweep,expected] of first.ropes.S2.arcs.map(x=>x.sweep).map((v,i)=>[v,[Math.PI/2,Math.PI,Math.PI][i]]))
   close(sweep,expected);
 record("Both styles preserve identical native values and source hashes, two distinct ropes, four correct pulleys and 6:3:1 displacement");

 const browser=await chromium.launch({headless:true});
 try{
  for(const [tag,file] of [["dark",darkPath],["light",lightPath]]){
   const page=await browser.newPage({viewport:{width:1024,height:760}});
   const url=pathToFileURL(file).href;
   page.on("pageerror",e=>report.errors.push(String(e)));
   page.on("console",m=>{if(m.type()==="error")report.errors.push(m.text())});
   page.on("request",r=>{if(r.url()!==url&&!/^(data|blob):/.test(r.url()))report.externalRequests.push(r.url())});
   await page.goto(url,{waitUntil:"load"});
   await page.waitForFunction(()=>Boolean(window.__rope2d));
   const value=await page.evaluate(()=>{
     const D=JSON.parse(document.getElementById("recording").textContent),api=window.__rope2d,W=880,H=520;
     const [xmin,ymin,xmax,ymax]=D.bounds,mid=[(xmin+xmax)/2,(ymin+ymax)/2];
     const check=(ok,why)=>{if(!ok)throw new Error(why)};
     const close=(a,b,why)=>{if(!Number.isFinite(a)||Math.abs(a-b)>1e-6)throw new Error(why+": "+a+" != "+b)};
     const xy=e=>e.tagName.toLowerCase()==="rect"
       ? [Number(e.getAttribute("x"))+Number(e.getAttribute("width"))/2,
          Number(e.getAttribute("y"))+Number(e.getAttribute("height"))/2]
       : [Number(e.getAttribute("cx")),Number(e.getAttribute("cy"))];
     const qs=(sel)=>document.querySelector(sel);
     check(document.querySelectorAll("[data-pulley]").length===4,"Four pulley circles");
     check(document.querySelectorAll("[data-axle]").length===4,"Four independent axle glyphs");
     check(document.querySelectorAll("[data-pulley-label]").length===4,"Pulley identities");
     check(document.querySelectorAll("[data-support]").length===2,"Two schematic support marks");
     check(document.querySelectorAll("rect[data-body]").length===2,"Both bodies drawn as decorative rectangles");
     check(document.querySelectorAll("[data-rigid-link]").length===1,"One native-owned rigid carriage link");
     check(document.querySelectorAll("[data-rope-label]").length===2,"Two rope identities");
     check(document.querySelectorAll("[data-metric]").length===D.metrics.length-1,"All native metrics visible");
     check(document.querySelectorAll("[data-rope-length]").length===1,"Both rope lengths visible");
     for(let index=0;index<D.times.length;index++){
       api.seek(index);
       const state=api.getState(),frame=state.frame,scale=state.scale;
       const project=p=>[W/2+(p[0]-mid[0])*scale,H/2-(p[1]-mid[1])*scale];
       check(state.index===index,"Recorded frame index");
       close(state.time,D.times[index],"Recorded time");
       for(const [name,p] of Object.entries(frame.pulleys)){
         const circle=qs('[data-pulley="'+name+'"]'),center=xy(circle);
         project(p.center).forEach((n,i)=>close(center[i],n,"Native pulley center "+name));
         close(Number(circle.getAttribute("r")),scale*p.radius,"Native pulley radius "+name);
         const axle=xy(qs('[data-axle="'+name+'"]'));
         axle.forEach((n,i)=>close(n,center[i],"Pulley axle follows center "+name));
         check(qs('[data-pulley-label="'+name+'"]').textContent===name,"Pulley label matches native ID");
       }
       for(const [name,nodes] of Object.entries(frame.rigidLinks||{})){
         const drawn=qs('[data-rigid-link="'+name+'"]').getAttribute("points").trim().split(/\s+/)
                    .map(value=>value.split(",").map(Number));
         check(drawn.length===nodes.length,"Complete rigid-link positions");
         for(let j=0;j<nodes.length;j++)project(nodes[j])
           .forEach((n,i)=>close(drawn[j][i],n,"Native rigid-link point "+j));
         frame.pulleys.P3.center.forEach((n,i)=>close(nodes[0][i],n,"P3 carrier starts at axle"));
         frame.bodies.B.position.forEach((n,i)=>close(nodes.at(-1)[i],n,"P3 carrier ends at B"));
         close(Math.hypot(nodes[0][0]-nodes[1][0],nodes[0][1]-nodes[1][1]),1,"Rigid vertical carriage span");
         close(Math.hypot(nodes[1][0]-nodes[2][0],nodes[1][1]-nodes[2][1]),1.1,"Rigid horizontal carriage span");
       }
       // Support marks stay attached to native world geometry, not guessed
       // pixel positions or invented physical boundary conditions.
       for(const mark of D.style.supportMarks){
         const display=qs('[data-support="'+mark.id+'"]');
         check(display.getAttribute("data-support-kind")===mark.kind,"Support kind");
         const physical=mark.kind==="wall"
           ? frame.attachments[mark.ref] : frame.pulleys[mark.ref].center;
         const [x,y]=project(physical),span=mark.sizePx;
         const coords=(display.getAttribute("d").match(/[-+]?(?:\d*\.?\d+)(?:e[-+]?\d+)?/gi)||[]).map(Number);
         if(mark.kind==="wall"){
           close(coords[0],x,"Native wall attachment X");
           close(coords[1],y-span/2,"Wall support top");
           close(coords[2],x,"Wall support main plate X");
           close(coords[3],y+span/2,"Wall support bottom");
         }else{
           const r=frame.pulleys[mark.ref].radius*scale,bar=y-r-16;
           close(coords[0],x-span/2,"Ceiling span starts");
           close(coords[1],bar,"Ceiling bar above native pulley");
           close(coords[2],x+span/2,"Ceiling span ends");
           close(coords[7],y-r,"Ceiling stem ends at pulley rim");
         }
       }
       for(const [name,rope] of Object.entries(frame.ropes)){
         const path=qs('[data-rope="'+name+'"]').getAttribute("points").trim().split(/\s+/)
                    .map(s=>s.split(",").map(Number));
         check(path.length===rope.points.length,"Rendered rope point count "+name);
         for(let j=0;j<path.length;j++)project(rope.points[j])
             .forEach((n,i)=>close(path[j][i],n,"Actual SVG rope "+name+" point "+j));
         close(rope.length,D.frames[0].ropes[name].length,"Constant rope "+name);
         check(qs('[data-rope-label="'+name+'"]').textContent===name,"Rope label");
       }
       for(const [name,b] of Object.entries(frame.bodies)){
         const symbol=qs('[data-body="'+name+'"]'),center=xy(symbol);
         const spec=D.style.bodySymbols[name];
         check(symbol.tagName.toLowerCase()==="rect","Generic block glyph used for "+name);
         close(Number(symbol.getAttribute("width")),spec.widthPx,"Decorative block width");
         close(Number(symbol.getAttribute("height")),spec.heightPx,"Decorative block height");
         project(b.position).forEach((n,i)=>close(center[i],n,"Native block "+name));
         const bounds=qs('[data-body-label="'+name+'"]').getBBox();
         check(bounds.x>=0&&bounds.x+bounds.width<=W&&
               bounds.y>=0&&bounds.y+bounds.height<=H,"Clipped body label "+name);
         if(name==="B")check(bounds.y>project(frame.rigidLinks["P3-to-B"][1])[1]+2,
             "Carriage stroke must not run through block B label");
       }
       for(const metric of D.metrics.slice(1)){
         const rendered=qs('[data-metric="'+metric.id+'"]');
         check(rendered.textContent.includes(metric.label),"Metric label "+metric.id);
       }
       check(qs('[data-rope-length="S2"]').textContent.includes("S2"),"Second rope HUD");
     }
     return {samples:D.times.length,pulleys:Object.keys(D.frames[0].pulleys),
             ropes:Object.keys(D.frames[0].ropes)};
   });
   record(tag+": actual SVG rope polylines, four moving/stationary wheels, 2 rope lengths and all metrics match all "+value.samples+" samples");
   for(const [suffix,sample] of [["initial",0],["mid",Math.floor(D.times.length/2)],["final",D.times.length-1]]){
     await page.evaluate(n=>window.__rope2d.seek(n),sample);
     if(tag==="dark"||suffix==="mid"){
       const name=tag+"-"+suffix+".png";
       await page.screenshot({path:path.join(outPath,name),fullPage:true});
       report.screenshots.push(name);
     }
   }
   await page.evaluate(()=>window.__rope2d.seek(0));
   await page.locator("#play").click();
   await page.waitForFunction(()=>window.__rope2d.getState().index>0,null,{timeout:4000});
   await page.locator("#play").click();
   assert.equal((await page.evaluate(()=>window.__rope2d.getState())).playing,false);
   await page.evaluate(n=>{
      const slider=document.getElementById("scrub");slider.value=String(n);
      slider.dispatchEvent(new Event("input",{bubbles:true}));
   },Math.floor(D.times.length/2));
   assert.ok((await page.evaluate(()=>window.__rope2d.getState())).index>0);
   record(tag+": play, pause, scrub works with both ropes and independently moving P1/P3");
   await page.setViewportSize({width:360,height:740});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
   const png=tag+"-mobile.png";
   await page.screenshot({path:path.join(outPath,png),fullPage:true});
   report.screenshots.push(png);
   record(tag+": 360 px layout has no horizontal overflow");
   await page.close();
  }
  assert.deepEqual(report.errors,[]);
  assert.deepEqual(report.externalRequests,[]);
  record("Two standalone files render without browser errors or external requests");
  report.passed=true;
 }finally{await browser.close()}
 save();
})().catch(e=>{report.error=String(e);save();console.error(e);process.exitCode=1});
