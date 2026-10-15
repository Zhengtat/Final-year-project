"""Comparison report for the 2026-10-16 rebuild with the current production settings (R1-key matching + rejected-link adjudicator).
$0, read-only; writes reports/cr021/rebuild.{json,md}. Frozen results are printed beside the rebuilds and never replaced.

    uv run python -m cumap.cr021.rebuild_report"""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr017 import headline as HL
from cumap.cr017 import run as R17
from cumap.cr019 import stage_b as SB
from cumap.cr019 import variants as V
from cumap.llm.cost import spend_from_log

OUT = REPO_ROOT / "reports/cr021"
TEST = ["2021.acl-long.353", "2024.acl-long.108-1-9.grobid", "P17-1058.grobid"]
SCORERS = ("FROZEN", "FROZEN-UNPLACED-FP", "IDX-P1", "IDXR1-P1", "IDXR1-P3")


def slug(d: str) -> str:
    return d.replace(".", "_").replace("-", "_")


def runs() -> dict:
    return {
        "scinlp_test": {d: (f"cr012_scinlp_heldout_{slug(d)}_E0", f"cr012_scinlp_cr021test_{slug(d)}_E0") for d in TEST},
        "scinlp_dev": {d: (SB.sc_base(d), f"cr012_scinlp_cr021dev_{slug(d)}_E0") for d in SB.SC_DEV},
        "pd": {"chapters 1-3": ("slice3_c2", "slice3_c3")},
    }  # fmt: skip


def graph_stats(rid: str) -> dict:
    cp = PG.load_run(rid)
    v4 = json.loads((PG.run_path(rid) / "v4_concepts.json").read_text())
    merges = Counter(m["rule_id"] for m in v4.get("merges", []))
    adj = Counter(
        m.get("decision") for m in v4.get("merges", []) if m["rule_id"] == "G-link-adjudicated"
    )
    edges = sum(
        1
        for r in cp["relation_results_v3"]
        if r["outcome"] == "edge" and r.get("group", "selected") == "selected"
    )
    return {"concepts": len(cp["concepts"]), "aliases": sum(len(c.get("aliases", [])) for c in cp["concepts"]), "edges": edges,
            "selected_pairs": len(cp["selected_pairs"]), "rejected_links": merges.get("G-link-rejected", 0), "adjudicated": dict(adj),
            "matching_mode": cp["selection_stats"].get("matching_mode", "token"), "spend_usd": round(spend_from_log(get_settings(), rid), 4)}  # fmt: skip


def scinlp(split: str, pairs: dict) -> dict:
    ad = SciNLPAdapter()
    gold, sym = ad.gold(split), ad.symmetric_relations()
    docs = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}
    out = {}
    for arm, i in (("before", 0), ("rebuild", 1)):
        per = {v: {} for v in SCORERS}
        for d, rr in pairs.items():
            f = PG.run_path(rr[i]) / "checkpoint.json"
            if not f.exists():
                continue
            cp = json.loads(f.read_text())
            if not cp.get("relation_results_v3"):
                continue
            for v in SCORERS:
                per[v][d] = V.sc_score(docs[d], gold[d], cp, sym, v)["scores"]
        out[arm] = {
            "documents": sorted(per["FROZEN"]),
            "relation": {v: S.aggregate_documents(per[v], "rel")["micro"] for v in SCORERS if per[v]},
            "concept_entity_strict": {v: S.aggregate_documents(per[v], "entity_strict")["micro"] for v in ("FROZEN", "IDXR1-P1") if per[v]},
            "graphs": {d: graph_stats(rr[i]) for d, rr in pairs.items() if (PG.run_path(rr[i]) / "checkpoint.json").exists()},
        }  # fmt: skip
    return out


def pd_dev_sections() -> dict:
    """The P&D development answer key (sections 1.5, 2.6) scored on each whole-slice graph, restricted to those sections."""
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    sheet, sections = R17.SHEETS["pilot"]
    reg = PD.registry()
    gold, problems = PD.load_gold(R17.ROOT / sheet, secs, reg)
    assert not problems, problems[:2]
    sym = {r.name for r in reg.all_relations() if r.symmetric}
    out = {}
    for rid in ("slice3_c2", "slice3_c3"):
        if not (PG.run_path(rid) / "checkpoint.json").exists():
            continue
        cp = PG.load_run(rid)
        if not cp.get("relation_results_v3"):
            continue
        units = {}
        for sid in sections:
            g = PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
            units[sid] = HL.UnitInput(gold[sid], g["nodes"], g["edges"], PG.proposed_pairs(cp, sid), HL.classifier_from_checkpoint(cp, sid))  # fmt: skip
        h = HL.evaluate(units, sym, boot=False)["headline"]
        out[rid] = {k: (h[k].get("f1") if k != "pair_recall" else h[k].get("recall")) for k in h}
    return out


