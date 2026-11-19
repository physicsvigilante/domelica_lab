/* Generic, sample-indexed observation presentation. No equations of motion.
 * World-resolved vectors and their application points are provided as data.
 * THREE and UI are optional; the same selection model drives the XY preview.
 */
"use strict";
const DomelicaObservationLayer = (() => {
  const kinds = {
    force: {label:"Force",unit:"N",scaleUnit:"m/N"},
    velocity: {label:"Velocity",unit:"m/s",scaleUnit:"s"},
    acceleration: {label:"Acceleration",unit:"m/s²",scaleUnit:"s²"},
    torque: {label:"Torque",unit:"N·m",scaleUnit:"m/(N·m)"}
  };
  const sourceLabels = {native:"Native result", "native-transform":"Native · world-resolved", derived:"Derived from native data"};
  const copy = a => a.slice();
  const length = a => Math.hypot(...a);
  function number(v) {
    if (v === 0) return "0";
    const a = Math.abs(v);
    return a < 1e-3 || a >= 1e4 ? v.toExponential(3) : v.toFixed(a >= 100 ? 2 : 3);
  }
  const make = (tag, cls, text) => {
    const node=document.createElement(tag);
    if(cls) node.className=cls;
    if(text!==undefined) node.textContent=text;
    return node;
  };
  function create(options={}) {
    const T=options.THREE || null, parent=options.parent || null, controls=options.controls || null;
    const onChange=options.onChange || (()=>{});
    let scene=null, index=0, kind="force", body="all", selected=null;
    let enabled=new Set(), byId=new Map(), glyphs=new Map(), baseScale={}, scales={}, boundCache=null;
    let ui=null, cards=new Map();
    const match = o => o.kind===kind && (body==="all" || body===o.body);
    const active = o => match(o) && enabled.has(o.id);
    const rowAt = (rows,i) => rows[rows.length===1?0:i];

    function emit(reason) {
      const focused=typeof document!=="undefined"?document.activeElement?.dataset?.overlayId:null;
      boundCache=null; refreshControls(); update(index);
      if(focused&&cards.has(focused))cards.get(focused).checkbox.focus();
      onChange(reason);
    }
    function disposeGlyphs() {
      // ArrowHelper uses shared geometry. Dispose only per-helper materials.
      for(const g of glyphs.values()) {
        if(parent) parent.remove(g.group);
        for(const arrow of g.arrows) { arrow.line.material.dispose(); arrow.cone.material.dispose(); }
      }
      glyphs.clear();
    }
    function makeGlyph(o) {
      if(!T || !parent) return;
      const group=new T.Group(); group.name="Observation: "+o.id;
      const arrows=[new T.ArrowHelper(new T.Vector3(0,1,0),new T.Vector3(),1,o.color || "#79e5cb")];
      if(o.kind==="torque") arrows.push(new T.ArrowHelper(new T.Vector3(0,1,0),new T.Vector3(),1,o.color || "#79e5cb"));
      for(const arrow of arrows) {
        for(const part of [arrow.line,arrow.cone]) {
          part.material.depthTest=false; part.material.depthWrite=false; part.renderOrder=90;
        }
        group.add(arrow);
      }
      group.visible=false; parent.add(group); glyphs.set(o.id,{group,arrows});
    }
    function loadScene(next) {
      if(!next || !Array.isArray(next.times) || !next.times.length) throw new Error("Observation scene has no native times");
      scene=next; index=0; body="all"; byId=new Map(); enabled=new Set(); disposeGlyphs();
      const bodies=new Set((scene.bodies||[]).map(b=>b.id));
      for(const o of scene.overlays || []) {
        if(!o.id || byId.has(o.id) || !kinds[o.kind] || o.frame!=="world" || !bodies.has(o.body)) throw new Error("Invalid observation metadata: "+o.id);
        for(const rows of [o.positions,o.vectors]) {
          if(!Array.isArray(rows) || ![1,scene.times.length].includes(rows.length) || !rows.every(r=>Array.isArray(r)&&r.length===3&&r.every(Number.isFinite))) throw new Error("Invalid native observation samples: "+o.id);
        }
        if(!sourceLabels[o.source?.mode]) throw new Error("Unspecified observation origin: "+o.id);
        byId.set(o.id,o); if(o.defaultVisible!==false) enabled.add(o.id); makeGlyph(o);
      }
      const available=Object.keys(kinds).filter(k=>(scene.overlays||[]).some(o=>o.kind===k));
      kind=available.includes("force")?"force":available[0]||"force";
      const extent=Math.max(.1,length(scene.bounds.max.map((v,k)=>v-scene.bounds.min[k])));
      baseScale={}; scales={};
      for(const k of available) {
        let max=0;
        for(const o of scene.overlays.filter(o=>o.kind===k)) for(const v of o.vectors) max=Math.max(max,length(v));
        const raw=max>0?.22*extent/max:1;
        // A readable shared scale, never separate per-vector normalisation.
        const decade=Math.pow(10,Math.floor(Math.log10(raw)));
        baseScale[k]=Math.max(Number.MIN_VALUE,Math.round(raw/decade*10)/10*decade);
        scales[k]=baseScale[k];
      }
      selected=(scene.overlays||[]).find(match)?.id || null; boundCache=null;
      refreshControls(); update(0);
    }
    function getActiveSamples(i=index) {
      if(!scene) return [];
      i=Math.max(0,Math.min(scene.times.length-1,Math.round(i)));
      const s=scales[kind] || 1;
      return (scene.overlays||[]).filter(active).map(o=>{
        const point=copy(rowAt(o.positions,i)), vector=copy(rowAt(o.vectors,i));
        return {id:o.id,label:o.label,kind:o.kind,unit:o.unit,body:o.body,point,vector,
          end:point.map((p,j)=>p+vector[j]*s),magnitude:length(vector),scale:s,
          color:o.color,source:o.source,signConvention:o.signConvention,pointLabel:o.point.label,frame:o.frame};
      });
    }
    function update(i=index) {
      if(!scene) return;
      index=Math.max(0,Math.min(scene.times.length-1,Math.round(i)));
      for(const glyph of glyphs.values()) glyph.group.visible=false;
      for(const sample of getActiveSamples()) {
        const glyph=glyphs.get(sample.id);
        // Only true zero lacks a direction. No near-zero cutoff or minimum length.
        if(!glyph || sample.magnitude===0) continue;
        const len=sample.magnitude*sample.scale, d=sample.vector.map(v=>v/sample.magnitude);
        glyph.group.visible=true;
        const arrow=glyph.arrows[0]; arrow.position.fromArray(sample.point); arrow.setDirection(new T.Vector3(...d));
        arrow.setLength(len,Math.min(.26*len,.14),Math.min(.14*len,.08));
        if(glyph.arrows.length===2) {
          const second=glyph.arrows[1];
          second.position.fromArray(sample.point.map((p,j)=>p+.56*len*d[j]));
          second.setDirection(new T.Vector3(...d));
          second.setLength(.22*len,.22*len,Math.min(.14*len,.08));
        }
      }
      updateReadouts();
    }
    function extendBounds(original) {
      if(boundCache) return {min:copy(boundCache.min),max:copy(boundCache.max)};
      const out={min:copy(original.min),max:copy(original.max)}, s=scales[kind]||1;
      for(const o of scene?.overlays||[]) if(active(o)) {
        for(let i=0;i<scene.times.length;i++) {
          const p=rowAt(o.positions,i),v=rowAt(o.vectors,i),m=length(v);
          const radius=Math.min(.14*m*s,.08);
          for(let k=0;k<3;k++) {
            out.min[k]=Math.min(out.min[k],p[k]-radius,p[k]+v[k]*s-radius);
            out.max[k]=Math.max(out.max[k],p[k]+radius,p[k]+v[k]*s+radius);
          }
        }
      }
      boundCache=out; return {min:copy(out.min),max:copy(out.max)};
    }
    function ensureSelection() {
      if(!selected || !byId.has(selected) || !match(byId.get(selected))) selected=(scene?.overlays||[]).find(match)?.id||null;
    }
    function setKind(value) {
      if(!kinds[value] || !(scene?.overlays||[]).some(o=>o.kind===value)) throw new Error("Unavailable observation quantity: "+value);
      kind=value; ensureSelection(); emit("kind");
    }
    function setBody(value) {
      if(value!=="all" && !(scene?.bodies||[]).some(b=>b.id===value)) throw new Error("Unknown observation body: "+value);
      body=value; ensureSelection(); emit("body");
    }
    function setScale(value) {
      if(!Number.isFinite(value)||value<=0) throw new Error("Arrow scale must be positive and finite");
      scales[kind]=value; emit("scale");
    }
    function setEnabled(id,show) {
      if(!byId.has(id)) throw new Error("Unknown observation: "+id);
      show?enabled.add(id):enabled.delete(id); emit("visibility");
    }
    function select(id) {
      if(!byId.has(id)) throw new Error("Unknown observation: "+id);
      selected=id; updateReadouts(); onChange("selection");
    }
    function getState() {
      return {kind,body,index,selected,scale:scales[kind]||1,scaleUnit:kinds[kind].scaleUnit,
        enabled:[...enabled],visible:(scene?.overlays||[]).filter(active).map(o=>o.id),
        availableKinds:Object.keys(kinds).filter(k=>(scene?.overlays||[]).some(o=>o.kind===k)),
        baseScale:baseScale[kind]||1};
    }
    function mountControls() {
      if(!controls) return;
      const top=make("div","observation-controls"), kindLabel=make("label",null,"Quantity"), bodyLabel=make("label",null,"Body");
      const quantity=make("select"), recipient=make("select"); quantity.setAttribute("aria-label","Observation quantity"); recipient.setAttribute("aria-label","Receiving or observed body");
      kindLabel.append(quantity); bodyLabel.append(recipient); top.append(kindLabel,bodyLabel);
      quantity.addEventListener("change",()=>setKind(quantity.value)); recipient.addEventListener("change",()=>setBody(recipient.value));
      const scaleBox=make("label","observation-scale"), scaleName=make("span",null,"Arrow scale"), scaleValue=make("output"), range=make("input");
      range.type="range"; range.min="0"; range.max="100"; range.step="1"; range.value="50"; range.setAttribute("aria-label","Common arrow scale for selected quantity");
      const scaleLine=make("span","observation-scale-line"); scaleLine.append(scaleName,scaleValue); scaleBox.append(scaleLine,range);
      range.addEventListener("input",()=>setScale((baseScale[kind]||1)*Math.pow(2,(Number(range.value)-50)/20)));
      const legend=make("p","observation-legend","World coordinates. In XY: X right, Y up, +Z toward the viewer. Arrows share one scale within each quantity.");
      const list=make("div","observation-list"), detail=make("div","observation-detail");
      const selectedName=make("strong"), components=make("div","observation-components"), location=make("div","observation-location"), sense=make("div","observation-sense");
      const source=make("details","observation-source"), summary=make("summary",null,"Inspect source"), sourceBody=make("div"); source.append(summary,sourceBody);
      detail.append(selectedName,components,location,sense,source);
      controls.replaceChildren(top,scaleBox,legend,list,detail);
      ui={quantity,recipient,scaleValue,range,legend,list,selectedName,components,location,sense,sourceBody};
    }
    function refreshControls() {
      if(!ui || !scene) return;
      ui.quantity.replaceChildren();
      for(const [key,info] of Object.entries(kinds)) {
        if(!scene.overlays.some(o=>o.kind===key)) continue;
        const op=make("option",null,info.label); op.value=key; ui.quantity.append(op);
      }
      ui.quantity.value=kind; ui.recipient.replaceChildren();
      const all=make("option",null,"All bodies"); all.value="all"; ui.recipient.append(all);
      for(const b of scene.bodies||[]) {const op=make("option",null,b.label);op.value=b.id;ui.recipient.append(op);}
      ui.recipient.value=body;
      const scale=scales[kind]||1;
      ui.scaleValue.textContent=number(scale)+" "+kinds[kind].scaleUnit;
      ui.range.value=String(Math.max(0,Math.min(100,50+20*Math.log2(scale/(baseScale[kind]||1)))));
      ui.range.setAttribute("aria-valuetext",number(scale)+" "+kinds[kind].scaleUnit);
      ui.legend.textContent=kind==="torque"?"Torque uses a double arrow along its axis, with the right-hand convention. In XY: ⊙ is +Z, ⊗ is −Z; ring size does not encode magnitude.":"World coordinates. In XY: X right, Y up, +Z toward the viewer. Arrows share one scale; zero has no arrow."+(kind==="force"&&scene.overlays.some(o=>o.kind==="torque")?" Torques are shown separately.":"");
      ui.list.replaceChildren(); cards=new Map();
      for(const o of scene.overlays.filter(match)) {
        const row=make("div","observation-row"), checkbox=make("input"), label=make("label","observation-check"), swatch=make("span","observation-swatch");
        checkbox.type="checkbox";checkbox.dataset.overlayId=o.id;checkbox.checked=enabled.has(o.id);checkbox.setAttribute("aria-label","Show "+o.label);checkbox.addEventListener("change",()=>setEnabled(o.id,checkbox.checked));
        swatch.style.background=o.color||"#79e5cb";label.append(checkbox,swatch);
        const choose=make("button","observation-select"), title=make("span",null,o.label), mode=make("small",null,sourceLabels[o.source.mode]); choose.type="button";choose.append(title,mode);choose.addEventListener("click",()=>select(o.id));
        const value=make("output","observation-value"); row.append(label,choose,value); ui.list.append(row);cards.set(o.id,{row,choose,value,checkbox});
      }
      if(!cards.size) ui.list.append(make("p","observation-empty","No "+kinds[kind].label.toLowerCase()+" observations for this body."));
    }
    function updateReadouts() {
      if(!ui || !scene) return;
      for(const [id,c] of cards) {
        const o=byId.get(id),v=rowAt(o.vectors,index); c.value.textContent=number(length(v))+" "+o.unit;
        c.row.classList.toggle("selected",id===selected);c.choose.setAttribute("aria-pressed",String(id===selected));
      }
      const o=byId.get(selected);
      if(!o || !match(o)) {ui.selectedName.textContent="";ui.components.textContent="";ui.location.textContent="";ui.sense.textContent="";ui.sourceBody.textContent="";return;}
      const v=rowAt(o.vectors,index),p=rowAt(o.positions,index),bodyLabel=(scene.bodies||[]).find(b=>b.id===o.body)?.label || o.body;
      ui.selectedName.textContent=o.label+" · "+bodyLabel;
      ui.components.textContent="X "+number(v[0])+"   Y "+number(v[1])+"   Z "+number(v[2])+"   "+o.unit;
      ui.location.textContent=o.point.label+": ("+p.map(number).join(", ")+") m";
      ui.sense.textContent=o.signConvention;
      ui.sourceBody.replaceChildren(make("div",null,sourceLabels[o.source.mode]+" · world coordinates"),make("code",null,o.source.expression));
    }
    mountControls();
    return {loadScene,update,getActiveSamples,getState,setKind,setBody,setScale,setEnabled,select,extendBounds,
      dispose:disposeGlyphs,formatNumber:number};
  }
  return {create,kinds,sourceLabels};
})();
