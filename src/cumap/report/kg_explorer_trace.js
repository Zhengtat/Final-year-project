// ====================================================================================================================
// CR-013 trace layer (P&D production mode only). Everything shown here is rendered from the DERIVED TRACE payload
// (events, journeys, per-section data, precomputed Why-not answers). Text comes from the same templates as the Python
// renderer (DATA.trace templates); a parity test proves the two outputs are identical. No gold data is present.
// ====================================================================================================================
const TRACE_TABS = [['pipeline','Pipeline'],['section','Explain a section'],['why','Why not?'],['lost','Rejected / lost'],['snap','Stage snapshots']];
const TRACE_PANES = ['pipeline','section','why','lost','snap','trace'];
const RIBBON = ['source','generator','verifier','pruner','canonicalisation','pair_generation','pair_selection','relation_classification','validation','graph_commit','organisation'];
const STAGE_NAME = {source:'Source text',generator:'Concept generator',verifier:'Verifier / correction',pruner:'Pruner',canonicalisation:'Canonicalisation',pair_generation:'Pair generation',pair_selection:'Pair ranking + budget',relation_classification:'Relation classification',validation:'Validation',graph_commit:'Graph commit',organisation:'Organisation (read-only)'};
const STEPS = [['source','1 · Source text'],['generator','2 · Concepts proposed'],['verifier','3 · Verification'],['pruner','4 · Pruning'],['canonicalisation','5 · Canonicalisation'],['pair_generation','6 · Eligible pairs'],['pair_selection','7 · Budget boundary'],['relation_classification','8 · Relation decision'],['validation','9 · Validation'],['graph_commit','10 · Local graph']];
const NOT_REC = 'NOT_RECORDED';
let TR = null, TRLOAD = null;
const TS = {stage:'pair_selection', sectionAll:true, section:null, step:0, snap:2, whyA:'', whyB:'', whyOut:null, lostMore:{}, evFilter:{stage:'',outcome:'',layer:'',q:''}};

// ---------------------------------------------------------------- loading (gzip + base64, decoded lazily on first use)
function traceAvailable(){ return S.mode==='pd' && !!$('trace-gz') && ($('trace-gz').textContent||'').length>10; }
function loadTrace(){
  if(TR) return Promise.resolve(TR);
  if(TRLOAD) return TRLOAD;
  TRLOAD = (async()=>{
    const b64=($('trace-gz').textContent||'').trim(); const bin=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));
    const stream=new Blob([bin]).stream().pipeThrough(new DecompressionStream('gzip'));
    TR=JSON.parse(await new Response(stream).text()); indexTrace(); return TR;
  })();
  return TRLOAD;
}
function indexTrace(){
  TR.events.forEach(e=>{ e.source_artifact=TR.artifacts[e.art]; e.source_locator=e.loc===undefined?null:e.loc; });
  TR.pairIdx = {}; TR.pool.forEach((r,i)=>TR.pairIdx[r[0]]=i);
  TR.finalSet = new Set(TR.final_concepts); TR.edgeSet = new Set(TR.final_edges);
  TR.secList = Object.values(TR.sections).sort((a,b)=>((a.chapter||0)-(b.chapter||0))||natcmp(a.id,b.id));
  TR.cname = {}; DATA.pd.nodes.forEach(n=>TR.cname[n.id]=n.name);
  TR.secOf = {}; TR.secList.forEach(s=>s.concepts.forEach(c=>{(TR.secOf[c]=TR.secOf[c]||[]).push(s.id);}));
  if(!TS.section) TS.section = TR.sections['3.3']?'3.3':TR.secList[0].id;
}
function natcmp(a,b){ return String(a).localeCompare(String(b),undefined,{numeric:true}); }
const cn = id => (TR&&TR.cname[id]) || id;

// ---------------------------------------------------------------- deterministic renderer (mirror of render.py)
function fmtv(v, path){
  if(v===null||v===undefined||v==='') return NOT_REC;
  if(typeof v==='boolean') return v?'True':'False';
  if(typeof v==='number'){ if(path==='score'||path==='threshold') return v.toFixed(3); return Number.isInteger(v)?String(v):v.toFixed(3); }
  if(Array.isArray(v)) return v.length? v.map(x=>fmtv(x)).join(', ') : NOT_REC;
  if(typeof v==='object'){ const k=Object.keys(v); return k.length? k.map(x=>x+'='+fmtv(v[x])).join('; ') : NOT_REC; }
  return String(v);
}
function getp(ev, path){ let cur=ev; for(const part of path.split('.')){ if(cur===null||cur===undefined||typeof cur!=='object'||!(part in cur)) return null; cur=cur[part]; } return cur===undefined?null:cur; }
function renderTemplate(t, ev){
  const segs=[]; let pos=0; const re=/\{([A-Za-z_.0-9]+)\}/g; let m;
  while((m=re.exec(t))){ if(m.index>pos) segs.push({text:t.slice(pos,m.index),field:null}); segs.push({text:fmtv(getp(ev,m[1]),m[1]),field:m[1]}); pos=m.index+m[0].length; }
  if(pos<t.length) segs.push({text:t.slice(pos),field:null}); return segs;
}
function renderEv(ev){
  const act=String(ev.action).split(':')[0].split('#')[0];
  let ts=TR.templates[ev.stage+'|'+act]; let fb=false;
  if(!ts&&ev.stage==='organisation') ts=TR.templates['organisation|org_event'];
  if(!ts){ ts=TR.fallback; fb=true; }
  const sentences=ts.map(t=>renderTemplate(fb?t.replace('{stage}',ev.stage).replace('{action}',ev.action):t, ev).map(s=>s.text).join(''));
  return {text:sentences.join(' '), sentences};
}
function poolEv(i, kind){
  const [pid,x,y,rank,sel,si,cue,cooc,sr,sp]=TR.pool[i]; const ids=TR.pool_ids[i];
  const base={stage:kind==='gen'?'pair_generation':'pair_selection', object_id:'pair:'+pid, section_id:TR.pool_sections[si], layer:'REPLAYED', authority:'SCORE', score:cue, eligible_count:TR.eligible, budget:TR.meta.replay.budget, event_id:'te_'+(kind==='gen'?ids[0]:ids[1]), source_artifact:'data/processed/kg/slice3_c2/checkpoint.json', source_locator:'selection_stats'};
  return kind==='gen' ? {...base, action:'pool_pair_replayed', outcome:'emitted', attrs:{cooccurrence_count:cooc, section_pool:sp, section_rank:sr}}
                      : {...base, action:'rank_replayed', outcome:sel?'selected':'not_selected', rank, input_refs:['concept:'+x,'concept:'+y], attrs:{section_rank:sr, section_pool:sp}};
}
const badge = ev => '<span class="chip auth auth-'+ev.authority+'" title="who decided: '+ev.authority+'">'+ev.authority+'</span>'+(ev.layer&&ev.layer!=='RECORDED'?'<span class="chip layer-'+ev.layer+'" title="'+(ev.layer==='REPLAYED'?'recomputed by the frozen deterministic code and verified against the retained selection; not originally recorded':'exact deterministic join')+'">'+ev.layer+'</span>':'');
function evCard(ev, dbg){
  const r=renderEv(ev);
  let h='<div class="evc"><div class="evh"><b>'+esc(STAGE_NAME[ev.stage]||ev.stage)+'</b> '+badge(ev)+'<span class="chip">'+esc(ev.outcome)+'</span></div><div>'+esc(r.text)+'</div>';
  if(dbg) h+='<details><summary>trace fields</summary><pre class="json" tabindex="0">'+esc(JSON.stringify(ev,null,1))+'</pre></details>';
  return h+'</div>';
}

