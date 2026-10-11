// CR-013 explorer harness: runs the generated KG explorer page's script in Node against a stubbed DOM and prints a JSON report.
// usage: node explorer_harness.js <index.html> <pairs.json> <out.json>
const fs = require('fs'), vm = require('vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const pairs = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const scripts = [...html.matchAll(/<script(?: type="application\/octet-stream" id="(?:trace|eval)-gz")?>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const traceB64 = scripts[0], evalB64 = scripts[1], main = scripts[2];
const els = {};
function El(id) {
  const o = { id, innerHTML: '', textContent: '', style: {}, dataset: {}, checked: true, value: '', className: '', classList: { toggle() {}, add() {}, remove() {} },
    getBoundingClientRect() { return { width: 1000, height: 700, left: 0, top: 0, right: 1000, bottom: 700 }; },
    getContext() { return new Proxy({}, { get: (t, k) => (k === 'measureText' ? () => ({ width: 5 }) : () => {}), set: () => true }); },
    addEventListener() {}, querySelectorAll() { return []; }, querySelector() { return El('q'); }, closest() { return null; }, setPointerCapture() {}, focus() {}, appendChild() {} };
  return o;
}
global.document = { body: { className: '' }, getElementById: id => els[id] || (els[id] = El(id)), querySelectorAll: () => [] };
els['trace-gz'] = El('trace-gz'); els['trace-gz'].textContent = traceB64;
els['eval-gz'] = El('eval-gz'); els['eval-gz'].textContent = evalB64;
global.window = global; global.devicePixelRatio = 1; global.addEventListener = () => {};
global.matchMedia = () => ({ matches: false }); global.requestAnimationFrame = f => setTimeout(() => f(performance.now()), 0); global.cancelAnimationFrame = () => {};
global.location = { hash: '' }; global.history = { replaceState() {} };
vm.runInThisContext(main);
(async () => {
  const out = { errors: [] };
  await loadTrace();
  out.texts = {};
  TR.events.forEach(e => { out.texts[e.event_id] = renderEv(e).text; });
  TR.pool.forEach((_, i) => { ['gen', 'sel'].forEach(k => { const e = poolEv(i, k); out.texts[e.event_id] = renderEv(e).text; }); });
  out.why = pairs.map(([a, b]) => { const w = whyAnswer(a, b); return { a, b, code: w.code, status: w.status, sentences: w.sentences, checks: w.checks.map(c => [c.id, c.answer]) }; });
  // UI smoke
  const ui = {};
  for (const view of ['review', 'debug']) {
    setView(view);
    for (const sid of ['3.3', '1.2', '2.6']) {
      TS.section = sid; TS.sectionAll = false;
      for (const k of ['pipeline', 'section', 'why', 'lost', 'snap'].concat(view === 'debug' ? ['trace'] : [])) {
        try { await renderTraceTab(k); ui[`${view}|${sid}|${k}`] = ($('v-' + k).innerHTML || '').length; } catch (e) { out.errors.push(`${view}|${sid}|${k}: ${e.message}`); }
      }
      for (let st = 0; st < STEPS.length; st++) { TS.step = st; try { await renderTraceTab('section'); } catch (e) { out.errors.push(`step ${st} ${sid}: ${e.message}`); } }
      for (const st of RIBBON) { TS.stage = st; try { await renderTraceTab('pipeline'); } catch (e) { out.errors.push(`stage ${st}: ${e.message}`); } }
    }
    TS.sectionAll = true; try { await renderTraceTab('pipeline'); await renderTraceTab('lost'); } catch (e) { out.errors.push('all scope: ' + e.message); }
    // journeys
    const edge = TR.final_edges.find(e => e.startsWith('RP-')); const node = TR.final_concepts[0];
    out['journey_edge_' + view] = journeyHTML('edge:' + edge, view === 'debug');
    out['journey_node_' + view] = journeyHTML('concept:' + node, view === 'debug');
    S.mode === 'pd' && selectNode(node); const eobj = S.G.edges.find(x => x.id === edge); selectEdge(eobj);
  }
  setMode('sci'); out.sci_tabs = $('tabs').innerHTML; out.sci_trace_available = traceAvailable(); setMode('pd'); out.pd_tabs_after = $('tabs').innerHTML;
  // ---- evaluation overlay: opt-in, dataset-scoped, separate payload
  out.ev_null_before_opt_in = (EV === null);
  const prodPanes = ['v-pipeline', 'v-section', 'v-why', 'v-lost', 'v-snap', 'v-trace', 'detailin', 'banner', 'side'];
  out.prod_text_has_eval = /EVALUATION|frozen CR-012|\bgold\b/i.test(prodPanes.map(k => $(k).innerHTML || '').join(' '));
  setView('review'); setMode('ev');
  out.ev = {};
  for (const ds of ['scinlp', 'pd']) {
    ES.ds = ds; ES.code = ''; ES.unit = ''; ES.status = 'all'; ES.q = ''; ES.sel = null; ES.more = true;
    await renderEvalTab('evmap'); await renderEvalTab('evlist');
    const d = EV.datasets[ds]; const first = d.units[0]; const rel = first.relations.find(r => r.code === 'P0') || first.relations[0];
    evSelect(first.id, rel.i);
    const rowsAll = d.units.flatMap(u => u.relations.filter(relMatches)).length;
    ES.code = 'P0'; const rowsP0 = d.units.flatMap(u => u.relations.filter(relMatches)).length;
    const dets = {}; for (const c of EV.code_order) { const x = d.units.flatMap(u => u.relations).find(r => r.code === c); if (x) { ES.sel = { u: x.unit, i: x.i }; dets[c] = evDetailHTML(); } }
    out.ev[ds] = { map: ($('v-evmap').innerHTML || '').length, list: ($('v-evlist').innerHTML || '').length, rows_all: rowsAll, rows_p0: rowsP0, units: d.units.map(u => u.id), unit_ids_of_relations_match: d.units.every(u => u.relations.every(r => r.unit === u.id)), details: dets, tabs: ($('tabs').innerHTML || '') };
  }
  out.ev_pooled = {}; for (const ds of ['scinlp', 'pd']) { const t = {}; EV.datasets[ds].units.forEach(u => Object.entries(u.counts).forEach(([c, n]) => { t[c] = (t[c] || 0) + n; })); out.ev_pooled[ds] = t; }
  setView('debug'); try { await renderEvalTab('evmap'); out.ev_debug_ok = true; } catch (e) { out.errors.push('ev debug: ' + e.message); }
  setView('review'); setMode('pd');
  out.after_leaving_has_eval = /EVALUATION|frozen CR-012/i.test(($('banner').innerHTML || '') + ($('detailin').innerHTML || '') + ($('tabs').innerHTML || ''));
  out.ui = ui; out.counts = { events: TR.events.length, pool: TR.pool.length, sections: TR.secList.length, journeys: Object.keys(TR.journeys).length, why: Object.keys(TR.why).length };
  out.tabs = { review: ($('tabs').innerHTML || '').length };
  fs.writeFileSync(process.argv[4], JSON.stringify(out));
  process.exit(0);
})().catch(e => { fs.writeFileSync(process.argv[4], JSON.stringify({ fatal: String(e && e.stack || e) })); process.exit(1); });
