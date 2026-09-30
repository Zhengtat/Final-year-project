"""`cumap demo build`: writes reports/demo/index.html (one self-contained, offline file: no
external scripts, styles or fonts) and reports/demo/figures/*.svg (one per chart/graph, each
with its provenance footer). Deterministic for a fixed run: layouts use a fixed seed.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from cumap.config import REPO_ROOT, DemoSliceConfig, Settings
from cumap.expert_kg.face_eval import FACE_CAVEAT, FACE_PUBLISHED, evaluate_run
from cumap.report import data as D
from cumap.report.graph import (
    FAMILY_ORDER,
    GNode,
    chapter_slot,
    family_slot,
    render_growth_graph,
    render_section_graph,
)
from cumap.report.graph3d import growth3d_page, layout2d_matching, layout3d
from cumap.report.provenance import LABEL_SOURCES, Provenance
from cumap.report.svg import grouped_bar_svg, hbar_svg, slot, theme_css
from cumap.report.viewer import Span, find_span, highlight_html
from cumap.schemas.relations import RelationRegistry

BANNER = (
    "Expert knowledge graph only. The student side (answer graphs, expert-vs-student "
    "comparison, misconception diagnosis) is deferred by owner decision; nothing on this "
    "page diagnoses a student."
)


class Figures:
    """Collects standalone SVGs; returns the SVG string for inlining."""

    def __init__(self, out_dir: Path):
        self.dir = out_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.written: list[str] = []

    def emit(self, slug: str, svg: str) -> str:
        (self.dir / f"{slug}.svg").write_text(svg, encoding="utf-8")
        self.written.append(slug)
        return svg


def _pct(x: float) -> str:
    return f"{x:.3f}"


def _ci_text(ci: dict) -> str:
    return f"{ci['successes']}/{ci['n']} = {ci['point']:.3f} (95% Wilson CI {ci['low']:.3f}–{ci['high']:.3f})"


def _metrics_table(evals: dict[str, dict]) -> str:
    rows = []
    for split, ev in evals.items():
        m = ev["metrics"]
        for match in ("exact", "lenient"):
            for agg in ("micro", "macro"):
                x = m[match][agg]
                rows.append(
                    f"<tr><td>{split}</td><td>{match}</td><td>{agg}</td><td>{_pct(x['precision'])}</td>"
                    f"<td>{_pct(x['recall'])}</td><td>{_pct(x['f1'])}</td>"
                    f"<td>{x['tp']}/{x['fp']}/{x['fn']}</td></tr>"
                )
    return (
        "<table><thead><tr><th>split</th><th>match</th><th>average</th><th>precision</th>"
        "<th>recall</th><th>F1</th><th>TP/FP/FN</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _iir_section_html(sec_eval: dict, text: str) -> str:
    spans: list[Span] = []
    unlocated: list[str] = []
    order = {"exact": 0, "lemma": 0, "embedding": 0}
    for p in sorted(sec_eval["predicted"], key=lambda p: order.get(p["status"], 1)):
        loc = find_span(text, p["name"])
        matched = p["status"] in order
        tip = (
            f"{p['name']} · role: {p['role']} · "
            + (f"matched gold '{p['matched_gold']}' ({p['status']})" if matched else "not in gold")
            + f" · evidence: “{p['evidence']}”"
        )
        if loc:
            spans.append(Span(*loc, "m-match" if matched else "m-extra", tip))
        else:
            unlocated.append(f"{p['name']} ({'✓' if matched else '~'})")
    for g in sec_eval["missed_gold"]:
        loc = find_span(text, g)
        if loc:
            spans.append(Span(*loc, "m-miss", f"gold concept the model missed: {g}"))
        else:
            unlocated.append(f"{g} (✗ missed)")
    extra = (
        f'<p class="small">Not located verbatim in the text: {escape("; ".join(unlocated))}</p>'
        if unlocated
        else ""
    )
    return f'<div class="doc">{highlight_html(text, spans)}</div>{extra}'


def _pd_section_html(mentions: list[dict], text: str) -> str:
    spans: list[Span] = []
    rank = {"defined": 0, "used": 1, "mentioned": 2}
    for m in sorted(mentions, key=lambda m: rank[m["role"]]):
        loc = find_span(text, m["evidence_quote"], ignore_case=False) or find_span(
            text, m["evidence_quote"]
        )
        if loc:
            spans.append(
                Span(
                    *loc,
                    f"r-{m['role']}",
                    f"{m['canonical_name']} · {m['role']} · “{m['evidence_quote']}”",
                )
            )
    return f'<div class="doc">{highlight_html(text, spans)}</div>'


def _viewer(vid: str, options: list[tuple[str, str, str]]) -> str:
    """options: (key, label, inner html). A <select> switches which pane is shown."""
    opts = "".join(f'<option value="{escape(k)}">{escape(lbl)}</option>' for k, lbl, _ in options)
    panes = "".join(
        f'<div class="pane" data-pane="{escape(k)}"{"" if i == 0 else " hidden"}>{html}</div>'
        for i, (k, _, html) in enumerate(options)
    )
    return (
        f'<div class="viewer" id="{vid}"><select data-viewer="{vid}">{opts}</select>{panes}</div>'
    )


def _errors_table(items: list[dict], kind: str) -> str:
    rows = "".join(
        f"<tr><td>{escape(i['cause'])}</td><td>{escape(i['section_id'])}</td>"
        f'<td><b>{escape(i["concept"])}</b></td><td class="small">{escape(i["context"])}</td></tr>'
        for i in sorted(items, key=lambda i: (i["cause"], i["section_id"], i["concept"]))
    )
    return (
        f"<table><thead><tr><th>likely cause ({kind})</th><th>section</th><th>concept</th>"
        f"<th>sentence</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _worked_example_html(ex: dict, registry: RelationRegistry, graph_svg: str) -> str:
    fam = "".join(
        f'<li class="{"chosen" if o["chosen"] else ""}">{escape(o["name"])} — {escape(o["label"])}'
        f"{' ← chosen' if o['chosen'] else ''}</li>"
        for o in ex["family_options"]
    )
    rel = "".join(
        f'<li class="{"chosen" if o["chosen"] else ""}">{escape(o["text"])}'
        f"{' ← chosen' if o['chosen'] else ''}</li>"
        for o in ex["relation_options"]
    )
    q = ex["qualifiers"]
    quals = ", ".join(f"{k}: {v}" for k, v in q.items() if v not in (None, [], ""))
    arrow = f"{escape(ex['source'])} —[{escape(ex['relation'])}]→ {escape(ex['target'])}"
    return (
        f'<div class="card"><h4>Section {escape(ex["section"])}</h4>'
        f'<ol class="steps"><li><b>Sentence</b><blockquote>{escape(ex["sentence"])}</blockquote></li>'
        f"<li><b>Candidate pair</b> (found by co-occurrence, no LLM): <i>{escape(ex['x'])}</i> and "
        f"<i>{escape(ex['y'])}</i> — {ex['cooccurrence']} co-occurring sentence(s), cue score {ex['cue_score']}</li>"
        f'<li><b>Step 1: which family?</b> The model picks one option:<ul class="opts">{fam}</ul></li>'
        f"<li><b>Step 2: which relation, and which direction?</b> Options for the chosen family, "
        f'filled with these two concepts:<ul class="opts">{rel}</ul></li>'
        f"<li><b>Step 3: qualifiers and evidence</b><br>Qualifiers: {escape(quals)}<br>"
        f"Evidence quote (verified as an exact substring of the sentence): “{escape(ex['quote'])}”<br>"
        f"Model’s statement: {escape(ex['statement'])}</li>"
        f"<li><b>Resulting edge</b>: {arrow}</li></ol>"
        f"<details open><summary>All accepted edges in this section</summary>"
        f'<div class="svgbox">{graph_svg}</div></details></div>'
    )


def _key_concept_grid(growth: D.GrowthData) -> str:
    secs = growth.section_labels
    head = "".join(f'<th title="{escape(s["id"])}">{escape(s["label"][:12])}</th>' for s in secs)
    glyph = {"defined": "●", "used": "◐", "mentioned": "○"}
    rows = []
    for c in growth.key_concepts:
        cells = "".join(
            f'<td class="gc r-{c["roles"][s["id"]]}" title="{escape(c["name"])} · {c["roles"][s["id"]]} in {escape(s["id"])}">'
            f"{glyph[c['roles'][s['id']]]}</td>"
            if s["id"] in c["roles"]
            else "<td></td>"
            for s in secs
        )
        rows.append(f'<tr><th class="rowh">{escape(c["name"])}</th>{cells}</tr>')
    return (
        '<div class="scroll"><table class="grid"><thead><tr><th></th>'
        + head
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
        '<p class="small">● defined · ◐ used · ○ mentioned only. Sections in book order; the 15 concepts '
        "appearing in the most sections.</p>"
    )


CSS = (
    theme_css(":root")
    + """
