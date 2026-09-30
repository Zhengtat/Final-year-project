"""3D interactive growth graph (growth3d.html): deterministic 3D layout in Python, a small
dependency-free canvas renderer in the page (drag to spin, wheel to zoom, click a node to
read the concept). No external library, so the page stays a single offline file.
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


CSS3D = """
#wrap{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px;align-items:start}
@media (max-width:900px){#wrap{grid-template-columns:1fr}}
#cv{width:100%;height:660px;border:1px solid var(--grid);border-radius:8px;background:var(--bg);
cursor:grab;touch-action:none;display:block}
#cv.drag{cursor:grabbing}
#panel{border:1px solid var(--grid);border-radius:8px;padding:10px 14px;background:var(--card);
max-height:660px;overflow:auto;font-size:13px}
#panel h3{margin:0 0 4px}#panel .rel{margin:6px 0;padding-top:6px;border-top:1px solid var(--grid)}
#panel a{color:var(--s1);cursor:pointer;text-decoration:underline}
#panel q{color:var(--ink2)}
.legend span{margin-right:12px;font-size:12px;white-space:nowrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}
"""

JS3D = r"""
(function(){
const D=JSON.parse(document.getElementById('d3d').textContent);
const $=s=>document.querySelector(s),cv=$('#cv'),ctx=cv.getContext('2d');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let W=0,H=0;
function resize(){const d=window.devicePixelRatio||1,r=cv.getBoundingClientRect();W=r.width;H=r.height;
 cv.width=Math.round(W*d);cv.height=Math.round(H*d);ctx.setTransform(d,0,0,d,0,0);}
window.addEventListener('resize',resize);resize();
let C={};function readColors(){const cs=getComputedStyle(document.documentElement),g=n=>cs.getPropertyValue(n).trim();
 C={bg:g('--bg'),ink:g('--ink'),ink2:g('--ink2'),ref:g('--ref'),s:[...Array(8)].map((_,i)=>g('--s'+(i+1)))};}
readColors();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',readColors);
const N=D.nodes.map(n=>Object.assign({a:0,ta:0,pop:0,popKind:0,sx:0,sy:0,p:1,z2:0,adj:[]},n)),byId={};
N.forEach(n=>byId[n.i]=n);
const E=D.edges.map(e=>Object.assign({a:0,ta:0,pop:0},e,{S:byId[e.s],T:byId[e.t]}));
E.forEach(e=>{e.S.adj.push(e);e.T.adj.push(e);});
const STEPS=D.steps,last=STEPS.length-1,R=D.radius;
let yaw=0.6,pitch=0.3,zoom=1,panX=0,panY=0,sel=null,hover=null,drag=false,moved=0,lx=0,ly=0,shift=false,prev=-1;
const bar=$('#timebar'),all=$('#showall'),pre=$('#showprereq'),auto=$('#autorot'),fam=$('#famcolor'),
 play=$('#play'),speed=$('#speed');
function visibleTargets(){const t=+bar.value,st=STEPS[t],ment=new Set(st.mentioned);
 $('#stepname').textContent='Section '+st.caption+' (ch'+st.chapter+')';
 N.forEach(n=>{n.ta=(n.sec<=t&&(all.checked||n.rank<D.topn))?1:0;
  if(t!==prev&&n.ta){if(n.sec===t){n.pop=1;n.popKind=1;}else if(ment.has(n.i)){n.pop=0.6;n.popKind=2;}}});
 let ne=0,nn=0;N.forEach(n=>{if(n.ta)nn++;});
 E.forEach(e=>{e.ta=(e.sec<=t&&e.S.ta&&e.T.ta)?1:0;if(e.ta)ne++;if(t!==prev&&e.ta&&e.sec===t)e.pop=1;});
 let m=0;for(let i=0;i<=t;i++)m+=STEPS[i].merges;
 $('#counts').textContent=nn+' concepts, '+ne+' edges, '+m+' alias merges so far';prev=t;}
function project(n){const cy=Math.cos(yaw),sy=Math.sin(yaw),cx=Math.cos(pitch),sx=Math.sin(pitch);
 let x=n.x*cy+n.z*sy,z=-n.x*sy+n.z*cy,y=n.y*cx-z*sx;z=n.y*sx+z*cx;
 const cam=2.8*R,p=cam/(cam+z),sc=Math.min(W,H)/(2.3*R)*zoom;
 n.sx=W/2+panX+x*p*sc;n.sy=H/2+panY+y*p*sc;n.p=p;n.z2=z;n.r=(3+1.7*Math.sqrt(n.size))*p*Math.sqrt(zoom);}
const depthA=n=>0.4+0.6*Math.max(0,Math.min(1,(R-n.z2)/(2*R)));
function arrow(x1,y1,x2,y2,size){const a=Math.atan2(y2-y1,x2-x1);ctx.beginPath();ctx.moveTo(x2,y2);
 ctx.lineTo(x2-size*Math.cos(a-0.4),y2-size*Math.sin(a-0.4));ctx.lineTo(x2-size*Math.cos(a+0.4),y2-size*Math.sin(a+0.4));ctx.closePath();ctx.fill();}
function nbr(n){return sel&&(n===sel||sel.adj.some(e=>e.S===n||e.T===n));}
function frame(){
 if(auto.checked&&!drag)yaw+=0.004;
 ctx.clearRect(0,0,W,H);ctx.fillStyle=C.bg;ctx.fillRect(0,0,W,H);
 N.forEach(n=>{n.a+=(n.ta-n.a)*0.15;n.pop*=0.94;project(n);});
 E.forEach(e=>{e.a+=(e.ta-e.a)*0.15;e.pop*=0.92;});
 for(const e of E){const al=Math.min(e.a,e.S.a,e.T.a);if(al<0.03)continue;
  const hi=sel&&(e.S===sel||e.T===sel),dim=sel&&!hi?0.12:1;
  ctx.globalAlpha=al*dim*(hi?1:0.5*(depthA(e.S)+depthA(e.T)))*(e.pop>0.05?1:0.85);
  const col=e.cross?C.ink:(fam.checked?C.s[e.slot]:C.ref);
  ctx.strokeStyle=col;ctx.fillStyle=col;ctx.lineWidth=(e.cross?2:1.1)+(hi?1.2:0)+e.pop*3;
  if(e.neg)ctx.setLineDash([6,4]);else ctx.setLineDash([]);
  const dx=e.T.sx-e.S.sx,dy=e.T.sy-e.S.sy,d=Math.hypot(dx,dy)||1,tr=e.T.r+2;
  const x2=e.T.sx-dx/d*tr,y2=e.T.sy-dy/d*tr;
  ctx.beginPath();ctx.moveTo(e.S.sx,e.S.sy);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);
  if(d>tr+12)arrow(e.S.sx,e.S.sy,x2,y2,6+2*e.T.p);}
 const vis=N.filter(n=>n.a>0.03).sort((a,b)=>b.z2-a.z2);
 for(const n of vis){const dim=sel&&!nbr(n)?0.15:1;ctx.globalAlpha=n.a*dim*depthA(n);
  const r=n.r*(1+0.5*n.pop);
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
 ctx.globalAlpha=1;requestAnimationFrame(frame);}
function pick(px,py){let best=null;for(const n of N){if(n.a<0.4)continue;
 const d=Math.hypot(n.sx-px,n.sy-py);if(d<=Math.max(n.r+4,8)&&(!best||n.z2<best.z2))best=n;}return best;}
function conceptName(id){return byId[id]?byId[id].l:id;}
function show(n){sel=n;const el=$('#panel');
 if(!n){el.innerHTML='<p>Click a concept to read it. Drag to spin, scroll to zoom, shift-drag to move.</p>';return;}
 const c=D.concepts[n.i]||{},cap=id=>D.secCaption[id]||id;
 let h='<h3>'+esc(n.l)+'</h3><div class="small">'+esc(n.type)+' · first appears in section '+esc(STEPS[n.sec].caption)+
  ' · in '+n.size+' section'+(n.size===1?'':'s')+(n.prereq?' · prerequisite candidate':'')+'</div>';
 if(c.aliases&&c.aliases.length)h+='<p><b>Also called:</b> '+c.aliases.map(esc).join(', ')+'</p>';
 if(c.def)h+='<p><b>Definition:</b> '+esc(c.def)+'</p>';
 h+='<p><b>Where it appears</b></p><ul>'+(c.mentions||[]).map(m=>'<li>'+esc(cap(m.sec))+' — '+esc(m.role)+': <q>'+esc(m.quote)+'</q></li>').join('')+'</ul>';
 h+='<p><b>Relations ('+n.adj.length+')</b></p>';
 n.adj.forEach(e=>{const out=e.S===n,o=out?e.T:e.S;
  h+='<div class="rel">'+(out?esc(n.l)+' —['+esc(e.rel)+']→ ':'')+'<a data-go="'+esc(o.i)+'">'+esc(o.l)+'</a>'+(out?'':' —['+esc(e.rel)+']→ '+esc(n.l))+
   '<br><span class="small">'+esc(e.fam)+', '+esc(e.polarity)+', '+esc(e.modality)+' · section '+esc(cap(e.section))+'</span><br>'+esc(e.statement)+
   '<br><q>'+esc(e.quote)+'</q></div>';});
 el.innerHTML=h;}
$('#panel').addEventListener('click',ev=>{const a=ev.target.closest('[data-go]');if(a){const n=byId[a.dataset.go];
 if(n&&n.a<0.4){bar.value=Math.max(+bar.value,n.sec);all.checked=all.checked||n.rank>=D.topn;visibleTargets();n.a=1;}show(n);}});
cv.addEventListener('pointerdown',ev=>{drag=true;moved=0;lx=ev.clientX;ly=ev.clientY;shift=ev.shiftKey;cv.setPointerCapture(ev.pointerId);cv.classList.add('drag');});
cv.addEventListener('pointermove',ev=>{const r=cv.getBoundingClientRect();
 if(drag){const dx=ev.clientX-lx,dy=ev.clientY-ly;moved+=Math.abs(dx)+Math.abs(dy);lx=ev.clientX;ly=ev.clientY;
  if(shift){panX+=dx;panY+=dy;}else{yaw+=dx*0.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+dy*0.008));}}
 else{hover=pick(ev.clientX-r.left,ev.clientY-r.top);cv.style.cursor=hover?'pointer':'grab';}});