// ---------------------------------------------------------------- scope helpers
function scopeEvents(scope){ if(!scope) return TR.events; return TR.sections[scope].ev.map(i=>TR.events[i]); }
function scopePool(scope){ if(!scope) return TR.pool.map((_,i)=>i); return TR.sections[scope].pairs; }
function scopeRows(scope){ if(!scope) return TR.secList.flatMap(s=>s.rowrecs||[]); return TR.sections[scope].rowrecs||[]; }
function counts(scope){
  const ev=scopeEvents(scope), c=(st,ac,oc)=>ev.filter(e=>e.stage===st&&(!ac||String(e.action).split(':')[0]===ac)&&(!oc||e.outcome===oc)).length;
  const pool=scopePool(scope), selPool=pool.filter(i=>TR.pool[i][4]).length, rows=scopeRows(scope).filter(r=>r.g!=='sample');
  const out={
    source:[['text units',c('source')]],
    generator:[['mentions recorded',c('generator','mention_recorded')],['concepts proposed',c('generator','proposed')]],
    verifier:[['flags raised',c('verifier','flag_raised')],['automatic corrections',c('verifier','autofix')],['candidates rejected',c('verifier','candidate_rejected')],['hints rejected',c('verifier','hint_rejected')]],
    pruner:[['candidates scored',c('pruner','prune_score')],['pruned',0]],
    canonicalisation:[['names linked to a concept',c('canonicalisation','alias_link','merged')+c('generator','alias_link','merged')],['kept separate (taxonomy decisions)',c('canonicalisation','taxonomy_candidate')]],
    pair_generation:[['eligible candidate pairs (replayed)',pool.length],['anchor pairs (recorded)',ev.filter(e=>e.stage==='pair_generation'&&e.action==='anchor_pair_join').length]],
    pair_selection:[['selected from the pool',selPool],['eligible but not selected',pool.length-selPool],['anchor pairs selected',ev.filter(e=>e.stage==='pair_selection'&&e.action==='selected_recorded'&&String(e.object_id).startsWith('pair:AP-')).length]],
    relation_classification:[['pairs classified',rows.length],['relation proposed',rows.filter(r=>r.o==='emitted').length],['no relation / other',rows.filter(r=>r.o==='no_relation').length]],
    validation:[['accepted',rows.filter(r=>r.vo==='accepted').length],['rejected',rows.filter(r=>r.vo==='rejected').length]],
    graph_commit:[['edges committed',scope?(TR.sections[scope].edges||[]).length:TR.final_edges.length],['concepts in the final graph',scope?TR.sections[scope].concepts.filter(x=>TR.finalSet.has(x)).length:TR.final_concepts.length]],
    organisation:[['organisation events',scope?'only for the whole graph':c('organisation')]],
  };
  return out;
}

// ---------------------------------------------------------------- tab rendering entry
async function renderTraceTab(k){
  const el=$('v-'+k); if(!el) return;
  el.innerHTML='<p class="na">Loading the trace…</p>';
  try{ await loadTrace(); }catch(e){ el.innerHTML='<p class="na">The trace could not be loaded in this browser ('+esc(e&&e.message||e)+'). It needs DecompressionStream support.</p>'; return; }
  ({pipeline:viewPipeline, section:viewSection, why:viewWhy, lost:viewLost, snap:viewSnap, trace:viewTrace})[k](el);
}
function secSelect(withAll){
  const allSel=withAll&&TS.sectionAll;
  return '<label class="small">Section <select class="tsec">'+(withAll?'<option value=""'+(allSel?' selected':'')+'>All sections</option>':'')+TR.secList.map(s=>'<option value="'+esc(s.id)+'"'+(!allSel&&s.id===TS.section?' selected':'')+'>'+esc(s.id)+' · '+esc(s.title)+'</option>').join('')+'</select></label>';
}
function wireSecSelect(el, rerender, allowAll){
  const s=el.querySelector('.tsec'); if(s) s.onchange=()=>{ if(s.value){ TS.section=s.value; TS.sectionAll=false; } else if(allowAll){ TS.sectionAll=true; } rerender(); };
}
const scopeOf = withAll => (withAll&&TS.sectionAll)?null:TS.section;
function funnelBar(c){
  const f=[['eligible',c.pair_generation[0][1]],['selected',c.pair_selection[0][1]+c.pair_selection[2][1]],['classified',c.relation_classification[0][1]],['relation proposed',c.relation_classification[1][1]],['validated',c.validation[0][1]],['committed',c.graph_commit[0][1]]];
  const mx=Math.max(1,...f.map(x=>x[1]));
  return '<div class="funnel">'+f.map(([l,v])=>'<div class="fr"><span class="fl">'+l+'</span><span class="fb"><i style="width:'+(100*v/mx)+'%"></i></span><span class="fv">'+v+'</span></div>').join('')+'</div>';
}

