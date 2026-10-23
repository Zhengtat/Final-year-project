"""CR-013 pair-selection REPLAY layer (Research decision D1).

The retained `slice3_c2` run kept only the selected pairs and aggregate selection stats, not the eligible pool or per-pair ranks. This module recomputes the pool
with the FROZEN deterministic code (`enumerate_candidates`, `dedupe`, `select_stage`: no model call) from the run's own retained concepts, anchors and the
section texts, and then checks that the replay reproduces the retained selected set EXACTLY (ids, order), the retained 50-pair unselected sample and the retained
selection stats. If any of these differ the replay is INVALID and no replayed rank is emitted (nothing is tuned to fit). Replayed ranks are always labelled
`REPLAYED`; they were never originally recorded."""

from __future__ import annotations

import copy
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path

from cumap.config import REPO_ROOT


def file_sha(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()


CODE_FILES = [
    "src/cumap/expert_kg/pair_selection.py",
    "src/cumap/expert_kg/slice_rerun.py",
    "src/cumap/expert_kg/relations.py",
]


@contextmanager
def _matching(mode: str):
    """Temporarily set CUMAP_MATCHING (CR-020), restoring the previous value."""
    prev = os.environ.get("CUMAP_MATCHING")
    os.environ["CUMAP_MATCHING"] = mode
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("CUMAP_MATCHING", None)
        else:
            os.environ["CUMAP_MATCHING"] = prev


def replay_pair_pool(
    run_dir: Path, sections, registry, embed_fn, *, budget: int, use_anchors: bool = True
) -> dict:
    """-> {"valid": bool, "mismatches": [...], "pool": [...], "eligible_count", "budget", "code_hashes"}. Read-only: the loaded checkpoint copies are never saved."""
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.pair_selection import _rank, dedupe, pair_key
    from cumap.expert_kg.pipeline import load_checkpoint
    from cumap.expert_kg.relations import enumerate_candidates

    cp = load_checkpoint(run_dir)
    retained_selected = [p["pair_id"] for p in cp.selected_pairs]
    retained_sample = [p["pair_id"] for p in cp.sample_pairs]
    retained_stats = copy.deepcopy(cp.selection_stats)

    cp2 = load_checkpoint(run_dir)  # an independent copy that select_stage may overwrite in memory
    mode = retained_stats.get(
        "matching_mode", "token"
    )  # CR-020: replay with the run's own matching
    with _matching(mode):
        stats = sr.select_stage(
            cp2, sections, registry, embed_fn, budget=budget, use_anchors=use_anchors
        )
    mismatches: list[str] = []
    if [p["pair_id"] for p in cp2.selected_pairs] != retained_selected:
        mismatches.append("selected_pairs ids/order differ from the retained selected set")
    if [p["pair_id"] for p in cp2.sample_pairs] != retained_sample:
        mismatches.append("unselected sample differs from the retained sample")
    if stats != retained_stats:
        mismatches.append("selection_stats differ from the retained stats")

    concepts = sr._restore_concept_registry(cp, embed_fn).all()
    with _matching(mode):  # the pool must be enumerated with the same matching as the selection
        per = {
            s.section_id: enumerate_candidates(s.section_id, s.text, concepts, registry)
            for s in sections
        }
    pool = dedupe(per)
    if len(pool) != retained_stats["unique_candidate_pairs"]:
        mismatches.append(
            f"pool size {len(pool)} != retained unique_candidate_pairs {retained_stats['unique_candidate_pairs']}"
        )
    pool_keys = {"|".join(sorted(pair_key(p))) for p in pool}
    key_of = lambda p: "|".join(sorted((p["concept_x_id"], p["concept_y_id"])))
    anchor_keys = {"|".join(sorted((a["concept_id"], a["anchor_id"]))) for a in cp.anchors}
    retained_all = [*cp.selected_pairs, *cp.sample_pairs]
    anchor_pairs = [
        p for p in retained_all if p["pair_id"].startswith("AP-")
    ]  # phase 0b: entered selection from the anchors, outside the enumerated pool
    if any(key_of(p) not in anchor_keys for p in anchor_pairs):
        mismatches.append("an AP- pair is not an anchor pair of the retained anchors")
    retained_by_key = {key_of(p): p for p in retained_all if not p["pair_id"].startswith("AP-")}
    if not set(retained_by_key) <= pool_keys:
        mismatches.append(
            "some retained selected / sample (non-anchor) concept pairs are not in the replayed pool"
        )
    rows: list[dict] = []
    if not mismatches:
        selected_keys = {
            "|".join(sorted((p["concept_x_id"], p["concept_y_id"]))) for p in cp.selected_pairs
        }
        sample_keys = {
            "|".join(sorted((p["concept_x_id"], p["concept_y_id"]))) for p in cp.sample_pairs
        }
        sec_count: dict[str, int] = {}
        for p in pool:
            sec_count[p.section_id] = sec_count.get(p.section_id, 0) + 1
        sec_seen: dict[str, int] = {}
        for i, p in enumerate(pool, 1):
            key = "|".join(sorted(pair_key(p)))
            sec_seen[p.section_id] = sec_seen.get(p.section_id, 0) + 1
            kept = retained_by_key.get(key)
            rows.append({
                "pair_id": kept["pair_id"] if kept else p.pair_id, "pool_pair_id": p.pair_id, "pair_key": key, "concept_x_id": p.concept_x_id, "concept_y_id": p.concept_y_id,
                "section_id": kept["section_id"] if kept else p.section_id, "best_occurrence_section": p.section_id, "cue_score": p.cue_score, "cooccurrence_count": p.cooccurrence_count,
                "global_rank": i, "rank_basis": "best-ranked occurrence of the concept pair", "section_rank": sec_seen[p.section_id], "section_pool": sec_count[p.section_id],
                "selected": key in selected_keys, "in_unselected_sample": key in sample_keys, "rank_key": list(_rank(p)),
            })  # fmt: skip
    return {
        "valid": not mismatches, "mismatches": mismatches, "pool": rows, "eligible_count": len(pool), "budget": budget,
        "retained_selected": len(retained_selected), "anchor_pairs_outside_pool": [p["pair_id"] for p in anchor_pairs], "code_hashes": {f: file_sha(f) for f in CODE_FILES},
    }  # fmt: skip