cv.addEventListener('pointerup',ev=>{drag=false;cv.classList.remove('drag');
 if(moved<5){const r=cv.getBoundingClientRect();show(pick(ev.clientX-r.left,ev.clientY-r.top));}});
cv.addEventListener('wheel',ev=>{ev.preventDefault();zoom=Math.max(0.35,Math.min(8,zoom*Math.exp(-ev.deltaY*0.001)));},{passive:false});
$('#reset').addEventListener('click',()=>{yaw=0.6;pitch=0.3;zoom=1;panX=panY=0;});
let timer=null;
function stop(){clearInterval(timer);timer=null;play.textContent='▶ Play';}
function start(){if(+bar.value>=last){bar.value=0;prev=-1;}play.textContent='⏸ Pause';
 timer=setInterval(()=>{if(+bar.value>=last){stop();return;}bar.value=+bar.value+1;visibleTargets();},1400/+speed.value);visibleTargets();}
play.addEventListener('click',()=>timer?stop():start());
speed.addEventListener('change',()=>{if(timer){stop();start();}});
bar.addEventListener('input',()=>{stop();visibleTargets();});
[all,pre].forEach(x=>x.addEventListener('input',visibleTargets));
N.forEach(n=>{n.a=n.ta;});visibleTargets();N.forEach(n=>{n.a=n.ta;n.pop=0;});E.forEach(e=>{e.a=e.ta;e.pop=0;});
const fl=$('#famlegend');
function legend(){fl.innerHTML=fam.checked?D.families.map(f=>'<span><i style="background:var(--s'+(f.slot+1)+')"></i>'+esc(f.name)+'</span>').join(''):'';}
fam.addEventListener('input',legend);legend();
show(null);requestAnimationFrame(frame);
})();
"""


def growth3d_page(data: dict, *, css: str, banner: str, footer: str, top_n: int) -> str:
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    n_steps = len(data["steps"])
    legend = "".join(
        f'<span><i style="background:var(--s{c["slot"] + 1})"></i>first introduced ch{c["ch"]}</span>'
        for c in data["chapters"]
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Expert KG 3D Growth</title><style>{css}{CSS3D}</style></head><body>"
        f'<header><h1>Expert knowledge graph — 3D growth</h1><div class="small">{escape(footer)}</div>'
        f'<div class="banner">{escape(banner)}</div></header><main>'
        '<p class="small">Drag to spin · scroll to zoom · shift-drag to move · click a concept to read it. '
        "The graph is built in book order, one section per step (Play, or drag the time bar): new concepts pop "
        "in, concepts mentioned again pulse, new edges thicken briefly. Book order is not a learner’s path "
        "and not prerequisite truth.</p>"
        f'<div class="legend">{legend}<span>size = sections mentioning</span>'
        "<span><b>dark edges</b> = cross-chapter</span><span>dashed edge = negated</span>"
        "<span>dashed ring = prerequisite candidate</span></div>"
        '<div class="controls"><button id="play" type="button">▶ Play</button>'
        f'<label>Time <input type="range" id="timebar" min="0" max="{n_steps - 1}" value="{n_steps - 1}" step="1"></label>'
        '<label>Speed <select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option>'
        '<option value="2">2×</option><option value="4">4×</option></select></label>'
        '<button id="reset" type="button">Reset view</button></div>'
        '<div class="controls"><b id="stepname"></b><span class="small" id="counts"></span></div>'
        '<div class="controls"><label><input type="checkbox" id="autorot" checked> auto-rotate</label>'
        f'<label><input type="checkbox" id="showall"> show all concepts (default: top {top_n} by connections)</label>'
        '<label><input type="checkbox" id="showprereq" checked> prerequisite layer</label>'
        '<label><input type="checkbox" id="famcolor"> colour edges by relation family</label></div>'
        '<div id="wrap"><canvas id="cv" role="img" aria-label="Interactive 3D knowledge graph; the side panel '
        'lists the selected concept and its relations"></canvas><aside id="panel"></aside></div>'
        '<div class="legend" id="famlegend" style="margin-top:8px"></div>'
        f'<div class="foot">{escape(footer)}</div></main>'
        f'<script type="application/json" id="d3d">{payload}</script><script>{JS3D}</script>'
        "</body></html>"
    )