:root{color-scheme:light dark;--card:#ffffff}
@media (prefers-color-scheme:dark){:root{--card:#232322}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
header{padding:16px 24px;border-bottom:1px solid var(--grid)}
h1{margin:0 0 6px;font-size:20px}h2{font-size:18px;margin:28px 0 8px}h3{font-size:16px;margin:22px 0 6px}
h4{margin:0 0 8px}
.banner{background:color-mix(in srgb,var(--warning) 22%,transparent);border-left:4px solid var(--warning);
padding:8px 12px;margin-top:8px;border-radius:4px}
nav{display:flex;gap:4px;padding:0 24px;border-bottom:1px solid var(--grid);flex-wrap:wrap}
nav button{background:none;border:0;border-bottom:3px solid transparent;color:var(--ink2);padding:10px 14px;
font:inherit;cursor:pointer}nav button[aria-selected=true]{color:var(--ink);border-color:var(--s1);font-weight:600}
main{padding:8px 24px 48px;max-width:1100px}.tab[hidden]{display:none}
table{border-collapse:collapse;margin:8px 0;font-size:13px}th,td{border:1px solid var(--grid);padding:4px 8px;
text-align:left;vertical-align:top}th{background:color-mix(in srgb,var(--grid) 50%,transparent)}
.small{font-size:12px;color:var(--ink2)}.card{border:1px solid var(--grid);border-radius:8px;padding:12px 16px;
margin:14px 0;background:var(--card)}
.svgbox,.scroll{overflow-x:auto;max-width:100%}.svgbox svg{max-width:100%;height:auto}
.doc{white-space:pre-wrap;max-height:420px;overflow:auto;border:1px solid var(--grid);padding:10px;
font-size:13px;line-height:1.6;border-radius:6px}
mark{color:inherit;border-radius:2px;cursor:help}
.m-match{background:color-mix(in srgb,var(--good) 32%,transparent)}.m-match::after{content:"✓";font-size:10px;color:var(--good)}
.m-extra{background:color-mix(in srgb,var(--warning) 40%,transparent)}.m-extra::after{content:"~";font-size:10px}
.m-miss{background:none;text-decoration:underline wavy var(--critical);text-decoration-thickness:2px}
.m-miss::after{content:"✗";font-size:10px;color:var(--critical)}
.r-defined{background:color-mix(in srgb,var(--s1) 32%,transparent)}
.r-used{background:color-mix(in srgb,var(--s3) 32%,transparent)}
.r-mentioned{background:color-mix(in srgb,var(--s4) 32%,transparent)}
.chip{display:inline-block;padding:0 6px;border-radius:3px;margin-right:6px;font-size:12px}
.steps li{margin:8px 0}blockquote{margin:4px 0;padding:4px 10px;border-left:3px solid var(--grid);color:var(--ink2)}
.opts{margin:4px 0;padding-left:20px}.opts li{margin:1px 0;color:var(--ink2)}
.opts li.chosen{color:var(--ink);font-weight:600}
.controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin:8px 0}
.grid td.gc{text-align:center;min-width:26px}.grid th{font-weight:400;font-size:11px}.rowh{white-space:nowrap}
.foot{font-size:12px;color:var(--ink2);margin-top:32px}
#detail{border:1px solid var(--grid);border-radius:6px;padding:8px 12px;min-height:56px;margin:8px 0;font-size:13px}
g.edge:hover line{stroke-width:4}
#growth .node,#growth .edge{transition:opacity .5s}
#growth .off{opacity:0;pointer-events:none}
#timebar{width:min(560px,90%)}
@keyframes pop{from{transform:scale(0)}to{transform:scale(1)}}
@keyframes flash{50%{stroke:var(--ink);stroke-width:6}}
#growth .node.new circle{transform-box:fill-box;transform-origin:center;animation:pop .6s ease-out}
#growth .node.pulse circle{animation:flash .7s}
#growth .edge.new line{animation:flash .9s}
@media (prefers-reduced-motion:reduce){#growth .node circle,#growth .edge line{animation:none!important}}
"""
)

JS = """
(function(){
const $=(s,r)=>(r||document).querySelector(s),$$=(s,r)=>Array.from((r||document).querySelectorAll(s));
$$('nav button').forEach(b=>b.addEventListener('click',()=>{
 $$('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
 $$('.tab').forEach(t=>t.hidden=t.id!==b.dataset.tab);}));
$$('select[data-viewer]').forEach(sel=>sel.addEventListener('change',()=>{
 const v=document.getElementById(sel.dataset.viewer);
 $$('.pane',v).forEach(p=>p.hidden=p.dataset.pane!==sel.value);}));
const EDGES=JSON.parse($('#edge-data').textContent);
function showEdge(id){const e=EDGES[id];if(!e)return;
 $('#detail').innerHTML='<b>'+esc(e.source)+' —['+esc(e.relation)+']→ '+esc(e.target)+'</b> ('+esc(e.family)+
 ', '+esc(e.polarity)+', '+esc(e.modality)+')<br>Section '+esc(e.section)+' · sentence: '+esc(e.sentence)+
 '<br>Evidence quote: “'+esc(e.quote)+'”<br>Statement: '+esc(e.statement);}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
document.addEventListener('click',ev=>{const g=ev.target.closest('[data-edge]');if(g)showEdge(g.dataset.edge);});
const gr=$('#growth');
if(gr){const bar=$('#timebar'),all=$('#showall'),pre=$('#showprereq'),play=$('#play'),speed=$('#speed'),
 topn=+gr.dataset.topn,STEPS=JSON.parse($('#steps-data').textContent),last=STEPS.length-1;
 let timer=null,prev=-1;
 function flash(el,cls){el.classList.remove(cls);void el.getBoundingClientRect();el.classList.add(cls);}
 function apply(){const t=+bar.value,st=STEPS[t],ment=new Set(st.mentioned),vis=new Set();
  $('#stepname').textContent='Section '+st.caption+' (ch'+st.chapter+')';
  $$('.node',gr).forEach(n=>{const show=+n.dataset.sec<=t&&(all.checked||+n.dataset.rank<topn);
   n.classList.toggle('off',!show);if(show)vis.add(n.dataset.id);
   n.classList.remove('new','pulse');
   if(show&&t!==prev){if(+n.dataset.sec===t)flash(n,'new');else if(ment.has(n.dataset.id))flash(n,'pulse');}
   const h=$('.halo',n);if(h)h.style.display=pre.checked?'':'none';});
  let ne=0;$$('.edge',gr).forEach(e=>{const show=+e.dataset.sec<=t&&vis.has(e.dataset.s)&&vis.has(e.dataset.t);
   e.classList.toggle('off',!show);e.classList.remove('new');if(show){ne++;if(+e.dataset.sec===t&&t!==prev)flash(e,'new');}});
  let m=0;for(let i=0;i<=t;i++)m+=STEPS[i].merges;
  $('#counts').textContent=vis.size+' concepts, '+ne+' edges, '+m+' alias merges so far';prev=t;}
 function stop(){clearInterval(timer);timer=null;play.textContent='▶ Play';}
 function start(){if(+bar.value>=last){bar.value=0;prev=-1;}play.textContent='⏸ Pause';
  timer=setInterval(()=>{if(+bar.value>=last){stop();return;}bar.value=+bar.value+1;apply();},1400/+speed.value);apply();}
 play.addEventListener('click',()=>timer?stop():start());
 speed.addEventListener('change',()=>{if(timer){stop();start();}});
 bar.addEventListener('input',()=>{stop();apply();});
 [all,pre].forEach(x=>x.addEventListener('input',apply));apply();}
})();
"""


def build_report(
    run_id: str,
    settings: Settings,
    demo: DemoSliceConfig,
    *,
    out_dir: Path | None = None,
    nlp=None,
    embed_fn=None,
    refresh_eval: bool = False,
    root: Path | None = None,
) -> Path:
    """`root` is the data root (default: the repo); registry and prompts always come from the repo."""
    cfg = demo.report
    root = root or REPO_ROOT
    out = out_dir or (root / "reports" / "demo")
    figs = Figures(out / "figures")
    run_dir = root / "data" / "processed" / "kg" / run_id
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text())
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    from cumap.expert_kg.pipeline import PromptSet

    prompts = PromptSet.load(REPO_ROOT / "prompts")
    strong = settings.llm.tiers["strong"]
    prov = Provenance(
        run_id=run_id,
        prompt_versions={
            "concepts": prompts.concept_extraction.version,
            "canonicalize": prompts.canonicalize.version,
            "relations": prompts.relation_family.version,
        },
        model_tier="strong",
        model=strong.model,
        date=datetime.now(UTC).date().isoformat(),
    )

    # ---- tab 1: concept extraction & FACE validation (IIR gold) -------------------------
    evals: dict[str, dict] = {}
    iir_texts: dict[str, str] = {}
    for split, run, gold, secs in [
        ("dev", cfg.iir_dev_run, cfg.iir_dev_gold, cfg.iir_dev_sections),
        ("test", cfg.iir_test_run, cfg.iir_test_gold, cfg.iir_test_sections),
    ]:
        rd = root / "data" / "processed" / "kg" / run
        cached = rd / "face_eval.json"
        if cached.exists() and not refresh_eval:
            evals[split] = json.loads(cached.read_text())
        else:
            evals[split] = evaluate_run(rd, root / gold, root / secs, nlp=nlp, embed_fn=embed_fn)
        for row in D.read_jsonl(root / secs):
            iir_texts[row["section_id"]] = row["text"]

    def m(split: str, match: str, agg: str = "micro") -> dict:
        return evals[split]["metrics"][match][agg]

    chart_prf = figs.emit(
        "face-prf-exact-vs-lenient",
        grouped_bar_svg(
            "Concept extraction vs FACE gold: micro P/R/F1",
            ["precision", "recall", "F1"],
            {
                "dev exact": [m("dev", "exact")[k] for k in ("precision", "recall", "f1")],
                "dev lenient": [m("dev", "lenient")[k] for k in ("precision", "recall", "f1")],
                "test exact": [m("test", "exact")[k] for k in ("precision", "recall", "f1")],
                "test lenient": [m("test", "lenient")[k] for k in ("precision", "recall", "f1")],
            },
            provenance=prov,
            label_source="gold_face",
            ymax=1.0,
            width=680,
            series_colors={"dev exact": 0, "dev lenient": 2, "test exact": 1, "test lenient": 4},
        ),
    )
    chart_ref = figs.emit(
        "face-f1-vs-published",
        hbar_svg(
            "Micro F1 against FACE's published numbers",
            [
                ("ours, dev, lenient", m("dev", "lenient")["f1"], 0),
                ("ours, test, lenient", m("test", "lenient")["f1"], 1),
                ("ours, test, exact", m("test", "exact")["f1"], 2),
            ]
            + [(k, v, None) for k, v in FACE_PUBLISHED.items()],
            provenance=prov,
            label_source="gold_face",
            xmax=1.0,
            width=680,
            note="Caveat: FACE was supervised (5-fold CV, same book); ours is zero/few-shot. Not like-for-like.",
        ),
    )
    lens = sorted(
        {int(k) for s in evals.values() for k in s["metrics"]["recall_by_ngram"]["lenient"]}
    )

    def rec(split: str, n: int) -> float:
        return evals[split]["metrics"]["recall_by_ngram"]["lenient"].get(str(n), {"recall": 0.0})[
            "recall"
        ]

    chart_ngram = figs.emit(
        "face-recall-by-ngram",
        grouped_bar_svg(
            "Recall by gold-term length (lenient)",
            [f"{n}-word" for n in lens],
            {"dev": [rec("dev", n) for n in lens], "test": [rec("test", n) for n in lens]},
            provenance=prov,
            label_source="gold_face",
            ymax=1.0,
            width=660,
            height=300,
            series_colors={"dev": 0, "test": 1},
        ),
    )
    role_items = [
        (f"{r} ({s})", v["precision"], i)
        for s, ev in evals.items()
        for i, (r, v) in enumerate(sorted(ev["metrics"]["precision_by_role"].items()))
    ]
    chart_role = figs.emit(
        "face-precision-by-role",
        hbar_svg(
            "Precision by the model's own role tag (lenient)",
            role_items,
            provenance=prov,
            label_source="gold_face",
            xmax=1.0,
            width=660,
        ),
    )

    iir_options = []
    for split in ("dev", "test"):
        for sec in evals[split]["per_section"]:
            sid = sec["section_id"]
            tp = sum(1 for p in sec["predicted"] if p["status"] != "extra")
            iir_options.append(
                (
                    f"{split}:{sid}",
                    (
                        f"{split} · {sid} · {tp} matched, "
                        f"{len(sec['predicted']) - tp} extra, {len(sec['missed_gold'])} missed"
                    ),
                    _iir_section_html(sec, iir_texts[sid]),
                )
            )
    pd_sections = [
        r
        for r in D.read_jsonl(root / demo.pd.source_jsonl)
        if r["section_id"] in checkpoint["mentions_by_section"]
    ]
    pd_sections.sort(key=lambda r: r["order_index"])
    pd_options = [
        (
            s["section_id"],
            f"{s['section_id']} — {s.get('section_title', '')}",
            _pd_section_html(checkpoint["mentions_by_section"][s["section_id"]], s["text"]),
        )
        for s in pd_sections
    ]

    # ---- growth data + tab 2/3 ------------------------------------------------------------
    snaps = D.load_snapshots(run_dir)
    growth = D.build_growth(checkpoint, snaps, pd_sections, key_n=cfg.key_concepts)
    fam_counts, rel_counts = D.edge_counts(growth)
    examples = D.worked_examples(checkpoint, registry, growth)
    by_id_node = {n.id: n for n in growth.nodes}
    ex_html = []
    for ex in examples:
        sec_edges = [
            e for e in growth.edges if growth.edge_details[e.id]["section"] == ex["section"]
        ]
        ids = {i for e in sec_edges for i in (e.source, e.target)}
        graph_svg = figs.emit(
            f"relations-section-{ex['section'].replace('.', '_')}",
            render_section_graph(
                f"Accepted relations in section {ex['section']}",
                [GNode(id=i, label=by_id_node[i].label) for i in sorted(ids)],
                sec_edges,
                provenance=prov,
                label_source="model_output",
            ),
        )
        ex_html.append(_worked_example_html(ex, registry, graph_svg))

    chart_fam = figs.emit(
        "edges-by-family",
        hbar_svg(
            "Accepted edges by relation family",
            [(f, fam_counts[f], family_slot(f)) for f in FAMILY_ORDER if fam_counts[f]],
            provenance=prov,
            label_source="model_output",
            value_fmt="{:.0f}",
            width=600,
        ),
    )
    chart_rel = figs.emit(
        "edges-by-relation",
        hbar_svg(
            "Accepted edges by relation (colour = family)",
            [
                (r, c, family_slot(f))
                for (f, r), c in sorted(rel_counts.items(), key=lambda kv: -kv[1])
            ],
            provenance=prov,
            label_source="model_output",
            value_fmt="{:.0f}",
            width=600,
        ),
    )
    reasons = Counter(
        d["reason"] for d in checkpoint["pair_registry"] if not d.get("edge") and d.get("reason")
    )
    reasons.update(
        "concept rejected: "
        + r["reason"].replace("evidence_quote", "quote").replace("section text", "the section")
        for r in checkpoint["rejected_concepts"]
    )
    chart_rej = figs.emit(
        "pair-outcomes",
        hbar_svg(
            "Where candidate pairs and mentions were rejected",
            [("accepted edge", len(growth.edges), 5)]
            + [(k, v, None) for k, v in reasons.most_common()],
            provenance=prov,
            label_source="model_output",
            value_fmt="{:.0f}",
            width=680,
            label_w=290,
        ),
    )

    spot = D.summarise_spotcheck(
        D._read_csv(root / cfg.edge_sheet), D._read_csv(root / cfg.edge_key)
    )
    merge = D.summarise_merge_marks(D._read_csv(root / cfg.merge_marks))
    chart_spot = figs.emit(
        "owner-spotcheck-precision",
        hbar_svg(
            "Edge precision on 30 sampled edges (owner-judged)",
            [
                ("strict (correct only)", spot["strict"]["point"], 0),
                ("lenient (+ wrong direction)", spot["lenient"]["point"], 2),
            ],
            provenance=prov,
            label_source="owner_spotcheck",
            xmax=1.0,
            width=600,
            note=f"strict {spot['strict']['low']:.2f}–{spot['strict']['high']:.2f}; "
            f"lenient {spot['lenient']['low']:.2f}–{spot['lenient']['high']:.2f} (95% Wilson CI)",
        ),
    )
    chart_merge = figs.emit(
        "owner-merge-check",
        hbar_svg(
            "Non-trivial 'same' merges the owner judged correct",
            [("ok", merge["ci"]["point"], 0)],
            provenance=prov,
            label_source="owner_merge_check",
            xmax=1.0,
            width=600,
            note=f"{_ci_text(merge['ci'])}",
        ),
    )

    # ---- tab 3 -----------------------------------------------------------------------------
    growth_svg = figs.emit(
        "growth-graph-all-chapters",
        render_growth_graph(
            "Expert KG growth (all chapters; filter with the controls above)",
            growth.nodes,
            growth.edges,
            provenance=prov,
            label_source="model_output",
        ),
    )
    figs.emit(
        "growth-animation",
        render_growth_graph(
            f"Expert KG built section by section (animated; top {cfg.growth_top_n} concepts)",
            [n for n in growth.nodes if n.rank < cfg.growth_top_n],
            [
                e
                for e in growth.edges
                if by_id_node[e.source].rank < cfg.growth_top_n
                and by_id_node[e.target].rank < cfg.growth_top_n
            ],
            provenance=prov,
            label_source="model_output",
            animate_steps=[st["caption"] for st in growth.steps],
        ),
    )
    for ch in growth.chapters:
        sub_nodes = [n for n in growth.nodes if n.chapter <= ch and n.rank < cfg.growth_top_n]
        keep = {n.id for n in sub_nodes}
        sub_edges = [
            e for e in growth.edges if e.chapter <= ch and e.source in keep and e.target in keep
        ]
        figs.emit(
            f"growth-graph-through-ch{ch}",
            render_growth_graph(
                f"Expert KG through chapter {ch} (top {cfg.growth_top_n} concepts)",
                sub_nodes,
                sub_edges,
                provenance=prov,
                label_source="model_output",
            ),
        )
    from cumap.expert_kg.snapshots import compute_growth_metrics

    gm = compute_growth_metrics(snaps)
    cats = [f"ch{g.chapter_num}" for g in gm]
    chart_g1 = figs.emit(
        "growth-concepts",
        grouped_bar_svg(
            "Concepts per chapter",
            cats,
            {
                "new": [g.concepts_new for g in gm],
                "reused from earlier": [g.concepts_reused for g in gm],
            },
            provenance=prov,
            label_source="model_output",
            value_fmt="{:.0f}",
            width=660,
            height=300,
            series_colors={"new": 0, "reused from earlier": 2},
        ),
    )
    chart_g2 = figs.emit(
        "growth-edges",
        grouped_bar_svg(
            "Edges per chapter",
            cats,
            {
                "new edges": [g.edges_new for g in gm],
                "cross-chapter": [g.cross_chapter_edges for g in gm],
                "merges": [g.merges for g in gm],
            },
            provenance=prov,
            label_source="model_output",
            value_fmt="{:.0f}",
            width=660,
            height=300,
            series_colors={"new edges": 0, "cross-chapter": 1, "merges": 2},
        ),
    )
    chart_g3 = figs.emit(
        "growth-prerequisites",
        grouped_bar_svg(
            "Prerequisite candidates and forward references",
            cats,
            {
                "prerequisite candidates": [g.prerequisite_candidates for g in gm],
                "forward references": [g.forward_references for g in gm],
            },
            provenance=prov,
            label_source="model_output",
            value_fmt="{:.0f}",
            width=660,
            height=300,
            series_colors={"prerequisite candidates": 0, "forward references": 1},
        ),
    )
    fams_present = [f for f in FAMILY_ORDER if any(f in g.family_share for g in gm)]
    chart_g4 = figs.emit(
        "growth-family-share",
        grouped_bar_svg(
            "Relation-family share of new edges",
            cats,
            {f: [g.family_share.get(f, 0.0) for g in gm] for f in fams_present},
            provenance=prov,
            label_source="model_output",
            ymax=1.0,
            width=680,
            height=320,
            series_colors={f: family_slot(f) for f in fams_present},
        ),
    )

    edge_json = json.dumps(growth.edge_details).replace("</", "<\\/")
    steps_json = json.dumps(growth.steps).replace("</", "<\\/")
    n_merges = sum(len(s.merges) for s in snaps)
    footer = prov.footer("model_output").rsplit(" · labels:", 1)[0]
    label_legend = "".join(f"<li>{escape(v)}</li>" for v in LABEL_SOURCES.values())
    legend_growth = (
        f'<span class="chip" style="background:{slot(0)};color:#fff">first introduced ch2</span>'
        f'<span class="chip" style="background:{slot(1)};color:#fff">first introduced ch3</span>'
        "size = sections mentioning · <b>bold dark edges</b> = cross-chapter · dashed ring = prerequisite candidate"
    )
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Expert KG Demo Report</title><style>{CSS}</style></head><body>
<header><h1>Expert knowledge graph — demo report</h1>
<div class="small">{escape(footer)}</div><div class="banner">{escape(BANNER)}</div></header>
<nav role="tablist"><button data-tab="t1" aria-selected="true">1 · Concepts &amp; FACE validation</button>
<button data-tab="t2" aria-selected="false">2 · Relations</button>
<button data-tab="t3" aria-selected="false">3 · Growth through chapters</button></nav><main>

<section class="tab" id="t1"><h2>Concept extraction, validated against FACE gold</h2>
<p>Concepts are extracted per section with an evidence quote checked verbatim against the text. To
check that the extractor works at all, it was run on Information Retrieval sections that come with
crowd-labelled gold concepts (FACE). Dev chapters were used to choose the prompt; test chapters were run once.</p>
{_metrics_table(evals)}
<div class="svgbox">{chart_prf}</div><div class="svgbox">{chart_ref}</div>
<p class="small">{escape(FACE_CAVEAT)} Exact = same words after case/whitespace normalisation; lenient also
accepts the same lemma or embedding cosine ≥ {evals["dev"]["embedding_threshold"]}.</p>
<div class="svgbox">{chart_ngram}</div><div class="svgbox">{chart_role}</div>
<h3>Section viewer — IIR (model output against gold)</h3>
<p class="small"><mark class="m-match">✓ matched gold</mark> <mark class="m-extra">~ extra (not in gold)</mark>
<mark class="m-miss">✗ gold concept missed</mark> — hover for role and evidence.</p>
{_viewer("v-iir", iir_options)}
<h3>Section viewer — Peterson &amp; Davie (no gold: model output only)</h3>
<p class="small"><mark class="r-defined">defined</mark> <mark class="r-used">used</mark>
<mark class="r-mentioned">mentioned</mark> — highlights are the evidence quotes; hover for the concept.</p>
{_viewer("v-pd", pd_options)}
<h3>Error analysis (dev split): 10 false positives, 10 false negatives</h3>
<p class="small">Causes are rule-based from the strings alone. Counts over all dev errors:
FP {escape(json.dumps(evals["dev"]["cause_counts"]["false_positive"]))} · FN {escape(json.dumps(evals["dev"]["cause_counts"]["false_negative"]))}.
“other” means none of the simple rules applied — the largest bucket, honestly reported.</p>
{_errors_table(evals["dev"]["false_positives"], "false positive")}
{_errors_table(evals["dev"]["false_negatives"], "false negative")}
</section>

<section class="tab" id="t2" hidden><h2>Relation extraction</h2>
<p>Only concept pairs that appear together in one sentence are considered. Each pair is judged once
(family, then relation and direction, then qualifiers), always as a choice among registry options.</p>
<h3>Three worked examples</h3>{"".join(ex_html)}
<h3>What was extracted</h3><div class="svgbox">{chart_fam}</div><div class="svgbox">{chart_rel}</div>
<div class="svgbox">{chart_rej}</div>
<h3>Checks against humans</h3>
<p>Owner spot-check of 30 accepted edges (blind: only the sentence and triple shown): strict precision
{_ci_text(spot["strict"])}; counting wrong-direction as right {_ci_text(spot["lenient"])}. Marks:
{escape(json.dumps(spot["counts"]))}. Small sample — read the interval, not the point.</p>
<div class="svgbox">{chart_spot}</div>
<p>Owner check of the {merge["ci"]["n"]} non-trivial concept merges: {_ci_text(merge["ci"])}. The wrong
ones ({", ".join(escape(w["alias"] + " → " + w["into"]) for w in merge["wrong"])}) are blocked in
<code>configs/canonical_overrides.yaml</code>.</p><div class="svgbox">{chart_merge}</div>
</section>

<section class="tab" id="t3" hidden><h2>Growth through chapters</h2>
<p class="small">The graph is built in book order, one section per step (press Play or drag the bar). New concepts pop in, concepts mentioned again flash, new edges flash. This is the order of the book, not a learner's path; book order is not prerequisite truth.</p>
<p>{legend_growth}</p>
<div class="controls"><button id="play" type="button">▶ Play</button>
<label>Time <input type="range" id="timebar" min="0" max="{len(growth.steps) - 1}" value="{len(growth.steps) - 1}" step="1"></label>
<label>Speed <select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option>
<option value="2">2×</option><option value="4">4×</option></select></label></div>
<div class="controls"><b id="stepname"></b><span class="small" id="counts"></span></div>
<div class="controls"><label><input type="checkbox" id="showall"> show all concepts (default: top {cfg.growth_top_n} by connections)</label>
<label><input type="checkbox" id="showprereq" checked> prerequisite layer</label></div>
<div id="detail" class="small">Click an edge to see its evidence.</div>
<div class="svgbox" id="growth" data-topn="{cfg.growth_top_n}">{growth_svg}</div>
<p class="small">Prerequisite candidates are rule-based (defined in one section, used in a later one;
book order is <b>not</b> prerequisite truth). {n_merges} alias merges across chapters.</p>
<div class="svgbox">{chart_g1}</div><div class="svgbox">{chart_g2}</div><div class="svgbox">{chart_g3}</div>
<div class="svgbox">{chart_g4}</div>
<h3>When key concepts appear</h3>{_key_concept_grid(growth)}
</section>

<div class="foot"><b>Label sources used on this page</b><ul>{label_legend}</ul>
Contains IIR (© Cambridge University Press) text for local research use only — do not redistribute this file.</div>
</main><script type="application/json" id="edge-data">{edge_json}</script>
<script type="application/json" id="steps-data">{steps_json}</script><script>{JS}</script></body></html>"""
    (out / "index.html").write_text(html, encoding="utf-8")
    _write_growth3d(out, growth, checkpoint, cfg, prov, footer)
    return out / "index.html"


def _write_growth3d(
    out: Path, growth, checkpoint: dict, cfg, prov: Provenance, footer: str
) -> None:
    """growth3d.html: the growth graph as an interactive 3D scene (spin, zoom, click a concept)."""
    pos = layout3d([n.id for n in growth.nodes], [(e.source, e.target) for e in growth.edges])
    top = [n for n in growth.nodes if n.rank < cfg.growth_top_n]
    radius = 1.05 * max(math.dist(pos[n.id], (0, 0, 0)) for n in top)
    pos2 = layout2d_matching(
        [n.id for n in growth.nodes],
        [(e.source, e.target) for e in growth.edges],
        {n.id for n in top},
        radius,
    )
    concepts = {c["concept_id"]: c for c in checkpoint["concepts"]}
    captions = {}
    for st, sec in zip(growth.steps, growth.section_labels, strict=True):
        captions[sec["id"]] = st["caption"]
    data = {
        "radius": round(radius, 1),
        "topn": cfg.growth_top_n,
        "labelTop": 30,
        "nodes": [
            {
                "i": n.id,
                "l": n.label,
                "ch": n.chapter,
                "col": chapter_slot(n.chapter),
                "sec": n.section,
                "rank": n.rank,
                "size": n.size,
                "prereq": n.prereq,
                "type": concepts[n.id]["node_type"],
                "x2": round(pos2[n.id][0], 1),
                "y2": round(pos2[n.id][1], 1),
                "x": round(pos[n.id][0], 1),
                "y": round(pos[n.id][1], 1),
                "z": round(pos[n.id][2], 1),
            }
            for n in growth.nodes
        ],
        "edges": [
            {
                "id": e.id,
                "s": e.source,
                "t": e.target,
                "rel": e.relation,
                "fam": e.family,
                "slot": family_slot(e.family),
                "sec": e.section,
                "cross": e.cross,
                "neg": e.negated,
                "statement": growth.edge_details[e.id]["statement"],
                "quote": growth.edge_details[e.id]["quote"],
                "polarity": growth.edge_details[e.id]["polarity"],
                "modality": growth.edge_details[e.id]["modality"],
                "section": growth.edge_details[e.id]["section"],
            }
            for e in growth.edges
        ],
        "concepts": {
            cid: {
                "def": c.get("definition"),
                "aliases": c["aliases"],
                "mentions": [
                    {"sec": m["section_id"], "role": m["role"], "quote": m["quote"]}
                    for m in c["mentions"]
                ],
            }
            for cid, c in concepts.items()
        },
        "steps": growth.steps,
        "secCaption": captions,
        "families": [
            {"name": f, "slot": family_slot(f)}
            for f in FAMILY_ORDER
            if any(e.family == f for e in growth.edges)
        ],
        "chapters": [{"ch": c, "slot": chapter_slot(c)} for c in growth.chapters],
    }
    (out / "growth3d.html").write_text(
        growth3d_page(
            data, css=theme_css(":root"), banner=BANNER, footer=footer, top_n=cfg.growth_top_n
        ),
        encoding="utf-8",
    )
