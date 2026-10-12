// ====================================================================================================================
// CR-013 STOP 4: EVALUATION OVERLAY (CR-012 frozen outputs). Everything here is evaluation material derived from the frozen
// benchmark gold and the retained E0 predictions. It is loaded only when the user explicitly opens the evaluation mode, from its
// own payload, and is never reachable from the production P&D views. Codes are observations of where a benchmark object was
// lost in the frozen run; they are not decision rules for the production pipeline.
// ====================================================================================================================
const EV_TABS = [['evmap','Failure map'],['evlist','Gold relations']];
const EV_PANES = ['evmap','evlist'];
const EV_COL = {N0:'#C23B3B',N1:'#D55E00',C0:'#B8A400',C1:'#2E8B8B',P0:'#E69F00',R0:'#56B4E9',R1:'#0072B2',R2:'#8C4FD8',R3:'#7A7A7A',E0:'#A0522D',recovered:'#009E73'};
const EV_SHORT = {N0:'endpoint never extracted',N1:'endpoint span wrong',C0:'concept split',C1:'false merge',P0:'pair never sent to the classifier',R0:'classifier said no relation',R1:'wrong relation',R2:'wrong direction',R3:'type / qualifier',E0:'evidence invalid'};
let EV = null, EVLOAD = null;
const ES = {ds:'scinlp', code:'', unit:'', status:'all', q:'', sel:null, more:false};

function evAvailable(){ return !!$('eval-gz') && ($('eval-gz').textContent||'').length>10; }
function loadEval(){
  if(EV) return Promise.resolve(EV);
  if(EVLOAD) return EVLOAD;
  EVLOAD=(async()=>{
    const b64=($('eval-gz').textContent||'').trim(); const bin=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));
    const stream=new Blob([bin]).stream().pipeThrough(new DecompressionStream('gzip'));
    EV=JSON.parse(await new Response(stream).text()); return EV;
  })();
  return EVLOAD;
}
const evds = () => EV.datasets[ES.ds];
const pct = (a,b) => b? (100*a/b).toFixed(1)+'%' : '—';

// ---------------------------------------------------------------- entering / leaving the mode (explicit, opt-in)
function evEnter(){
  S.mode='ev'; S.sel=null; S.tab='evmap'; S.G=null; S.doc=null;
  chrome(); banner(); evSide(); tabs(); showTab('evmap'); renderDetail(true); hashWrite();
}
function evBanner(){
  const names={scinlp:'SciNLP held-out test documents',pd:'P&D held-out sections (not the Chapters 1–3 graph)'};
  $('banner').innerHTML='<div class="banner warn"><b>CR-012 EVALUATION OVERLAY — EVALUATION OUTPUT, gold-derived. NOT the production Expert KG.</b> Dataset: <b>'+esc(names[ES.ds])+'</b>. This view compares the frozen E0 predictions with the benchmark gold and shows the earliest stage at which each gold relation was lost. <b>These codes are observations of the frozen run, not decision rules for the production pipeline.</b></div>';
}
function evSide(){
  const s=$('side'); const ds=[['scinlp','SciNLP held-out'],['pd','P&D held-out']];
  s.innerHTML='<h3>Dataset (never pooled)</h3><div class="tour">'+ds.map(([k,l])=>'<button data-ds="'+k+'" class="'+(ES.ds===k?'on':'')+'">'+esc(l)+'</button>').join('')+'</div>'+
   '<div class="card" style="margin-top:12px"><h4>What this is</h4><span class="small">Frozen CR-012 outputs only (tag <code>cr012-stop4-complete</code>): the retained E0 predictions, the benchmark gold and the frozen earliest-failure attribution. Nothing was re-run or re-scored; the pooled counts below equal the frozen STOP-4 report.</span></div>'+
   '<div class="card"><h4>Reading the codes</h4><span class="small">Each gold relation gets at most one <b>earliest</b> failure; stages after it are not evaluated. N = node, C = canonical identity, P = pair delivery, R = relation, E = evidence. S0 / S1 do not apply (CR-011 adopted no transformation).</span></div>'+
   '<button id="ev-back" style="margin-top:6px">← Back to the production P&amp;D graph</button>';
  s.querySelectorAll('button[data-ds]').forEach(b=>b.onclick=()=>{ ES.ds=b.dataset.ds; ES.code=''; ES.unit=''; ES.sel=null; ES.status='all'; ES.q=''; evBanner(); evSide(); showTab(S.tab); renderDetail(true); });
  s.querySelector('#ev-back').onclick=()=>{ ES.sel=null; setMode('pd'); };
}

