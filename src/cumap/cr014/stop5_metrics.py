"""CR-014 STOP 5: downstream consequences of baseline (U0) vs frozen V3 concepts, same frozen downstream stages. Evaluation-only module (reads the held-out gold
for node-support and merge checks); never imported by a prediction path.

    uv run python -m cumap.cr014.stop5_metrics"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from cumap.config import get_settings
from cumap.expert_kg.lexicon import Lexicon

ROOT = Path(".")
KG = ROOT / "data/processed/kg"
MAN = yaml.safe_load((ROOT / "configs/cr014_manifest.yaml").read_text())
SECS = MAN["heldout_sealed"]
norm = lambda s: " ".join(s.lower().split())


def rid(sid: str) -> str:
    return sid.replace(".", "_")


def log_rows() -> list[dict]:
    return [
        json.loads(x) for x in (ROOT / "data/logs/llm_calls.jsonl").read_text().splitlines() if x
    ]


def spend(rows: list[dict], run_ids: set[str]) -> dict:
    s = get_settings()
    out: dict[str, dict] = defaultdict(
        lambda: {"usd": 0.0, "calls": 0, "cache_hits": 0, "latency_s": 0.0}
    )
    for r in rows:
        if r["run_id"] not in run_ids:
            continue
        o = out[r["task"]]
        o["calls"] += 1
        o["latency_s"] += (r.get("latency_ms") or 0) / 1000
        if r["cache_hit"]:
            o["cache_hits"] += 1
            continue
        t = s.llm.tiers.get(r["model_tier"])
        if t and t.usd_per_1m_input_tokens is not None:
            u = r["usage"]
            o["usd"] += (
                u.get("input_tokens", 0) / 1e6 * t.usd_per_1m_input_tokens
                + u.get("output_tokens", 0) / 1e6 * t.usd_per_1m_output_tokens
            )
    return {
        k: {**v, "usd": round(v["usd"], 4), "latency_s": round(v["latency_s"], 1)}
        for k, v in out.items()
    }


def gold_maps() -> tuple[dict[str, set[str]], dict[str, dict[str, set[str]]]]:
    sents = {
        r["sentence_id"]: r
        for r in csv.DictReader(
            (ROOT / "data/interim/checks/cr014/pd_concept_test_sentences.csv").open(
                encoding="utf-8"
            )
        )
    }
    surf: dict[str, set[str]] = defaultdict(set)
    ids: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for r in csv.DictReader(
        (ROOT / "data/gold/pd_concept_test_blind.csv").open(encoding="utf-8-sig")
    ):
        if r["row_type"] != "MENTION":
            continue
        s = sents[r["sentence_id"]]
        surf[s["section_id"]].add(norm(r["span_text"]))
        ids[s["section_id"]][norm(r["span_text"])].add(r["concept_id"])
    return surf, ids


def arm_metrics(
    arm: str, sid: str, gsurf: set[str], gids: dict[str, set[str]], lex: Lexicon
) -> dict:
    cp = json.loads((KG / f"cr014_heldout_{rid(sid)}_{arm}/checkpoint.json").read_text())
    concepts = cp["concepts"]
    forms = lambda c: {norm(c["canonical_name"]), *(norm(a) for a in c["aliases"])}
    supported = {c["concept_id"] for c in concepts if forms(c) & gsurf}
    res = [r for r in cp["relation_results_v3"] if r.get("group", "selected") == "selected"]
    edges = [
        r
        for r in res
        if r["outcome"] == "edge" and not r.get("gated_dropped") and not r.get("consolidated_into")
    ]
    ep = lambda r: (r["pair"]["concept_x_id"], r["pair"]["concept_y_id"])
    both = sum(1 for r in edges if all(e in supported for e in ep(r)))
    one = sum(1 for r in edges if sum(e in supported for e in ep(r)) == 1)
    # identity: merges whose two forms are mapped to DIFFERENT gold concept ids (false merge vs gold), and lexicon DIFFERENT violations
    by_id = {c["concept_id"]: c for c in concepts}
    false_merge = lexicon_viol = checked = 0
    for m in cp["merges"]:
        c = by_id.get(m["concept_id"])
        if not c or m.get("stage") == "generator":
            continue
        a, b = norm(m["alias"]), norm(c["canonical_name"])
        if a == b:
            continue
        if a in gids and b in gids:
            checked += 1
            false_merge += not (gids[a] & gids[b])
        if lex.is_different(m["alias"], c["canonical_name"]):
            lexicon_viol += 1
    prov_concepts = sum(
        1 for c in concepts if c["mentions"] and all(x.get("quote") for x in c["mentions"])
    )
    return {
        "concepts": len(concepts), "concepts_gold_supported": len(supported), "concepts_unsupported": len(concepts) - len(supported),
        "canonical_merges": len([m for m in cp["merges"] if m.get("stage") != "generator"]), "merge_review_queue": len(cp["merge_review"]),
        "taxonomy_candidates": len(cp["taxonomy_candidates"]), "anchors": len(cp["anchors"]),
        "candidate_pairs": cp["selection_stats"].get("unique_candidate_pairs"), "budget": cp["selection_stats"].get("budget"),
        "selected_pairs": len(cp["selected_pairs"]), "concepts_in_any_candidate": cp["selection_stats"].get("concepts_in_any_candidate"),
        "concepts_covered": cp["selection_stats"].get("concepts_covered"),
        "relation_results": len(res), "outcomes": dict(Counter(r["outcome"] for r in res)), "edges": len(edges),
        "edges_both_endpoints_gold_supported": both, "edges_one_endpoint_supported": one, "edges_no_endpoint_supported": len(edges) - both - one,
        "edge_relations": dict(Counter(r["relation"] for r in edges)),
        "edges_with_evidence_quote": sum(1 for r in edges if r.get("evidence_quote")),
        "merge_pairs_checked_vs_gold": checked, "false_merges_vs_gold": false_merge, "lexicon_different_violations": lexicon_viol,
        "concepts_with_full_provenance": prov_concepts,
    }  # fmt: skip


def main() -> dict:
    rows = log_rows()
    lex = Lexicon.load(ROOT / "configs/term_lexicon.yaml")
    gsurf, gids = gold_maps()
    out: dict = {"sections": {}, "totals": {}}
    tot: dict[str, Counter] = {"U0": Counter(), "V3": Counter()}
    for sid in SECS:
        out["sections"][sid] = {}
        for arm in ("U0", "V3"):
            m = arm_metrics(arm, sid, gsurf[sid], gids[sid], lex)
            out["sections"][sid][arm] = m
            for k, v in m.items():
                if isinstance(v, (int, float)):
                    tot[arm][k] += v
    out["totals"] = {a: dict(c) for a, c in tot.items()}
    runs = {
        "U0": {f"cr014_heldout_{rid(s)}_U0" for s in SECS},
        "V3_proposal_verifier": {f"cr014_heldout_V3_{rid(s)}" for s in SECS},
        "V3_typing": {f"cr014_heldout_{rid(s)}_V3_typing" for s in SECS},
        "V3_canonicalise": {f"cr014_heldout_{rid(s)}_V3_build" for s in SECS},
        "V3_relations": {f"cr014_heldout_{rid(s)}_V3" for s in SECS},
    }
    out["spend_by_stage_task"] = {k: spend(rows, v) for k, v in runs.items()}
    out["spend_totals"] = {
        k: round(sum(t["usd"] for t in v.values()), 3)
        for k, v in out["spend_by_stage_task"].items()
    }
    Path("reports/cr014/stop5_metrics.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps(r["totals"], indent=1)[:3500])
    print(r["spend_totals"])