// ---------------------------------------------------------------- Pipeline
function viewPipeline(el){
  const scope=scopeOf(true), c=counts(scope), st=TS.stage, ex=scopeEvents(scope);
  let h='<h2 class="vh">Pipeline</h2><p class="small">How a textbook becomes a graph, stage by stage. Pick a stage to see what it does, what happened here and why it matters. '+secSelect(true).replace('class="small"','')+'</p>';
  h+='<div class="ribbon" role="tablist" aria-label="Pipeline stages" id="ribbon">'+RIBBON.map((s,i)=>'<button role="tab" aria-selected="'+(s===st)+'" tabindex="'+(s===st?0:-1)+'" data-st="'+s+'" class="'+(s===st?'on':'')+'"><span class="n">'+(i+1)+'</span>'+esc(STAGE_NAME[s])+'<small>'+esc(c[s].map(x=>x[1]+' '+x[0]).slice(0,2).join(' · '))+'</small></button>').join('')+'</div>';
  h+=funnelBar(c);
  h+='<div class="card"><h4>What does this stage do?</h4>'+esc(TR.stage_info[st==='verifier'?'verifier':st])+'</div>';
  h+='<div class="card"><h4>What happened here? <span class="small">('+(scope?esc(scope):'whole graph')+')</span></h4><ul>'+c[st].map(([l,v])=>'<li><b>'+esc(v)+'</b> '+esc(l)+'</li>').join('')+'</ul>';
  const samples=ex.filter(e=>e.stage===st||(st==='verifier'&&e.stage==='correction')).slice(0,3);
  if(st==='pair_selection'){ const p=scopePool(scope).slice(0,3); h+=p.map(i=>evCard(poolEv(i,'sel'),S.view==='debug')).join(''); }
  else if(st==='pair_generation'){ const p=scopePool(scope).slice(0,2); h+=p.map(i=>evCard(poolEv(i,'gen'),S.view==='debug')).join('')+samples.map(e=>evCard(e,S.view==='debug')).join(''); }
  else h+=samples.map(e=>evCard(e,S.view==='debug')).join('')||'<p class="na">No retained event of this stage in this scope.</p>';
  h+='</div><div class="card"><h4>Why does it matter?</h4>'+esc(TR.stage_matters[st])+'</div>';
  if(st==='pair_selection') h+='<div class="card warn"><h4>Replayed ranks</h4>Ranks come from the REPLAYED layer: the frozen selection code was re-run (no model call) and verified to reproduce the retained selected set exactly. They were not originally recorded. Replay valid: <b>'+TR.meta.replay.valid+'</b>, deterministic: <b>'+TR.meta.replay.deterministic+'</b>.</div>';
  el.innerHTML=h; wireSecSelect(el,()=>viewPipeline(el),true);
  const rb=el.querySelector('#ribbon'); rb.querySelectorAll('button').forEach(b=>b.onclick=()=>{TS.stage=b.dataset.st; viewPipeline(el); const nb=$('v-pipeline').querySelector('#ribbon button.on'); if(nb) nb.focus();});
  rb.onkeydown=ev=>{ if(ev.key!=='ArrowRight'&&ev.key!=='ArrowLeft') return; ev.preventDefault(); const i=RIBBON.indexOf(TS.stage), j=(i+(ev.key==='ArrowRight'?1:-1)+RIBBON.length)%RIBBON.length; TS.stage=RIBBON[j]; S.kb=true; viewPipeline(el); S.kb=false; const nb=el.querySelector('#ribbon button.on'); if(nb) nb.focus(); };
}