// ---------------------------------------------------------------- tabs
async function renderEvalTab(k){
  const el=$('v-'+k); if(!el) return;
  el.innerHTML='<p class="na">Loading the evaluation overlay…</p>';
  try{ await loadEval(); }catch(e){ el.innerHTML='<p class="na">The overlay could not be loaded in this browser ('+esc(e&&e.message||e)+').</p>'; return; }
  (k==='evmap'?viewEvMap:viewEvList)(el);
}
function codeChip(c){ return c? '<span class="chip" style="border-left:4px solid '+EV_COL[c]+'" title="'+esc(EV.codes[c]||'')+'">'+esc(c)+'</span>' : '<span class="chip" style="border-left:4px solid '+EV_COL.recovered+'">no node-level loss</span>'; }
function viewEvMap(el){
  const d=evds(), h=d.headline; const miss=d.frozen_attribution.misses, rec=d.frozen_attribution.recovered, by=d.frozen_attribution.by_code;
  let o='<h2 class="vh">Failure map <span class="chip">EVALUATION</span></h2>';
  o+='<div class="card"><b>'+esc(d.label)+'</b><div class="big"><div><b>'+h.f1.toFixed(3)+'</b>'+esc(h.metric)+'</div><div><b>'+h.precision.toFixed(3)+'</b>precision</div><div><b>'+h.recall.toFixed(3)+'</b>recall</div></div><div class="small">CI status: <b>'+esc(h.ci_status)+'</b>'+(h.ci?' · section-bootstrap interval ['+h.ci[0].toFixed(3)+', '+h.ci[1].toFixed(3)+'] (descriptive, '+d.units.length+' units)':'')+(ES.ds==='pd'?' · '+esc(EV.meta.single_annotator):' · '+d.units.length+' documents; '+esc('no entity- or edge-level bootstrap'))+'</div></div>';
  o+='<h3 class="jh">Where gold relations were lost (earliest failure)</h3><p class="small">'+(miss+rec)+' gold relations: <b>'+miss+'</b> with an earliest failure, <b>'+rec+'</b> with none at node level. '+esc(d.not_applicable_note)+' '+esc(EV.meta.s0_s1)+'.</p>';
  o+='<div class="bar" style="height:18px">'+EV.code_order.filter(c=>by[c]).map(c=>'<span title="'+esc(c)+' '+by[c]+'" style="width:'+(100*by[c]/miss)+'%;background:'+EV_COL[c]+'"></span>').join('')+'</div>';
  o+='<div class="leg" style="margin-bottom:8px">'+EV.code_order.filter(c=>by[c]).map(c=>'<span><i style="background:'+EV_COL[c]+'"></i>'+esc(c)+' '+esc(EV_SHORT[c])+' · <b>'+by[c]+'</b> ('+pct(by[c],miss)+')</span>').join('')+'</div>';
  o+='<table class="t evmatrix"><tr><th>'+esc(d.unit_word)+'</th><th>gold</th>'+EV.code_order.map(c=>'<th title="'+esc(EV_SHORT[c])+'">'+c+'</th>').join('')+'<th>none</th><th>F1</th></tr>';
  d.units.forEach(u=>{ const mx=Math.max(1,...Object.values(u.counts)); o+='<tr><td><a class="lnk" data-unit="'+esc(u.id)+'">'+esc(u.title)+'</a></td><td>'+u.gold_n+'</td>'+EV.code_order.map(c=>{ const n=u.counts[c]; return n?'<td class="evcell" data-code="'+c+'" data-unit="'+esc(u.id)+'" style="background:linear-gradient(90deg,'+EV_COL[c]+'66 '+(100*n/mx)+'%,transparent 0)">'+n+'</td>':'<td class="evzero">'+(d.not_applicable.includes(c)?'n/a':'·')+'</td>'; }).join('')+'<td class="evcell" data-code="none" data-unit="'+esc(u.id)+'">'+u.recovered+'</td><td>'+u.f1.toFixed(3)+'</td></tr>'; });
  o+='</table><p class="small">Click a count to list those gold relations; click a document or section to list all of its gold relations.</p>';
  o+='<h3 class="jh">What each code means, with a concrete example</h3><table class="t"><tr><th>code</th><th>frozen meaning</th><th>count</th><th>example</th></tr>'+EV.code_order.map(c=>{ const ex=firstExample(c); return '<tr><td>'+codeChip(c)+'</td><td>'+esc(EV.codes[c])+'</td><td>'+by[c]+'</td><td>'+(ex?'<a class="lnk" data-ex="'+ex[0]+'|'+ex[1]+'">'+esc(clip(ex[2].src,24))+' → '+esc(clip(ex[2].tgt,24))+'</a>':'<span class="na">'+(d.not_applicable.includes(c)?'not applicable here':'none in this dataset')+'</span>')+'</td></tr>'; }).join('')+'</table>';
  o+='<h3 class="jh">Oracle context <span class="small">(frozen diagnostics)</span></h3><p class="small">'+Object.entries(d.ladder).map(([k,v])=>'<b>'+esc(k)+'</b> '+v.toFixed(3)).join(' · ')+'<br>'+esc(EV.meta.oracle_note)+' The E0 row is the headline system score.</p>';
  o+='<p class="small" style="margin-top:14px"><b>'+esc(EV.meta.notice)+'</b></p>';
  el.innerHTML=o;
  el.querySelectorAll('td.evcell').forEach(td=>td.onclick=()=>{ ES.code=td.dataset.code; ES.unit=td.dataset.unit; ES.status='all'; ES.q=''; showTab('evlist'); });
  el.querySelectorAll('a[data-unit]').forEach(a=>a.onclick=()=>{ ES.code=''; ES.unit=a.dataset.unit; ES.status='all'; showTab('evlist'); });
  el.querySelectorAll('a[data-ex]').forEach(a=>a.onclick=()=>{ const [u,i]=a.dataset.ex.split('|'); evSelect(u,+i); ES.code=''; ES.unit=u; showTab('evlist'); });
}
const clip = (s,n) => s&&s.length>n? s.slice(0,n-1)+'…' : s;
function firstExample(c){ const d=evds(); for(const u of d.units){ const r=u.relations.find(x=>x.code===c); if(r) return [u.id,r.i,r]; } return null; }

