"""CR-012 STOP 5: final reports and figures, generated ONLY from the frozen STOP-4 results (no model call, no rerun, no rescoring).

uv run python -m cumap.cr012.stop5
"""

from __future__ import annotations

import json
from pathlib import Path

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import attribution as A
from cumap.llm.cost import spend_from_log

R = REPO_ROOT / "reports/cr012"
FIG = R / "figures"
RES = json.loads((R / "stop4_heldout_results.json").read_text())
PD, SC = RES["pd"]["levels"], RES["scinlp"]["levels"]
STAB = json.loads((R / "stop4_stability.json").read_text())
LOG = [json.loads(x) for x in (R / "stop4_log.jsonl").read_text().splitlines()]
PILOT = json.loads((R / "pilot_oracles.json").read_text())["1.5"]
NA = "NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION"
SPENT_BEFORE = json.loads((R / "spend_to_date.json").read_text())["total_usd"]


def f3(x) -> str:
    return f"{x:.3f}"


def prf(d: dict) -> str:
    return f"{f3(d['precision'])} / {f3(d['recall'])} / {f3(d['f1'])}"


# ------------------------------------------------------------------ dependency-free SVG
def svg(w: int, h: int, body: list[str], title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="sans-serif" font-size="12">'
        f'<rect width="{w}" height="{h}" fill="white"/><text x="10" y="20" font-size="14" font-weight="bold">{title}</text>'
        + "".join(body)
        + "</svg>"
    )


def bars(
    path: Path, title: str, items: list[tuple[str, float, str]], ymax: float, note: str = ""
) -> None:
    w, h, left, top, bot = 640, 330, 60, 40, 60
    pw = w - left - 20
    ph = h - top - bot
    body = [
        f'<line x1="{left}" y1="{top + ph}" x2="{left + pw}" y2="{top + ph}" stroke="#444"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + ph}" stroke="#444"/>',
    ]
    for k in range(6):
        v = ymax * k / 5
        y = top + ph - ph * k / 5
        body.append(
            f'<text x="{left - 8}" y="{y + 4}" text-anchor="end">{v:.2f}</text><line x1="{left}" y1="{y}" x2="{left + pw}" y2="{y}" stroke="#ddd"/>'
        )
    n = len(items)
    bw = pw / n * 0.6
    for i, (lab, v, colour) in enumerate(items):
        x = left + pw / n * (i + 0.2)
        bh = ph * v / ymax
        body.append(
            f'<rect x="{x}" y="{top + ph - bh}" width="{bw}" height="{bh}" fill="{colour}"/><text x="{x + bw / 2}" y="{top + ph - bh - 4}" text-anchor="middle">{v:.3f}</text><text x="{x + bw / 2}" y="{top + ph + 16}" text-anchor="middle">{lab}</text>'
        )
    if note:
        body.append(f'<text x="10" y="{h - 8}" fill="#a00">{note}</text>')
    path.write_text(svg(w, h, body, title), encoding="utf-8")


def stacked(path: Path, title: str, rows: list[tuple[str, dict]], note: str = "") -> None:
    cols = dict(
        zip(
            A.CODES,
            [
                "#c0392b",
                "#e67e22",
                "#f1c40f",
                "#8e44ad",
                "#2c3e50",
                "#2980b9",
                "#16a085",
                "#27ae60",
                "#7f8c8d",
                "#bdc3c7",
            ],
            strict=True,
        )
    )
    w, h = 720, 60 + 44 * len(rows) + 60
    body = []
    for i, (lab, a) in enumerate(rows):
        y = 40 + i * 44
        tot = max(a["misses"], 1)
        x = 190.0
        body.append(f'<text x="10" y="{y + 18}">{lab} ({a["misses"]} misses)</text>')
        for c in A.CODES:
            v = a["by_code"][c]
            if not v:
                continue
            ww = 500 * v / tot
            body.append(
                f'<rect x="{x}" y="{y}" width="{ww}" height="26" fill="{cols[c]}"><title>{c}: {v}</title></rect>'
            )
            if ww > 22:
                body.append(
                    f'<text x="{x + ww / 2}" y="{y + 17}" text-anchor="middle" fill="white">{c}</text>'
                )
            x += ww
    lx = 190
    for c in A.CODES:
        body.append(
            f'<rect x="{lx}" y="{h - 40}" width="12" height="12" fill="{cols[c]}"/><text x="{lx + 16}" y="{h - 30}">{c}</text>'
        )
        lx += 50
    if note:
        body.append(f'<text x="10" y="{h - 8}" fill="#a00">{note}</text>')
    path.write_text(svg(w, h, body, title), encoding="utf-8")


