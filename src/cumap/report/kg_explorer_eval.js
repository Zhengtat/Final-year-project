// ====================================================================================================================
// CR-013 STOP 4: EVALUATION OVERLAY (CR-012 frozen outputs). Everything here is evaluation material derived from the frozen
// benchmark gold and the retained E0 predictions. It is loaded only when the user explicitly opens the evaluation mode, from its
// own payload, and is never reachable from the production P&D views. Codes are observations of where a benchmark object was
// lost in the frozen run; they are not decision rules for the production pipeline.
// ====================================================================================================================
const EV_TABS = [['evscore','Scorecard'],['evmap','Where it goes wrong'],['evlist','Answer-key relations']];
const EV_PANES = ['evscore','evmap','evlist'];
const EV_COL = {N0:'#C23B3B',N1:'#D55E00',C0:'#B8A400',C1:'#2E8B8B',P0:'#E69F00',R0:'#56B4E9',R1:'#0072B2',R2:'#8C4FD8',R3:'#7A7A7A',E0:'#A0522D',recovered:'#009E73'};
const EV_SHORT = {N0:'a concept was never found',N1:'a concept was found with the wrong words',C0:'one concept split in two',C1:'two concepts wrongly merged',P0:'the pair was never sent to the model',R0:'the model said “no relation”',R1:'wrong kind of relation',R2:'wrong direction',R3:'wrong type or condition',E0:'the quote failed the check'};
const METRIC_PLAIN = {concept_f1:'Does it find the right concepts?',ancestor_hierarchy_f1:'Does it put concepts under the right broader ones (“X is a kind of Y”)?',pair_recall:'Of the concept pairs that should be linked, how many reached the relation step?',relation_macro_f1:'When it looks at a correct pair, does it pick the right kind of relation? (averaged over relation kinds)',strict_e2e_edge_f1:'Overall: does a fully correct relation end up in the graph? (the strictest score)'};
const STATUS_PLAIN = {NOT_EVALUABLE:'cannot be measured here',NOT_COMPUTED:'not calculated'};
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
const SET_PLAIN = {pd_heldout:'P&D dataset · test sections (main result)',pd_pilot:'P&D dataset · practice sections (development)',scinlp:'SciNLP dataset · 3 test papers'};
const SET_OF_DS = {pd:'pd_heldout',scinlp:'scinlp'}, DS_OF_SET = {pd_heldout:'pd',scinlp:'scinlp'};
function evEnter(){
  ES.ds=DS_OF_SET[SCS.set]||ES.ds;
  S.mode='ev'; S.sel=null; S.tab='evscore'; S.G=null; S.doc=null;
  chrome(); banner(); evSide(); tabs(); showTab('evscore'); renderDetail(true); hashWrite();
}
function evBanner(){
  const names={scinlp:'SciNLP dataset: test papers',pd:(S.tab==='evscore'&&SCS.set==='pd_pilot')?'P&D dataset: practice sections (development)':'P&D dataset: test sections (not the chapters 1–3 graph)'};
  $('banner').innerHTML='<div class="banner warn"><b>How well it scores</b> — the system\'s output compared with a human answer key (also called “gold”). Showing: <b>'+esc(names[ES.ds])+'</b>. These are test results only, not the main graph.'+
   '<details><summary>More about these results</summary>The results come from one frozen test run (CR-012, the system as-is, level E0). For each answer-key relation the system missed, a code shows the first step where it was lost. The codes describe what happened in that test run; they are not rules the system follows.</details></div>';
}
function evSide(){
  const s=$('side'); const ds=[['scinlp','SciNLP dataset (test papers)'],['pd','P&D dataset (test sections)']];
  s.innerHTML='<h3>Dataset <span class="small" style="font-weight:400">· results are never combined</span></h3><div class="tour">'+ds.map(([k,l])=>'<button data-ds="'+k+'" class="'+(ES.ds===k?'on':'')+'">'+esc(l)+'</button>').join('')+'</div>'+
   '<div class="card" style="margin-top:12px"><h4>What this is</h4><span class="small" title="git tag cr012-stop4-complete">Saved results from an earlier test run: what the system produced, the human answer key, and where each missed relation was first lost. Nothing here was re-run or re-scored.</span></div>'+
   '<div class="card"><h4>Reading the codes</h4><span class="small">Each missed relation gets one code: the <b>first</b> step where it was lost. Later steps are not checked.<br><b>N</b> = finding concepts · <b>C</b> = merging names · <b>P</b> = choosing pairs · <b>R</b> = picking the relation · <b>E</b> = checking the evidence.</span></div>'+
   '<button id="ev-back" style="margin-top:6px">← Back to the P&amp;D graph</button>';
  s.querySelectorAll('button[data-ds]').forEach(b=>b.onclick=()=>{ ES.ds=b.dataset.ds; SCS.set=SET_OF_DS[ES.ds]; ES.code=''; ES.unit=''; ES.sel=null; ES.status='all'; ES.q=''; evBanner(); evSide(); showTab(S.tab); renderDetail(true); });
  s.querySelector('#ev-back').onclick=()=>{ ES.sel=null; setMode('pd'); };
}