// ---------------------------------------------------------------- Explain a section
function mentionHighlight(sec){
  const text=sec.text, low=text.toLowerCase(), marks=new Array(text.length).fill(0), spans=[];
  (sec.mentions||[]).forEach(m=>{ const ev=m[2]; if(!ev) return; const q=ev.replace(/\s+/g,' ').toLowerCase(); const i=low.indexOf(q); if(i>=0) spans.push([i,i+q.length]); });
  spans.forEach(([a,b])=>{ for(let k=a;k<b;k++) marks[k]=1; });
  let out='',i=0; while(i<text.length){ let j=i; while(j<text.length&&marks[j]===marks[i]) j++; const seg=esc(text.slice(i,j)); out+=marks[i]?'<mark class="a">'+seg+'</mark>':seg; i=j; }
  return {html:out, found:spans.length};
}
function stepContent(sec, id, dbg){
  const ev=sec.ev.map(i=>TR.events[i]), by=(st,ac)=>ev.filter(e=>e.stage===st&&(!ac||String(e.action).split(':')[0]===ac));
  const list=(arr,n)=>arr.slice(0,n).map(e=>evCard(e,dbg)).join('')+(arr.length>n?'<p class="small">… '+(arr.length-n)+' more (Rejected / lost tab lists them)</p>':'');
  const rows=(sec.rowrecs||[]).filter(r=>r.g!=='sample');
  const rowLink=(r)=>'<a class="lnk" data-pair="'+esc(r.p)+'">'+esc(cn(r.x))+' ⟷ '+esc(cn(r.y))+'</a>';
  switch(id){
    case 'source': { const h=mentionHighlight(sec); return '<p class="small">Section <b>'+esc(sec.id)+'</b>, '+esc(sec.title)+' (chapter '+esc(sec.chapter)+'). Highlighted: the sentences the generator cited as evidence for a concept ('+h.found+' located).</p><div class="srcbox" tabindex="0">'+h.html+'</div>'; }
    case 'generator': return '<p class="small">The generator proposed '+(sec.proposed||[]).length+' new candidate concepts in this section and recorded '+(sec.mentions||[]).length+' mentions. A proposal is not yet a graph node.</p>'+'<table class="t"><tr><th>proposed concept</th><th>type</th><th>recorded model reason</th><th>final concept</th></tr>'+(sec.proposed||[]).slice(0,60).map(p=>'<tr><td>'+esc(p[1])+'</td><td>'+esc(p[2])+'</td><td>'+(p[3]?esc(p[3]):'<span class="na">'+NOT_REC+'</span>')+'</td><td>'+(p[4]?'<a class="lnk" data-c="'+esc(p[4])+'">'+esc(cn(p[4]))+'</a>':'<span class="na">no unique join</span>')+'</td></tr>').join('')+'</table>';
    case 'verifier': return '<p class="small">Deterministic checks on the proposals: '+by('verifier','flag_raised').length+' flags, '+by('verifier','autofix').length+' automatic corrections, '+by('verifier','candidate_rejected').length+' rejected candidates, '+by('verifier','hint_rejected').length+' rejected hints.</p>'+list(by('verifier','candidate_rejected'),8)+list(by('verifier','autofix'),6)+list(by('verifier','hint_rejected'),4);
    case 'pruner': return '<p class="small">The pruner scored '+by('pruner').length+' candidates. In this run it was configured not to drop any (threshold: <span class="na">'+NOT_REC+'</span> in the artifact), so everything scored here was kept.</p><table class="t"><tr><th>candidate</th><th>score</th><th>outcome</th></tr>'+by('pruner').slice(0,40).map(e=>'<tr><td>'+esc(getp(e,'attrs.name'))+'</td><td>'+esc(fmtv(e.score,'score'))+'</td><td>'+esc(e.outcome)+'</td></tr>').join('')+'</table>';
    case 'canonicalisation': return '<p class="small">Identity decisions (which names are one concept). '+by('canonicalisation','alias_link').length+' name links, '+by('canonicalisation','taxonomy_candidate').length+' taxonomy decisions that kept concepts separate. Blocked merges are <span class="na">'+NOT_REC+'</span> in this run.</p>'+list(by('canonicalisation','alias_link'),6)+list(by('canonicalisation','taxonomy_candidate'),6);
    case 'pair_generation': { const ps=sec.pairs; return '<p class="small"><b>'+ps.length+'</b> eligible candidate pairs are attributed to this section (REPLAYED layer: recomputed by the frozen code, verified against the retained selection).</p><table class="t"><tr><th>pair</th><th>cue</th><th>co-occurrence</th><th>global rank</th><th>selected</th></tr>'+ps.slice(0,25).map(i=>{const r=TR.pool[i]; return '<tr><td><a class="lnk" data-pair="'+esc(r[0])+'">'+esc(cn(r[1]))+' ⟷ '+esc(cn(r[2]))+'</a></td><td>'+r[6]+'</td><td>'+r[7]+'</td><td>'+r[3]+'</td><td>'+(r[4]?'yes':'no')+'</td></tr>';}).join('')+'</table>'+(ps.length>25?'<p class="small">… '+(ps.length-25)+' more</p>':''); }
    case 'pair_selection': { const B=TR.meta.replay.budget, ps=sec.pairs.map(i=>TR.pool[i]).sort((a,b)=>a[3]-b[3]); const inside=ps.filter(r=>r[4]).length; return '<p class="small">Budget for the whole run: <b>'+B+'</b> pairs out of <b>'+TR.eligible+'</b> eligible. In this section <b>'+inside+'</b> of '+ps.length+' eligible pairs were selected. Selection also applies a per-section minimum, an anchor phase and a coverage phase, so the global rank alone is not a cut-off.</p><div class="boundary">'+ps.slice(0,30).map(r=>'<div class="'+(r[4]?'in':'out')+'"><span class="rk">#'+r[3]+'</span> '+(r[4]?'selected':'<b>not selected</b>')+' · <a class="lnk" data-pair="'+esc(r[0])+'">'+esc(cn(r[1]))+' ⟷ '+esc(cn(r[2]))+'</a></div>').join('')+'</div>'; }
    case 'relation_classification': return '<p class="small">The classifier decided '+rows.length+' pairs of this section ('+rows.filter(r=>r.o==='emitted').length+' with a relation proposed, '+rows.filter(r=>r.o==='no_relation').length+' with no accepted relation).</p><table class="t"><tr><th>pair</th><th>outcome</th><th>relation</th><th>direction</th><th>reason code</th></tr>'+rows.slice(0,40).map(r=>'<tr><td>'+rowLink(r)+'</td><td>'+esc(r.o)+'</td><td>'+esc(r.rel||'—')+'</td><td>'+esc(r.d||'—')+'</td><td>'+esc(r.rc||'—')+'</td></tr>').join('')+'</table>'+(rows.length>40?'<p class="small">… '+(rows.length-40)+' more</p>':'');
    case 'validation': return '<p class="small">Proposed relations are checked for grounding and type constraints: '+rows.filter(r=>r.vo==='accepted').length+' accepted, '+rows.filter(r=>r.vo==='rejected').length+' rejected.</p>'+list(sec.ev.map(i=>TR.events[i]).filter(e=>e.stage==='validation'&&e.outcome==='rejected'),10);
    case 'graph_commit': return '<p class="small">The local final graph of this section: '+(sec.edges||[]).length+' committed edges in this section (the section mentions '+sec.concepts.filter(c=>TR.finalSet.has(c)).length+' final concepts). Red dashed = proposed but rejected at validation. Open a relation to see its journey.</p><canvas id="cv-sec" class="mini"></canvas><div class="small" id="sec-edges">'+(sec.edges||[]).slice(0,20).map(e=>'<a class="lnk" data-edge="'+esc(e)+'">'+esc(e)+'</a>').join(' · ')+'</div>';
  }
  return '';
}
function viewSection(el){
  const sec=TR.sections[TS.section], dbg=S.view==='debug', id=STEPS[TS.step][0];
  let h='<h2 class="vh">Explain a section</h2><p class="small">Walk from the source text to the local final graph. '+secSelect(false)+'</p><div class="stepper" role="tablist" aria-label="Walkthrough steps" id="stepper">'+STEPS.map((s,i)=>'<button role="tab" aria-selected="'+(i===TS.step)+'" tabindex="'+(i===TS.step?0:-1)+'" data-i="'+i+'" class="'+(i===TS.step?'on':'')+'">'+esc(s[1])+'</button>').join('')+'</div>';
  h+='<div class="card stepbody" id="stepbody"><h4>'+esc(STEPS[TS.step][1].slice(4))+' <span class="small">— '+esc(TR.stage_info[id==='verifier'?'verifier':id])+'</span></h4>'+stepContent(sec,id,dbg)+'</div>';
  h+='<div class="nav"><button id="prev">← Previous</button> <button id="next">Next →</button></div>';
  el.innerHTML=h;
  wireSecSelect(el,()=>viewSection(el));
  const go=(i,kb)=>{ TS.step=Math.max(0,Math.min(STEPS.length-1,i)); S.kb=!!kb; viewSection(el); S.kb=false; const b=el.querySelector('#stepper button.on'); if(kb&&b) b.focus(); };
  el.querySelectorAll('#stepper button').forEach(b=>b.onclick=()=>go(+b.dataset.i));
  el.querySelector('#prev').onclick=()=>go(TS.step-1); el.querySelector('#next').onclick=()=>go(TS.step+1);
  el.querySelector('#stepper').onkeydown=ev=>{ if(ev.key==='ArrowRight'){ ev.preventDefault(); go(TS.step+1,true);} else if(ev.key==='ArrowLeft'){ ev.preventDefault(); go(TS.step-1,true);} };
  wireLinks(el);
  if(id==='graph_commit') drawLocal(el.querySelector('#cv-sec'), TS.section, 4);
  const sb=el.querySelector('#stepbody'); if(sb&&animOK()){ sb.style.opacity=0; sb.style.transform='translateY(6px)'; requestAnimationFrame(()=>requestAnimationFrame(()=>{ sb.style.transition='opacity 180ms var(--ease-out),transform 180ms var(--ease-out)'; sb.style.opacity=1; sb.style.transform='none'; })); }
}
function wireLinks(el){
  el.querySelectorAll('a[data-pair]').forEach(a=>a.onclick=()=>openPair(a.dataset.pair));
  el.querySelectorAll('a[data-c]').forEach(a=>a.onclick=()=>openConcept(a.dataset.c));
  el.querySelectorAll('a[data-edge]').forEach(a=>a.onclick=()=>openEdge(a.dataset.edge));
  el.querySelectorAll('a[data-why]').forEach(a=>a.onclick=()=>{ const [x,y]=a.dataset.why.split('|'); TS.whyA=x; TS.whyB=y; showTab('why'); });
}
function openConcept(cid){ showTab('graph'); if(byId['c_'+cid.replace(/^c_/,'')]||byId[cid]) selectNode(byId[cid]?cid:'c_'+cid); }
function openEdge(eid){ showTab('graph'); const e=S.G.edges.find(x=>x.id===eid); if(e) selectEdge(e); }
function openPair(pid){
  const i=TR.pairIdx[pid]; const row=TR.sections?null:null; void row;
  const r=i!==undefined?TR.pool[i]:null;
  if(r){ TS.whyA=r[1]; TS.whyB=r[2]; showTab('why'); } else { const e=S.G.edges.find(x=>x.id===pid); if(e) { showTab('graph'); selectEdge(e); } }
}

