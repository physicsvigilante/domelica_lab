#!/usr/bin/env node
"use strict";
// One fresh native run, one rope, three pulley centers. Focused acceptance only.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {pathToFileURL}=require("node:url"),{chromium}=require("playwright");
if(process.argv.length!==5)throw new Error("Pass dark HTML, light HTML, output directory");
const [dark,light,out]=process.argv.slice(2).map(path.resolve);
fs.mkdirSync(out,{recursive:true});
const parse=p=>{let s=fs.readFileSync(p,"utf8");let m=s.match(/<script id="recording" type="application\/json">([\s\S]*?)<\/script>/);assert.ok(m);return JSON.parse(m[1])};
const a=parse(dark),b=parse(light);
assert.deepEqual(a.frames,b.frames);assert.deepEqual(a.times,b.times);
assert.equal(a.provenance.csvSHA256,b.provenance.csvSHA256);
assert.notDeepEqual(a.style,b.style);
assert.ok(a.times.length>=290);
const report={status:"fail",samples:a.times.length,checks:[],screenshots:[],errors:[],externalRequests:[]};
const pass=x=>{report.checks.push(x);console.log("PASS",x)};
(async()=>{
const browser=await chromium.launch({headless:true});
try{
 for(const [name,file] of [["dark",dark],["light",light]]){
  const page=await browser.newPage({viewport:{width:900,height:750}});
  const url=pathToFileURL(file).href;
  page.on("pageerror",e=>report.errors.push(String(e)));
  page.on("request",r=>{if(r.url()!==url&&!/^(data|blob):/.test(r.url()))report.externalRequests.push(r.url())});
  await page.goto(url);await page.waitForFunction(()=>!!window.__rope2d);
  for(const index of [0,Math.floor(a.times.length/2),a.times.length-1]){
   const state=await page.evaluate(i=>{window.__rope2d.seek(i);return window.__rope2d.getState()},index);
   assert.equal(state.index,index);
   assert.equal(Object.keys(state.frame.ropes).length,1);
   assert.equal(Object.keys(state.frame.pulleys).length,3);
   assert.ok(Math.abs(state.frame.ropes["continuous-rope"].length-a.frames[0].ropes["continuous-rope"].length)<1e-7);
   const screen=await page.evaluate(()=>({
     points:document.querySelector('[data-rope="continuous-rope"]').getAttribute("points").split(/\s+/).length,
     pulleys:document.querySelectorAll("[data-pulley]").length,
     blocks:document.querySelectorAll("rect[data-body]").length,
     wall:document.querySelectorAll("[data-support]").length,
     rigid:document.querySelectorAll("[data-rigid-link]").length}));
   assert.equal(screen.points,state.frame.ropes["continuous-rope"].points.length);
   assert.deepEqual([screen.pulleys,screen.blocks,screen.wall,screen.rigid],[3,2,1,1]);
  }
  pass(name+": native one-rope path, 3 pulley centers, A/B blocks, ceiling support and B carrier");
  await page.evaluate(()=>window.__rope2d.seek(0));
  await page.locator("#play").click();await page.waitForFunction(()=>window.__rope2d.getState().index>0,null,{timeout:5000});
  await page.locator("#play").click();
  assert.equal((await page.evaluate(()=>window.__rope2d.getState())).playing,false);
  pass(name+": recorded playback starts and pauses");
  const png=path.join(out,name+"-last.png");
  await page.evaluate(n=>window.__rope2d.seek(n),a.times.length-1);
  await page.screenshot({path:png,fullPage:true});report.screenshots.push(png);
  await page.close();
 }
 assert.deepEqual(report.errors,[]);assert.deepEqual(report.externalRequests,[]);
 pass("No runtime errors or external requests");
 report.status="pass";
}finally{await browser.close();}
fs.writeFileSync(path.join(out,"report.json"),JSON.stringify(report,null,2));
})().catch(e=>{report.error=String(e);fs.writeFileSync(path.join(out,"report.json"),JSON.stringify(report,null,2));console.error(e);process.exitCode=1});
