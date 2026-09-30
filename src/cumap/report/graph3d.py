"""Interactive growth graph (growth3d.html): deterministic 3D and 2D layouts in Python, a small
dependency-free canvas renderer in the page (drag to spin/move, wheel to zoom, click a node to
read the concept, toggle 2D/3D with a morph). No external library, so the page stays a single
offline file.
"""

from __future__ import annotations

import json
import math
from html import escape

import networkx as nx
import numpy as np


def _fibonacci_sphere(n: int, radius: float) -> list[tuple[float, float, float]]:
    golden = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / max(n, 1)
        r = math.sqrt(max(0.0, 1 - y * y))
        theta = golden * i
        out.append((radius * r * math.cos(theta), radius * y, radius * r * math.sin(theta)))
    return out


def layout3d(
    node_ids: list[str], edges: list[tuple[str, str]], *, seed: int = 42
) -> dict[str, tuple[float, float, float]]:
    """Connected components: Kamada-Kawai in 3D (seeded random start, otherwise the planar start
    would stay flat), the biggest at the origin, the rest on a shell around it; isolated nodes on
    an outer shell. Same input -> same output.
    """
    g = nx.Graph()
    g.add_edges_from(sorted(edges))
    connected = set(g.nodes)
    isolated = [n for n in node_ids if n not in connected]
    comps = sorted((sorted(c) for c in nx.connected_components(g)), key=lambda c: (-len(c), c[0]))
    rng = np.random.default_rng(seed)
    pos: dict[str, tuple[float, float, float]] = {}
    main_radius = 100.0
    shell = _fibonacci_sphere(max(len(comps) - 1, 1), main_radius * 2.0)
    for ci, comp in enumerate(comps):
        n = len(comp)
        if n == 1:
            raw = {comp[0]: np.zeros(3)}
        elif n == 2:
            raw = {comp[0]: np.array([-1.0, 0, 0]), comp[1]: np.array([1.0, 0, 0])}
        else:
            start = {c: rng.normal(size=3) for c in comp}
            raw = nx.kamada_kawai_layout(g.subgraph(comp), pos=start, dim=3)
        pts = np.array([raw[c] for c in comp], dtype=float)
        pts -= pts.mean(axis=0)
        extent = float(np.abs(pts).max()) or 1.0
        radius = main_radius if ci == 0 else 10 + 9 * math.sqrt(n)
        centre = (0.0, 0.0, 0.0) if ci == 0 else shell[ci - 1]
        for c, p in zip(comp, pts, strict=True):
            q = p / extent * radius
            pos[c] = (centre[0] + q[0], centre[1] + q[1], centre[2] + q[2])
    for n, p in zip(isolated, _fibonacci_sphere(len(isolated), main_radius * 2.7), strict=True):
        pos[n] = p
    return pos


def layout2d_matching(
    node_ids: list[str], edges: list[tuple[str, str]], top_ids: set[str], radius: float
) -> dict[str, tuple[float, float]]:
    """2D layout (component-packed Kamada-Kawai from graph.layout), centred and uniformly scaled
    so the default (top-N) nodes span about `radius`, matching the 3D scene's scale."""
    from cumap.report.graph import layout

    raw = layout(node_ids, edges, width=1300, height=1000)
    ref = [raw[i] for i in top_ids if i in raw] or list(raw.values())
    cx = (min(p[0] for p in ref) + max(p[0] for p in ref)) / 2
    cy = (min(p[1] for p in ref) + max(p[1] for p in ref)) / 2
    extent = max(max(abs(p[0] - cx) for p in ref), max(abs(p[1] - cy) for p in ref)) or 1.0
    k = radius / extent
    return {i: ((p[0] - cx) * k, (p[1] - cy) * k) for i, p in raw.items()}