// ---------------------------------------------------------------- local canvases (section graph and stage snapshots)
function frLayout(ids, edges, init, iters){
  // small deterministic Fruchterman-Reingold on the visible subset (positions start from the precomputed layout)
  const pos={}, n=ids.length; if(!n) return pos;
  const hash=str=>{ let h=2166136261; for(let i=0;i<str.length;i++){ h^=str.charCodeAt(i); h=Math.imul(h,16777619); } return ((h>>>0)%1000)/1000; };
  ids.forEach(id=>{ const b=init[id]||[0,0]; pos[id]=[b[0]+(hash(id)-.5)*.05, b[1]+(hash(id+'y')-.5)*.05]; });
  const k=Math.sqrt(5.0/n); let t=0.3;
  for(let it=0; it<iters; it++){
    const disp={}; ids.forEach(id=>disp[id]=[0,0]);
    for(let i=0;i<n;i++) for(let j=i+1;j<n;j++){ const a=ids[i], b=ids[j]; let dx=pos[a][0]-pos[b][0], dy=pos[a][1]-pos[b][1]; let d=Math.hypot(dx,dy)||0.01; const f=k*k/d; dx/=d; dy/=d; disp[a][0]+=dx*f; disp[a][1]+=dy*f; disp[b][0]-=dx*f; disp[b][1]-=dy*f; }
    edges.forEach(([a,b])=>{ if(!pos[a]||!pos[b]) return; let dx=pos[a][0]-pos[b][0], dy=pos[a][1]-pos[b][1]; const d=Math.hypot(dx,dy)||0.01; const f=d*d/k; dx/=d; dy/=d; disp[a][0]-=dx*f; disp[a][1]-=dy*f; disp[b][0]+=dx*f; disp[b][1]+=dy*f; });
    ids.forEach(id=>{ disp[id][0]-=pos[id][0]*k*5; disp[id][1]-=pos[id][1]*k*5; const dd=Math.hypot(disp[id][0],disp[id][1])||0.01, m=Math.min(dd,t); pos[id][0]+=disp[id][0]/dd*m; pos[id][1]+=disp[id][1]/dd*m; pos[id][0]=Math.max(-1.3,Math.min(1.3,pos[id][0])); pos[id][1]=Math.max(-1.3,Math.min(1.3,pos[id][1])); });
    t*=0.985;
  }
  return pos;
}
function drawLocal(cvs, sid, stage){
  if(!cvs) return; const sec=TR.sections[sid], lay=TR.layouts[sid]||{}; const W=cvs.clientWidth||cvs.getBoundingClientRect().width||700, H=440; cvs.width=W; cvs.height=H; cvs.style.height=H+'px';
  const c=cvs.getContext('2d'); c.clearRect(0,0,W,H); const dark=DARK(), ink=dark?'#e8e8ea':'#15171c';
  const all=Object.keys(lay); if(!all.length){ c.fillStyle=ink; c.fillText('no local concepts retained for this section',10,20); return; }
  const rows=(sec.rowrecs||[]).filter(r=>r.g!=='sample'&&r.x&&r.y&&lay[r.x]&&lay[r.y]);
  const pairsSel=sec.pairs.map(i=>TR.pool[i]).filter(r=>r[4]&&lay[r[1]]&&lay[r[2]]);
  const committed=rows.filter(r=>r.ce);
  // what is visible at each stage: extraction/canonicalisation = all concepts; selection = endpoints of selected pairs; classification = classified pairs; validation = committed edges (rejected shown too)
  let vis, edges=[];
  if(stage<2){ vis=all; }
  else if(stage===2){ vis=[...new Set(pairsSel.flatMap(r=>[r[1],r[2]]))]; edges=pairsSel.map(r=>[r[1],r[2]]); }
  else if(stage===3){ vis=[...new Set(rows.flatMap(r=>[r.x,r.y]))]; edges=rows.map(r=>[r.x,r.y]); }
  else { const keep=rows.filter(r=>r.ce||r.vo==='rejected'); vis=[...new Set(keep.flatMap(r=>[r.x,r.y]))]; edges=keep.map(r=>[r.x,r.y]); }
  const pos=stage<2?lay:frLayout(vis,edges,lay,vis.length>260?60:220);
  const P=id=>[34+(Math.max(-1.4,Math.min(1.4,pos[id][0]))+1.4)/2.8*(W-68), 30+(Math.max(-1.4,Math.min(1.4,pos[id][1]))+1.4)/2.8*(H-60)];
  const line=(a,b,col,dash,w)=>{ if(!pos[a]||!pos[b]) return; const [x1,y1]=P(a),[x2,y2]=P(b); c.setLineDash(dash||[]); c.strokeStyle=col; c.lineWidth=w||1.4; c.beginPath(); c.moveTo(x1,y1); c.lineTo(x2,y2); c.stroke(); c.setLineDash([]); };
  if(stage===2) pairsSel.forEach(r=>line(r[1],r[2],dark?'#666':'#aaa',[3,3],1));
  if(stage===3) rows.forEach(r=>{ if(r.o==='emitted') line(r.x,r.y,relCol(r.rel),null,1.7); else line(r.x,r.y,dark?'#555':'#ccc',[1,3],1); });
  if(stage>=4) rows.filter(r=>r.ce||r.vo==='rejected').forEach(r=>{ if(r.ce) line(r.x,r.y,relCol(r.rel),null,2.8); else line(r.x,r.y,'#C23B3B',[5,3],1.6); });
  const deg={}; edges.forEach(([a,b])=>{ deg[a]=(deg[a]||0)+1; deg[b]=(deg[b]||0)+1; });
  vis.forEach(id=>{ const [x,y]=P(id), fin=TR.finalSet.has(id); c.fillStyle=typeCol((DATA.pd.nodes.find(n=>n.id===id)||{}).type); c.beginPath(); c.arc(x,y,fin?5:3.4,0,6.283); c.fill(); });
  c.fillStyle=ink; c.font='11px sans-serif';
  const showAll=stage>=4||vis.length<45; const placed=[];
  [...vis].sort((a,b)=>(deg[b]||0)-(deg[a]||0)).forEach(id=>{ if(!showAll&&(deg[id]||0)<2) return; const [x,y]=P(id), label=cn(id), w=c.measureText(label).width; const box=[x+7,y-9,x+7+w,y+3]; if(placed.some(b=>box[0]<b[2]&&box[2]>b[0]&&box[1]<b[3]&&box[3]>b[1])) return; placed.push(box); c.fillText(label,x+7,y+3); });
  c.fillStyle=dark?'#a3aab8':'#5a6070'; c.fillText(vis.length+' concepts · '+edges.length+' pairs shown',10,H-8);
}
const SNAP_STAGES=['After extraction (concepts in the section)','After canonicalisation (identity settled)','After pair selection (dashed = pairs sent to the classifier)','After relation classification (coloured = relation proposed, dotted = no relation)','After validation (thick = committed edge, red = rejected)'];
function viewSnap(el){
  const sec=TR.sections[TS.section];
  el.innerHTML='<h2 class="vh">Stage snapshots</h2><p class="small">The local state of one section after each stage. '+secSelect(false)+'</p><div class="snapctl"><label>Stage <input type="range" id="snapr" min="0" max="4" step="1" value="'+TS.snap+'" aria-label="pipeline stage"></label> <b id="snapl">'+esc(SNAP_STAGES[TS.snap])+'</b></div><canvas id="cv-snap" class="mini"></canvas><p class="small">'+sec.concepts.length+' concepts, '+(sec.rowrecs||[]).filter(r=>r.g!=='sample').length+' classified pairs, '+(sec.edges||[]).length+' committed edges in section '+esc(sec.id)+'. Intermediate candidates appear only here; the normal graph shows the final result.</p>';
  wireSecSelect(el,()=>viewSnap(el));
  const r=el.querySelector('#snapr'); r.oninput=()=>{ TS.snap=+r.value; el.querySelector('#snapl').textContent=SNAP_STAGES[TS.snap]; drawLocal(el.querySelector('#cv-snap'),TS.section,TS.snap); };
  drawLocal(el.querySelector('#cv-snap'),TS.section,TS.snap);
}

