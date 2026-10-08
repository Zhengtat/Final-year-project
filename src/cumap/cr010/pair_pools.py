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
from cumap.cr010.strict_cues import StrictCueMatcher, build_matcher, config_hashes, load_config
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

# SUPERSEDED by cr010.strict_cues (Research decision 2026-10-05). Kept only to log the old pool size (the STOP 4 prep rule: word
# boundary, 15 function cues incl. 'is a' left out). The frozen P0 ranking keeps its own (substring) cue score untouched.
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


def strict_cue_v0(span: str, cues: set[str]) -> bool:
    """The STOP 4 prep rule (word boundary, 14 function cues removed). Superseded by cr010.strict_cues; kept only to log old pool sizes."""
    low = span.lower()
    return any(
        re.search(rf"(?<![a-z]){re.escape(c)}(?![a-z])", low)
        for c in cues
        if c not in FUNCTION_CUES
    )


def adjacent_pairs(
    text: str, concepts, cues: set[str], matcher: StrictCueMatcher | None = None
) -> dict[frozenset[str], dict]:
    """Pairs whose concepts are mentioned in ADJACENT sentences (never in the same one). For each: the cue verdicts
    (loose = the frozen substring rule, strict_v0 = the STOP 4 prep word-boundary rule, strict = the frozen CR-010
    matcher) and the two-sentence spans, in sentence order, with the strict verdict per span."""
    matcher = matcher or build_matcher()
    sentences = split_sentences(text)
    mentions = sentence_mentions(sentences, concepts)
    ids = [c.concept_id for c in concepts if mentions.get(c.concept_id)]
    out: dict[frozenset[str], dict] = {}
    for i, x in enumerate(ids):
        for y in ids[i + 1 :]:
            same = any(a == b for a in mentions[x] for b in mentions[y])
            hits = sorted({min(a, b) for a in mentions[x] for b in mentions[y] if abs(a - b) == 1})
            if same or not hits:
                continue
            spans = []
            for lo in hits:
                pair_sents = sentences[lo : lo + 2]
                span = " ".join(pair_sents)
                spans.append(
                    {
                        "first_sentence_index": lo,
                        "text": span,
                        "sentences": pair_sents,
                        "strict": matcher.matches(pair_sents),
                        "loose": any(c in span.lower() for c in cues),
                        "strict_v0": strict_cue_v0(span, cues),
                    }
                )
            out[frozenset((x, y))] = {
                "loose_cue": any(sp["loose"] for sp in spans),
                "strict_v0_cue": any(sp["strict_v0"] for sp in spans),
                "strict_cue": any(sp["strict"] for sp in spans),
                "spans": spans,
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
    """Pools, nested by construction and asserted: P0 (frozen) < P1 = P0 + same-sentence pairs the budget left out
    < P2 = P1 + adjacent-sentence pairs holding a strict cue. Extra pools exclude every earlier pool."""
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
    # P1-extra is every enumerated same-sentence pair P0 left out. The 50 CR-007 random-sample pairs were left out of P0
    # too (classified, but never part of the selection), so they stay in the P1-extra population.
    p1_extra = set(universe0) - p0
    cues = _cue_words(registry)
    matcher = build_matcher()
    order = {s.section_id: i for i, s in enumerate(sections)}
    adj: dict[frozenset[str], dict] = {}
    for sec in sections:
        for k, v in adjacent_pairs(sec.text, concepts, cues, matcher).items():
            if (
                k in universe0 or k in p0
            ):  # earlier pools never re-enter (P0 includes the anchor-derived pairs)
                continue
            cur = adj.setdefault(
                k, {"loose_cue": False, "strict_v0_cue": False, "strict_cue": False, "spans": []}
            )
            for f in ("loose_cue", "strict_v0_cue", "strict_cue"):
                cur[f] |= v[f]
            cur["spans"] += [{**sp, "section_id": sec.section_id} for sp in v["spans"]]
    for v in adj.values():
        v["spans"].sort(
            key=lambda sp: (not sp["strict"], order[sp["section_id"]], sp["first_sentence_index"])
        )
    p2_loose = {k for k, v in adj.items() if v["loose_cue"]}
    p2_v0 = {k for k, v in adj.items() if v["strict_v0_cue"]}
    p2_extra = {k for k, v in adj.items() if v["strict_cue"]}
    p1, p2 = p0 | p1_extra, p0 | p1_extra | p2_extra
    nesting = {
        "p0_subset_p1": p0 <= p1,
        "p1_subset_p2": p1 <= p2,
        "p1_extra_disjoint_from_p0": not (p1_extra & p0),
        "p2_extra_disjoint_from_p0_and_p1": not (p2_extra & p1),
        "sizes": {"P0": len(p0), "P1": len(p1), "P2": len(p2)},
    }
    assert all(v for k, v in nesting.items() if k != "sizes"), nesting
    outside = p0 - set(universe0)
    exact = build_matcher({**load_config(), "lemma_forms": {}})
    cue_hits = {
        k: {
            m
            for sp in v["spans"]
            if sp["strict"]
            for sent in sp["sentences"]
            for m in matcher.find(sent)
        }
        for k, v in adj.items()
        if v["strict_cue"]
    }
    without_is_a = {k for k, h in cue_hits.items() if h - {"is a"}}
    without_forms = {
        k for k, v in adj.items() if any(exact.matches(sp["sentences"]) for sp in v["spans"])
    }
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
            "adjacent_sentence_pairs_outside_P0_and_the_same_sentence_universe": len(adj),
            "P2_extra_strict_cue_FROZEN": len(p2_extra),
            "P2_extra_strict_cue_prep_v0 (superseded)": len(p2_v0),
            "P2_extra_loose_cue (the frozen substring cue; not selective)": len(p2_loose),
            "P3_extra": "needs the experimental eRST graph (evidence-span scope)",
        },
        "nesting": nesting,
        "strict_cue_config": {**config_hashes(), "kept_cues": list(matcher.names)},
        "sensitivity_not_used_for_selection": {
            "P2_extra_if_is_a_were_removed": len(without_is_a),
            "P2_extra_if_inflection_forms_were_not_used (exact tokens only)": len(without_forms),
            "P2_extra_pairs_whose_ONLY_strict_cue_is": dict(
                Counter(next(iter(h)) for h in cue_hits.values() if len(h) == 1).most_common()
            ),
        },
        "by_section_p2_extra": dict(
            Counter(adj[k]["spans"][0]["section_id"] for k in p2_extra).most_common()
        ),
        "full_classification_cost_usd": {
            "P1_extra": round(len(p1_extra) * USD_PER_PAIR, 1),
            "P2_extra": round(len(p2_extra) * USD_PER_PAIR, 1),
        },
        "_sets": {"p0": p0, "sample": sample, "p1_extra": p1_extra, "p2_extra": p2_extra},
        "_universe0": universe0,
        "_adj": adj,
        "_order": order,
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