CSS3D = """
:root{--ease:cubic-bezier(0.23,1,0.32,1);--card:#ffffff;--line:var(--grid);--accent:var(--s1);
--r-box:12px;--r-ctl:8px;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--card:#232322;--ink:#ecebe6}}
*{box-sizing:border-box}
::selection{background:color-mix(in srgb,var(--accent) 30%,transparent)}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,sans-serif;
-webkit-font-smoothing:antialiased;text-wrap:pretty}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 20px 4px;flex-wrap:wrap}
h1{margin:0;font-size:18px;font-weight:650;letter-spacing:-0.02em;text-wrap:balance}
.sub{margin:2px 0 0;color:var(--ink2);font-size:13px}
.note{margin:8px 20px 12px;padding:7px 12px;border:1px solid color-mix(in srgb,var(--warning) 45%,transparent);
border-radius:var(--r-ctl);background:color-mix(in srgb,var(--warning) 12%,transparent);color:var(--ink2);font-size:12px}
.note b{color:var(--ink)}
button,select,input{font:inherit;color:var(--ink)}
button{cursor:pointer}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.num{font-variant-numeric:tabular-nums}
.seg{position:relative;display:inline-grid;grid-template-columns:1fr 1fr;background:color-mix(in srgb,var(--ink) 8%,transparent);
border-radius:var(--r-ctl);padding:3px;width:120px}
.seg button{position:relative;z-index:1;background:none;border:0;padding:5px 0;border-radius:6px;color:var(--ink2);
font-weight:600;transition:color 160ms var(--ease),transform 160ms var(--ease)}
.seg button:hover{color:var(--ink)}
.seg button[aria-pressed=true]{color:var(--ink)}
.seg button:active{transform:scale(0.97)}
.seg-ind{position:absolute;top:3px;bottom:3px;left:3px;width:calc(50% - 3px);background:var(--card);border-radius:6px;
box-shadow:0 1px 3px color-mix(in srgb,var(--ink) 22%,transparent);transition:transform 220ms var(--ease)}
.seg[data-v="3"] .seg-ind{transform:translateX(100%)}
#app{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:14px;padding:0 20px;align-items:start}
@media (max-width:980px){#app{grid-template-columns:1fr}}
#stage,#panel{height:clamp(520px,78vh,820px)}
#stage{position:relative;border:1px solid var(--line);border-radius:var(--r-box);background:var(--bg);overflow:hidden}
#cv{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;touch-action:none}
#cv:focus-visible{outline-offset:-3px}
#cv.drag{cursor:grabbing}
.hud{position:absolute;display:flex;gap:6px;flex-wrap:wrap;align-items:center;pointer-events:none}
.hud>*{pointer-events:auto}
.tl{top:12px;left:12px;right:132px}.tr{top:12px;right:12px}
.pill,.find{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;font-size:12px;
background:var(--card);border:1px solid var(--line);color:var(--ink);cursor:pointer;user-select:none;
transition:transform 160ms var(--ease),background-color 160ms var(--ease),border-color 160ms var(--ease)}
.pill:hover{border-color:color-mix(in srgb,var(--ink) 35%,var(--line))}
.pill:active,.btn:active,.play:active{transform:scale(0.97)}
.pill:has(input:checked){border-color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,var(--card))}
.pill input{position:absolute;opacity:0;pointer-events:none}
.pill:has(input:focus-visible){outline:2px solid var(--accent);outline-offset:2px}
.find{cursor:text;padding:2px 4px 2px 10px}
.find span{color:var(--ink2)}
.find input{width:150px;background:none;border:0;padding:3px 6px;outline:none;min-width:0}
.find:focus-within{border-color:var(--accent);outline:2px solid var(--accent);outline-offset:2px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border-radius:999px;font-size:12px;
background:var(--card);border:1px solid var(--line);color:var(--ink2)}
.btn{background:var(--card);border:1px solid var(--line);border-radius:var(--r-ctl);padding:5px 11px;
transition:transform 160ms var(--ease),border-color 160ms var(--ease)}
.btn:hover{border-color:color-mix(in srgb,var(--ink) 35%,var(--line))}
.hint{top:52px;right:14px;max-width:46%;justify-content:flex-end;gap:2px 14px;color:var(--ink2);font-size:12px;
text-shadow:0 0 6px var(--bg),0 0 6px var(--bg)}
.dock{position:absolute;left:12px;right:12px;bottom:12px;display:grid;grid-template-columns:auto 1fr auto;gap:8px 12px;
align-items:center;padding:10px 12px;border:1px solid var(--line);border-radius:var(--r-box);background:var(--card)}
.play{width:36px;height:36px;border-radius:50%;border:0;background:var(--accent);color:#fff;
display:grid;place-items:center;transition:transform 160ms var(--ease),filter 160ms var(--ease)}
.play:hover{filter:brightness(1.08)}
.play svg{width:14px;height:14px;fill:currentColor}
.play .i-pause,.play[data-state=playing] .i-play{display:none}
.play[data-state=playing] .i-pause{display:block}
.scrub{position:relative;padding-bottom:14px}
#timebar{width:100%;margin:0;accent-color:var(--accent)}
.ticks{position:absolute;left:8px;right:8px;bottom:0;height:12px;font-size:11px;color:var(--ink2)}
.ticks span{position:absolute;transform:translateX(-50%)}
#speed{background:var(--card);border:1px solid var(--line);border-radius:var(--r-ctl);padding:4px 6px}
.cap{grid-column:1/-1;display:flex;justify-content:space-between;gap:4px 16px;flex-wrap:wrap;font-size:12px;color:var(--ink2)}
.cap b{color:var(--ink);font-size:13px;font-weight:600}
.cap .stats{display:flex;gap:14px}
#panel{border:1px solid var(--line);border-radius:var(--r-box);padding:16px;background:var(--card);overflow:auto;font-size:13px;
scrollbar-width:thin;scrollbar-color:color-mix(in srgb,var(--ink) 28%,transparent) transparent}
#panel .in{animation:in 150ms var(--ease)}
@keyframes in{from{opacity:0}to{opacity:1}}
#panel h2{margin:0 0 8px;font-size:18px;font-weight:650;letter-spacing:-0.02em;text-wrap:balance}
#panel .meta{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
#panel h4{margin:18px 0 6px;font-size:12px;font-weight:600;color:var(--ink2)}
#panel p{margin:0 0 6px}
#panel blockquote{margin:4px 0 0;padding:0 0 0 10px;border-left:1px solid var(--line);color:var(--ink2)}
.item{padding:9px 0;border-top:1px solid var(--line)}
h4+.item{border-top:0}
.item .sec{font-size:12px;color:var(--ink2)}
#panel a{color:var(--accent);cursor:pointer;font-weight:600;text-decoration:none;text-underline-offset:3px}
#panel a:hover{text-decoration:underline}
.empty{color:var(--ink2);padding:24px 6px}
.empty b{display:block;color:var(--ink);font-size:15px;margin-bottom:6px}
.err{padding:24px;color:var(--ink)}
footer{padding:12px 20px 28px;color:var(--ink2);font-size:12px}
footer .prov{display:flex;flex-wrap:wrap;gap:2px 18px;margin-bottom:4px}
@media (max-width:720px){.hint{display:none}.tl{right:12px;top:56px}.tr{top:12px}
.top{padding-inline:14px}#app{padding-inline:14px}.note{margin-inline:14px}#stage{height:74vh}}
@media (pointer:coarse){.play{width:44px;height:44px}.pill,.btn,.find{min-height:36px}}
@media (prefers-reduced-motion:reduce){*{transition-duration:0.01ms!important;animation-duration:0.01ms!important}}
"""

