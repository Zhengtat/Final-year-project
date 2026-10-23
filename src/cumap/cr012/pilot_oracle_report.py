"""CR-012 STOP 3: score the pilot oracle runs (E0-E4) of one section against the reviewed pilot gold. Development rehearsal only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scoring as S
from cumap.llm.cost import spend_from_log


def _ran(run_id: str) -> bool:
    f = REPO_ROOT / "data/processed/kg" / run_id / "checkpoint.json"
    return f.exists() and bool(json.loads(f.read_text()).get("relation_results_v3"))


def score_run(run_id: str, sid: str, gold, text: str, sym: set[str]) -> dict:
    cp = PG.load_run(run_id)
    pg = PG.graph_for_sections(cp, {sid: text})[sid]
    r = S.score_graph_unit(
        gold, pg["nodes"], pg["edges"], sym, proposed_pairs=PG.proposed_pairs(cp, sid)
    )
    q = r["strict_e2e_edge"]
    rc = r["relation_conditional"]
    pr = r["pair_recall"]
    return {
        "run": run_id,
        "strict_e2e": q.to_dict(),
        "gold_headline_edges": pr["gold_edges"],
        "pair_recall": {
            "reached": pr["reached_classification"],
            "reachable": pr["denominator"],
            "missing_endpoint_excluded": pr["missing_endpoint_excluded"],
            "rate": pr["pair_recall"],
        },
        "canonical_node_f1": r["canonical_node"].f1,
        "concept_mentions_typed_f1": r["concept_mentions_typed"].f1,
        "identity_pairwise_f1": r["identity"]["pairwise"]["f1"],
        "bcubed_f1": (r["identity"]["bcubed"] or {}).get("f1"),
        "relation_given_pair": {
            "gold_pairs_with_proposed_edge": rc.get("gold_with_proposed_edge", 0),
            "relation_correct": rc.get("relation_correct", 0),
            "direction_correct": rc.get("direction_correct", 0),
        },
        "qualifier_accuracy": r["qualifier_accuracy"],
        "predicted_edges": len(pg["edges"]),
        "false_merge_nodes": len(r["alignment"]["false_merge_nodes"]),
        "split_concepts": len(r["alignment"]["split_concepts"]),
        "usd": round(spend_from_log(get_settings(), run_id), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", required=True)
    ap.add_argument("--pilot-sheet", required=True)
    a = ap.parse_args()
    sid = a.section
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    gold, problems = PD.load_gold(Path(a.pilot_sheet), secs, PD.registry())
    assert not problems
    sym = {r.name for r in PD.registry().all_relations() if r.symmetric}
    tag = sid.replace(".", "_")
    out = {
        o: score_run(f"cr012_pilot_{tag}_{o}", sid, gold[sid], secs[sid], sym)
        for o in ("E0", "E1", "E2", "E3", "E4")
        if _ran(f"cr012_pilot_{tag}_{o}")
    }  # oracle levels that were not run live for this section (a dry-run leaves an empty checkpoint) are absent
    p = REPO_ROOT / "reports/cr012/pilot_oracles.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old[sid] = out
    p.write_text(json.dumps(old, indent=1), encoding="utf-8")
    for o, v in out.items():
        q = v["strict_e2e"]
        print(
            o,
            "P/R/F1",
            round(q["precision"], 3),
            round(q["recall"], 3),
            round(q["f1"], 3),
            "tp",
            q["tp"],
            "fp",
            q["fp"],
            "fn",
            q["fn"],
            "| pair recall",
            v["pair_recall"]["reached"],
            "/",
            v["pair_recall"]["reachable"],
            "| canon F1",
            round(v["canonical_node_f1"], 3),
            "| mention F1",
            round(v["concept_mentions_typed_f1"], 3),
            "| rel|pair",
            v["relation_given_pair"],
            "| qual",
            v["qualifier_accuracy"],
            "| usd",
            v["usd"],
        )


if __name__ == "__main__":
    main()