// ---------------------------------------------------------------- tabs
async function renderEvalTab(k){
  const el=$('v-'+k); if(!el) return;
  el.innerHTML='<p class="na">Loading…</p>';
  try{ await loadEval(); }catch(e){ el.innerHTML='<p class="na">The overlay could not be loaded in this browser ('+esc(e&&e.message||e)+').</p>'; return; }
  if(k==='evscore'){ await renderScorecard(el); return; }
  (k==='evmap'?viewEvMap:viewEvList)(el);
}
function codeChip(c){ return c? '<span class="chip" style="border-left:4px solid '+EV_COL[c]+'" title="'+esc(EV.codes[c]||'')+'">'+esc(c)+'</span>' : '<span class="chip" style="border-left:4px solid '+EV_COL.recovered+'" title="no node-level loss">not lost</span>'; }
function viewEvMap(el){
  const d=evds(), h=d.headline; const miss=d.frozen_attribution.misses, rec=d.frozen_attribution.recovered, by=d.frozen_attribution.by_code;
  let o='<h2 class="vh">Where it goes wrong <span class="chip">EVALUATION</span></h2><p class="lede">For every relation in the human answer key, the first step where the system lost it.</p>';
  o+='<div class="card"><b>'+esc(d.label)+'</b><div class="big"><div><b>'+h.f1.toFixed(3)+'</b>'+esc(h.metric)+'</div><div><b>'+h.precision.toFixed(3)+'</b>precision</div><div><b>'+h.recall.toFixed(3)+'</b>recall</div></div><div class="small">'+ciPlain(h.ci_status)+(h.ci?' Rough range: '+h.ci[0].toFixed(3)+' – '+h.ci[1].toFixed(3)+' (from '+d.units.length+' sections).':'')+(ES.ds==='pd'?' '+esc(EV.meta.single_annotator):' '+d.units.length+' papers.')+'</div></div>';
  o+='<h3 class="jh">Where answer-key relations were lost</h3><p class="small">'+(miss+rec)+' relations in the answer key: <b>'+miss+'</b> lost at some step, <b>'+rec+'</b> never lost at the concept level. '+esc(d.not_applicable_note)+'</p>';
  o+='<div class="bar" style="height:18px">'+EV.code_order.filter(c=>by[c]).map(c=>'<span title="'+esc(c)+' '+by[c]+'" style="width:'+(100*by[c]/miss)+'%;background:'+EV_COL[c]+'"></span>').join('')+'</div>';
  o+='<div class="leg" style="margin-bottom:8px">'+EV.code_order.filter(c=>by[c]).map(c=>'<span><i style="background:'+EV_COL[c]+'"></i>'+esc(c)+' '+esc(EV_SHORT[c])+' · <b>'+by[c]+'</b> ('+pct(by[c],miss)+')</span>').join('')+'</div>';
  o+='<table class="t evmatrix"><tr><th>'+esc(d.unit_word)+'</th><th title="relations in the answer key">answer key</th>'+EV.code_order.map(c=>'<th title="'+esc(EV_SHORT[c])+'">'+c+'</th>').join('')+'<th title="never lost at the concept level">not lost</th><th title="relation score">F1</th></tr>';
  d.units.forEach(u=>{ const mx=Math.max(1,...Object.values(u.counts)); o+='<tr><td><a class="lnk" data-unit="'+esc(u.id)+'">'+esc(u.title)+'</a></td><td>'+u.gold_n+'</td>'+EV.code_order.map(c=>{ const n=u.counts[c]; return n?'<td class="evcell" data-code="'+c+'" data-unit="'+esc(u.id)+'" style="background:linear-gradient(90deg,'+EV_COL[c]+'66 '+(100*n/mx)+'%,transparent 0)">'+n+'</td>':'<td class="evzero">'+(d.not_applicable.includes(c)?'n/a':'·')+'</td>'; }).join('')+'<td class="evcell" data-code="none" data-unit="'+esc(u.id)+'">'+u.recovered+'</td><td>'+u.f1.toFixed(3)+'</td></tr>'; });
  o+='</table><p class="small">Hover a code for its meaning. Click a number to list those relations, or a name to list all of its relations.</p>';
  o+='<h3 class="jh">What each code means, with an example</h3><table class="t"><tr><th>code</th><th>meaning</th><th>count</th><th>example</th></tr>'+EV.code_order.map(c=>{ const ex=firstExample(c); return '<tr><td>'+codeChip(c)+'</td><td>'+esc(EV.codes[c])+'</td><td>'+by[c]+'</td><td>'+(ex?'<a class="lnk" data-ex="'+ex[0]+'|'+ex[1]+'">'+esc(clip(ex[2].src,24))+' → '+esc(clip(ex[2].tgt,24))+'</a>':'<span class="na">'+(d.not_applicable.includes(c)?'not applicable here':'none in this dataset')+'</span>')+'</td></tr>'; }).join('')+'</table>';
  o+='<h3 class="jh">With help at each step <span class="small">(E0 – E4, see the Scorecard tab)</span></h3><p class="small">'+Object.entries(d.ladder).map(([k,v])=>'<b>'+esc(k)+'</b> '+v.toFixed(3)).join(' · ')+'<br>E0 is the system on its own (the main score). E1–E4 hand it the correct answer for one more step each, to show how much each step costs. '+esc(EV.meta.oracle_note)+'</p>';
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
  let o='<h2 class="vh">Answer-key relations <span class="chip">EVALUATION</span></h2><div class="whyform"><label class="small">'+esc(d.unit_word)+' <select id="evu"><option value="">all</option>'+d.units.map(u=>'<option value="'+esc(u.id)+'"'+(ES.unit===u.id?' selected':'')+'>'+esc(u.title)+' ('+u.gold_n+')</option>').join('')+'</select></label>'+
   '<label class="small">result <select id="evs"><option value="all">all</option><option value="strict"'+(ES.status==='strict'?' selected':'')+'>found exactly</option><option value="missed"'+(ES.status==='missed'?' selected':'')+'>not found exactly</option></select></label><input id="evq" type="search" aria-label="Search the answer key" placeholder="search concepts or relation" value="'+esc(ES.q)+'"></div>';
  o+='<div class="leg" style="margin:6px 0">'+chips.map(c=>'<button class="evchip'+(ES.code===c?' on':'')+'" data-c="'+c+'">'+(c===''?'all codes':c==='none'?'not lost':esc(c)+' '+esc(EV_SHORT[c]))+'</button>').join(' ')+'</div>';
  o+='<p class="small">'+rows.length+' relation(s). Click a row to see where it was lost.</p>';
  o+='<table class="t"><tr><th>'+esc(d.unit_word)+'</th><th>answer-key relation</th><th>first lost at</th><th>found exactly</th></tr>'+rows.slice(0,ES.more?2000:150).map(({u,r})=>'<tr data-u="'+esc(u.id)+'" data-i="'+r.i+'" class="'+(ES.sel&&ES.sel.u===u.id&&ES.sel.i===r.i?'sel':'')+'"><td>'+esc(u.title)+'</td><td>'+esc(clip(r.src,40))+' <span class="small">'+esc(r.rel)+(r.sym?' ⟷':' →')+'</span> '+esc(clip(r.tgt,40))+'</td><td>'+codeChip(r.code)+'</td><td>'+(r.strict?'yes':'no')+'</td></tr>').join('')+'</table>'+(rows.length>150&&!ES.more?'<button id="evmore">show all '+rows.length+'</button>':'');
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
  if(!EV||!ES.sel) return '<p class="na">Choose a relation in the Answer-key relations list (or an example in Where it goes wrong) to see where it was lost.</p>'+(EV?'<div class="card small">'+esc(EV.meta.notice)+'</div>':'');
  const d=evds(), u=d.units.find(x=>x.id===ES.sel.u), r=u.relations[ES.sel.i]; if(!r) return '';
  const dec=r.code?EV.decisive[r.code]:null;
  let h='<h2>'+esc(r.src)+' <span style="color:var(--ink2)">— '+esc(r.rel)+(r.sym?' ⟷':' →')+'</span> '+esc(r.tgt)+'</h2><span class="chip" title="gold">answer key</span> <span class="chip auth auth-UNKNOWN" title="from the human answer key and the frozen CR-012 test run">EVALUATION · frozen</span> '+(r.strict?'<span class="chip">found exactly</span>':'<span class="chip">not found exactly</span>');
  h+='<dl><dt>Sentence'+(ES.ds==='pd'?' (chosen by the human annotator)':'')+'</dt><dd><div class="sent">'+(r.sentence?highlight(r.sentence,null,{name:r.src,aliases:[]},{name:r.tgt,aliases:[]}):'<span class="na">'+NA+'</span>')+'</div><span class="small"><mark class="a" style="padding:0 4px">first concept</mark> <mark class="b" style="padding:0 4px">second concept</mark></span></dd>';
  h+='<dt>Where it was first lost <span class="small">(earliest failure)</span></dt><dd>'+codeChip(r.code)+' <b>'+esc(r.code?EV_SHORT[r.code]:'')+'</b><div class="small" style="margin-top:4px">'+esc(r.code?EV.codes[r.code]:'Never lost at the concept level: the checks below all passed.'+(r.strict?'':' It still does not match the exact words in the answer key, so the strict score does not count it as found.'))+'</div></dd>';
  h+='<dt>Step-by-step checks (stop at the first failure)</dt><dd><ol class="checks">'+r.checks.map(([id,ans],k)=>{ const label=(EV.checks.find(c=>c[0]===id)||[0,id])[1]; const after=dec!==null&&k>dec; const bad=dec!==null&&k===dec; return '<li class="'+(bad?'evbad':'')+(after?' evafter':'')+'"><span class="ans">'+esc(after?'—':ans)+'</span> '+esc(label)+(bad?' <b>← first failure</b>':'')+(after?' <span class="small">(not evaluated)</span>':'')+'</li>'; }).join('')+'</ol></dd>';
  h+='<dt>What the system had for these two concepts</dt><dd class="small">Concepts it found at these words: '+(r.end_nodes.length?r.end_nodes.map(x=>'<span class="chip">'+esc(x)+'</span>').join(''):'<span class="na">none</span>')+'<br>Relations it found between them: '+(r.pred_rels.length?r.pred_rels.map(x=>'<span class="chip">'+esc(x)+'</span>').join(''):'<span class="na">none</span>')+'</dd>';
  h+='<dt>Pair choice in this '+esc(d.unit_word)+'</dt><dd class="small">'+u.selection.eligible_pool+' possible pairs, '+u.selection.selected+' chosen (room for '+u.selection.budget+'). Only the counts were saved; the list of pairs is '+NA+' for this run.</dd>';
  if(r.graph_edge) h+='<dt>Graph</dt><dd><button id="ev-opengraph" data-e="'+esc(r.graph_edge)+'" data-d="'+esc(u.id)+'">Open in the SciNLP graph</button></dd>';
  h+='</dl><p class="small">'+esc(EV.meta.notice)+'</p>';
  return h;
}
function wireEvDetail(box){
  const b=box.querySelector('#ev-opengraph'); if(b) b.onclick=()=>{ const doc=DATA.sci.docs.find(x=>x.doc_id===b.dataset.d); setMode('sci',doc); S.F.missed=true; side(); const e=S.G.edges.find(x=>x.id===b.dataset.e); if(e) selectEdge(e); draw(); };
}