JS3D = r"""
(function(){
const $=s=>document.querySelector(s),esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
try{main();}catch(err){$('#panel').innerHTML='<div class="err"><b>The graph could not be drawn.</b><p>'+esc(err&&err.message)+
 '</p><p>Rebuild the report with <code>cumap demo build</code>.</p></div>';}
function main(){
const D=JSON.parse(document.getElementById('d3d').textContent),cv=$('#cv'),ctx=cv.getContext('2d');
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
let W=0,H=0,need=1;
function resize(){const d=window.devicePixelRatio||1,r=cv.getBoundingClientRect();W=r.width;H=r.height;
 cv.width=Math.round(W*d);cv.height=Math.round(H*d);ctx.setTransform(d,0,0,d,0,0);need=1;}
window.addEventListener('resize',resize);resize();
let C={};function readColors(){const cs=getComputedStyle(document.documentElement),g=n=>cs.getPropertyValue(n).trim();
 C={bg:g('--bg'),ink:g('--ink'),ink2:g('--ink2'),ref:g('--ref'),s:[...Array(8)].map((_,i)=>g('--s'+(i+1)))};need=1;}
readColors();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',readColors);
const N=D.nodes.map(n=>Object.assign({a:0,ta:0,pop:0,sx:0,sy:0,p:1,z2:0,r:4,adj:[]},n)),byId={};
N.forEach(n=>byId[n.i]=n);
const E=D.edges.map(e=>Object.assign({a:0,ta:0,pop:0},e,{S:byId[e.s],T:byId[e.t]}));
E.forEach(e=>{e.S.adj.push(e);e.T.adj.push(e);});
const STEPS=D.steps,last=STEPS.length-1,R=D.radius;
let yaw=0.6,pitch=0.3,zoom=1,panX=0,panY=0,sel=null,hover=null,drag=false,moved=0,lx=0,ly=0,shift=false,prev=-1;
let goX=null,goY=null;
let mode=3,mix=0,mixFrom=0,mixTo=0,mixT0=0;const MIX_MS=360;
const bar=$('#timebar'),all=$('#showall'),pre=$('#showprereq'),fam=$('#famcolor'),play=$('#play'),speed=$('#speed');
const easeOut=t=>1-Math.pow(1-t,5);
const HINTS={2:['Drag to move','Scroll to zoom','Click a concept'],3:['Drag to spin','Scroll to zoom','Shift-drag to move','Click a concept']};
function setHint(){$('#hint').innerHTML=HINTS[mode].map(t=>'<span>'+t+'</span>').join('');}
function setMode(m){if(m===mode)return;mode=m;mixFrom=mix;mixTo=m===2?1:0;mixT0=performance.now();
 $('.seg').dataset.v=m;$('#v2').setAttribute('aria-pressed',m===2);$('#v3').setAttribute('aria-pressed',m===3);
 setHint();if(reduce){mix=mixTo;}need=1;}
function visibleTargets(){const t=+bar.value,st=STEPS[t],ment=new Set(st.mentioned);
 $('#stepname').textContent='Section '+st.caption;$('#stepch').textContent='Chapter '+st.chapter+', step '+(t+1)+' of '+STEPS.length;
 N.forEach(n=>{n.ta=(n.sec<=t&&(all.checked||n.rank<D.topn))?1:0;
  if(t!==prev&&n.ta&&!reduce){if(n.sec===t)n.pop=1;else if(ment.has(n.i))n.pop=0.55;}});
 let ne=0,nn=0;N.forEach(n=>{if(n.ta)nn++;});
 E.forEach(e=>{e.ta=(e.sec<=t&&e.S.ta&&e.T.ta)?1:0;if(e.ta)ne++;if(t!==prev&&e.ta&&e.sec===t&&!reduce)e.pop=1;});
 let m=0;for(let i=0;i<=t;i++)m+=STEPS[i].merges;
 $('#cn').textContent=nn+' concepts';$('#ce').textContent=ne+' relations';$('#cm').textContent=m+' merged names';prev=t;need=1;}
function project(n){const ym=yaw*(1-mix),pm=pitch*(1-mix),cy=Math.cos(ym),sy=Math.sin(ym),cx=Math.cos(pm),sx=Math.sin(pm);
 const X=n.x+(n.x2-n.x)*mix,Y=n.y+(n.y2-n.y)*mix,Z=n.z*(1-mix);
 let x=X*cy+Z*sy,z=-X*sy+Z*cy,y=Y*cx-z*sx;z=Y*sx+z*cx;
 const cam=2.8*R,p=cam/(cam+z),sc=Math.min(W,H)/(2.3*R)*zoom;
 n.sx=W/2+panX+x*p*sc;n.sy=H/2+panY+y*p*sc;n.p=p;n.z2=z;
 n.r=(3+1.7*Math.sqrt(n.size))*p*Math.sqrt(zoom)*(0.85+0.15*Math.min(1,n.a));}
const depthA=n=>{const b=0.4+0.6*Math.max(0,Math.min(1,(R-n.z2)/(2*R)));return 1-(1-b)*(1-mix);};
function arrow(x1,y1,x2,y2,size){const a=Math.atan2(y2-y1,x2-x1);ctx.beginPath();ctx.moveTo(x2,y2);
 ctx.lineTo(x2-size*Math.cos(a-0.4),y2-size*Math.sin(a-0.4));ctx.lineTo(x2-size*Math.cos(a+0.4),y2-size*Math.sin(a+0.4));ctx.closePath();ctx.fill();}
function nbr(n){return sel&&(n===sel||sel.adj.some(e=>e.S===n||e.T===n));}
function frame(){
 let busy=false;
 if(mix!==mixTo){const t=Math.min(1,(performance.now()-mixT0)/MIX_MS);mix=mixFrom+(mixTo-mixFrom)*easeOut(t);if(t>=1)mix=mixTo;else busy=true;need=1;}
 if(goX!==null){const dx=goX-panX,dy=goY-panY;if(Math.abs(dx)+Math.abs(dy)<0.5||reduce){panX=goX;panY=goY;goX=goY=null;}
  else{panX+=dx*0.2;panY+=dy*0.2;busy=true;}need=1;}
 for(const n of N){const d=n.ta-n.a;if(Math.abs(d)>0.004){n.a+=d*0.2;busy=true;}else n.a=n.ta;
  if(n.pop>0.02){n.pop*=0.93;busy=true;}else n.pop=0;}
 for(const e of E){const d=e.ta-e.a;if(Math.abs(d)>0.004){e.a+=d*0.2;busy=true;}else e.a=e.ta;
  if(e.pop>0.02){e.pop*=0.92;busy=true;}else e.pop=0;}
 if(busy||need){need=busy?1:0;draw();}
 requestAnimationFrame(frame);}
function draw(){
 ctx.clearRect(0,0,W,H);ctx.fillStyle=C.bg;ctx.fillRect(0,0,W,H);
 N.forEach(project);
 for(const e of E){const al=Math.min(e.a,e.S.a,e.T.a);if(al<0.03)continue;
  const hi=sel&&(e.S===sel||e.T===sel),dim=sel&&!hi?0.12:1;
  ctx.globalAlpha=al*dim*(hi?1:0.5*(depthA(e.S)+depthA(e.T)));
  const col=e.cross?C.ink:(fam.checked?C.s[e.slot]:C.ref);
  ctx.strokeStyle=col;ctx.fillStyle=col;ctx.lineWidth=(e.cross?2:1.1)+(hi?1.2:0)+e.pop*3;
  ctx.setLineDash(e.neg?[6,4]:[]);
  const dx=e.T.sx-e.S.sx,dy=e.T.sy-e.S.sy,d=Math.hypot(dx,dy)||1,tr=e.T.r+2;
  const x2=e.T.sx-dx/d*tr,y2=e.T.sy-dy/d*tr;
  ctx.beginPath();ctx.moveTo(e.S.sx,e.S.sy);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);
  if(d>tr+12)arrow(e.S.sx,e.S.sy,x2,y2,6+2*e.T.p);}
 const vis=N.filter(n=>n.a>0.03).sort((a,b)=>b.z2-a.z2);
 for(const n of vis){const dim=sel&&!nbr(n)?0.15:1;ctx.globalAlpha=n.a*dim*depthA(n);
  const r=n.r*(1+0.4*n.pop);
  if(n.prereq&&pre.checked){ctx.strokeStyle=C.ink;ctx.lineWidth=1.5;ctx.setLineDash([3,3]);
   ctx.beginPath();ctx.arc(n.sx,n.sy,r+4,0,6.283);ctx.stroke();ctx.setLineDash([]);}
  ctx.fillStyle=C.s[n.col];ctx.beginPath();ctx.arc(n.sx,n.sy,r,0,6.283);ctx.fill();
  ctx.strokeStyle=C.bg;ctx.lineWidth=1.5;ctx.stroke();
  if(n.pop>0.05){ctx.strokeStyle=C.ink;ctx.lineWidth=2;ctx.globalAlpha=n.a*Math.min(1,n.pop);
   ctx.beginPath();ctx.arc(n.sx,n.sy,r+4+10*(1-n.pop),0,6.283);ctx.stroke();}
  if(n===sel||n===hover){ctx.globalAlpha=1;ctx.strokeStyle=C.ink;ctx.lineWidth=2.5;
   ctx.beginPath();ctx.arc(n.sx,n.sy,r+3,0,6.283);ctx.stroke();}}
 ctx.font='12px system-ui,sans-serif';ctx.textAlign='center';ctx.lineJoin='round';
 for(const n of vis){const show=n===sel||n===hover||(sel&&nbr(n))||n.rank<D.labelTop*zoom;
  if(!show||n.a<0.5)continue;const dim=sel&&!nbr(n)?0.2:1;ctx.globalAlpha=n.a*dim*Math.max(0.55,depthA(n));
  ctx.lineWidth=3;ctx.strokeStyle=C.bg;ctx.strokeText(n.l,n.sx,n.sy+n.r+13);
  ctx.fillStyle=C.ink;ctx.fillText(n.l,n.sx,n.sy+n.r+13);}
 ctx.globalAlpha=1;}
function pick(px,py){let best=null;for(const n of N){if(n.a<0.4)continue;
 const d=Math.hypot(n.sx-px,n.sy-py);if(d<=Math.max(n.r+4,8)&&(!best||n.z2<best.z2))best=n;}return best;}
function reveal(n){if(n.a<0.4){bar.value=Math.max(+bar.value,n.sec);if(n.rank>=D.topn)all.checked=true;visibleTargets();n.a=1;}}
function centre(n){project(n);goX=panX-(n.sx-W/2);goY=panY-(n.sy-H/2);need=1;}
function show(n,focus){sel=n;need=1;const el=$('#panel'),cap=id=>D.secCaption[id]||id;
 if(!n){el.innerHTML='<div class="empty in"><b>Select a concept</b>Click a node, or use Find, to read the concept, see where the book '+
  'introduces it and follow its relations. Keyboard: arrow keys move the view, + and - zoom, Esc clears.</div>';return;}
 if(focus){reveal(n);centre(n);}
 const c=D.concepts[n.i]||{};
 let h='<div class="in"><h2>'+esc(n.l)+'</h2><div class="meta"><span class="chip"><i class="dot" style="background:var(--s'+(n.col+1)+')"></i>'+
  'introduced in chapter '+n.ch+'</span><span class="chip">'+esc(n.type)+'</span>'+(n.prereq?'<span class="chip">prerequisite candidate</span>':'')+'</div>';
 h+='<p>First appears in section <b>'+esc(STEPS[n.sec].caption)+'</b> and is mentioned in '+n.size+' section'+(n.size===1?'':'s')+'.</p>';
 if(c.aliases&&c.aliases.length)h+='<h4>Also called</h4><p>'+c.aliases.map(esc).join(', ')+'</p>';
 if(c.def)h+='<h4>Definition</h4><p>'+esc(c.def)+'</p>';
 h+='<h4>Where it appears</h4>'+(c.mentions||[]).map(m=>'<div class="item"><div class="sec">'+esc(cap(m.sec))+' ('+esc(m.role)+')</div>'+
  '<blockquote>'+esc(m.quote)+'</blockquote></div>').join('');
 h+='<h4>Relations ('+n.adj.length+')</h4>'+(n.adj.length?'':'<p class="sec">No relations were extracted for this concept.</p>');
 n.adj.forEach(e=>{const out=e.S===n,o=out?e.T:e.S;
  h+='<div class="item"><div>'+(out?esc(n.l)+' <b>'+esc(e.rel)+'</b> to <a data-go="'+esc(o.i)+'">'+esc(o.l)+'</a>':
   '<a data-go="'+esc(o.i)+'">'+esc(o.l)+'</a> <b>'+esc(e.rel)+'</b> to '+esc(n.l))+'</div>'+
   '<div class="sec">'+esc(e.fam)+', '+esc(e.polarity)+', '+esc(e.modality)+'</div><div class="sec">Section '+esc(cap(e.section))+'</div>'+
   '<div>'+esc(e.statement)+'</div><blockquote>'+esc(e.quote)+'</blockquote></div>';});
 el.innerHTML=h+'</div>';el.scrollTop=0;}
$('#panel').addEventListener('click',ev=>{const a=ev.target.closest('[data-go]');if(a)show(byId[a.dataset.go],true);});
const pts=new Map();let pinch0=0,zoom0=1;
function zoomAt(z2,cx,cy){z2=Math.max(0.35,Math.min(10,z2));const k=z2/zoom;panX=cx-(cx-panX)*k;panY=cy-(cy-panY)*k;zoom=z2;need=1;}
cv.addEventListener('pointerdown',ev=>{pts.set(ev.pointerId,{x:ev.clientX,y:ev.clientY});drag=true;moved=0;lx=ev.clientX;ly=ev.clientY;
 shift=ev.shiftKey;cv.setPointerCapture(ev.pointerId);cv.classList.add('drag');goX=goY=null;
 if(pts.size===2){const [a,b]=[...pts.values()];pinch0=Math.hypot(a.x-b.x,a.y-b.y)||1;zoom0=zoom;moved=99;}});
cv.addEventListener('pointermove',ev=>{const r=cv.getBoundingClientRect();
 if(pts.has(ev.pointerId))pts.set(ev.pointerId,{x:ev.clientX,y:ev.clientY});
 if(pts.size===2){const [a,b]=[...pts.values()];zoomAt(zoom0*Math.hypot(a.x-b.x,a.y-b.y)/pinch0,(a.x+b.x)/2-r.left-W/2,(a.y+b.y)/2-r.top-H/2);return;}
 if(drag){const dx=ev.clientX-lx,dy=ev.clientY-ly;moved+=Math.abs(dx)+Math.abs(dy);lx=ev.clientX;ly=ev.clientY;
  if(shift||mode===2){panX+=dx;panY+=dy;}else{yaw+=dx*0.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+dy*0.008));}need=1;}
 else{const h=pick(ev.clientX-r.left,ev.clientY-r.top);if(h!==hover){hover=h;need=1;}cv.style.cursor=hover?'pointer':'grab';}});
cv.addEventListener('pointerup',ev=>{pts.delete(ev.pointerId);if(pts.size)return;drag=false;cv.classList.remove('drag');
 if(moved<5){const r=cv.getBoundingClientRect();show(pick(ev.clientX-r.left,ev.clientY-r.top));}});
cv.addEventListener('pointercancel',ev=>{pts.delete(ev.pointerId);drag=false;cv.classList.remove('drag');});
cv.addEventListener('pointerleave',()=>{if(hover){hover=null;need=1;}});
cv.addEventListener('wheel',ev=>{ev.preventDefault();const r=cv.getBoundingClientRect();
 zoomAt(zoom*Math.exp(-ev.deltaY*0.0015),ev.clientX-r.left-W/2,ev.clientY-r.top-H/2);},{passive:false});   // 1.5x the original rate
cv.addEventListener('keydown',ev=>{const k=ev.key,st=mode===2?40:0.12;let used=true;
 if(k==='ArrowLeft'){mode===2?panX+=st:yaw-=st;}else if(k==='ArrowRight'){mode===2?panX-=st:yaw+=st;}
 else if(k==='ArrowUp'){mode===2?panY+=st:pitch=Math.max(-1.5,pitch-st);}else if(k==='ArrowDown'){mode===2?panY-=st:pitch=Math.min(1.5,pitch+st);}
 else if(k==='+'||k==='='){zoomAt(zoom*1.25,0,0);}else if(k==='-'){zoomAt(zoom/1.25,0,0);}else used=false;
 if(used){ev.preventDefault();need=1;}});
$('#reset').addEventListener('click',()=>{yaw=0.6;pitch=0.3;zoom=1;panX=panY=0;goX=goY=null;need=1;});
$('#v2').addEventListener('click',()=>setMode(2));$('#v3').addEventListener('click',()=>setMode(3));
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&sel)show(null);});
const byName={};N.forEach(n=>byName[n.l.toLowerCase()]=n);
$('#findlist').innerHTML=N.map(n=>'<option value="'+esc(n.l)+'">').join('');
$('#find').addEventListener('change',ev=>{const n=byName[ev.target.value.trim().toLowerCase()];if(n){show(n,true);}});
let timer=null;
function stop(){clearInterval(timer);timer=null;play.dataset.state='paused';play.setAttribute('aria-label','Play');}
function start(){if(+bar.value>=last){bar.value=0;prev=-1;}play.dataset.state='playing';play.setAttribute('aria-label','Pause');
 timer=setInterval(()=>{if(+bar.value>=last){stop();return;}bar.value=+bar.value+1;visibleTargets();},1400/+speed.value);visibleTargets();}
play.addEventListener('click',()=>timer?stop():start());
speed.addEventListener('change',()=>{if(timer){stop();start();}});
bar.addEventListener('input',()=>{stop();visibleTargets();});
[all,pre,fam].forEach(x=>x.addEventListener('input',()=>{visibleTargets();legend();}));
const fl=$('#famlegend');
function legend(){fl.innerHTML=fam.checked?D.families.map(f=>'<span class="chip"><i class="dot" style="background:var(--s'+(f.slot+1)+')"></i>'+esc(f.name)+'</span>').join(''):'';need=1;}
visibleTargets();N.forEach(n=>{n.a=n.ta;n.pop=0;});E.forEach(e=>{e.a=e.ta;e.pop=0;});
setHint();legend();show(null);requestAnimationFrame(frame);
}
})();
"""