// ---------------------------------------------------------------- Why not?
function whyAnswer(a, b){
  const idLabel=(id,i)=>TR.check_labels[id].replace('{c}', cn(i===0?a:b));
  const letters=TR.why_answer_letters; const finA=TR.finalSet.has(a), finB=TR.finalSet.has(b);
  let code='', status='lost', seq='', rank=null, elig=null, budget=null, layer=null, reason=null;
  if(!finA||!finB){ code='N0'; seq=(finA?'y':'n')+(finB?'y':'n')+'i'; }
  else {
    const rec=TR.why[[a,b].sort().join('|')];
    if(rec){ [code,status,seq,rank,elig,budget,layer,reason]=rec; }
    else if(TR.meta.replay.valid){ code='P0'; status='lost'; seq='yyin'; }
    else { code=''; status='unknown'; seq='yyiu'; }
  }
  const order=['final','final','identity','eligible','selected','classified','validated','committed'];
  const checks=[...seq].map((ch,i)=>({id:order[i], answer:letters[ch], label:order[i]==='final'?idLabel('final',i):TR.check_labels[order[i]]}));
  const sentences=[];
  if(code){ sentences.push(TR.code_text[code]); if(rank!==null&&rank!==undefined) sentences.push(TR.why_sentences.rank.replace('{rank}',fmtv(rank)).replace('{eligible_count}',fmtv(elig)).replace('{rank_layer}',fmtv(layer)).replace('{budget}',fmtv(budget))); if(reason) sentences.push(TR.why_sentences.reason.replace('{reason_code}',fmtv(reason))); }
  return {code, status, checks, sentences, rank, elig, budget, key:[a,b].sort().join('|')};
}
function conceptOptions(){ return TR.final_concepts.map(c=>'<option value="'+esc(cn(c))+'">').join(''); }
function resolveName(s){ s=(s||'').trim().toLowerCase(); if(!s) return ''; if(TR.finalSet.has(s)) return s; return TR.final_concepts.find(c=>cn(c).toLowerCase()===s)||''; }
function viewWhy(el){
  const A=resolveName(TS.whyA)||'', B=resolveName(TS.whyB)||'';
  let h='<h2 class="vh">Why not?</h2><p class="small">Pick two concepts. The explorer walks the observable stages and stops at the earliest loss. It uses only retained or replayed trace data and never claims that a missing relation <i>should</i> exist.</p>'+
   '<div class="whyform"><label>Concept A <input id="wa" list="wl" value="'+esc(A?cn(A):TS.whyA)+'"></label> <label>Concept B <input id="wb" list="wl" value="'+esc(B?cn(B):TS.whyB)+'"></label> <button id="wgo">Explain</button> <button id="wswap" title="swap A and B">⇄</button><datalist id="wl">'+conceptOptions()+'</datalist></div>';
  const ex=lostExamples(); h+='<p class="small">Try: '+ex.map(e=>'<a class="lnk" data-why="'+esc(e[0]+'|'+e[1])+'">'+esc(cn(e[0])+' ⟷ '+cn(e[1]))+'</a>').join(' · ')+'</p>';
  h+='<div id="whyout">';
  if(A&&B&&A!==B){ const w=whyAnswer(A,B); TS.whyOut=w; h+=renderWhy(w,A,B); }
  else if(TS.whyA||TS.whyB) h+='<p class="na">Choose two different concepts of the final graph (type a name and pick from the list).</p>';
  el.innerHTML=h+'</div>'; wireLinks(el);
  const go=()=>{ TS.whyA=el.querySelector('#wa').value; TS.whyB=el.querySelector('#wb').value; viewWhy(el); };
  el.querySelector('#wgo').onclick=go; el.querySelector('#wswap').onclick=()=>{ const t=el.querySelector('#wa').value; el.querySelector('#wa').value=el.querySelector('#wb').value; el.querySelector('#wb').value=t; go(); };
  el.querySelectorAll('#wa,#wb').forEach(i=>i.onkeydown=ev=>{ if(ev.key==='Enter') go(); });
}
function renderWhy(w, a, b){
  const dbg=S.view==='debug';
  let h='<div class="card"><h4>'+esc(cn(a))+' ⟷ '+esc(cn(b))+'</h4><ol class="checks">'+w.checks.map(c=>'<li class="ck-'+c.answer+'"><span class="ans">'+esc(c.answer.replace(/_/g,' '))+'</span> '+esc(c.label)+'</li>').join('')+'</ol>';
  if(w.code){ h+='<div class="fail"><b>Earliest observable failure: '+esc(w.code)+'</b><br>'+w.sentences.map(s=>esc(s)).join(' ')+'</div>'; }
  else if(w.status==='edge_exists') h+='<div class="okk"><b>An edge exists between these concepts.</b> See its journey in the graph view.</div>';
  else h+='<div class="fail"><b>Unknown.</b> The trace does not retain enough to decide ('+NOT_REC+').</div>';
  if(w.rank!==null&&w.rank!==undefined) h+='<p class="small">Replayed rank <b>'+w.rank+'</b> of '+w.elig+' · budget '+w.budget+' (REPLAYED layer, not originally recorded).</p>';
  const pid=pairIdOf(a,b); if(pid) h+='<p class="small">Pair <code>'+esc(pid)+'</code>'+(dbg?' · <a class="lnk" data-copy="'+esc(pid)+'">copy id</a>':'')+'</p>';
  h+='<p class="small">Identity (C0/C1) and wrong relation or direction (R1/R2) need a reference; they exist only in the evaluation overlay.</p></div>';
  return h;
}
function pairIdOf(a,b){ const k=[a,b].sort().join('|'); for(let i=0;i<TR.pool.length;i++){ const r=TR.pool[i]; if([r[1],r[2]].sort().join('|')===k) return r[0]; } return null; }
function lostExamples(){ const out=[]; for(const r of TR.pool){ if(!r[4]&&r[3]>TR.meta.replay.budget&&out.length<4&&TR.finalSet.has(r[1])&&TR.finalSet.has(r[2])) out.push([r[1],r[2]]); } const nr=scopeRows(null).filter(r=>r.o==='no_relation'&&r.g!=='sample'&&r.x&&r.y).slice(0,2); nr.forEach(r=>out.push([r.x,r.y])); return out; }

