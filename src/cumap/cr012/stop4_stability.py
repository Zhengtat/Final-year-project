"""CR-012 STOP 4 stability report: three independent E0 repeats (private LLM caches) on the frozen subset. All runs are listed; no best run."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012 import stability as ST
from cumap.cr012.adapters import SciNLPAdapter

CFG = yaml.safe_load((REPO_ROOT / "configs/cr012_e2e_eval.yaml").read_text())


def pd_run(i: int, sid: str, gold, text: str, sym: set[str]) -> ST.RunGraph:
    rid = f"cr012_stab{i}_{sid.replace('.', '_')}_E0"
    cp = PG.load_run(rid)
    pg = PG.graph_for_sections(cp, {sid: text})[sid]
    f1 = S.score_graph_unit(gold, pg["nodes"], pg["edges"], sym)["strict_e2e_edge"].f1
    return ST.RunGraph(
        rid, tuple(pg["nodes"]), tuple(pg["edges"]), f1, f"data/cache/cr012_stability/run_{i}"
    )


def sc_run(i: int, doc, gold, sym: set[str]) -> ST.RunGraph:
    rid = f"cr012_scinlp_stab{i}_{doc.doc_key.replace('.', '_').replace('-', '_')}_E0"
    cp = json.loads((REPO_ROOT / "data/processed/kg" / rid / "checkpoint.json").read_text())
    pred = SR.predict(doc, cp)
    rels, _ = S.project_edges_to_mentions(pred["nodes"], pred["edges"])
    f1 = S.score_scinlp_unit(gold, S.project_nodes_to_mentions(pred["nodes"]), rels, sym)["rel"].f1
    return ST.RunGraph(
        rid, tuple(pred["nodes"]), tuple(pred["edges"]), f1, f"data/cache/cr012_stability/run_{i}"
    )


def main() -> None:
    sub, n = CFG["stability"]["subset"], CFG["stability"]["repeats"]
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    gold, problems = PD.load_gold(Path("data/gold/pd_e2e_test_blind.csv"), secs, PD.registry())
    assert not problems
    sym = {r.name for r in PD.registry().all_relations() if r.symmetric}
    ad = SciNLPAdapter()
    docs = {d.doc_key: d for d in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY)}
    sg, ssym = ad.gold("test"), ad.symmetric_relations()
    out: dict = {"pd": {}, "scinlp": {}, "selection": "none: all runs listed"}
    for sid in map(str, sub["pd_sections"]):
        out["pd"][sid] = ST.stability_report(
            [pd_run(i, sid, gold[sid], secs[sid], sym) for i in range(1, n + 1)]
        )
    for dk in sub["scinlp_documents"]:
        out["scinlp"][dk] = ST.stability_report(
            [sc_run(i, docs[dk], sg[dk], ssym) for i in range(1, n + 1)]
        )
    (REPO_ROOT / "reports/cr012/stop4_stability.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8"
    )
    L = ["# CR-012 STOP 4 stability (3 independent E0 repeats, private caches, no best-run selection)", "",
         "| benchmark | unit | F1 per run | mean | sd | node Jaccard | edge Jaccard | canonicalisation disagreement | relation disagreement |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for b in ("pd", "scinlp"):
        for u, r in out[b].items():
            f = ", ".join(f"{x['strict_e2e_f1']:.3f}" for x in r["per_run"])
            sd = r["strict_e2e_f1_sd"]
            L.append(f"| {b} | {u} | {f} | {r['strict_e2e_f1_mean']:.3f} | {sd:.3f} | {r['node_set_jaccard_mean']:.3f} | {r['edge_set_jaccard_mean']:.3f} | {r['canonicalisation_disagreement_rate_mean']:.3f} | {r['relation_disagreement_rate_mean']:.3f} |")  # fmt: skip
    (REPO_ROOT / "reports/cr012/stop4_stability.md").write_text(
        "\n".join(L) + "\n", encoding="utf-8"
    )
    print("\n".join(L))


if __name__ == "__main__":
    main()