// ---------------------------------------------------------------- gold relation list
function relMatches(r){
  if(ES.code==='none'){ if(r.code) return false; } else if(ES.code && r.code!==ES.code) return false;
  if(ES.status==='strict'&&!r.strict) return false; if(ES.status==='missed'&&r.strict) return false;
  const q=ES.q.trim().toLowerCase(); if(q&&!(r.src+' '+r.tgt+' '+r.rel).toLowerCase().includes(q)) return false; return true;
}
function viewEvList(el){
  const d=evds(); const units=ES.unit?d.units.filter(u=>u.id===ES.unit):d.units;
  const rows=units.flatMap(u=>u.relations.map(r=>({u,r}))).filter(x=>relMatches(x.r));
  const chips=['', ...EV.code_order.filter(c=>d.frozen_attribution.by_code[c]), 'none'];
  let o='<h2 class="vh">Gold relations <span class="chip">EVALUATION</span></h2><div class="whyform"><label class="small">'+esc(d.unit_word)+' <select id="evu"><option value="">all</option>'+d.units.map(u=>'<option value="'+esc(u.id)+'"'+(ES.unit===u.id?' selected':'')+'>'+esc(u.title)+' ('+u.gold_n+')</option>').join('')+'</select></label>'+
   '<label class="small">status <select id="evs"><option value="all">all</option><option value="strict"'+(ES.status==='strict'?' selected':'')+'>strict match</option><option value="missed"'+(ES.status==='missed'?' selected':'')+'>not a strict match</option></select></label><input id="evq" type="search" aria-label="Search gold text or relation" placeholder="search gold text or relation" value="'+esc(ES.q)+'"></div>';
  o+='<div class="leg" style="margin:6px 0">'+chips.map(c=>'<button class="evchip'+(ES.code===c?' on':'')+'" data-c="'+c+'">'+(c===''?'all codes':c==='none'?'no node-level loss':esc(c)+' '+esc(EV_SHORT[c]))+'</button>').join(' ')+'</div>';
  o+='<p class="small">'+rows.length+' gold relation(s). Click a row for its earliest-failure explanation.</p>';
  o+='<table class="t"><tr><th>'+esc(d.unit_word)+'</th><th>gold relation</th><th>earliest failure</th><th>strict match</th></tr>'+rows.slice(0,ES.more?2000:150).map(({u,r})=>'<tr data-u="'+esc(u.id)+'" data-i="'+r.i+'" class="'+(ES.sel&&ES.sel.u===u.id&&ES.sel.i===r.i?'sel':'')+'"><td>'+esc(u.title)+'</td><td>'+esc(clip(r.src,40))+' <span class="small">'+esc(r.rel)+(r.sym?' ⟷':' →')+'</span> '+esc(clip(r.tgt,40))+'</td><td>'+codeChip(r.code)+'</td><td>'+(r.strict?'yes':'no')+'</td></tr>').join('')+'</table>'+(rows.length>150&&!ES.more?'<button id="evmore">show all '+rows.length+'</button>':'');
  el.innerHTML=o;
  el.querySelector('#evu').onchange=e=>{ ES.unit=e.target.value; viewEvList(el); }; el.querySelector('#evs').onchange=e=>{ ES.status=e.target.value; viewEvList(el); };
  el.querySelector('#evq').onchange=e=>{ ES.q=e.target.value; viewEvList(el); };
  el.querySelectorAll('button.evchip').forEach(b=>b.onclick=()=>{ ES.code=b.dataset.c; ES.more=false; viewEvList(el); });
  const mb=el.querySelector('#evmore'); if(mb) mb.onclick=()=>{ ES.more=true; viewEvList(el); };
  el.querySelectorAll('tr[data-u]').forEach(tr=>tr.onclick=()=>{ evSelect(tr.dataset.u,+tr.dataset.i); });
}
function evSelect(u,i){ ES.sel={u,i}; renderDetail(true); if(S.tab==='evlist'&&$('v-evlist')) $('v-evlist').querySelectorAll('tr[data-u]').forEach(tr=>tr.classList.toggle('sel',tr.dataset.u===u&&+tr.dataset.i===i)); }

