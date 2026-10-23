// CR-017 STOP 5 scorecard harness: runs the generated explorer page in Node against a stubbed DOM and renders the Scorecard for every dataset and level.
// usage: node scorecard_harness.js <index.html> <out.json>
const fs = require('fs'), vm = require('vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const scripts = [...html.matchAll(/<script(?: type="application\/octet-stream" id="(?:trace|eval)-gz")?>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const traceB64 = scripts[0], evalB64 = scripts[1], main = scripts[2];
const scB64 = (html.match(/id="scorecard-gz">([^<]*)<\/script>/) || [])[1] || '';
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
els['scorecard-gz'] = El('scorecard-gz'); els['scorecard-gz'].textContent = scB64;
vm.runInThisContext(main);
(async () => {
  const out = { errors: [], renders: {}, tabs: '' };
  for (const view of ['review', 'debug']) {
    setView(view); setMode('ev');
    out.tabs = $('tabs').innerHTML; out.entry_tab = S.tab;
    const P = await loadScorecard();
    for (const [k, d] of Object.entries(P.datasets)) {
      for (const lv of Object.keys(d.levels)) {
        SCS.set = k; SCS.level = lv; const el = $('v-evscore');
        try { await renderScorecard(el); out.renders[view + '|' + k + '|' + lv] = el.innerHTML; } catch (e) { out.errors.push(view + k + lv + ': ' + e.message); }
      }
    }
  }
  setView('review'); setMode('pd');
  out.after_leaving_has_scorecard = /Scorecard|HEADLINE/.test(($('banner').innerHTML || '') + ($('detailin').innerHTML || '') + ($('tabs').innerHTML || '') + ($('side').innerHTML || ''));
  fs.writeFileSync(process.argv[3], JSON.stringify(out));
  process.exit(0);
})().catch(e => { fs.writeFileSync(process.argv[3], JSON.stringify({ fatal: String(e && e.stack || e) })); process.exit(1); });