// ====================================================================================================================
// CR-017 STOP 5: SCORECARD. HEADLINE (five metrics) / DIAGNOSTICS (expandable) / AUDIT (pointer) / ORGANISATION (separate, not accuracy).
// Rendered from its own payload (reports/cr017/*.json via cumap.cr017.scorecard); no number is computed in the page.
// ====================================================================================================================
let SC = null;
const SCS = {set:'pd_heldout', level:'E0', variant:'frozen'};
async function loadScorecard(){
  if(SC) return SC;
  const raw=(($('scorecard-gz')||{}).textContent||'').trim(); if(raw.length<10) return null;
  const bin=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));
  const stream=new Blob([bin]).stream().pipeThrough(new DecompressionStream('gzip'));
  SC=JSON.parse(await new Response(stream).text()); return SC;
}
const n3 = v => v==null? '—' : v.toFixed(3);
function scCard(c){
  const val = c.value==null? '<b class="na" style="font-size:15px">'+esc(STATUS_PLAIN[c.status]||c.status)+'</b><span class="tier">'+esc(c.status)+'</span>' : '<b>'+n3(c.value)+'</b>';
  const pr = c.key==='pair_recall' ? (c.value==null?'':'<div class="small">a share (recall only), not an F1</div>')
    : (c.precision==null&&c.recall==null) ? '' : '<div class="small">precision <b>'+n3(c.precision)+'</b> · recall <b>'+n3(c.recall)+'</b>'+(c.key==='relation_macro_f1'?' <span class="gl" title="mean of per-class precision / recall over relation kinds with answer-key examples; a kind with no predictions counts as precision 0">(averaged)</span>':'')+'</div>';
  const ci = c.ci95? '<div class="small" title="descriptive section-bootstrap interval">rough range '+n3(c.ci95[0])+' – '+n3(c.ci95[1])+' †</div>' : '';
  const cnt = c.tp!=null ? c.tp+' right · '+c.fp+' wrong · '+c.fn+' missed' : c.reached!=null ? c.reached+' of '+c.denominator+' pairs' : '';
  const warn = c.key==='relation_macro_f1' && c.low_support_classes.length ? '<div class="small" style="color:var(--warn)" title="low support">⚠ '+c.low_support_classes.length+' of '+c.n_classes+' relation kinds have 3 or fewer examples, so this score is shaky</div>' : '';
  const an = c.analogue? '<div class="small" title="mention-level analogue">measured on the exact words (mention-level analogue)</div>' : '';
  const why = c.reason? '<div class="small" style="word-break:break-word">'+esc(c.reason)+'</div>' : '';
  return '<div class="card sccard" data-metric="'+esc(c.key)+'" style="flex:1 1 210px;max-width:260px"><div style="font-weight:600;font-size:13px">'+esc(c.label)+'</div><div class="mdesc">'+esc(METRIC_PLAIN[c.key]||'')+'</div><div class="big"><div>'+val+'</div></div>'+pr+ci+(cnt?'<div class="small" title="'+esc(c.counts)+'">'+esc(cnt)+'</div>':'')+warn+an+why+'</div>';
}
async function renderScorecard(el){
  const P=await loadScorecard();
  if(!P){ el.innerHTML='<p class="na">The scorecard payload is not present in this build (run <code>cumap.cr017.replay</code> first).</p>'; return; }
  const d=P.datasets[SCS.set]; const V19=(SCS.variant==='cr019'&&P.cr019)?P.cr019.datasets[SCS.set]||null:null; const LV=V19||d.levels;
  if(!LV[SCS.level]) SCS.level=Object.keys(LV)[0]; const L=LV[SCS.level];
  let o='<h2 class="vh">Scorecard <span class="chip">EVALUATION</span> <span class="tier">scorer '+esc(P.meta.scorer_version)+'</span></h2><p class="lede">Five scores, each from 0 (none right) to 1 (perfect). Most are <b>F1</b> scores, which balance <b>precision</b> (how many of its answers are right) and <b>recall</b> (how many of the right answers it found). Pick a dataset and a level below.</p>';
  if(P.cr019) o+='<div class="small" style="margin-bottom:4px">Scoring</div><div class="tour" style="margin-bottom:10px;flex-direction:row;flex-wrap:wrap">'+[['frozen','Frozen (CR-017)'],['cr019','Grounding-consistent (CR-019)']].map(([k,l])=>'<button data-sc-var="'+k+'" class="'+(k===SCS.variant?'on':'')+'">'+l+'</button>').join('')+'</div>';
  o+='<div class="small" style="margin-bottom:4px">Dataset</div><div class="tour" style="margin-bottom:10px;flex-direction:row;flex-wrap:wrap">'+Object.entries(P.datasets).map(([k,v])=>'<button data-sc-set="'+k+'" title="'+esc(v.label)+'" class="'+(k===SCS.set?'on':'')+'">'+esc(SET_PLAIN[k]||v.label)+'</button>').join('')+'</div>';
  o+='<div class="small" style="margin-bottom:4px">Level <span class="gl" title="E0 is the system on its own; E1–E4 give it the correct answer for one more step each">(E0 = the real system)</span></div><div class="tour" style="margin-bottom:10px;flex-direction:row;flex-wrap:wrap">'+Object.keys(LV).map(k=>'<button data-sc-level="'+k+'" class="'+(k===SCS.level?'on':'')+'">'+k+'</button>').join('')+'</div>';
  if(d.note) o+='<div class="banner warn">'+esc(d.note)+'</div>';
  if(V19) o+='<div class="banner">'+esc(P.cr019.note)+'</div>';
  o+='<h3 class="jh">Main scores <span class="tier">HEADLINE</span> <span class="small" style="font-weight:400">· five scores, never added up into one (no composite score)</span></h3><div class="scgrid" style="display:flex;flex-wrap:wrap;gap:10px">'+L.headline.map(scCard).join('')+'</div>';
  if(V19&&P.cr019.stage_b){ const sb=P.cr019.stage_b, rc=sb.recommendation;
    o+='<h3 class="jh">Stage B: showing the classifier more sentences <span class="tier">DEVELOPMENT DATA</span></h3><p class="small">'+esc(sb.note)+' Spend $'+sb.spend_usd.toFixed(2)+' of the $'+sb.cap_usd.toFixed(0)+' cap.</p>'+
      '<div class="banner'+(rc.status==='RECOMMEND_MULTI'?'':' warn')+'"><b>'+(rc.status==='RECOMMEND_MULTI'?'Recommended: show the classifier several sentences (MULTI)':rc.status==='KEEP_SINGLE'?'Keep the current single-sentence classifier (SINGLE)':'Stage B incomplete')+'</b>'+(rc.scinlp_dev_idx_p1_f1_delta!=null?' · SciNLP dev F1 change '+(rc.scinlp_dev_idx_p1_f1_delta>=0?'+':'')+rc.scinlp_dev_idx_p1_f1_delta.toFixed(3)+' · P&amp;D dev strict F1 change '+(rc.pd_dev_strict_f1_delta>=0?'+':'')+rc.pd_dev_strict_f1_delta.toFixed(3):'')+'<div class="small">'+esc(rc.rule||'')+'</div></div>'+
      '<table class="t" style="margin-top:8px"><tr><th>dataset</th><th>measure</th><th>arm</th><th>precision</th><th>recall</th><th>F1</th></tr>'+sb.rows.map(r=>'<tr><td>'+esc(r.dataset)+'</td><td>'+esc(r.measure)+'</td><td>'+esc(r.arm)+'</td><td>'+n3(r.precision)+'</td><td>'+n3(r.recall)+'</td><td><b>'+n3(r.f1)+'</b></td></tr>').join('')+'</table>'; }
  if(V19&&P.cr019.cr020){ const c=P.cr019.cr020, dc=c.decision;
    o+='<h3 class="jh">CR-020: matching spelling variants <span class="tier">DEVELOPMENT DATA</span></h3><p class="small">'+esc(c.note)+' Spend $'+c.spend_usd.toFixed(2)+'.</p>'+
      '<div class="banner'+(dc.status==='ADOPT_R1KEY'?'':' warn')+'"><b>'+(dc.status==='ADOPT_R1KEY'?'Adopted: production matches spelling variants (R1KEY)':'Kept whole-word matching (TOKEN)')+'</b> · SciNLP dev F1 change '+(dc.scinlp_dev_idxr1_p1_f1_delta>=0?'+':'')+dc.scinlp_dev_idxr1_p1_f1_delta.toFixed(3)+' · P&amp;D dev strict F1 change '+(dc.pd_dev_strict_f1_delta>=0?'+':'')+dc.pd_dev_strict_f1_delta.toFixed(3)+'<div class="small">'+esc(dc.rule)+'</div></div>'+
      '<table class="t" style="margin-top:8px"><tr><th>dataset</th><th>measure</th><th>arm</th><th>precision</th><th>recall</th><th>F1</th></tr>'+c.rows.map(r=>'<tr><td>'+esc(r.dataset)+'</td><td>'+esc(r.measure)+'</td><td>'+esc(r.arm)+'</td><td>'+n3(r.precision)+'</td><td>'+n3(r.recall)+'</td><td><b>'+n3(r.f1)+'</b></td></tr>').join('')+'</table>'; }
  o+='<p class="small">† A rough range from resampling the test sections; with fewer than 10 sections it is only a guide. Tested on: '+esc(L.sections.join(', '))+'.</p>';
  o+='<details class="scdiag" open><summary>What do the levels E0 – E4 mean?</summary><table class="t"><tr><th>level</th><th>meaning</th></tr>'+
    '<tr><td><b>E0</b></td><td>The real system on its own: it finds concepts, merges duplicate names, chooses pairs and decides relations by itself. <b>This is the main score.</b></td></tr>'+
    '<tr><td><b>E1</b></td><td>The system is given the correct concepts from the answer key, so finding concepts cannot go wrong.</td></tr>'+
    '<tr><td><b>E2</b></td><td>As E1, and it is also told which names mean the same concept, so merging cannot go wrong. P&amp;D only: SciNLP has no such information.</td></tr>'+
    '<tr><td><b>E3</b></td><td>Every pair that should be linked is sent to the relation step (without saying which relation), so choosing pairs cannot go wrong. On SciNLP this is called E3-M.</td></tr>'+
    '<tr><td><b>E4</b></td><td>Only the correct pairs are given; the model still picks the relation and direction itself. This is the best the relation step can do. On SciNLP this is called E4-M.</td></tr></table>'+
    '<p class="small">Comparing E0 with E1–E4 shows which step loses the most (finding concepts → merging names → choosing pairs → picking the relation). These are test settings, not separate systems, and the gaps do not simply add up.</p></details>';
  const dg=L.diagnostics||{};
  o+='<h3 class="jh">More detail <span class="tier">DIAGNOSTICS</span> <span class="small" style="font-weight:400">· breakdowns behind the main scores</span></h3>';
  if(dg.relation_classes&&dg.relation_classes.length){
    o+='<details class="scdiag"><summary>Relation score by kind of relation</summary><table class="t"><tr><th>relation</th><th title="support: examples in the answer key">examples</th><th title="true positives">right</th><th title="false positives">wrong</th><th title="false negatives">missed</th><th>F1</th><th></th></tr>'+dg.relation_classes.map(r=>'<tr><td>'+esc(r.relation)+'</td><td>'+r.support+'</td><td>'+r.tp+'</td><td>'+r.fp+'</td><td>'+r.fn+'</td><td>'+n3(r.f1)+'</td><td>'+(!r.support?'<span title="excluded (no gold)">not scored: no examples</span>':(r.low_support?'<span title="low support">⚠ few examples</span>':''))+'</td></tr>').join('')+'</table>'+
      (dg.relation_micro?'<p class="small">All kinds pooled (micro) precision / recall / F1: '+n3(dg.relation_micro.precision)+' / '+n3(dg.relation_micro.recall)+' / '+n3(dg.relation_micro.f1)+' · direction right (when the relation was right): '+n3(dg.direction_accuracy)+'</p>':'')+'</details>';
  }
  if(dg.per_section&&Object.keys(dg.per_section).length){
    o+='<details class="scdiag"><summary>Scores for each test section</summary><table class="t"><tr><th>section</th><th>concepts (F1)</th><th>hierarchy (F1)</th><th>pairs reached</th><th>strict relations (F1)</th></tr>'+Object.entries(dg.per_section).map(([s,v])=>'<tr><td>'+esc(s)+'</td><td>'+n3(v.concept_f1)+'</td><td>'+(v.hierarchy_f1==null?'—':n3(v.hierarchy_f1))+'</td><td>'+(v.pair_recall?v.pair_recall[0]+' / '+v.pair_recall[1]:'—')+'</td><td>'+n3(v.strict_f1)+'</td></tr>').join('')+'</table></details>';
  }
  if(dg.direct_parent_f1) o+='<details class="scdiag"><summary>Hierarchy: direct parent only</summary><p class="small">'+dg.direct_parent_f1.tp+' right · '+dg.direct_parent_f1.fp+' wrong · '+dg.direct_parent_f1.fn+' missed → F1 '+n3(dg.direct_parent_f1.f1)+'</p></details>';
  o+='<p class="small">'+esc(P.meta.legacy_note)+'</p>';
  o+='<h3 class="jh">Check the details <span class="tier">AUDIT</span></h3><p class="small">To see individual examples, open <a class="lnk" id="sc-to-map">Where it goes wrong</a> or <a class="lnk" id="sc-to-list">Answer-key relations</a>. Sources and file hashes are in <code>reports/cr017/diagnostics.json</code> and <code>historical_replay.md</code>.</p>';
  const og=P.organisation;
  o+='<div class="card scorg" style="border-style:dashed"><h3 class="jh" style="margin-top:0">'+esc(og.title)+'</h3><p class="small">'+esc(og.note)+'</p><ul class="small">'+og.items.map(i=>'<li>'+esc(i)+'</li>').join('')+'</ul><p class="small">To see these, open the P&amp;D graph and choose the Rings layout. They are not scored here.</p></div>';
  el.innerHTML=o;
  el.querySelectorAll('button[data-sc-set]').forEach(b=>b.onclick=()=>{ SCS.set=b.dataset.scSet; if(S.mode==='ev'){ if(DS_OF_SET[SCS.set]){ ES.ds=DS_OF_SET[SCS.set]; ES.code=''; ES.unit=''; ES.sel=null; evSide(); } evBanner(); } renderScorecard(el); });
  el.querySelectorAll('button[data-sc-var]').forEach(b=>b.onclick=()=>{ SCS.variant=b.dataset.scVar; renderScorecard(el); });
  el.querySelectorAll('button[data-sc-level]').forEach(b=>b.onclick=()=>{ SCS.level=b.dataset.scLevel; renderScorecard(el); });
  const m=el.querySelector('#sc-to-map'); if(m) m.onclick=()=>showTab('evmap'); const l=el.querySelector('#sc-to-list'); if(l) l.onclick=()=>showTab('evlist');
}
