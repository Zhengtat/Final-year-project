"""CR-017 STOP 2 evidence ($0, no model): ancestor-pair examples from the frozen gold, a perfect-prediction sanity check on every annotated section, and a code-path run on the frozen CR-012 E0
checkpoints (counts to prove the scorer runs end to end; the official historical numbers belong to the STOP-4 replay)."""

from __future__ import annotations

import json
from pathlib import Path

from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012.types import PredEdge, PredNode
from cumap.cr017 import hierarchy as H

ROOT = Path(".")
SETS = [
    ("pilot", "data/gold/pd_e2e_pilot_blind.csv", ["1.5", "2.6"]),
    (
        "heldout",
        "data/gold/pd_e2e_test_blind.csv",
        ["4.4", "4.5", "5.4", "6.3", "7.1", "8.2", "9.3"],
    ),
]


def main() -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    reg = PD.registry()
    out: dict = {"perfect_prediction": {}, "examples": {}, "e0_code_path": {}, "e0_pooled": {}}
    e0_units: dict[str, dict] = {}
    for name, sheet, sections in SETS:
        gold, problems = PD.load_gold(ROOT / sheet, secs, reg)
        assert not problems
        for sid in sections:
            g = gold[sid]
            names = {c.concept_id: c.name for c in g.concepts}
            # perfect prediction: one node per gold concept grounded on that concept's own mentions, edges copied from gold
            by_c: dict[str, list] = {}
            for m in g.mentions:
                if m.concept_id:
                    by_c.setdefault(m.concept_id, []).append(m.span)
            nodes = [
                PredNode(f"n:{c}", sid, "Concept", names[c], tuple(sp)) for c, sp in by_c.items()
            ]
            edges = [
                PredEdge(sid, f"n:{r.src_concept}", f"n:{r.tgt_concept}", r.relation)
                for r in g.relations
                if r.src_concept in by_c and r.tgt_concept in by_c
            ]
            r = H.score_hierarchy_unit(g, nodes, edges)
            out["perfect_prediction"][sid] = {
                "gold_pairs": r["gold_ancestor_pairs"],
                "f1": r["ancestor_hierarchy"].f1,
            }
            gp = H.gold_pairs(g)
            direct = gp.direct_edges
            added = sorted(gp.pairs - direct)
            if added:
                out["examples"][sid] = {
                    "direct_edges_sample": [
                        f"{names[a]} -> {names[b]}" for a, b in sorted(direct)[:4]
                    ],
                    "pairs_added_by_closure": [f"{names[a]} => {names[b]}" for a, b in added[:5]],
                }
            # code path on the frozen E0 run
            rid = f"cr012_{name}_{sid.replace('.', '_')}_E0"
            pg = PG.graph_for_sections(PG.load_run(rid), {sid: secs[sid]})[sid]
            e = H.score_hierarchy_unit(g, pg["nodes"], pg["edges"])
            out["e0_code_path"][sid] = {
                "set": name,
                "gold_pairs": e["gold_ancestor_pairs"],
                "predicted_pairs": e["predicted_ancestor_pairs"],
                "tp_fp_fn": [
                    e["ancestor_hierarchy"].tp,
                    e["ancestor_hierarchy"].fp,
                    e["ancestor_hierarchy"].fn,
                ],
                "predicted_cycles": e["predicted_cycles"],
            }
            if name == "heldout":
                e0_units[sid] = e
    pooled = H.pool(e0_units)
    out["e0_pooled"] = {
        "heldout_7_sections": pooled.to_dict(),
        "status": "CODE-PATH CHECK ONLY (CI_status NOT_EVALUABLE_SMALL_N); the reported historical scores come from the STOP-4 replay",
    }
    out["cycle_summary"] = {
        "gold_cycles": 0,
        "predicted_cycles_in_E0_runs": sum(
            len(v["predicted_cycles"]) for v in out["e0_code_path"].values()
        ),
    }
    Path("reports/cr017/stop2_hierarchy.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    o = main()
    print(
        json.dumps(
            {k: o[k] for k in ("perfect_prediction", "e0_pooled", "cycle_summary")}, indent=1
        )
    )
    print(json.dumps(o["e0_code_path"], indent=0)[:1200])
    print(json.dumps(o["examples"], indent=0)[:1800])