def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def markdown(r: dict) -> str:
    L = ["# Rebuild with the current production settings (2026-10-16)", "",
         "R1-key matching (CR-020) + rejected-link adjudicator (CR-021), new run ids; frozen results unchanged and shown as `before`. SciNLP test: owner-approved final-reporting run (DECISIONS 2026-10-16).", ""]  # fmt: skip
    for key, title in (
        ("scinlp_test", "SciNLP test (3 papers)"),
        ("scinlp_dev", "SciNLP dev (6 papers)"),
    ):
        x = r[key]
        L += [
            f"## {title}",
            "",
            "| scorer | before P / R / F1 | rebuild P / R / F1 |",
            "|---|---|---|",
        ]
        for v in SCORERS:
            b, a = x["before"]["relation"].get(v), x["rebuild"]["relation"].get(v)
            if b and a:
                L.append(
                    f"| strict relation `{v}` | {_f(b['precision'])} / {_f(b['recall'])} / **{_f(b['f1'])}** | {_f(a['precision'])} / {_f(a['recall'])} / **{_f(a['f1'])}** |"
                )
        for v in ("FROZEN", "IDXR1-P1"):
            b, a = (
                x["before"]["concept_entity_strict"].get(v),
                x["rebuild"]["concept_entity_strict"].get(v),
            )
            if b and a:
                L.append(
                    f"| concept (entity strict) `{v}` | {_f(b['precision'])} / {_f(b['recall'])} / {_f(b['f1'])} | {_f(a['precision'])} / {_f(a['recall'])} / {_f(a['f1'])} |"
                )
        sb = Counter()
        sa = Counter()
        for g in x["before"]["graphs"].values():
            sb.update({k: v for k, v in g.items() if isinstance(v, (int, float))})
        for g in x["rebuild"]["graphs"].values():
            sa.update({k: v for k, v in g.items() if isinstance(v, (int, float))})
            sa.update({f"adjudicated:{k}": v for k, v in g["adjudicated"].items()})
        L += ["", f"Graphs before: {dict(sb)}", f"Graphs rebuilt: {dict(sa)}", ""]
    p = r["pd"]
    L += ["## P&D chapters 1-3: `slice3_c2` (production) vs `slice3_c3` (rebuild)", "", f"- slice3_c2: {p['graphs'].get('slice3_c2')}", f"- slice3_c3: {p['graphs'].get('slice3_c3')}", "",
          "Five metrics on the P&D development answer key (sections 1.5, 2.6), each whole-slice graph restricted to those sections:", "", "| run | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 | Strict E2E Edge F1 |", "|---|---|---|---|---|---|"]  # fmt: skip
    for rid, h in p["dev_sections"].items():
        L.append(
            f"| {rid} | {_f(h['concept_f1'])} | {_f(h['ancestor_hierarchy_f1'])} | {_f(h['pair_recall'])} | {_f(h['relation_macro_f1'])} | {_f(h['strict_e2e_edge_f1'])} |"
        )
    L += ["", f"Total rebuild spend: **${r['spend_usd']:.2f}**"]
    return "\n".join(L) + "\n"


def main() -> dict:
    rr = runs()
    r = {"scinlp_test": scinlp("test", rr["scinlp_test"]), "scinlp_dev": scinlp("dev", rr["scinlp_dev"]),
         "pd": {"graphs": {rid: graph_stats(rid) for rid in ("slice3_c2", "slice3_c3") if (PG.run_path(rid) / "checkpoint.json").exists()}, "dev_sections": pd_dev_sections()}}  # fmt: skip
    st = get_settings()
    r["spend_usd"] = round(
        sum(spend_from_log(st, x[1]) for k in ("scinlp_test", "scinlp_dev") for x in rr[k].values())
        + spend_from_log(st, "slice3_c3"),
        4,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rebuild.json").write_text(json.dumps(r, indent=1, default=str))
    (OUT / "rebuild.md").write_text(markdown(r))
    return {"report": str(OUT / "rebuild.md"), "spend_usd": r["spend_usd"]}


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
