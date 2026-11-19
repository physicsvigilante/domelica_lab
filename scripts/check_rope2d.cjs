#!/usr/bin/env node
"use strict";
// Exact delivered standalone 2D SVG playback acceptance; no browser solver.
const assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path");
const {pathToFileURL}=require("node:url");
const {chromium}=require("playwright");
const {createHash}=require("node:crypto");
const [darkPath,lightPath,outPath]=process.argv.slice(2).map(x=>path.resolve(x));
if(!darkPath||!lightPath||!outPath)throw new Error("Pass dark HTML, light HTML, output directory");
fs.mkdirSync(outPath,{recursive:true});
const read=p=>{
 const html=fs.readFileSync(p,"utf8");
 const match=html.match(/<script id="recording" type="application\/json">([\s\S]*?)<\/script>/);
 assert.ok(match,"Standalone HTML requires native JSON payload");
 return {payload:JSON.parse(match[1]),sha256:createHash("sha256").update(html).digest("hex")};
};
const dark=read(darkPath),light=read(lightPath);
assert.equal(dark.payload.schema,"domelica.rope-playback-2d/v1");
assert.deepEqual(dark.payload.times,light.payload.times);
assert.deepEqual(dark.payload.frames,light.payload.frames);
assert.deepEqual(dark.payload.bounds,light.payload.bounds);
assert.equal(dark.payload.provenance.csvSHA256,light.payload.provenance.csvSHA256);
assert.notDeepEqual(dark.payload.style,light.payload.style,"Style changes must not change physical recordings");
assert.ok(dark.payload.times.length>=1000);
for(const payload of [dark.payload,light.payload]){
 assert.ok(payload.maxRopeLengthDrift_m.rope < 1e-6);
 const first=payload.frames[0],last=payload.frames.at(-1);
 assert.ok(Math.abs(last.bodies.light.position[1]-first.bodies.light.position[1]-1.4)<2e-4);
 assert.ok(Math.abs(first.bodies.heavy.position[1]-last.bodies.heavy.position[1]-1.4)<2e-4);
 assert.ok(Math.abs(first.ropes.rope.arcs[0].sweep-Math.PI)<1e-8);
 assert.ok(first.ropes.rope.points.length>=20);
}
const report={passed:false,darkSHA256:dark.sha256,lightSHA256:light.sha256,
 steps:[],screenshots:[],errors:[],externalRequests:[]};
const pass=name=>{report.steps.push(name);console.log("PASS",name);};
const fail=err=>{report.error=String(err);fs.writeFileSync(path.join(outPath,"report.json"),JSON.stringify(report,null,2));throw err};
const browserURL=p=>pathToFileURL(p).href;
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const [tag,file] of [["dark",darkPath],["light",lightPath]]){
   const page=await browser.newPage({viewport:{width:900,height:760}});
   const uri=browserURL(file);
   page.on("pageerror",e=>report.errors.push(String(e)));
   page.on("console",msg=>{if(msg.type()==="error")report.errors.push(msg.text());});
   page.on("request",req=>{if(req.url()!==uri&&!/^(data|blob):/.test(req.url()))report.externalRequests.push(req.url());});
   await page.goto(uri,{waitUntil:"load"});
   await page.waitForFunction(()=>!!window.__rope2d);
   let state=await page.evaluate(()=>window.__rope2d.getState());
   assert.equal(state.index,0);
   const native=tag==="dark"?dark.payload:light.payload;
   for(const index of [0,Math.floor(native.times.length/2),native.times.length-1]){
    await page.evaluate(n=>window.__rope2d.seek(n),index);
    state=await page.evaluate(()=>window.__rope2d.getState());
    assert.equal(state.index,index);
    assert.equal(state.time,native.times[index]);
    const rendered=await page.evaluate(()=>{
     const points=document.querySelector("[data-rope='rope']").getAttribute("points")
       .trim().split(/\s+/).map(x=>x.split(",").map(Number));
     const pos=(name)=>{const c=document.querySelector('[data-body="'+name+'"]');
       return [Number(c.getAttribute("cx")),Number(c.getAttribute("cy"))];};
     const pulley=document.querySelector("[data-pulley='P']");
     return {points,light:pos("light"),heavy:pos("heavy"),
       pulley:[Number(pulley.getAttribute("cx")),Number(pulley.getAttribute("cy"))],
       radius:Number(pulley.getAttribute("r"))};
    });
    const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,String(a)+" != "+String(b));
    rendered.light.forEach((v,i)=>close(v,rendered.points[0][i]));
    rendered.heavy.forEach((v,i)=>close(v,rendered.points.at(-1)[i]));
    close(rendered.radius,state.frame.pulleys.P.radius*state.scale);
    const c=state.frame.pulleys.P.center;
    const start=state.frame.ropes.rope.arcs[0].center;
    start.forEach((v,i)=>close(v,c[i]));
    assert.ok(rendered.points.length>20);
   }
   pass(tag+": real SVG rope endpoints, arc, pulley radius and both native bodies agree across frames");
   await page.evaluate(()=>window.__rope2d.seek(0));
   await page.locator("#play").click();
   await page.waitForFunction(()=>window.__rope2d.getState().index>0,null,{timeout:4000});
   await page.locator("#play").click();
   assert.equal((await page.evaluate(()=>window.__rope2d.getState())).playing,false);
   await page.evaluate(()=>{
     const el=document.querySelector("#scrub");el.value=String(Math.floor(Number(el.max)/2));
     el.dispatchEvent(new Event("input",{bubbles:true}));
   });
   assert.ok((await page.evaluate(()=>window.__rope2d.getState())).index>0);
   pass(tag+": playback, pause and timeline scrub update actual SVG from recordings");
   await page.screenshot({path:path.join(outPath,tag+"-desktop.png")});
   await page.setViewportSize({width:360,height:740});
   await page.evaluate(()=>window.__rope2d.seek(Math.floor(Number(document.querySelector("#scrub").max)/2)));
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
   assert.equal(overflow,false,"Mobile layout has horizontal overflow");
   if(tag==="dark")await page.screenshot({path:path.join(outPath,"dark-mobile.png")});
   pass(tag+": 360 px layout fits without overflow");
   await page.close();
  }
  assert.deepEqual(report.errors,[]);
  assert.deepEqual(report.externalRequests,[]);
  pass("Both styles preserve identical native physics, no browser errors or network requests");
  report.passed=true;
 }finally{await browser.close();}
 fs.writeFileSync(path.join(outPath,"report.json"),JSON.stringify(report,null,2));
})().catch(fail);
