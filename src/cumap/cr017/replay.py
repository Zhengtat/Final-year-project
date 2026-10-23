"""CR-017 STOP 4: replay the unified evaluator over frozen CR-012 prediction artefacts (no model call, nothing written into a source run).

uv run python -m cumap.cr017.replay"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr017 import run as R

ROOT = Path(".")
OUT = ROOT / "reports/cr017"
FROZEN = json.loads((ROOT / "reports/cr012/stop4_heldout_results.json").read_text())
LEVELS_PD = ["E0", "E1", "E2", "E3", "E4"]
LEVELS_SC = ["E0", "E1", "E3", "E4"]
SC_DOCS = ["2021.acl-long.353", "2024.acl-long.108-1-9.grobid", "P17-1058.grobid"]
WATCH = ["reports/cr012", "data/gold/pd_e2e_pilot_blind.csv", "data/gold/pd_e2e_test_blind.csv"]


def hash_tree() -> dict[str, str]:
    files = []
    for w in WATCH:
        p = ROOT / w
        files += [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
    files += sorted(ROOT.glob("data/processed/kg/cr012_*/checkpoint.json"))
    return {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def scinlp_replay(level: str) -> dict:
    ad = SciNLPAdapter()
    gold_all = ad.gold("test")
    dmap = {d.doc_key: d for d in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY)}
    sym = ad.symmetric_relations()
    per, codes_all = {}, []
    for dk in SC_DOCS:
        rid = f"cr012_scinlp_heldout_{dk.replace('.', '_').replace('-', '_')}_{level}"
        f = ROOT / "data/processed/kg" / rid / "checkpoint.json"
        if not f.exists():
            continue
        import json as _j

        cp = _j.loads(f.read_text())
        if not cp.get("relation_results_v3"):
            continue
        doc, g = dmap[dk], gold_all[dk]
        pred = SR.predict(doc, cp)
        rels, _ = S.project_edges_to_mentions(pred["nodes"], pred["edges"])
        per[dk] = S.score_scinlp_unit(g, S.project_nodes_to_mentions(pred["nodes"]), rels, sym)
        codes_all += sc_attribution(doc, g, pred, cp, sym)
    agg = {m: S.aggregate_documents(per, m) for m in ("entity_strict", "rel")}
    n_end = sum(1 for c in codes_all if c not in ("N0", "N1"))
    n_prop = sum(1 for c in codes_all if c not in ("N0", "N1", "P0"))
    return {
        "benchmark": "SciNLP (mention-level, separate; never pooled with P&D)",
        "documents": sorted(per),
        "concept_f1": {
            "variant": "mention_level_entity_strict_ANALOGUE",
            **agg["entity_strict"]["micro"],
        },
        "ancestor_hierarchy_f1": {
            "status": "NOT_EVALUABLE",
            "reason": "NOT_SUPPORTED_NO_IDENTITY_GOLD",
            "f1": None,
        },
        "pair_recall": {
            "variant": "mention_level_ANALOGUE",
            "reached": n_prop,
            "denominator": n_end,
            "recall": n_prop / n_end if n_end else None,
        },
        "relation_macro_f1": {
            "status": "NOT_COMPUTED",
            "reason": "RESEARCH_DECISION_REQUIRED: scorer keeps no per-class classifier outcomes for mention-level gold",
            "f1": None,
        },
        "strict_e2e_edge_f1": {"variant": "relation_strict_mention_level", **agg["rel"]["micro"]},
        "ci_status": agg["rel"]["CI_status"],
        "frozen_check": _sc_check(level, agg),
    }


def _sc_check(level: str, agg: dict) -> dict:
    fz = FROZEN["scinlp"]["levels"][level]["aggregates"]
    return {
        m: agg[m]["micro"] == {k: fz[m]["micro"][k] for k in agg[m]["micro"]}
        or _close(agg[m]["micro"], fz[m]["micro"])
        for m in agg
    }


def _close(a: dict, b: dict) -> bool:
    return all(abs(a[k] - b[k]) < 1e-12 for k in ("tp", "fp", "fn", "f1"))


def pd_check(tag: str, level: str, h: dict) -> dict | None:
    if tag != "heldout":
        return None
    fz = FROZEN["pd"]["levels"][level]
    pairs = {
        "strict_e2e_edge_f1": (h["strict_e2e_edge_f1"]["f1"], fz["pooled_strict_e2e"]["f1"]),
        "concept_f1": (h["concept_f1"]["f1"], fz["pooled_canonical_node"]["f1"]),
        "pair_recall": (h["pair_recall"]["recall"], fz["pair_recall_pooled"]["rate"]),
    }
    return {k: {"new": a, "frozen": b, "match": abs(a - b) < 1e-12} for k, (a, b) in pairs.items()}


def main() -> None:
    before = hash_tree()
    headline: dict = {"pd": {}, "scinlp": {}}
    diag: dict = {"pd": {}, "scinlp": {}}
    for tag in ("pilot", "heldout"):
        for lv in LEVELS_PD:
            try:
                r = R.evaluate_run(tag, lv)
            except (FileNotFoundError, KeyError, AssertionError) as e:  # missing level run dirs
                headline["pd"].setdefault(tag, {})[lv] = {
                    "status": "NOT_AVAILABLE",
                    "reason": repr(e)[:200],
                }
                continue
            if not r["sections"]:
                headline["pd"].setdefault(tag, {})[lv] = {
                    "status": "NOT_AVAILABLE",
                    "reason": "no run dirs",
                }
                continue
            h = r["headline"]
            headline["pd"].setdefault(tag, {})[lv] = {
                "sections": r["sections"],
                "headline": h,
                "frozen_compat": pd_check(tag, lv, h),
                "population": "7 held-out (headline)"
                if tag == "heldout"
                else "pilot (development)",
            }
            diag["pd"].setdefault(tag, {})[lv] = r["diagnostics"]
            print(tag, lv, r["sections"], flush=True)
    for lv in LEVELS_SC:
        s = scinlp_replay(lv)
        headline["scinlp"][lv] = s
        print("scinlp", lv, s["frozen_check"], flush=True)
    after = hash_tree()
    changed = sorted(k for k in before if before[k] != after.get(k))
    meta = {
        "scorer_version": "cr017-1",
        "model_calls": 0,
        "frozen_artifacts_hashed": len(before),
        "frozen_artifacts_changed": changed,
        "relation_macro_low_support_warning": "classes with support <=3 are flagged low-support; read Relation Macro F1 with its per-class support table",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "headline_metrics.json").write_text(
        json.dumps({"meta": meta, **headline}, indent=1, default=str)
    )
    (OUT / "diagnostics.json").write_text(json.dumps({"meta": meta, **diag}, indent=1, default=str))
    print("changed:", changed)


if __name__ == "__main__":
    main()