// ---------------------------------------------------------------- Rejected / lost items
function viewLost(el){
  const scope=scopeOf(true), ev=scopeEvents(scope), rows=scopeRows(scope).filter(r=>r.g!=='sample'), dbg=S.view==='debug';
  const pool=scopePool(scope).map(i=>TR.pool[i]).filter(r=>!r[4]).sort((a,b)=>a[3]-b[3]);
  const by=(st,ac)=>ev.filter(e=>e.stage===st&&String(e.action).split(':')[0]===ac);
  const more=k=>TS.lostMore[k]?200:12;
  const sec=(k,title,n,body,note)=>'<details class="card" '+(n?'open':'')+'><summary><b>'+esc(title)+'</b> <span class="chip">'+n+'</span></summary>'+(note?'<p class="small">'+note+'</p>':'')+body+'</details>';
  const evl=(arr,k)=>arr.slice(0,more(k)).map(e=>evCard(e,dbg)).join('')+(arr.length>more(k)?'<button data-more="'+k+'">show all '+arr.length+'</button>':'');
  let h='<h2 class="vh">Rejected / lost items</h2><p class="small">What did not make it, and where it was lost. '+secSelect(true)+'</p>';
  h+=sec('rej','Rejected concepts (verifier)',by('verifier','candidate_rejected').length,evl(by('verifier','candidate_rejected'),'rej'));
  h+=sec('fix','Corrected proposals (automatic corrections)',by('verifier','autofix').length,evl(by('verifier','autofix'),'fix'));
  h+=sec('hint','Rejected hints',by('verifier','hint_rejected').length,evl(by('verifier','hint_rejected'),'hint'));
  h+=sec('prn','Pruned concepts',0,'<p class="small">None: the pruner was configured not to drop candidates in this run.</p>');
  h+=sec('blk','Concepts kept separate by a taxonomy decision',by('canonicalisation','taxonomy_candidate').length,evl(by('canonicalisation','taxonomy_candidate'),'blk'),'Blocked merges (the lexicon veto) are '+NOT_REC+' in this run.');
  h+=sec('out','Eligible pairs outside the selection (not sent to the classifier)',pool.length,'<table class="t"><tr><th>pair</th><th>replayed rank</th><th>cue</th><th></th></tr>'+pool.slice(0,more('out')).map(r=>'<tr><td>'+esc(cn(r[1]))+' ⟷ '+esc(cn(r[2]))+'</td><td>'+r[3]+' / '+TR.eligible+'</td><td>'+r[6]+'</td><td><a class="lnk" data-why="'+esc(r[1]+'|'+r[2])+'">Why not?</a></td></tr>').join('')+'</table>'+(pool.length>more('out')?'<button data-more="out">show more</button>':''),'REPLAYED layer. Selection also uses a per-section minimum, anchor and coverage phases.');
  const nr=rows.filter(r=>r.o==='no_relation');
  h+=sec('nr','Pairs the classifier judged to have no accepted relation',nr.length,'<table class="t"><tr><th>pair</th><th>reason code</th><th></th></tr>'+nr.slice(0,more('nr')).map(r=>'<tr><td>'+esc(cn(r.x))+' ⟷ '+esc(cn(r.y))+'</td><td>'+esc(r.rc||NOT_REC)+'</td><td><a class="lnk" data-why="'+esc(r.x+'|'+r.y)+'">Why not?</a></td></tr>').join('')+'</table>'+(nr.length>more('nr')?'<button data-more="nr">show more</button>':''));
  const vr=rows.filter(r=>r.vo==='rejected');
  h+=sec('vr','Relations rejected at validation',vr.length,'<table class="t"><tr><th>pair</th><th>proposed relation</th><th>reason</th></tr>'+vr.slice(0,more('vr')).map(r=>'<tr><td>'+esc(cn(r.x))+' ⟷ '+esc(cn(r.y))+'</td><td>'+esc(r.rel||'—')+'</td><td>'+esc(r.vr||NOT_REC)+'</td></tr>').join('')+'</table>');
  const gaps=TR.gaps.filter(g=>g.scope==='run'||(scope&&g.object_id&&String(g.object_id).includes(scope)));
  h+=sec('gap','Objects and fields with missing trace data',gaps.length,'<ul class="small">'+gaps.slice(0,more('gap')+10).map(g=>'<li><b>'+esc(g.status)+'</b> · '+esc(g.stage)+' · '+esc(g.field)+(g.object_id?' · <code>'+esc(g.object_id)+'</code>':'')+' — '+esc(g.detail)+'</li>').join('')+'</ul>');
  el.innerHTML=h; wireSecSelect(el,()=>viewLost(el),true); wireLinks(el);
  el.querySelectorAll('button[data-more]').forEach(b=>b.onclick=()=>{ TS.lostMore[b.dataset.more]=true; viewLost(el); });
}