def dots(path: Path, title: str, rows: list[tuple[str, list[float]]]) -> None:
    w, h = 640, 60 + 40 * len(rows) + 30
    mx = max(max(v) for _, v in rows) * 1.2 or 0.1
    body = []
    for i, (lab, vals) in enumerate(rows):
        y = 50 + 40 * i
        body.append(
            f'<text x="10" y="{y + 4}">{lab}</text><line x1="230" y1="{y}" x2="620" y2="{y}" stroke="#ccc"/>'
        )
        for j, v in enumerate(vals):
            x = 230 + 390 * v / mx
            body.append(
                f'<circle cx="{x}" cy="{y}" r="6" fill="#2980b9"><title>repeat {j + 1}: {v:.3f}</title></circle><text x="{x}" y="{y - 10}" text-anchor="middle">{v:.3f}</text>'
            )
    body.append(
        f'<text x="10" y="{h - 8}">all three repeats shown; no best-run selection; axis 0 to {mx:.2f}</text>'
    )
    path.write_text(svg(w, h, body, title), encoding="utf-8")


# ------------------------------------------------------------------ numbers
def main() -> None:
    FIG.mkdir(exist_ok=True)
    e0 = PD["E0"]
    att = e0["attribution_pooled"]
    miss = att["misses"]
    b = att["by_code"]
    p0, ext = b["P0"], b["N0"] + b["N1"]
    pr = e0["pair_recall_pooled"]
    ladder = [(lv, PD[lv]["pooled_strict_e2e"]) for lv in ("E0", "E1", "E2", "E3", "E4")]
    f1 = {lv: q["f1"] for lv, q in ladder}
    rc = PD["E3"]["relation_given_correct_endpoints_pooled"]
    sc_f1 = {lv: SC[lv]["aggregates"]["rel"]["micro"]["f1"] for lv in SC}
    sc_att = SC["E0"]["attribution_pooled"]
    n0 = sc_att["by_code"]["N0"]
    sc_usd = {lv: SC[lv]["usd"] for lv in SC}
    pd_usd = {lv: PD[lv]["usd"] for lv in PD}
    stab_usd = round(
        sum(spend_from_log(get_settings(), r["run_id"]) for r in LOG if "stab" in r["run_id"]), 2
    )
    total = LOG[-1]["spent_total_after"]
    stop4_spend = round(total - SPENT_BEFORE, 2)
    tp_pd, tp_sc = e0["pooled_strict_e2e"]["tp"], SC["E0"]["aggregates"]["rel"]["micro"]["tp"]
    ci = e0["bootstrap_by_section_95"]

    # ---------------- figures
    bars(FIG / "pd_oracle_waterfall.svg", "P&D held-out: strict E2E edge F1, E0 (system) and E1-E4 (oracle diagnostics)",
         [(lv, f1[lv], "#2c3e50" if lv == "E0" else "#95a5a6") for lv in f1], 0.6,
         "E0 is the headline system score; E1-E4 are conditional / oracle uplifts, not an additive causal decomposition")  # fmt: skip
    stacked(FIG / "earliest_failure_distribution.svg", "Earliest-failure attribution of missed gold edges (share of misses)",
            [("P&D E0", att), ("P&D E1", PD["E1"]["attribution_pooled"]), ("P&D E2", PD["E2"]["attribution_pooled"]), ("P&D E3", PD["E3"]["attribution_pooled"]),
             ("SciNLP E0", sc_att), ("SciNLP E1", SC["E1"]["attribution_pooled"]), ("SciNLP E3-M", SC["E3"]["attribution_pooled"])],
            "SciNLP: no identity gold, so C0/C1 do not apply; schemas and annotation density differ from P&D")  # fmt: skip
    bars(FIG / "headline_e0_pd_vs_scinlp.svg", "Headline E0 (two different annotation schemas; do not compare as one accuracy)",
         [("P&D strict E2E edge", f1["E0"], "#2c3e50"), ("SciNLP strict relation", sc_f1["E0"], "#8e44ad")], 0.1,
         "WARNING: P&D is exhaustive 17-relation canonical graph gold; SciNLP is selective mention-level 11-relation gold")  # fmt: skip
    dots(FIG / "stability.svg", "Stability: strict F1 of three independent E0 repeats",
         [(f"{bn} {u}", [x["strict_e2e_f1"] for x in r["per_run"]]) for bn, d in (("P&D", STAB["pd"]), ("SciNLP", STAB["scinlp"])) for u, r in d.items()])  # fmt: skip
    bars(FIG / "cost_per_correct_edge_e0.svg", "E0 model spend per correctly recovered edge (USD)",
         [("P&D", pd_usd["E0"] / max(tp_pd, 1), "#2c3e50"), ("SciNLP", sc_usd["E0"] / max(tp_sc, 1), "#8e44ad")], max(pd_usd["E0"] / max(tp_pd, 1), sc_usd["E0"] / max(tp_sc, 1)) * 1.2,
         f"P&D {tp_pd} correct edges for ${pd_usd['E0']}; SciNLP {tp_sc} correct relations for ${sc_usd['E0']}")  # fmt: skip

    # ---------------- pd_e2e.md
    L = ["# CR-012 P&D-E2E held-out results", "",
         "Gold: `data/gold/pd_e2e_test_blind.csv` (7 sections, 426 headline edges). **Inter-annotator agreement: NOT_EVALUABLE_SINGLE_ANNOTATOR.** The LLM prefill was reviewed by the owner and is not a second annotator.", "",
         "## Headline (E0, the system score)", "",
         f"STRICT_E2E_EDGE precision / recall / F1 = **{prf(e0['pooled_strict_e2e'])}** (micro-pooled over 7 sections; tp {tp_pd}).",
         f"Section-bootstrap 95% interval for F1: [{f3(ci['ci']['f1'][0])}, {f3(ci['ci']['f1'][1])}], labelled **DESCRIPTIVE_SMALL_N** / {ci['CI_status']} (7 sections; {ci['distinct_resamples_possible']} distinct resamples): not a strong inferential CI.", "",
         "## Oracle diagnostics (conditional / oracle uplifts; not an additive causal decomposition)", "",
         "| level | P / R / F1 | pair recall | canonical-node F1 | typed mention F1 |", "|---|---|---|---|---|"]  # fmt: skip
    for lv, q in ladder:
        p = PD[lv]["pair_recall_pooled"]
        L.append(f"| {lv}{' (headline)' if lv == 'E0' else ''} | {prf(q.to_dict() if hasattr(q, 'to_dict') else q)} | {p['reached']}/{p['reachable_denominator']} | {f3(PD[lv]['pooled_canonical_node']['f1'])} | {f3(PD[lv]['pooled_typed_mentions']['f1'])} |")  # fmt: skip
    L += [
        "",
        "## Per section (E0)",
        "",
        "| section | P / R / F1 | tp / fp / fn | pair recall | nodes | edges |",
        "|---|---|---|---|---|---|",
    ]
    for s, v in e0["per_section"].items():
        q = v["strict_e2e_edge"]
        pr_ = v["pair_recall"]
        L.append(f"| {s} | {prf(q)} | {q['tp']} / {q['fp']} / {q['fn']} | {pr_['reached_classification']}/{pr_['denominator']} | {v['graph_stats']['nodes']} | {v['graph_stats']['edges']} |")  # fmt: skip
    L += ["", "## Identity (canonical graph)", "",
          f"E0 pooled canonical-node F1 {f3(e0['pooled_canonical_node']['f1'])}; macro pairwise identity F1 {f3(e0['identity_pairwise_f1_macro'])}; macro B-cubed F1 {f3(e0['identity_bcubed_f1_macro'])}. With gold identity supplied (E2) the node F1 is {f3(PD['E2']['pooled_canonical_node']['f1'])}.", "",
          "## Relation stage", "",
          f"Given the gold endpoint pairs (E3), a predicted edge exists for {rc['gold_with_proposed_edge']} gold pairs; relation correct {rc['relation_correct']} / {rc['gold_with_proposed_edge']} = {rc['relation_correct'] / rc['gold_with_proposed_edge']:.1%}; direction correct {rc['direction_correct']} / {rc['gold_with_proposed_edge']} = {rc['direction_correct'] / rc['gold_with_proposed_edge']:.1%}. E4 ({f3(f1['E4'])}) is the frozen relation-stage ceiling **under gold endpoint assistance**, not achievable production accuracy.", ""]  # fmt: skip
    (R / "pd_e2e.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- external_e2e.md
    L = ["# CR-012 external benchmark (SciNLP-repo-e78342be) held-out results", "",
         "3 test documents; mention-level strict scoring (exact span + type for typed; relation direction and symmetry per registry). **CI_status = NOT_EVALUABLE_SMALL_N**: micro, per-document, macro mean and min/max are reported; no entity- or edge-level bootstrap. Identity metrics, E2 and canonical-node F1: **NOT_SUPPORTED** (no identity gold). Not pooled with P&D.", "",
         "| level | relation strict micro P / R / F1 | per-document F1 | macro F1 | min / max doc F1 | entity strict micro F1 | entity typed micro F1 |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for lv, v in SC.items():
        a = v["aggregates"]["rel"]
        pdoc = "; ".join(f"{d.split('.')[0]}={f3(x['f1'])}" for d, x in a["per_document"].items())
        L.append(f"| {lv.replace('E3', 'E3-M').replace('E4', 'E4-M')} | {prf(a['micro'])} | {pdoc} | {f3(a['macro_mean']['f1'])} | {f3(a['min_document_f1'])} / {f3(a['max_document_f1'])} | {f3(v['aggregates']['entity_strict']['micro']['f1'])} | {f3(v['aggregates']['entity_typed']['micro']['f1'])} |")  # fmt: skip
    gold_rel = {d: x["gold_relations"] for d, x in SC["E0"]["per_document"].items()}
    L += ["", f"Gold relations per document: {gold_rel}. **P17-1058 has a single gold relation**, so its per-document F1 is almost uninformative.", "",
          f"E0 -> E1: {f3(sc_f1['E0'])} -> {f3(sc_f1['E1'])}; E1 -> E3-M: {f3(sc_f1['E1'])} -> {f3(sc_f1['E3'])} (**post-mention / endpoint-delivery loss**, not pure pair-selection loss, because there is no E2 identity oracle); E3-M -> E4-M: {f3(sc_f1['E3'])} -> {f3(sc_f1['E4'])}.",
          "E3-M / E4-M operate on surface-level pseudo-nodes (one node per distinct normalised surface string; canonicalisation replaced). E1 keeps the normal canonicalisation.", "",
          "The SciNLP gold is selectively annotated (few entities per document), whereas the pipeline extracts every concept; over-extraction relative to the benchmark's selectivity is a legitimate architecture-transfer outcome and was not tuned on.", ""]  # fmt: skip
    (R / "external_e2e.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- oracle_error_attribution.md
    def row(lv, a):
        return (
            f"| {lv} | {a['misses']} | "
            + " | ".join(str(a["by_code"][c]) for c in A.CODES)
            + f" | {a['recovered']} |"
        )

    hdr = [
        "| level | misses | " + " | ".join(A.CODES) + " | recovered |",
        "|---|---|" + "---|" * (len(A.CODES) + 1),
    ]
    L = [
        "# CR-012 oracle results and earliest-failure attribution",
        "",
        "Each missed gold edge gets exactly one earliest failure code (S0/S1: NOT_APPLICABLE, CR-011 adopted no transformation). Oracle differences are **conditional / oracle uplifts**, not an additive causal decomposition.",
        "",
        "## P&D",
        "",
        *hdr,
    ]
    L += [row(lv, PD[lv]["attribution_pooled"]) for lv in ("E0", "E1", "E2", "E3", "E4")]
    L += [
        "",
        f"- E0 earliest failures: pair delivery (P0) {p0} / {miss} = {p0 / miss:.1%}; extraction (N0+N1) {ext} / {miss} = {ext / miss:.1%}; together {p0 + ext} / {miss} = {(p0 + ext) / miss:.1%}.",
        f"- E0 pair recall: {pr['reached']} / {pr['reachable_denominator']} = {pr['rate']:.1%} of gold edges whose endpoints existed reached relation classification ({pr['missing_endpoint_excluded']} gold edges excluded for a missing endpoint node).",
        f"- Largest oracle uplift: E2 -> E3, F1 {f3(f1['E2'])} -> {f3(f1['E3'])} (delta {f1['E3'] - f1['E2']:+.3f}). The frozen candidate / pair-delivery stage is the largest demonstrated in-domain end-to-end bottleneck. This is not permission to change the pair budget in CR-012.",
        f"- Relation stage: when E3 produces an edge, relation correct {rc['relation_correct']} / {rc['gold_with_proposed_edge']} = {rc['relation_correct'] / rc['gold_with_proposed_edge']:.1%}, direction correct {rc['direction_correct']} / {rc['gold_with_proposed_edge']} = {rc['direction_correct'] / rc['gold_with_proposed_edge']:.1%}.",
        "",
        "### Canonicalisation: held-out versus development pilot",
        "",
        f"Held-out: E1 {f3(f1['E1'])} -> E2 {f3(f1['E2'])}, delta {f1['E2'] - f1['E1']:+.3f}. The held-out experiment does **not** support canonicalisation as the dominant current bottleneck. The development pilot (section 1.5 only, development-only) showed E1 {f3(PILOT['E1']['strict_e2e']['f1'])} -> E2 {f3(PILOT['E2']['strict_e2e']['f1'])} (delta {PILOT['E2']['strict_e2e']['f1'] - PILOT['E1']['strict_e2e']['f1']:+.3f}) and suggested otherwise. The held-out result has priority for final conclusions; the pilot discrepancy is reported, not hidden.",
        "",
        "## SciNLP (mention level; C0/C1 not applicable)",
        "",
        *hdr,
    ]
    L += [
        row(lv.replace("E3", "E3-M").replace("E4", "E4-M"), SC[lv]["attribution_pooled"])
        for lv in SC
    ]
    L += ["", f"- E0 earliest failures are extraction: N0 {n0} / {sc_att['misses']} = {n0 / sc_att['misses']:.1%}. Cross-domain entity / concept extraction is the dominant observed SciNLP bottleneck; E0 -> E1 ({f3(sc_f1['E0'])} -> {f3(sc_f1['E1'])}) is consistent with this.",
          f"- E3-M -> E4-M ({f3(sc_f1['E3'])} -> {f3(sc_f1['E4'])}): comparatively limited remaining improvement at the classifier-ceiling step once endpoints are provided.", "",
          "Figures (generated from the frozen results): `figures/pd_oracle_waterfall.svg`, `figures/earliest_failure_distribution.svg`, `figures/headline_e0_pd_vs_scinlp.svg`.", ""]  # fmt: skip
    (R / "oracle_error_attribution.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- stability.md
    L = ["# CR-012 stability (3 independent E0 repeats, private LLM cache per repeat, all repeats reported, no best-run selection)", "",
         "Frozen subset (length rule, outcome-blind): P&D 4.5, 4.4; SciNLP P17-1058, 2021.acl-long.353.", "",
         "| benchmark | unit | F1 repeat 1 / 2 / 3 | mean | sd | node-set Jaccard | edge-set Jaccard | canonicalisation disagreement | relation disagreement |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for bn, d in (("P&D", STAB["pd"]), ("SciNLP", STAB["scinlp"])):
        for u, r in d.items():
            f = " / ".join(f3(x["strict_e2e_f1"]) for x in r["per_run"])
            L.append(f"| {bn} | {u} | {f} | {f3(r['strict_e2e_f1_mean'])} | {f3(r['strict_e2e_f1_sd'])} | {f3(r['node_set_jaccard_mean'])} | {f3(r['edge_set_jaccard_mean'])} | {f3(r['canonicalisation_disagreement_rate_mean'])} (NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR) | {f3(r['relation_disagreement_rate_mean'])} |")  # fmt: skip
    L += ["", "- Stability is generally modest, with P&D 4.4 the widest spread (F1 0.022-0.072). Node sets agree only about 0.5-0.7 and edge sets about 0.2-0.4 between repeats, so individual runs differ substantially in what they extract even where F1 is similar.",
          "- The frozen canonicalisation disagreement value is kept for reproducibility but is **NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR**: its denominator is essentially all span pairs common to two runs, so it is insensitive to the small subset of pairs where an identity decision could differ. 0.000 must not be read as evidence that canonicalisation is deterministic. The primary stability metric was not redefined after the test; a corrected metric is proposed for future work (CR-013) only.",
          "- Figure: `figures/stability.svg`.", ""]  # fmt: skip
    (R / "stability.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- unsupported_facts.md and provenance.md
    def agg_pd(lv):
        ps = [v["provenance"] for v in PD[lv]["per_section"].values()]
        return ps

    def agg_sc(lv):
        return [v["provenance"] for v in SC[lv]["per_document"].values()]

    def line(name, ps):
        n, e = sum(p["nodes"] for p in ps), sum(p["edges"] for p in ps)
        nu = n - sum(p["nodes_with_grounded_span"] for p in ps)
        eu = e - sum(p["edges_with_located_evidence_quote"] for p in ps)
        dr = sum(p["edges_dropped_without_endpoint_node"] for p in ps)
        comp = (n - nu + e - eu) / (n + e) if n + e else 1.0
        return f"| {name} | {n} | {nu} ({nu / max(n, 1):.3f}) | {e} | {eu} ({eu / max(e, 1):.3f}) | {dr} | {comp:.3f} |"

    th = [
        "| run | nodes | nodes without a grounded mention span (rate) | edges | edges without a located evidence quote (rate) | edges dropped: endpoint node absent | provenance completeness |",
        "|---|---|---|---|---|---|---|",
    ]
    L = ["# CR-012 unsupported facts", "",
         "Definitions (fixed before reading results): an **unsupported node** has no mention span that can be located inside its recorded evidence quotes (rule 24: mentions come only from the generator, with evidence); an **unsupported edge** has an evidence quote that cannot be located in the unit text. Evidence quotes are verified exact substrings at generation time (rule 3), so unsupported edges are expected to be rare.", "",
         "Distinct from this: a predicted edge that no gold edge matches is **not confirmed by the gold**, which is not the same as unsupported by the text (the gold is a single-annotator reference and may be incomplete, and SciNLP is selectively annotated). Those counts are the false-positive columns in `pd_e2e.md` / `external_e2e.md`.", "",
         "## P&D", "", *th]  # fmt: skip
    L += [line(lv, agg_pd(lv)) for lv in ("E0", "E1", "E2", "E3", "E4")]
    L += ["", "## SciNLP", "", *th]
    L += [line(lv.replace("E3", "E3-M").replace("E4", "E4-M"), agg_sc(lv)) for lv in SC]
    neg = sum(v["prediction_stats"]["negated_dropped"] for v in SC["E0"]["per_document"].values())
    ung = sum(
        v["prediction_stats"]["ungrounded_dropped"] for v in SC["E0"]["per_document"].values()
    )
    L += [
        "",
        f"SciNLP E0: {neg} negated relations were dropped (never emitted as positive edges); {ung} edges were dropped because an endpoint or the evidence span could not be grounded at token level.",
        "",
    ]
    (R / "unsupported_facts.md").write_text("\n".join(L), encoding="utf-8")

    pe = agg_pd("E0")
    n, e = sum(p["nodes"] for p in pe), sum(p["edges"] for p in pe)
    L = ["# CR-012 provenance completeness", "",
         "Every graph element is traceable to a located source quote under the frozen workflow (evidence-or-it-doesn't-enter-the-graph).", "",
         f"- P&D E0: provenance completeness {sum(p['provenance_completeness'] * (p['nodes'] + p['edges']) for p in pe) / (n + e):.3f} over {n} nodes and {e} edges (edges with located quote: {sum(p['edges_with_located_evidence_quote'] for p in pe)} / {e}).",
         f"- SciNLP E0: see `unsupported_facts.md` (completeness {sum(p['provenance_completeness'] * (p['nodes'] + p['edges']) for p in agg_sc('E0')) / max(sum(p['nodes'] + p['edges'] for p in agg_sc('E0')), 1):.3f}).",
         "- Run provenance: every model run is recorded in `reports/cr012/stop4_log.jsonl` (run id, level, tag, seconds, cumulative spend); prompt text per call is in `data/logs/llm_prompts.jsonl` (rule 16); configuration and code hashes in `frozen_hashes.json` (STOP-3 freeze plus the STOP-4 execution addendum); gold provenance in `heldout_gold_provenance.json` (sha256, single annotator).",
         "- Dataset versions: P&D 6e textbook sections (CC BY 4.0); SciNLP release `SciNLP-repo-e78342be` (`dataset_manifest.json`). Results are never mixed across dataset versions.", ""]  # fmt: skip
    (R / "provenance.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- cost.md
    L = ["# CR-012 cost", "",
         f"- Spent before STOP 4 (pilot, rehearsal, oracle development): ${SPENT_BEFORE}", f"- STOP-4 model spend: **${stop4_spend}** (main held-out ${round(sum(pd_usd.values()) + sum(sc_usd.values()), 2)}; stability repeats ${stab_usd})",
         f"- **Cumulative CR-012 spend: ${total}**. Forecast $28.09-$33.92 (approved); soft warning $40 and hard cap $50 were never reached. No optional paid benchmark was run, and STOP 5 made no model call.", "",
         "| level | P&D USD | SciNLP USD |", "|---|---|---|"]  # fmt: skip
    for lv in ("E0", "E1", "E2", "E3", "E4"):
        L.append(
            f"| {lv} | {pd_usd[lv]} | {sc_usd.get(lv, 'NOT_SUPPORTED' if lv == 'E2' else '-')} |"
        )
    L += ["", "E4 costs $0 on both benchmarks because it reuses the E3 classifications of the identical gold pairs from the cache (byte-identical calls).", "",
          f"E0 spend per correctly recovered edge: P&D ${pd_usd['E0'] / max(tp_pd, 1):.2f} ({tp_pd} correct edges); SciNLP ${sc_usd['E0'] / max(tp_sc, 1):.2f} ({tp_sc} correct relations). With so few correct edges this ratio is descriptive only and is not a cost-effectiveness claim.", "",
          "Figure: `figures/cost_per_correct_edge_e0.svg`.", ""]  # fmt: skip
    (R / "cost.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- FINAL_EVALUATION.md
    L = ["# CR-012 FINAL EVALUATION: end-to-end Expert-KG evaluation", "",
         "Written for: the examiners and Research. All numbers come from the single frozen held-out execution (`cr012-stop4-complete`, 4697acb) under the `stop3-frozen` configuration; nothing was tuned, rerun or rescored after it.", "",
         "## 1. What this evaluation is", "",
         "**Software / operational result.** The complete pipeline runs from raw text to a canonical typed graph under a frozen, reproducible workflow (hashes, run log, cache-keyed model calls, evidence-checked output).",
         "**Accuracy result.** The current frozen system has **low strict end-to-end graph accuracy**. The Expert KG must not be described as validated or high-accuracy on the basis of these results. CR-012 is not a failure: it identifies where the architecture loses accuracy, which is its research purpose.", "",
         "## 2. Headline results (two benchmarks, never pooled)", "",
         "| benchmark | headline | value |", "|---|---|---|",
         f"| P&D-E2E (in-domain, 7 held-out sections) | STRICT_E2E_EDGE P / R / F1, E0 | **{prf(e0['pooled_strict_e2e'])}**; section-bootstrap interval [{f3(ci['ci']['f1'][0])}, {f3(ci['ci']['f1'][1])}], DESCRIPTIVE_SMALL_N |",
         f"| SciNLP (external, 3 test documents) | strict relation P / R / F1, E0 | **{prf(SC['E0']['aggregates']['rel']['micro'])}**; CI_status NOT_EVALUABLE_SMALL_N; per-document / macro / min-max in `external_e2e.md` |", "",
         "The annotation schemas differ (P&D: exhaustive canonical-graph gold with 17 relations; SciNLP: selective mention-level gold with 11 relations), so the two E0 numbers are not comparable accuracy scores (`figures/headline_e0_pd_vs_scinlp.svg`).", "",
         "## 3. Where accuracy is lost (hypotheses supported by the oracle runs; conditional / oracle uplifts, not an additive decomposition)", "",
         f"- **P&D main bottleneck: candidate pair / endpoint delivery.** {p0 + ext} / {miss} = {(p0 + ext) / miss:.1%} of earliest E0 misses are extraction or pair delivery (P0 {p0 / miss:.1%}, N0+N1 {ext / miss:.1%}). Pair recall at E0 is {pr['reached']} / {pr['reachable_denominator']} = {pr['rate']:.1%}. Largest oracle uplift E2 -> E3: {f3(f1['E2'])} -> {f3(f1['E3'])}.",
         f"- **Relation classification** is not solved but is much stronger than E0 suggests: {rc['relation_correct'] / rc['gold_with_proposed_edge']:.1%} relation / {rc['direction_correct'] / rc['gold_with_proposed_edge']:.1%} direction correct on E3 pairs. E4 ({f3(f1['E4'])}) is a gold-endpoint ceiling, not production accuracy.",
         f"- **Canonicalisation** is not the dominant held-out bottleneck (E1 {f3(f1['E1'])} -> E2 {f3(f1['E2'])}); the development pilot suggested otherwise and the held-out result takes priority.",
         f"- **SciNLP main bottleneck: entity / concept extraction** ({n0} / {sc_att['misses']} = {n0 / sc_att['misses']:.1%} of E0 misses; E0 {f3(sc_f1['E0'])} -> E1 {f3(sc_f1['E1'])}). E3-M - E1 is the post-mention / endpoint-delivery loss (no E2 identity oracle); E3-M -> E4-M {f3(sc_f1['E3'])} -> {f3(sc_f1['E4'])}.", "",
         "## 4. Stability, support and provenance", "",
         "- Three independent repeats on the frozen subset: generally modest stability, P&D 4.4 the widest (F1 0.022-0.072). The canonicalisation-disagreement statistic is NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR (`stability.md`).",
         f"- Unsupported nodes / edges and provenance completeness (E0 P&D): see `unsupported_facts.md` and `provenance.md` (provenance completeness {sum(p['provenance_completeness'] * (p['nodes'] + p['edges']) for p in pe) / (n + e):.3f}).", "",
         "## 5. CR-011", "", f"CR011_PRE_POST = {NA}. CR-011 adopted no production graph transformation, so no pre/post comparison and no delta_F1_sleep exist or are reported.", "",
         "## 6. Cost", "", f"STOP-4 spend ${stop4_spend}; cumulative CR-012 spend **${total}**, within the approved budget (`cost.md`).", "",
         "## 7. Limitations", "",
         "1. **Single annotator** for the P&D held-out gold: inter-annotator agreement NOT_EVALUABLE_SINGLE_ANNOTATOR. The LLM prefill was reviewed by the owner and is not a second annotator. This weakens certainty in the exact gold graph.",
         "2. **Small n**: 7 P&D sections and 3 SciNLP documents; one SciNLP test document has only one gold relation. Intervals are descriptive.",
         "3. Annotation schemas and densities differ between the benchmarks; SciNLP is selectively annotated while the pipeline extracts exhaustively, which depresses strict precision by construction.",
         "4. SciNLP E3-M / E4-M use surface-level pseudo-nodes; SciNLP identity metrics, E2 and canonical-node scores are NOT_SUPPORTED.",
         "5. Strict scoring (exact spans, types, relations, direction) is deliberately harsh; the scores are not a measure of human-judged usefulness of the graph.",
         "6. One system recipe (CR-009 `slice3_c2` with the frozen D3 pair budget) and one execution; no ablation of the budget or ranking was run, by design.",
         "7. The development pilot and held-out results disagree on the canonicalisation share; the held-out result is used.",
         "8. The stability disagreement metric is non-informative under its frozen denominator.",
         "9. The pair budget (14.2 pairs / 1k words) was saturated in all 10 held-out E0 units (pool larger than budget, selected = budget), so pair-delivery results are specific to that budget.", "",
         "## 8. Process record", "",
         "One execution defect (an over-eager leakage assertion that false-positived on words of the book sentence in the section 4.4 E3 oracle; stopped before any spend, fixed, logged in `invalid_runs.md`). Earlier development-time converter defects are likewise logged. No result was discarded or selected.", "",
         "## 9. Reports and figures", "",
         "`pd_e2e.md`, `external_e2e.md`, `oracle_error_attribution.md`, `stability.md`, `unsupported_facts.md`, `provenance.md`, `cost.md`, `CR012_FAILURE_ANALYSIS.md`; `figures/*.svg`. CR-011 consolidation: NOT APPLICABLE, no production transformation adopted (no fake pre/post chart is produced).", ""]  # fmt: skip
    (R / "FINAL_EVALUATION.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- CR012_FAILURE_ANALYSIS.md
    L = ["# CR-012 failure analysis and future research hypotheses", "",
         "This document proposes follow-up research. It does **not** modify CR-012; none of it was implemented or tested here.", "",
         "## Failure taxonomy (measured, held-out)", "", "| stage | P&D E0 share of misses | SciNLP E0 share of misses |", "|---|---|---|"]  # fmt: skip
    for c, nm in (
        ("N0", "concept not extracted"),
        ("N1", "wrong / partial span"),
        ("C0", "concept split"),
        ("C1", "false merge"),
        ("P0", "pair not delivered"),
        ("R0", "classifier said no relation"),
        ("R1", "wrong relation"),
        ("R2", "wrong direction"),
        ("R3", "type / qualifier"),
        ("E0", "evidence invalid"),
    ):
        L.append(
            f"| {c} {nm} | {b[c]} ({b[c] / miss:.1%}) | {sc_att['by_code'][c]} ({sc_att['by_code'][c] / sc_att['misses']:.1%}) |"
        )
    L += ["", "## Hypotheses (for later change requests)", "",
          f"1. **High-recall pair delivery / candidate generation.** In P&D, {p0 / miss:.1%} of E0 misses are P0 and pair recall is {pr['rate']:.1%}; the oracle uplift E2 -> E3 is the largest ({f1['E3'] - f1['E2']:+.3f}). Hypothesis: a higher-recall, budget-aware candidate stage would recover more gold edges. To test: recall-vs-cost curves on development data, then a single held-out confirmation.",
          "2. **Concept extraction recall, especially out of domain.** In SciNLP, N0 dominates (89.8%) and E0 -> E1 is the largest uplift. Hypothesis: domain-adaptive extraction (without over-narrowing precision) is the lever for external transfer.",
          "3. **Relation acceptance / classification after endpoint recovery.** At E3, about 30% of pairs with an edge have the wrong relation or direction, and many gold pairs receive no relation (R0). Hypothesis: calibrated acceptance and relation choice could raise the ceiling above E4 = 0.470.",
          "4. **Redesign the canonicalisation stability diagnostic.** The frozen disagreement rate is non-informative under its denominator. Proposal (future work / CR-013, not applied post-test): restrict the denominator to candidate identity decisions (pairs of mentions that either run linked, or that share a surface form), and report counts alongside the rate.",
          "5. **Independently double-annotated P&D gold.** Obtain a second human annotator on at least 25-30% of the held-out sections (4.4 and 9.3 were designated) and report agreement before drawing stronger conclusions about the exact gold graph.", "",
          "## Not recommended from these results", "",
          "- Changing the pair budget, ranking, coverage policy or thresholds inside CR-012 based on these numbers.",
          "- Narrowing concept extraction because SciNLP precision is low (over-extraction relative to selective annotation is an architecture-transfer outcome).",
          "- Reading E4 as achievable accuracy, or summing oracle uplifts as if they were additive.", ""]  # fmt: skip
    (R / "CR012_FAILURE_ANALYSIS.md").write_text("\n".join(L), encoding="utf-8")
    print(
        "written", sorted(p.name for p in R.glob("*.md")), sorted(p.name for p in FIG.glob("*.svg"))
    )


if __name__ == "__main__":
    main()
