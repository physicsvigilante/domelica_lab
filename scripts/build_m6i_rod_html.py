#!/usr/bin/env python3
"""Tiny offline 2D SVG for one OpenModelica ball/rod impact recording.

No browser dynamics: rod endpoint positions and ball centers are native
Modelica outputs, including the event-updated angular/linear velocities.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

HTML = r'''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenModelica — elastic ball–rod collision</title>
<style>
*{box-sizing:border-box}
body{background:#101b29;color:#eaf2fc;font:15px system-ui,-apple-system,Segoe UI,sans-serif;margin:0}
main{max-width:990px;margin:0 auto;padding:20px 14px 36px}
h1{margin:6px 0 8px;font-size:clamp(20px,3vw,28px)}
p{color:#a9bdcc;line-height:1.5}
.stage{border:1px solid #35526d;border-radius:16px;overflow:hidden;background:#192c40}
svg{width:100%;height:auto;display:block}
.controls{padding:15px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;background:#243e55}
button{border:1px solid #709bb3;border-radius:8px;background:#3e6b8a;color:white;padding:9px 15px;font-weight:650;cursor:pointer}
input{accent-color:#74cbdc;flex:1;min-width:110px}
.readings{display:flex;gap:17px;flex-wrap:wrap;padding:0 15px 15px;background:#243e55;font-variant-numeric:tabular-nums}
.muted{color:#9cb6ca;font-size:13px}
</style>
<main>
<div class="muted">Domelica Lab · native OpenModelica recording</div>
<h1>Perfectly elastic collision: equal-mass ball and free rod</h1>
<p>Ball strikes the lower end of a freely translating and rotating rod. Motion is computed by OpenModelica, with one instantaneous elastic impact event.</p>
<div class="stage">
<svg viewBox="0 0 900 520" role="img" aria-label="Recorded ball approaching a vertical rod, then the rod translating and rotating">
<rect width="900" height="520" fill="#192c40"/>
<line x1="40" y1="382" x2="860" y2="382" stroke="#6d8da3" stroke-width="1.5" stroke-dasharray="8 7" opacity=".55"/>
<text x="45" y="412" fill="#7898ae" font-size="13">Reference y = 0 (no floor)</text>
<line id="rod" x1="350" y1="22" x2="350" y2="382" stroke="#d3d9de" stroke-width="11" stroke-linecap="round"/>
<circle id="center" cx="350" cy="202" r="5" fill="#f5af6a" stroke="#fff" stroke-width="1"/>
<circle id="ball" cx="130" cy="382" r="17" fill="#46bde2" stroke="#b0f3ff" stroke-width="2"/>
<text id="ball-label" x="130" y="416" text-anchor="middle" fill="#b9e9f6" font-size="17">m</text>
<text id="rod-label" x="365" y="198" fill="#e5ebf0" font-size="17">M</text>
<text id="event-label" x="565" y="56" fill="#fac379" font-size="21" font-weight="700"></text>
<text x="45" y="35" fill="#a7becd" font-size="14">M = m · uniform rod · e = 1 · no pivot</text>
</svg>
<div class="controls">
<button id="play" type="button">Play</button>
<input id="seek" type="range" min="0" value="0" aria-label="Scrub native simulation samples">
<strong id="time">0.000 s</strong>
</div>
<div class="readings">
<span id="vball">Ball: —</span>
<span id="vrod">Rod: —</span>
<span id="omega">Rotation: —</span>
</div>
</div>
<p class="muted">Illustrative values: m = M = 1 kg, rod length 2 m, initial ball speed 2 m/s. Gravity is neglected. This is one ideal instantaneous collision; later recontacts are not modeled. HTML has no OpenModelica dependency or physics solver.</p>
<p class="muted" id="provenance"></p>
</main>
<script type="application/json" id="recording">__DATA_JSON__</script>
<script>
"use strict";
(() => {
 const D=JSON.parse(document.getElementById("recording").textContent);
 const svg=id=>document.getElementById(id);
 const play=svg("play"),seek=svg("seek");
 const X=x=>80+(x+1.5)*180, Y=y=>382-y*180;
 seek.max=String(D.frames.length-1);
 let frameIndex=0,active=false,clockStart=0,offset=0,raf=0;
 const rate=0.55;
 function draw(i){
   frameIndex=Math.max(0,Math.min(D.frames.length-1,i|0));
   const f=D.frames[frameIndex];
   const rod=svg("rod"),ball=svg("ball");
   rod.setAttribute("x1",X(f.upper[0]));rod.setAttribute("y1",Y(f.upper[1]));
   rod.setAttribute("x2",X(f.lower[0]));rod.setAttribute("y2",Y(f.lower[1]));
   ball.setAttribute("cx",X(f.ball[0]));ball.setAttribute("cy",Y(f.ball[1]));
   svg("center").setAttribute("cx",X(f.rodCenter[0]));
   svg("center").setAttribute("cy",Y(f.rodCenter[1]));
   svg("ball-label").setAttribute("x",X(f.ball[0]));
   svg("ball-label").setAttribute("y",Y(f.ball[1])+35);
   svg("rod-label").setAttribute("x",X(f.rodCenter[0])+18);
   svg("rod-label").setAttribute("y",Y(f.rodCenter[1])-7);
   svg("event-label").textContent=f.impacted?"IMPACT · rod rotates":"";
   svg("time").textContent=f.t.toFixed(3)+" s";
   svg("vball").textContent="Ball vx: "+f.ballV.toFixed(3)+" m/s";
   svg("vrod").textContent="Rod vx: "+f.rodV.toFixed(3)+" m/s";
   svg("omega").textContent="Rod ω: "+f.omega.toFixed(3)+" rad/s";
   seek.value=String(frameIndex);
 }
 function indexAt(t){
   let lo=0,hi=D.frames.length;
   while(lo<hi){let m=(lo+hi)>>1;if(D.frames[m].t<=t)lo=m+1;else hi=m;}
   return Math.max(0,lo-1);
 }
 function pause(){active=false;cancelAnimationFrame(raf);play.textContent="Play"}
 function tick(now){
   if(!active)return;
   const t=offset+(now-clockStart)/1000*rate;
   if(t>=D.frames.at(-1).t){draw(D.frames.length-1);pause();return}
   draw(indexAt(t));raf=requestAnimationFrame(tick);
 }
 play.addEventListener("click",()=>{
   if(active){pause();return}
   if(frameIndex===D.frames.length-1)draw(0);
   offset=D.frames[frameIndex].t;clockStart=performance.now();
   active=true;play.textContent="Pause";raf=requestAnimationFrame(tick);
 });
 seek.addEventListener("input",()=>{pause();draw(Number(seek.value))});
 svg("provenance").textContent="OpenModelica native CSV SHA-256: "+D.csvSHA256.slice(0,20)+"…";
 window.__rodDemo={seek:i=>{pause();draw(i)},getState:()=>({...D.frames[frameIndex],frameIndex})};
 draw(0);
})();
</script>
</html>
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    with args.csv.open(encoding="utf-8",newline="") as stream:
        rows=list(csv.DictReader(stream))
    required=["time","ballCenter[1]","ballCenter[2]","rodUpper[1]",
              "rodUpper[2]","rodLower[1]","rodLower[2]","rodCenter[1]",
              "rodCenter[2]","ballV","rodVx","rodOmega","impacted"]
    if not rows or any(key not in rows[0] for key in required):
        raise ValueError("Native recording does not contain all motion coordinates")
    def number(row,key):
        return float(row[key])
    frames=[{
        "t":number(row,"time"),
        "ball":[number(row,"ballCenter[1]"),number(row,"ballCenter[2]")],
        "upper":[number(row,"rodUpper[1]"),number(row,"rodUpper[2]")],
        "lower":[number(row,"rodLower[1]"),number(row,"rodLower[2]")],
        "rodCenter":[number(row,"rodCenter[1]"),number(row,"rodCenter[2]")],
        "ballV":number(row,"ballV"),
        "rodV":number(row,"rodVx"),
        "omega":number(row,"rodOmega"),
        "impacted":number(row,"impacted")>.5
    } for row in rows]
    if len(frames)<100 or not any(f["impacted"] for f in frames):
        raise ValueError("Native impact event or time series missing")
    payload=json.dumps({
        "csvSHA256":hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        "frames":frames},separators=(",",":"),allow_nan=False).replace("<","\\u003c")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(HTML.replace("__DATA_JSON__",payload),encoding="utf-8")
    print(json.dumps({"output":str(args.output),"nativeSamples":len(frames),
                      "firstImpactSample":next(i for i,f in enumerate(frames) if f["impacted"]),
                      "stopTime":frames[-1]["t"]},indent=2))


if __name__=="__main__":
    main()