// ---------------------------------------------------------------- detail panel (explain one gold relation)
function evDetailHTML(){
  if(!EV||!ES.sel) return '<p class="na">Choose a gold relation in the list (or an example in the failure map) to see where it was lost.</p><div class="card"><b>'+esc(EV?EV.meta.notice:'Evaluation overlay')+'</b></div>';
  const d=evds(), u=d.units.find(x=>x.id===ES.sel.u), r=u.relations[ES.sel.i]; if(!r) return '';
  const dec=r.code?EV.decisive[r.code]:null;
  let h='<h2>'+esc(r.src)+' <span style="color:var(--ink2)">— '+esc(r.rel)+(r.sym?' ⟷':' →')+'</span> '+esc(r.tgt)+'</h2><span class="chip">gold</span> <span class="chip auth auth-UNKNOWN" title="derived from the benchmark gold and the frozen CR-012 attribution">EVALUATION · frozen</span> '+(r.strict?'<span class="chip">strict match</span>':'<span class="chip">not a strict match</span>');
  h+='<dl><dt>Source sentence'+(ES.ds==='pd'?' (cited by the annotator)':'')+'</dt><dd><div class="sent">'+(r.sentence?highlight(r.sentence,null,{name:r.src,aliases:[]},{name:r.tgt,aliases:[]}):'<span class="na">'+NA+'</span>')+'</div><span class="small"><mark class="a" style="padding:0 4px">gold source</mark> <mark class="b" style="padding:0 4px">gold target</mark></span></dd>';
  h+='<dt>Earliest failure (frozen CR-012 attribution order)</dt><dd>'+codeChip(r.code)+' <b>'+esc(r.code?EV_SHORT[r.code]:'')+'</b><div class="small" style="margin-top:4px">'+esc(r.code?EV.codes[r.code]:'No earliest failure at node level: the checks below all passed.'+(r.strict?'':' The relation is nevertheless not a strict mention-level match, so it is not counted as a hit by the strict scorer.'))+'</div></dd>';
  h+='<dt>Stage checks (stop at the first failure)</dt><dd><ol class="checks">'+r.checks.map(([id,ans],k)=>{ const label=(EV.checks.find(c=>c[0]===id)||[0,id])[1]; const after=dec!==null&&k>dec; const bad=dec!==null&&k===dec; return '<li class="'+(bad?'evbad':'')+(after?' evafter':'')+'"><span class="ans">'+esc(after?'—':ans)+'</span> '+esc(label)+(bad?' <b>← earliest failure</b>':'')+(after?' <span class="small">(not evaluated)</span>':'')+'</li>'; }).join('')+'</ol></dd>';
  h+='<dt>What the run retained for the endpoints</dt><dd class="small">Predicted nodes at the gold spans: '+(r.end_nodes.length?r.end_nodes.map(x=>'<span class="chip">'+esc(x)+'</span>').join(''):'<span class="na">none</span>')+'<br>Relations predicted between them: '+(r.pred_rels.length?r.pred_rels.map(x=>'<span class="chip">'+esc(x)+'</span>').join(''):'<span class="na">none</span>')+'</dd>';
  h+='<dt>Selection context for this '+esc(d.unit_word)+'</dt><dd class="small">budget '+u.selection.budget+' pairs; selected '+u.selection.selected+'; eligible pool '+u.selection.eligible_pool+' (retained as a count only; the pool itself is '+NA+' for this run).</dd>';
  if(r.graph_edge) h+='<dt>Graph</dt><dd><button id="ev-opengraph" data-e="'+esc(r.graph_edge)+'" data-d="'+esc(u.id)+'">Open in the SciNLP evaluation graph</button></dd>';
  h+='</dl><p class="small"><b>'+esc(EV.meta.notice)+'</b></p>';
  return h;
}
function wireEvDetail(box){
  const b=box.querySelector('#ev-opengraph'); if(b) b.onclick=()=>{ const doc=DATA.sci.docs.find(x=>x.doc_id===b.dataset.d); setMode('sci',doc); S.F.missed=true; side(); const e=S.G.edges.find(x=>x.id===b.dataset.e); if(e) selectEdge(e); draw(); };
}
