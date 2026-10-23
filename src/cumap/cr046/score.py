"""CR-046 scoring ($0): BASE vs AMEND on the same concepts and pairs, P&D development sections 1.5 / 2.6, pilot gold sheet.
Applies the rule pre-registered in docs/DECISIONS.md. Writes reports/cr046/qualifier_amendments.{json,md}."""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr017 import headline as HL
from cumap.cr017 import run as R17
from cumap.cr019 import stage_b as SB
from cumap.cr046 import run as R

OUT = REPO_ROOT / "reports" / "cr046"
LIMIT = 0.01  # pre-registered: Strict E2E F1 and Relation Macro F1 may fall by at most 0.01


def _selected(cp: dict) -> list[dict]:
    return [r for r in cp["relation_results_v3"] if r.get("group", "selected") == "selected"]


def _key(r: dict) -> tuple:
    p = r["pair"]
    return (p["section_id"], p["concept_x_id"], p["concept_y_id"], p["sentence"])


def qualifier_stats(rows: list[dict]) -> dict:
    edges = [r for r in rows if r["outcome"] == "edge"]
    q = [r.get("qualifiers") or {} for r in edges]
    long_phrase = sum(
        1
        for r, x in zip(edges, q, strict=True)
        if x.get("surface_phrase")
        and len(x["surface_phrase"]) >= len(r.get("evidence_quote") or "")
    )
    return {
        "outcomes": dict(Counter(r["outcome"] if r["outcome"] != "rejected" else f"rejected:{r.get('reason')}" for r in rows)),
        "no_relation_reasons": dict(Counter(r.get("reason") for r in rows if r["outcome"] == "no_relation" and r.get("reason"))),
        "edges": len(edges),
        "polarity": dict(Counter(x.get("polarity") for x in q)),
        "modality": dict(Counter(x.get("modality") for x in q)),
        "part_type_set": sum(1 for x in q if x.get("part_type")),
        "dimension_qualifier_set": sum(1 for x in q if x.get("dimension")),
        "surface_phrase_as_long_as_quote": long_phrase,
        "contrasts_with_edges": sum(1 for r in edges if r["relation"] == "contrasts_with"),
        "contrasts_with_with_dimension": sum(1 for r in edges if r["relation"] == "contrasts_with" and r.get("comparison_dimension")),
    }  # fmt: skip


def agreement(base: list[dict], amend: list[dict]) -> dict:
    """Qualifier agreement on edges both arms produced with the same relation and direction for the same pair."""
    b = {_key(r): r for r in base if r["outcome"] == "edge"}
    a = {_key(r): r for r in amend if r["outcome"] == "edge"}
    both = [
        (b[k], a[k])
        for k in b.keys() & a.keys()
        if (b[k]["relation"], b[k].get("direction")) == (a[k]["relation"], a[k].get("direction"))
    ]
    out = {
        "pairs_classified_by_both": len({_key(r) for r in base} & {_key(r) for r in amend}),
        "same_edge_both_arms": len(both),
    }
    for f in ("polarity", "modality", "part_type"):
        out[f"{f}_agree"] = sum(
            1
            for x, y in both
            if (x.get("qualifiers") or {}).get(f) == (y.get("qualifiers") or {}).get(f)
        )
    out["modality_never_to"] = dict(Counter((y.get("qualifiers") or {}).get("modality") for x, y in both if (x.get("qualifiers") or {}).get("modality") == "never"))  # fmt: skip
    out["relation_agree_on_edges_of_either"] = sum(
        1 for k in b.keys() | a.keys() if k in b and k in a and b[k]["relation"] == a[k]["relation"]
    )
    out["edges_of_either"] = len(b.keys() | a.keys())
    return out  # fmt: skip


