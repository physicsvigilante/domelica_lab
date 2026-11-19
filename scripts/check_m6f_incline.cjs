#!/usr/bin/env node
"use strict";
// Focused browser smoke: no external physics and no unrelated mechanism suite.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {pathToFileURL}=require("node:url"),{chromium}=require("playwright");
if(process.argv.length!==5)throw new Error("dark.html light.html output-dir required");
const [dark,light,output]=process.argv.slice(2).map(p=>path.resolve(p));
fs.mkdirSync(output,{recursive:true});
function data(p){
 const h=fs.readFileSync(p,"utf8");
 const m=h.match(/<script id="recording" type="application\/json">([\s\S]*?)<\/script>/);
 assert.ok(m,"Missing recorded payload");
 return JSON.parse(m[1]);
}
const a=data(dark),b=data(light),report={passed:false,steps:[],errors:[],requests:[]};
const pass=s=>{report.steps.push(s);console.log("PASS",s)};
(async()=>{
 assert.deepEqual(a.frames,b.frames);assert.deepEqual(a.times,b.times);
 assert.equal(a.provenance.csvSHA256,b.provenance.csvSHA256);
 assert.notDeepEqual(a.style,b.style);
 assert.ok(a.times.length>=490);
 assert.deepEqual(Object.keys(a.frames[0].ropes),["S1","S2"]);
 assert.deepEqual(Object.keys(a.frames[0].pulleys),["C","Top"]);
 const begin=a.frames[0],end=a.frames.at(-1);
 assert.ok(end.pulleys.C.center[1]>begin.pulleys.C.center[1]);
 assert.deepEqual(end.pulleys.Top,begin.pulleys.Top);
 assert.ok(end.bodies.B.position[1]<begin.bodies.B.position[1]);
 for(const id of ["S1","S2"])assert.ok(a.maxRopeLengthDrift_m[id]<1e-6);
 pass("Native inclined motion and both constant rope lengths match in dark/light styles");
 const browser=await chromium.launch({headless:true});
 try{
   for(const [name,file] of [["dark",dark],["light",light]]){
     const page=await browser.newPage({viewport:{width:900,height:760}});
     const url=pathToFileURL(file).href;
     page.on("pageerror",e=>report.errors.push(String(e)));
     page.on("request",r=>{if(r.url()!==url&&!/^(data|blob):/.test(r.url()))report.requests.push(r.url());});
     await page.goto(url,{waitUntil:"load"});
     await page.waitForFunction(()=>Boolean(window.__rope2d));
     for(const index of [0,Math.floor(a.times.length/2),a.times.length-1]){
       const state=await page.evaluate(i=>{window.__rope2d.seek(i);return window.__rope2d.getState()},index);
       assert.equal(state.index,index);
       assert.equal(Object.keys(state.frame.ropes).length,2);
       const rendered=await page.evaluate(()=>({
        rope1:document.querySelector('[data-rope="S1"]').getAttribute("points").trim().split(/\s+/).length,
        rope2:document.querySelector('[data-rope="S2"]').getAttribute("points").trim().split(/\s+/).length,
        pulleys:document.querySelectorAll("[data-pulley]").length,
        wedges:document.querySelectorAll('[data-rigid-link="incline-outline"]').length,
        bodies:document.querySelectorAll("rect[data-body]").length,
        supports:document.querySelectorAll("[data-support]").length
       }));
       assert.equal(rendered.rope1,state.frame.ropes.S1.points.length);
       assert.equal(rendered.rope2,state.frame.ropes.S2.points.length);
       assert.deepEqual([rendered.pulleys,rendered.wedges,rendered.bodies,rendered.supports],[2,1,2,2]);
     }
     pass(name+": native rope paths, incline geometry, moving/fixed pulley and block glyphs render");
     await page.evaluate(()=>window.__rope2d.seek(0));
     await page.locator("#play").click();
     await page.waitForFunction(()=>window.__rope2d.getState().index>0,null,{timeout:5000});
     await page.locator("#play").click();
     assert.equal((await page.evaluate(()=>window.__rope2d.getState())).playing,false);
     const png=path.join(output,name+"-final.png");
     await page.evaluate(n=>window.__rope2d.seek(n),a.times.length-1);
     await page.screenshot({path:png,fullPage:true});
     pass(name+": recorded play/pause and final screenshot");
     await page.close();
   }
   assert.deepEqual(report.errors,[]);assert.deepEqual(report.requests,[]);
   pass("No browser errors or external requests");report.passed=true;
 }finally{await browser.close();}
 fs.writeFileSync(path.join(output,"report.json"),JSON.stringify(report,null,2));
})().catch(e=>{report.error=String(e);fs.writeFileSync(path.join(output,"report.json"),JSON.stringify(report,null,2));console.error(e);process.exitCode=1});