def growth3d_page(data: dict, *, css: str, banner: str, footer: str, top_n: int) -> str:
    """`css` is the report's shared token CSS (colour custom properties, light/dark)."""
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    n = len(data["steps"])
    first: dict[int, int] = {}
    for i, st in enumerate(data["steps"]):
        first.setdefault(st["chapter"], i)
    ticks = "".join(
        f'<span style="left:{(i / max(n - 1, 1)) * 100:.1f}%">ch{ch}</span>'
        for ch, i in first.items()
    )
    legend = "".join(
        f'<span class="chip"><i class="dot" style="background:var(--s{c["slot"] + 1})"></i>'
        f"First seen in chapter {c['ch']}</span>"
        for c in data["chapters"]
    )
    prov = "".join(f"<span>{escape(part)}</span>" for part in footer.split(" · "))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Expert KG Growth</title><style>{css}{CSS3D}</style></head><body>"
        '<div class="top"><div><h1>Expert knowledge graph</h1>'
        '<p class="sub">How the graph grows through the book, one section at a time</p></div>'
        '<div class="seg" data-v="3" role="group" aria-label="View mode">'
        '<span class="seg-ind"></span><button id="v2" type="button" aria-pressed="false">2D</button>'
        '<button id="v3" type="button" aria-pressed="true">3D</button></div></div>'
        f'<p class="note"><b>Scope:</b> {escape(banner)} Growth follows book order, which is not a '
        "learner’s path and not prerequisite order.</p>"
        '<noscript><p class="note">This page needs JavaScript to draw the graph.</p></noscript>'
        '<div id="app"><section id="stage" aria-label="Knowledge graph">'
        '<canvas id="cv" tabindex="0" role="img" aria-label="Interactive knowledge graph. Use the Find box '
        'or the side panel to read concepts; arrow keys move the view."></canvas>'
        f'<div class="hud tl">{legend}'
        '<label class="find"><span>Find</span><input id="find" type="search" list="findlist" '
        'autocomplete="off" spellcheck="false"><datalist id="findlist"></datalist></label>'
        '<label class="pill"><input type="checkbox" id="showall">Show all concepts</label>'
        '<label class="pill"><input type="checkbox" id="showprereq" checked>Show prerequisite rings</label>'
        '<label class="pill"><input type="checkbox" id="famcolor">Colour edges by relation</label>'
        '<span id="famlegend" style="display:contents"></span></div>'
        '<div class="hud tr"><button class="btn" id="reset" type="button">Reset view</button></div>'
        '<div class="hud hint" id="hint"></div>'
        '<div class="dock"><button class="play" id="play" type="button" data-state="paused" aria-label="Play">'
        '<svg class="i-play" viewBox="0 0 16 16" aria-hidden="true"><polygon points="4,2 14,8 4,14"/></svg>'
        '<svg class="i-pause" viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="3.5" height="12" rx="1"/>'
        '<rect x="9.5" y="2" width="3.5" height="12" rx="1"/></svg></button>'
        f'<div class="scrub"><input type="range" id="timebar" min="0" max="{n - 1}" value="{n - 1}" step="1" '
        f'aria-label="Time: section of the book"><div class="ticks">{ticks}</div></div>'
        '<select id="speed" aria-label="Playback speed"><option value="0.5">0.5×</option>'
        '<option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select>'
        '<div class="cap"><span><b id="stepname"></b> <span id="stepch" class="num"></span></span>'
        '<span class="stats num"><span id="cn"></span><span id="ce"></span><span id="cm"></span></span></div></div>'
        '</section><aside id="panel" aria-live="polite"></aside></div>'
        f'<footer><div class="prov">{prov}</div>Showing the top {top_n} concepts by connections by default. '
        "Dark edges cross chapters, dashed edges are negated, and node size is the number of sections "
        "that mention the concept.</footer>"
        f'<script type="application/json" id="d3d">{payload}</script><script>{JS3D}</script>'
        "</body></html>"
    )