def main() -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    sheet, _ = R17.SHEETS["pilot"]
    reg = PD.registry()
    gold, problems = PD.load_gold(R17.ROOT / sheet, secs, reg)
    assert not problems, problems[:2]
    sym = {r.name for r in reg.all_relations() if r.symmetric}
    res: dict = {"sections": SB.PD_DEV, "gold_sheet": sheet, "arms": {}}
    rows: dict = {}
    for arm in R.ARMS:
        units, arm_rows = {}, []
        for sid in SB.PD_DEV:
            cp = PG.load_run(R.arm_id(sid, arm))
            arm_rows += _selected(cp)
            g = PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
            units[sid] = HL.UnitInput(gold[sid], g["nodes"], g["edges"], PG.proposed_pairs(cp, sid), HL.classifier_from_checkpoint(cp, sid))  # fmt: skip
        rows[arm] = arm_rows
        res["arms"][arm] = {"headline": HL.evaluate(units, sym, boot=False)["headline"], "qualifiers": qualifier_stats(arm_rows)}  # fmt: skip
    res["agreement"] = agreement(rows["BASE"], rows["AMEND"])
    h = {a: res["arms"][a]["headline"] for a in R.ARMS}
    d_strict = h["AMEND"]["strict_e2e_edge_f1"]["f1"] - h["BASE"]["strict_e2e_edge_f1"]["f1"]
    d_macro = h["AMEND"]["relation_macro_f1"]["f1"] - h["BASE"]["relation_macro_f1"]["f1"]
    res["decision"] = {
        "status": "ADOPT_V6" if d_strict >= -LIMIT and d_macro >= -LIMIT else "KEEP_OFF",
        "strict_e2e_f1_delta": d_strict,
        "relation_macro_f1_delta": d_macro,
        "rule": "adopt qualifier_amendments v6 if pooled Strict E2E F1 and Relation Macro F1 (P&D dev 1.5 + 2.6, pilot gold) each fall by at most 0.01 vs BASE",
    }  # fmt: skip
    res["spend"] = R.spend()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qualifier_amendments.json").write_text(
        json.dumps(res, indent=1, default=str), encoding="utf-8"
    )
    (OUT / "qualifier_amendments.md").write_text(markdown(res), encoding="utf-8")
    return res["decision"]


def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def markdown(r: dict) -> str:
    L = [
        "# CR-046: qualifier amendments (CR-038 v6) measured on P&D development sections",
        "",
        (f"Generated by `cumap.cr046.score` ($0). Sections {', '.join(r['sections'])}; gold sheet `{r['gold_sheet']}`; same concepts and selected pairs in both arms "
        "(copied from `cr020_r1key_cr012_pilot_*_E0`); luna profile; `qualifier_checks: v1` in both arms."),
        "",
        "| arm | concept F1 | pair recall | relation macro F1 | strict E2E F1 (P / R) |",
        "|---|---|---|---|---|",
    ]  # fmt: skip
    for arm, v in r["arms"].items():
        h = v["headline"]
        se = h["strict_e2e_edge_f1"]
        L.append(f"| {arm} | {_f(h['concept_f1']['f1'])} | {_f(h['pair_recall']['recall'])} | {_f(h['relation_macro_f1']['f1'])} | {_f(se['f1'])} ({_f(se['precision'])} / {_f(se['recall'])}) |")  # fmt: skip
    d = r["decision"]
    L += ["", f"**Decision ({d['rule']}): {d['status']}** (strict E2E delta {d['strict_e2e_f1_delta']:+.3f}, macro delta {d['relation_macro_f1_delta']:+.3f}).", "", "## Qualifiers", "", "| | BASE | AMEND |", "|---|---|---|"]  # fmt: skip
    for k in r["arms"]["BASE"]["qualifiers"]:
        L.append(
            f"| {k} | {r['arms']['BASE']['qualifiers'][k]} | {r['arms']['AMEND']['qualifiers'][k]} |"
        )
    L += ["", "## Agreement on the same edges", "", *[f"- {k}: {v}" for k, v in r["agreement"].items()], "", f"Spend: ${r['spend']['total_usd']} of ${r['spend']['cap_usd']}.", ""]  # fmt: skip
    return "\n".join(L)
