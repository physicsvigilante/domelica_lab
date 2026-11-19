#!/usr/bin/env node
"use strict";
// Focused 10 s recorded browser acceptance; all physics comes from native CSV.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {pathToFileURL}=require("node:url"),{chromium}=require("playwright");
const args=process.argv.slice(2);
if(args.length!==3)throw new Error("dark.html light.html browser-output-dir required");
const [dark,light,out]=args.map(x=>path.resolve(x));
fs.mkdirSync(out,{recursive:true});
const payload=file=>{
 const html=fs.readFileSync(file,"utf8");
 const match=html.match(/<script id="recording" type="application\/json">([\s\S]*?)<\/script>/);
 assert.ok(match,"Missing recorded payload");
 return JSON.parse(match[1]);
};
const A=payload(dark),B=payload(light);
assert.deepEqual(A.times,B.times);
assert.deepEqual(A.frames,B.frames);
assert.equal(A.provenance.csvSHA256,B.provenance.csvSHA256);
assert.notDeepEqual(A.style,B.style);
assert.ok(A.times.length>=995 && A.times.at(-1)>=9.999);
const rises=A.frames.map(f=>f.metrics.aLift);
const peakIndex=rises.indexOf(Math.max(...rises));
assert.ok(rises[peakIndex]>.08);
const impactIndex=rises.findIndex((x,i)=>i>peakIndex&&x<1e-4);
assert.ok(impactIndex>peakIndex);
assert.ok(A.maxRopeLengthDrift_m.rope<1e-5);
const report={passed:false,samples:A.times.length,peakIndex,impactIndex,checks:[],errors:[],externalRequests:[]};
const pass=x=>{report.checks.push(x);console.log("PASS",x)};
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const [tag,file] of [["dark",dark],["light",light]]){
   const page=await browser.newPage({viewport:{width:900,height:750}});
   const url=pathToFileURL(file).href;
   page.on("pageerror",e=>report.errors.push(String(e)));
   page.on("console",m=>{if(m.type()==="error")report.errors.push(m.text())});
   page.on("request",r=>{if(r.url()!==url&&!/^(data|blob):/.test(r.url()))report.externalRequests.push(r.url());});
   await page.goto(url,{waitUntil:"load"});
   await page.waitForFunction(()=>!!window.__rope2d);
   for(const index of [0,peakIndex,impactIndex,A.times.length-1]){
    const state=await page.evaluate(i=>{window.__rope2d.seek(i);return window.__rope2d.getState()},index);
    assert.equal(state.index,index);
    assert.equal(Object.keys(state.frame.ropes).length,1);
    assert.equal(Object.keys(state.frame.springs).length,1);
    const displayed=await page.evaluate(()=>{
      const box=name=>document.querySelector('[data-body="'+name+'"]');
      const a=box("A"),b=box("B"),spring=document.querySelector('[data-spring="A-spring"]');
      const floor=document.querySelector('[data-support="floor-plate"]');
      return {springPoints:spring.getAttribute("points").split(/\s+/).length,
        ropePoints:document.querySelector('[data-rope="rope"]').getAttribute("points").split(/\s+/).length,
        aY:Number(a.getAttribute("y"))+Number(a.getAttribute("height"))/2,
        bY:Number(b.getAttribute("y"))+Number(b.getAttribute("height"))/2,
        floor:floor?.getAttribute("d"),top:document.querySelectorAll("[data-pulley]").length};
    });
    assert.ok(displayed.springPoints>30);
    assert.equal(displayed.ropePoints,state.frame.ropes.rope.points.length);
    assert.ok(displayed.floor&&displayed.floor.startsWith("M "));
    assert.equal(displayed.top,1);
    const [minX,minY,maxX,maxY]=state.bounds;
    const projectY=y=>260-(y-(minY+maxY)/2)*state.scale;
    assert.ok(Math.abs(displayed.aY-projectY(state.frame.bodies.A.position[1]))<1e-7);
    assert.ok(Math.abs(displayed.bY-projectY(state.frame.bodies.B.position[1]))<1e-7);
   }
   pass(tag+": actual A/B, spring, rope arc and floor follow native positions at key contact frames");
   await page.evaluate(()=>window.__rope2d.seek(0));
   await page.locator("#play").click();
   await page.waitForFunction(()=>window.__rope2d.getState().index>0,null,{timeout:5000});
   await page.locator("#play").click();
   assert.equal((await page.evaluate(()=>window.__rope2d.getState())).playing,false);
   pass(tag+": play/pause uses 10 second native recording");
   for(const [label,index] of [["lift",peakIndex],["impact",impactIndex]]){
      await page.evaluate(i=>window.__rope2d.seek(i),index);
      await page.screenshot({path:path.join(out,tag+"-"+label+".png"),fullPage:true});
   }
   await page.setViewportSize({width:360,height:740});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
   pass(tag+": responsive 360 px playback no horizontal overflow");
   await page.close();
  }
  assert.deepEqual(report.errors,[]);
  assert.deepEqual(report.externalRequests,[]);
  pass("No browser errors or unexpected external requests");
  report.passed=true;
 }finally{await browser.close()}
 fs.writeFileSync(path.join(out,"report.json"),JSON.stringify(report,null,2));
})().catch(e=>{report.error=String(e);fs.writeFileSync(path.join(out,"report.json"),JSON.stringify(report,null,2));console.error(e);process.exitCode=1});
