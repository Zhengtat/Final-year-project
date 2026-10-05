"""CR-010 STOP 4: pair-selection pools P0-P3 and the pair-recall metric ($0 enumeration, no model).

Pair recall = validated true edges whose endpoint pair reached classification / validated true edges for which BOTH
endpoint nodes exist. A missing endpoint is a node-recall failure (excluded from the denominator and counted
separately); a proposed pair that gets the wrong relation is a classification failure (not measured here).

    P0  the frozen CR-009 selection (budget-limited, anchor-first coverage), unchanged;
    P1  P0 + the same-sentence co-mention pairs the budget left out (the enumeration is complete at window 0);
    P2  P1 + relation-cue expansion: pairs whose concepts sit in ADJACENT sentences (window 1) and whose span holds a
        registry relation cue;
    P3  P2 + pairs prioritised by the experimental eRST graph (needs the discourse graph; built later, evidence only).

    uv run python -m cumap.cr010.pair_pools --run slice3_c2
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict

import numpy as np

from cumap.config import REPO_ROOT, get_settings, load_demo_slice
from cumap.eval.stats import wilson_ci
from cumap.expert_kg import slice_rerun as sr
from cumap.expert_kg.pair_selection import dedupe, pair_key
from cumap.expert_kg.pipeline import load_checkpoint
from cumap.expert_kg.relations import (
    _cue_words,
    enumerate_candidates,
    sentence_mentions,
    split_sentences,
)
from cumap.schemas.relations import RelationRegistry

# P2 "high-confidence" cue proposal (to be confirmed by Research): word-boundary match on relation-bearing cues only; the
# function words of the shared cue list (for, so, if, but, then, when, while, since, after, before, until, next, once)
# and the copula 'is a' are left out. The frozen P0 ranking keeps its own (substring) cue score untouched.
FUNCTION_CUES = frozenset(
    {
        "for",
        "so",
        "if",
        "but",
        "then",
        "when",
        "while",
        "since",
        "after",
        "afterwards",
        "before",
        "until",
        "next",
        "once",
        "is a",
    }
)


def strict_cue(span: str, cues: set[str]) -> bool:
    low = span.lower()
    return any(
        re.search(rf"(?<![a-z]){re.escape(c)}(?![a-z])", low)
        for c in cues
        if c not in FUNCTION_CUES
    )


def adjacent_pairs(text: str, concepts, cues: set[str]) -> dict[frozenset[str], dict]:
    """Pairs whose concepts are mentioned in ADJACENT sentences (never in the same one): the two-sentence span, whether it
    holds a cue under the loose (substring, as the frozen ranking) or the strict rule."""
    sentences = split_sentences(text)
    mentions = sentence_mentions(sentences, concepts)
    ids = [c.concept_id for c in concepts if mentions.get(c.concept_id)]
    out: dict[frozenset[str], dict] = {}
    for i, x in enumerate(ids):
        for y in ids[i + 1 :]:
            same = any(a == b for a in mentions[x] for b in mentions[y])
            hits = [(a, b) for a in mentions[x] for b in mentions[y] if abs(a - b) == 1]
            if same or not hits:
                continue
            span = " ".join(sentences[min(hits[0]) : max(hits[0]) + 1])
            out[frozenset((x, y))] = {
                "loose_cue": any(c in span.lower() for c in cues),
                "strict_cue": strict_cue(span, cues),
            }
    return out


USD_PER_PAIR = 0.0083  # measured on slice3_c2: $9.58 for 1,150 strong-tier classifications


def pair_recall(
    valid_edges: list[tuple[str, str]], node_ids: set[str], reached: set[frozenset[str]]
) -> dict:
    """`valid_edges`: validated true edges as (concept_id, concept_id). Edges with a missing endpoint node are a
    node-recall failure and leave the denominator."""
    eligible = [e for e in valid_edges if e[0] in node_ids and e[1] in node_ids]
    hit = [e for e in eligible if frozenset(e) in reached]
    return {
        "validated_true_edges": len(valid_edges),
        "missing_endpoint_excluded": len(valid_edges) - len(eligible),
        "denominator": len(eligible),
        "reached_classification": len(hit),
        "pair_recall": (len(hit) / len(eligible)) if eligible else None,
    }


def enumerate_pools(run: str) -> dict:
    settings = get_settings()
    cfg = load_demo_slice()
    sections = sr.load_sections(REPO_ROOT / cfg.pd.source_jsonl, list(cfg.pd.chapters))
    cp = load_checkpoint(REPO_ROOT / "data/processed/kg" / run)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    concepts = sr._restore_concept_registry(cp, lambda t: np.zeros(1)).all()
    w0 = {
        s.section_id: enumerate_candidates(s.section_id, s.text, concepts, registry)
        for s in sections
    }
    universe0 = {pair_key(p): p for p in dedupe(w0)}
    p0 = {frozenset((p["concept_x_id"], p["concept_y_id"])) for p in cp.selected_pairs}
    sample = {frozenset((p["concept_x_id"], p["concept_y_id"])) for p in cp.sample_pairs}
    p1_extra = set(universe0) - p0 - sample
    cues = _cue_words(registry)
    adj: dict[frozenset[str], dict] = {}
    for sec in sections:
        for k, v in adjacent_pairs(sec.text, concepts, cues).items():
            if k in universe0:
                continue
            cur = adj.setdefault(k, {"loose_cue": False, "strict_cue": False, "sections": set()})
            cur["loose_cue"] |= v["loose_cue"]
            cur["strict_cue"] |= v["strict_cue"]
            cur["sections"].add(sec.section_id)
    p2_loose = {k for k, v in adj.items() if v["loose_cue"]}
    p2_extra = {
        k for k, v in adj.items() if v["strict_cue"]
    }  # the proposed "high-confidence" cue expansion
    outside = p0 - set(universe0)
    return {
        "run": run,
        "frozen_selection_reproduced": {
            "unique_window0_pairs_now": len(universe0),
            "unique_window0_pairs_recorded": cp.selection_stats["unique_candidate_pairs"],
            "match": len(universe0) == cp.selection_stats["unique_candidate_pairs"],
            "p0_pairs": len(p0),
            "p0_pairs_outside_the_same_sentence_universe": len(outside),
        },
        "pools": {
            "P0": len(p0),
            "P0_unselected_random_sample_classified": len(sample),
            "P1_extra_same_sentence": len(p1_extra),
            "adjacent_sentence_pairs_not_in_the_same_sentence_universe": len(adj),
            "P2_extra_strict_cue (proposed definition)": len(p2_extra),
            "P2_extra_loose_cue (the frozen substring cue; not selective)": len(p2_loose),
            "P3_extra": "needs the experimental eRST graph (evidence-span scope)",
        },
        "cue_signal": {
            "note": "the frozen ranking tests cues by substring ('for' fires in 'information', 'so' in 'also'); strict = word boundary, function words (for, so, if, but, then, when, while, since, after, before, until, next, once, is a) excluded",
            "strict_cues": sorted(c for c in cues if c not in FUNCTION_CUES),
        },
        "by_section_p2_extra": dict(
            Counter(sec for k in p2_extra for sec in adj[k]["sections"]).most_common()
        ),
        "full_classification_cost_usd": {
            "P1_extra": round(len(p1_extra) * USD_PER_PAIR, 1),
            "P2_extra": round(len(p2_extra) * USD_PER_PAIR, 1),
        },
        "_sets": {"p0": p0, "sample": sample, "p1_extra": p1_extra, "p2_extra": p2_extra},
        "_cp": cp,
    }


def p0_miss_indication(cp) -> dict:
    """From the CR-007 random sample of UNSELECTED same-sentence pairs (seeded, uniform): the classifier-accepted yield
    among them, with a Wilson interval, projected on the unselected universe. UNVALIDATED (no owner marks): the accepted
    share of the selected set was owner-measured at about 90% precision, the unselected share has not been."""
    rr = cp.relation_results_v3
    s = [r for r in rr if r.get("group") == "sample"]
    sel_edges = sum(
        1
        for r in rr
        if r.get("group", "selected") == "selected"
        and r["outcome"] == "edge"
        and not r.get("gated_dropped")
        and not r.get("consolidated_into")
    )
    n_unsel = cp.selection_stats["unique_candidate_pairs"] - cp.selection_stats["selected"]
    k = sum(r["outcome"] == "edge" for r in s)
    w = wilson_ci(k, len(s))
    proj = lambda y: y * n_unsel
    rec = lambda e: sel_edges / (sel_edges + e)
    return {
        "sample_size": len(s),
        "sample_accepted_edges": k,
        "unselected_yield": {"point": w.point_estimate, "wilson95": [w.low, w.high]},
        "unselected_pairs": n_unsel,
        "projected_unselected_accepted_edges": {
            "point": round(proj(w.point_estimate)),
            "range": [round(proj(w.low)), round(proj(w.high))],
        },
        "selected_accepted_edges": sel_edges,
        "classifier_accepted_pair_recall_of_p0": {
            "point": round(rec(proj(w.point_estimate)), 3),
            "range": [round(rec(proj(w.high)), 3), round(rec(proj(w.low)), 3)],
        },
        "status": "indicative only: classifier-accepted edges, not owner-validated; n=50",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="slice3_c2")
    ap.add_argument("--out", default="data/interim/checks/cr010_pair_pools_summary.json")
    a = ap.parse_args()
    d = enumerate_pools(a.run)
    out = {k: v for k, v in d.items() if not k.startswith("_")}
    out["p0_miss_indication"] = p0_miss_indication(d["_cp"])
    (REPO_ROOT / a.out).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    _ = asdict


if __name__ == "__main__":
    main()