// ---------------------------------------------------------------- Audit table (debug)
function viewTrace(el){
  const f=TS.evFilter; const obj=S.sel?(S.sel.kind==='node'?'concept:'+S.sel.id:'edge:'+S.sel.e.id):null;
  let evs;
  if(obj&&TR.journeys[obj]){ evs=TR.journeys[obj].ev.map(i=>TR.events[i]); TR.journeys[obj].pairs.forEach(p=>{ const i=TR.pairIdx[p]; if(i!==undefined) evs=evs.concat([poolEv(i,'gen'),poolEv(i,'sel')]); }); }
  else evs=scopeEvents(scopeOf(true));
  const q=f.q.toLowerCase(); evs=evs.filter(e=>(!f.stage||e.stage===f.stage)&&(!f.outcome||e.outcome===f.outcome)&&(!f.layer||(e.layer||'RECORDED')===f.layer)&&(!q||JSON.stringify(e).toLowerCase().includes(q)));
  const cols=['event_id','stage','outcome','authority','reason_code','rule_id','source_artifact','source_locator','evidence_refs','score','threshold','rank','eligible_count','budget','model_id','prompt_version','config_hash','registry_version','layer'];
  let h='<h2 class="vh">Trace table</h2><p class="small">'+(obj?'Events in the lineage of <code>'+esc(obj)+'</code>':'Events of '+(scopeOf(true)?'section '+esc(scopeOf(true)):'the whole run'))+' · '+evs.length+' shown (max 500). '+secSelect(true)+'</p>'+
   '<div class="whyform"><select id="ts" aria-label="Filter by stage"><option value="">stage</option>'+TR.stages.map(s=>'<option'+(f.stage===s?' selected':'')+'>'+s+'</option>').join('')+'</select> <select id="to" aria-label="Filter by outcome"><option value="">outcome</option>'+['accepted','corrected','rejected','merged','blocked','selected','not_selected','no_relation','emitted','not_recorded'].map(s=>'<option'+(f.outcome===s?' selected':'')+'>'+s+'</option>').join('')+'</select> <select id="tl" aria-label="Filter by layer"><option value="">layer</option>'+['RECORDED','REPLAYED','JOINED'].map(s=>'<option'+(f.layer===s?' selected':'')+'>'+s+'</option>').join('')+'</select> <input id="tq" type="search" aria-label="Search any field" placeholder="search any field" value="'+esc(f.q)+'"></div>';
  h+='<table class="t"><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>'+evs.slice(0,500).map(e=>'<tr>'+cols.map(c=>'<td>'+esc(c==='evidence_refs'?(e.evidence_refs||[]).map(r=>r.split('::')[1]).join(' | '):fmtv(e[c],c).replace(NOT_REC,'')) +'</td>').join('')+'</tr>').join('')+'</table>';
  el.innerHTML=h; wireSecSelect(el,()=>viewTrace(el),true);
  const upd=()=>{ TS.evFilter={stage:el.querySelector('#ts').value,outcome:el.querySelector('#to').value,layer:el.querySelector('#tl').value,q:el.querySelector('#tq').value}; viewTrace(el); };
  ['#ts','#to','#tl'].forEach(s=>el.querySelector(s).onchange=upd); el.querySelector('#tq').onchange=upd;
}

// ---------------------------------------------------------------- Journeys (Node / Edge) in the detail panel
function journeyHTML(oid, dbg){
  const j=TR.journeys[oid]; if(!j) return '<p class="na">No trace lineage is retained for this object ('+NOT_REC+').</p>';
  const evs=j.ev.map(i=>TR.events[i]); const by={}; evs.forEach(e=>{ (by[e.stage]=by[e.stage]||[]).push(e); });
  j.pairs.forEach(p=>{ const i=TR.pairIdx[p]; if(i!==undefined){ (by.pair_generation=by.pair_generation||[]).push(poolEv(i,'gen')); (by.pair_selection=by.pair_selection||[]).push(poolEv(i,'sel')); } });
  const present=RIBBON.filter(s=>by[s]||(s==='verifier'&&by.correction));
  let h='<div class="journey"><div class="small">Chronological journey, from retained or replayed trace data. '+evs.length+' events · '+j.nodes+' lineage objects.</div>';
  RIBBON.forEach(s=>{ const arr=by[s]; if(!arr||!arr.length){ h+='<div class="jst"><b>'+esc(STAGE_NAME[s])+'</b> <span class="na">'+(s==='verifier'?'verifier events attach to a text unit, not to this object (see the section walkthrough)':NOT_REC+' / not applicable to this object')+'</span></div>'; return; }
    const mention=arr.filter(e=>e.action==='mention_recorded'), rest=arr.filter(e=>e.action!=='mention_recorded'&&e.stage!=='source');
    const units=arr.filter(e=>e.stage==='source');
    if(units.length) h+='<div class="jst"><b>'+esc(STAGE_NAME[s])+'</b> <span class="small">'+esc(TR.stage_info[s]||'')+'</span><div class="evc"><div class="evh"><b>Text units</b> '+badge(units[0])+'</div>'+esc(units.length+' unit(s) of source text contributed (sections: '+[...new Set(units.map(u=>u.section_id))].join(", ")+').')+'</div></div>';
    if(units.length&&!rest.length&&!mention.length) return;
    if(s!=='source') h+='<div class="jst"><b>'+esc(STAGE_NAME[s])+'</b> <span class="small">'+esc(TR.stage_info[s]||'')+'</span>';
    if(mention.length) h+='<div class="evc"><div class="evh"><b>Mentions</b> '+badge(mention[0])+'</div>'+esc(mention.length+' mention(s) recorded; first: '+renderEv(mention[0]).text)+(dbg?'<details><summary>all mentions</summary>'+mention.map(e=>'<div class="small">'+esc(renderEv(e).text)+'</div>').join('')+'</details>':'')+'</div>';
    h+=rest.slice(0,3).map(e=>evCard(e,dbg)).join('');
    if(rest.length>3) h+='<details><summary>'+(rest.length-3)+' more '+esc(STAGE_NAME[s])+' event(s)</summary>'+rest.slice(3,60).map(e=>evCard(e,dbg)).join('')+'</details>';
    h+='</div>'; });
  if(j.evid.length) h+='<div class="jst"><b>Source evidence</b>'+j.evid.slice(0,6).map(([r,t])=>'<div class="sent">'+esc(t)+(dbg?'<div class="small"><code>'+esc(r)+'</code></div>':'')+'</div>').join('')+'</div>';
  const runGaps=TR.gaps.filter(g=>g.scope==='run'); if(runGaps.length) h+='<details><summary>Not recorded for this run ('+runGaps.length+')</summary><ul class="small">'+runGaps.map(g=>'<li>'+esc(g.stage+' · '+g.field+': '+g.detail)+'</li>').join('')+'</ul></details>';
  void present; return h+'</div>';
}
async function fillJourney(box){
  const slot=box.querySelector('#journey'); if(!slot) return;
  slot.innerHTML='<p class="na">Loading the trace…</p>';
  try{ await loadTrace(); }catch(e){ slot.innerHTML='<p class="na">The trace is not available in this browser.</p>'; return; }
  slot.innerHTML=journeyHTML(slot.dataset.oid, S.view==='debug'); wireLinks(slot);
  slot.querySelectorAll('a[data-copy]').forEach(a=>a.onclick=()=>{ try{navigator.clipboard.writeText(a.dataset.copy);}catch(e){} });
}
function journeySlot(oid){ return traceAvailable() ? '<h3 class="jh">'+(oid.startsWith('edge:')?'Edge journey':'Node journey')+' <span class="small">how we got here</span></h3><div id="journey" data-oid="'+esc(oid)+'"></div>'+(oid.startsWith('concept:')?'<p class="small"><a class="lnk" id="whyfrom" data-whya="'+esc(oid.slice(8))+'">Why not a relation from this concept to another?</a></p>':''):''; }
