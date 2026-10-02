"""CR-007 §6: the P&D ch1-3 slice re-run, stage by stage, each with a preflight cost check.

concepts (prompt v2, cached where the text is unchanged) -> propagate (E3, $0) -> canonicalize v2 (type-aware,
0.70 review band) + first-occurrence/role rules ($0) -> select (coverage-aware global pair budget, $0) -> relations
(registry v1.1, prompts v3, strong tier) -> snapshots ($0). Every LLM call goes through LLMClient, whose stage
budgets are checked before each call; checkpoints are written after each section / batch of pairs so a run can
be resumed. New run_id; old runs are kept.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from cumap.expert_kg.canonicalize import CanonicalOverrides
from cumap.expert_kg.concept_experiments import propagate
from cumap.expert_kg.llm_schemas import QualifiersLLM
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.pair_selection import select_pairs
from cumap.expert_kg.pipeline import (
    Checkpoint,
    PromptSet,
    SectionInput,
    _concept_to_dict,
    _restore_concept_registry,
    build_snapshots_stage,
    load_checkpoint,
    run_canonicalize_stage,
    run_concepts_stage,
    save_checkpoint,
)
from cumap.expert_kg.relations import (
    CandidatePair,
    PairRegistry,
    PairResolution,
    RelationEdgeCandidate,
    concept_vocab,
    enumerate_candidates,
)
from cumap.expert_kg.relations_v3 import V3Result, classify_pair_v3
from cumap.expert_kg.roles import SectionText, apply_first_occurrence, apply_role_rules
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

USD_PER_PAIR = 0.0069  # measured in the STOP 3 pilot (hard pairs; the average pair is cheaper)
USD_PER_CANONICALIZE_CALL = 0.0031  # measured in CR-005


def load_sections(
    source_jsonl: Path, chapters: list[int], domain: str = "computer networking"
) -> list[SectionInput]:
    rows = [
        json.loads(x) for x in source_jsonl.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    rows = sorted(
        (r for r in rows if r.get("chapter_num") in chapters), key=lambda r: r["order_index"]
    )
    return [
        SectionInput(
            section_id=r["section_id"],
            chapter_num=r["chapter_num"],
            text=r["text"],
            heading_path=r["heading_path"],
            domain=domain,
        )
        for r in rows
    ]


def _section_texts(sections: list[SectionInput]) -> list[SectionText]:
    return [SectionText(s.section_id, s.chapter_num, i, s.text) for i, s in enumerate(sections)]


# ---------------------------------------------------------------- stage: propagation ($0)
def propagate_stage(cp: Checkpoint, sections: list[SectionInput]) -> int:
    """E3: tag every accepted concept in each other section where a longest-match mention occurs."""
    texts = {s.section_id: s.text for s in sections}
    before = sum(len(v) for v in cp.mentions_by_section.values())
    final = {s.section_id: list(cp.mentions_by_section.get(s.section_id, [])) for s in sections}
    cp.mentions_by_section = propagate(final, texts)
    return sum(len(v) for v in cp.mentions_by_section.values()) - before


# ---------------------------------------------------------------- stage: canonicalize + roles
def finish_concepts(cp: Checkpoint, sections: list[SectionInput], embed_fn) -> dict[str, int]:
    """First occurrence by longest match, `defined` only on the first definition (later ones `refined`)."""
    registry = _restore_concept_registry(cp, embed_fn)
    concepts = registry.all()
    chapters = apply_first_occurrence(concepts, _section_texts(sections))
    order = {s.section_id: i for i, s in enumerate(sections)}
    for c in concepts:
        apply_role_rules(c, order)
    cp.concepts = [_concept_to_dict(c) for c in concepts]
    cp.concept_first_chapter = {**cp.concept_first_chapter, **chapters}
    return chapters


class _StubClient:
    """Counts the canonicalize calls a real run would make (answers 'different' to everything)."""

    def __init__(self):
        self.calls = 0
        self.run_id = "preflight"

    def parse(self, **kw):
        self.calls += 1

        class _O:
            decision, matched_candidate_index, reason = "different", None, "preflight"

        class _R:
            output = _O()

        return _R()


def preflight_canonicalize(
    cp: Checkpoint, sections, prompts, embed_fn, overrides, tmp_dir: Path
) -> dict:
    stub = _StubClient()
    probe = Checkpoint(**json.loads(json.dumps(asdict(cp))))
    probe.completed_section_ids = []
    run_canonicalize_stage(stub, prompts, sections, embed_fn, tmp_dir, probe, overrides=overrides)  # type: ignore[arg-type]
    return {
        "llm_calls": stub.calls,
        "est_usd": stub.calls * USD_PER_CANONICALIZE_CALL,
        "mentions": sum(len(v) for v in cp.mentions_by_section.values()),
    }


# ---------------------------------------------------------------- stage: pair selection ($0)
def select_stage(
    cp: Checkpoint,
    sections: list[SectionInput],
    registry: RelationRegistry,
    embed_fn,
    *,
    budget: int = 700,
    min_per_section: int = 8,
    sample: int = 50,
    seed: int = 42,
) -> dict:
    concepts = _restore_concept_registry(cp, embed_fn).all()
    per: dict[str, list[CandidatePair]] = {
        s.section_id: enumerate_candidates(s.section_id, s.text, concepts, registry)
        for s in sections
    }
    rank = {"defined": 3, "refined": 3, "used": 2, "mentioned": 1}
    role = {
        c.concept_id: max((m.role for m in c.mentions), key=lambda r: rank.get(r, 0))
        for c in concepts
        if c.mentions
    }
    sel = select_pairs(
        per,
        role,
        budget=budget,
        min_per_section=min_per_section,
        sample_unselected=sample,
        seed=seed,
    )
    cp.selected_pairs = [asdict(p) for p in sel.selected]
    cp.sample_pairs = [asdict(p) for p in sel.unselected_sample]
    cp.selection_stats = {
        **sel.stats,
        "budget": budget,
        "min_per_section": min_per_section,
        "candidate_pairs_before_dedup": sum(len(v) for v in per.values()),
    }
    return cp.selection_stats


def preflight_relations(cp: Checkpoint) -> dict:
    n = len(cp.selected_pairs) + len(cp.sample_pairs)
    done = len(cp.relation_results_v3)
    return {"pairs": n, "already_classified": done, "est_usd_upper": (n - done) * USD_PER_PAIR}


# ---------------------------------------------------------------- stage: relations v3
def relations_stage(
    client: LLMClient,
    cp: Checkpoint,
    run_dir: Path,
    registry: RelationRegistry,
    prompts_dir: Path,
    embed_fn,
    *,
    save_every: int = 20,
    progress=None,
) -> Checkpoint:
    concepts = {c.concept_id: c for c in _restore_concept_registry(cp, embed_fn).all()}
    matcher = MentionMatcher(concept_vocab(list(concepts.values())))
    fam, rel, qual = (
        load_prompt(prompts_dir, t, "v3")
        for t in ("relation_family", "relation_choice", "relation_qualifiers")
    )
    done = {
        frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
        for r in cp.relation_results_v3
    }
    todo = [("selected", p) for p in cp.selected_pairs] + [("sample", p) for p in cp.sample_pairs]
    for i, (group, p) in enumerate(todo):
        key = frozenset((p["concept_x_id"], p["concept_y_id"]))
        if key in done:
            continue
        pair = CandidatePair(**p)
        try:
            res = classify_pair_v3(
                client,
                fam,
                rel,
                qual,
                registry,
                pair,
                concepts[pair.concept_x_id],
                concepts[pair.concept_y_id],
                matcher,
            )
        except BudgetExceededError:
            save_checkpoint(cp, run_dir)
            raise
        cp.relation_results_v3.append({**res.to_dict(), "group": group})
        done.add(key)
        if len(cp.relation_results_v3) % save_every == 0:
            save_checkpoint(cp, run_dir)
            if progress:
                progress(
                    f"{len(cp.relation_results_v3)}/{len(todo)} pairs, spend ${client.spent_usd:.3f}"
                )
    cp.stage = "snapshots"
    save_checkpoint(cp, run_dir)
    return cp


def mark_gated_dropped(cp: Checkpoint, registry: RelationRegistry) -> int:
    """Edges of a relation the registry no longer has (it failed its gate) stay in the run data,
    flagged `gated_dropped`, and are kept out of the graph. Never deleted. Returns how many."""
    n = 0
    for r in cp.relation_results_v3:
        if r["outcome"] == "edge" and r["relation"] not in registry:
            r["gated_dropped"] = True
            n += 1
    return n


def build_pair_registry(cp: Checkpoint) -> PairRegistry:
    """Adapter: v3 results of the SELECTED group -> the PairRegistry the snapshot writer expects. (The
    unselected sample is measurement only and is kept out of the graph.)"""
    reg = PairRegistry()
    edge_pairs: set[frozenset[str]] = set()  # CR-008: an edge on a node pair is never overwritten
    for r in cp.relation_results_v3:
        if r["group"] != "selected" or r.get("self_pair"):
            continue
        if r.get("consolidated_into") or r.get("snapshot_secondary"):
            continue
        pk = frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
        if r["outcome"] != "edge" and pk in edge_pairs:
            continue
        if r["outcome"] == "edge" and not r.get("gated_dropped"):
            edge_pairs.add(pk)
        pair = CandidatePair(**r["pair"])
        edge = None
        if r["outcome"] == "edge" and not r.get("gated_dropped"):
            q = r["qualifiers"]
            edge = RelationEdgeCandidate(
                pair=pair,
                family=r["family"],
                relation=r["relation"],
                direction=r["direction"],
                statement=r["statement"],
                evidence_quote=r["evidence_quote"],
                qualifiers=QualifiersLLM(
                    polarity=q["polarity"],
                    modality=q["modality"],
                    conditions=q["conditions"],
                    part_type=q["part_type"],
                    dimension=q["dimension"],
                    surface_phrase=q["surface_phrase"],
                ),
            )
        reg.restore(
            [
                PairResolution(
                    pair.concept_x_id,
                    pair.concept_y_id,
                    True,
                    edge,
                    None if edge else ("gated_dropped" if r.get("gated_dropped") else (r["reason"] or r["outcome"])),
                    [pair.sentence],
                )
            ]
        )
    return reg


def snapshots_stage(
    cp: Checkpoint,
    run_dir: Path,
    sections: list[SectionInput],
    registry: RelationRegistry,
    embed_fn,
):
    concept_registry = _restore_concept_registry(cp, embed_fn)
    pair_registry = build_pair_registry(cp)
    cp.pair_registry = [_pair_dict(p) for p in pair_registry.all()]
    return build_snapshots_stage(
        registry,
        sections,
        concept_registry,
        pair_registry,
        run_dir / "snapshots",
        cp.run_id,
        merges=cp.merges,
    )


def _pair_dict(p: PairResolution) -> dict:
    from cumap.expert_kg.pipeline import _pair_resolution_to_dict

    return _pair_resolution_to_dict(p)


__all__ = [
    "CanonicalOverrides",
    "PromptSet",
    "V3Result",
    "finish_concepts",
    "load_checkpoint",
    "load_sections",
    "preflight_canonicalize",
    "preflight_relations",
    "propagate_stage",
    "relations_stage",
    "run_canonicalize_stage",
    "run_concepts_stage",
    "save_checkpoint",
    "select_stage",
    "snapshots_stage",
]
