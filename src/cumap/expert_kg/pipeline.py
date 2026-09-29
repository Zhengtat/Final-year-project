"""M5 pipeline orchestration (CR-005 §2, redesigned by §9): stage-by-stage, not
section-by-section-interleaved --

  a. concepts for all sections (bulk tier; the disk cache means a re-run never re-bills
     an already-extracted section);
  b. canonicalisation in book order (builds the growing ConceptRegistry);
  c. enumerate candidate pairs offline (no LLM call) and report the exact relation
     call count/cost, with run-level dedup already applied;
  d. relations (only when explicitly invoked -- e.g. after the owner's OK on (c)'s
     estimate);
  e. chapter snapshots, built from the book-order state afterwards.

Checkpointed after every section and after every stage (`save_checkpoint`/
`load_checkpoint`), so a run interrupted by `BudgetExceededError` (raised by
`LLMClient.parse` before it would ever exceed a cap -- CR-005 §9 item 2) or anything
else can `--resume` without re-doing already-completed work. This replaces the
per-chapter, section-interleaved pipeline that produced the $14.03 IIR-dev overrun
with no usable output (docs/DECISIONS.md).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cumap.expert_kg.canonicalize import (
    ConceptRegistry,
    Mention,
    RegisteredConcept,
    canonicalize_mention,
)
from cumap.expert_kg.checks import StructuralCheckResult, check_structure
from cumap.expert_kg.concepts import ConceptMentionCandidate, extract_concepts_for_section
from cumap.expert_kg.llm_schemas import QualifiersLLM
from cumap.expert_kg.prerequisites import find_forward_references, find_prerequisite_candidates
from cumap.expert_kg.relations import (
    CandidatePair,
    PairRegistry,
    PairResolution,
    RelationEdgeCandidate,
    extract_relations_for_section,
    find_candidate_pairs,
)
from cumap.expert_kg.snapshots import (
    ChapterSnapshot,
    SnapshotEdge,
    SnapshotMerge,
    SnapshotNode,
    write_snapshot,
)
from cumap.expert_kg.stats import extract_candidate_terms
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import PromptTemplate, load_prompt
from cumap.schemas.relations import RelationRegistry


@dataclass
class SectionInput:
    section_id: str
    chapter_num: int
    text: str
    heading_path: list[str]
    domain: str


@dataclass
class PromptSet:
    concept_extraction: PromptTemplate
    concept_extraction_gleaning: PromptTemplate
    canonicalize: PromptTemplate
    relation_family: PromptTemplate
    relation_choice: PromptTemplate
    relation_qualifiers: PromptTemplate

    @classmethod
    def load(cls, prompts_dir: Path, *, relation_prompt_version: str = "v2") -> PromptSet:
        return cls(
            concept_extraction=load_prompt(prompts_dir, "concept_extraction", "v1"),
            concept_extraction_gleaning=load_prompt(
                prompts_dir, "concept_extraction_gleaning", "v1"
            ),
            canonicalize=load_prompt(prompts_dir, "canonicalize", "v1"),
            relation_family=load_prompt(prompts_dir, "relation_family", relation_prompt_version),
            relation_choice=load_prompt(prompts_dir, "relation_choice", relation_prompt_version),
            relation_qualifiers=load_prompt(
                prompts_dir, "relation_qualifiers", relation_prompt_version
            ),
        )


# ---------------------------------------------------------------------------
# Checkpoint: serialises everything a resumed run needs to skip already-done work.
# RegisteredConcept.embedding is deliberately excluded -- ConceptRegistry recomputes
# it lazily from embed_fn, and a numpy array isn't JSON-safe.
# ---------------------------------------------------------------------------


@dataclass
class Checkpoint:
    run_id: str
    stage: (
        str  # "concepts" | "canonicalize" | "pairs_enumerated" | "relations" | "snapshots" | "done"
    )
    completed_section_ids: list[str] = field(default_factory=list)  # within the current stage
    mentions_by_section: dict[str, list[dict]] = field(default_factory=dict)  # stage a's output
    rejected_concepts: list[dict] = field(default_factory=list)
    concepts: list[dict] = field(default_factory=list)  # stage b's ConceptRegistry state
    concept_first_chapter: dict[str, int] = field(default_factory=dict)
    merges: list[dict] = field(default_factory=list)
    pair_registry: list[dict] = field(default_factory=list)  # stage d's PairRegistry state
    rejected_relations: list[dict] = field(default_factory=list)


def checkpoint_path(run_dir: Path) -> Path:
    return run_dir / "checkpoint.json"


def save_checkpoint(checkpoint: Checkpoint, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path(run_dir).write_text(json.dumps(asdict(checkpoint), indent=2))


def load_checkpoint(run_dir: Path) -> Checkpoint | None:
    path = checkpoint_path(run_dir)
    if not path.exists():
        return None
    return Checkpoint(**json.loads(path.read_text()))


def _mention_to_dict(m: ConceptMentionCandidate) -> dict:
    return asdict(m)


def _mention_from_dict(d: dict) -> ConceptMentionCandidate:
    return ConceptMentionCandidate(**d)


def _concept_to_dict(c: RegisteredConcept) -> dict:
    d = asdict(c)
    d.pop("embedding", None)
    return d


def _concept_from_dict(d: dict) -> RegisteredConcept:
    d = dict(d)
    d.pop("embedding", None)
    d["mentions"] = [Mention(**m) for m in d.get("mentions", [])]
    return RegisteredConcept(**d)


def _pair_resolution_to_dict(p: PairResolution) -> dict:
    d = {
        "concept_x_id": p.concept_x_id,
        "concept_y_id": p.concept_y_id,
        "resolved": p.resolved,
        "reason": p.reason,
        "evidence_sentences": list(p.evidence_sentences),
        "edge": None,
    }
    if p.edge is not None:
        e = p.edge
        d["edge"] = {
            "pair": asdict(e.pair),
            "family": e.family,
            "relation": e.relation,
            "direction": e.direction,
            "statement": e.statement,
            "evidence_quote": e.evidence_quote,
            "qualifiers": e.qualifiers.model_dump(),
        }
    return d


def _pair_resolution_from_dict(d: dict) -> PairResolution:
    edge = None
    if d.get("edge") is not None:
        e = d["edge"]
        edge = RelationEdgeCandidate(
            pair=CandidatePair(**e["pair"]),
            family=e["family"],
            relation=e["relation"],
            direction=e["direction"],
            statement=e["statement"],
            evidence_quote=e["evidence_quote"],
            qualifiers=QualifiersLLM(**e["qualifiers"]),
        )
    return PairResolution(
        concept_x_id=d["concept_x_id"],
        concept_y_id=d["concept_y_id"],
        resolved=d["resolved"],
        edge=edge,
        reason=d["reason"],
        evidence_sentences=list(d["evidence_sentences"]),
    )


def _restore_concept_registry(checkpoint: Checkpoint, embed_fn) -> ConceptRegistry:
    registry = ConceptRegistry(embed_fn)
    registry.restore([_concept_from_dict(d) for d in checkpoint.concepts])
    return registry


def _restore_pair_registry(checkpoint: Checkpoint) -> PairRegistry:
    pair_registry = PairRegistry()
    pair_registry.restore([_pair_resolution_from_dict(d) for d in checkpoint.pair_registry])
    return pair_registry


# ---------------------------------------------------------------------------
# Stage A: concepts for all sections.
# ---------------------------------------------------------------------------


def run_concepts_stage(
    client: LLMClient,
    prompts: PromptSet,
    registry: RelationRegistry,
    sections: list[SectionInput],
    nlp,
    run_dir: Path,
    checkpoint: Checkpoint,
) -> Checkpoint:
    for section in sections:
        if section.section_id in checkpoint.completed_section_ids:
            continue
        candidate_terms = extract_candidate_terms(section.text, nlp)
        try:
            extraction = extract_concepts_for_section(
                client,
                prompts.concept_extraction,
                prompts.concept_extraction_gleaning,
                registry,
                section_id=section.section_id,
                section_text=section.text,
                heading_path=section.heading_path,
                candidate_terms=candidate_terms,
                domain=section.domain,
            )
        except BudgetExceededError:
            save_checkpoint(checkpoint, run_dir)
            raise
        checkpoint.mentions_by_section[section.section_id] = [
            _mention_to_dict(m) for m in extraction.mentions
        ]
        checkpoint.rejected_concepts.extend(extraction.rejected)
        checkpoint.completed_section_ids.append(section.section_id)
        save_checkpoint(checkpoint, run_dir)

    checkpoint.stage = "canonicalize"
    checkpoint.completed_section_ids = []
    save_checkpoint(checkpoint, run_dir)
    return checkpoint


# ---------------------------------------------------------------------------
# Stage B: canonicalisation, in book order.
# ---------------------------------------------------------------------------


def run_canonicalize_stage(
    client: LLMClient,
    prompts: PromptSet,
    sections: list[SectionInput],  # book order
    embed_fn,
    run_dir: Path,
    checkpoint: Checkpoint,
) -> tuple[Checkpoint, ConceptRegistry]:
    concept_registry = _restore_concept_registry(checkpoint, embed_fn)
    concept_first_chapter: dict[str, int] = dict(checkpoint.concept_first_chapter)
    merges = list(checkpoint.merges)

    for section in sections:
        if section.section_id in checkpoint.completed_section_ids:
            continue
        mentions = [
            _mention_from_dict(d)
            for d in checkpoint.mentions_by_section.get(section.section_id, [])
        ]
        try:
            for mention in mentions:
                outcome = canonicalize_mention(
                    client, prompts.canonicalize, concept_registry, mention
                )
                if outcome.decision == "same" and outcome.llm_called:
                    merges.append(
                        {
                            "concept_id": outcome.concept_id,
                            "alias": mention.canonical_name,
                            "section_id": section.section_id,
                        }
                    )
                concept_first_chapter.setdefault(outcome.concept_id, section.chapter_num)
        except BudgetExceededError:
            checkpoint.concepts = [_concept_to_dict(c) for c in concept_registry.all()]
            checkpoint.concept_first_chapter = concept_first_chapter
            checkpoint.merges = merges
            save_checkpoint(checkpoint, run_dir)
            raise

        checkpoint.completed_section_ids.append(section.section_id)
        checkpoint.concepts = [_concept_to_dict(c) for c in concept_registry.all()]
        checkpoint.concept_first_chapter = concept_first_chapter
        checkpoint.merges = merges
        save_checkpoint(checkpoint, run_dir)

    checkpoint.stage = "pairs_enumerated"
    checkpoint.completed_section_ids = []
    save_checkpoint(checkpoint, run_dir)
    return checkpoint, concept_registry


# ---------------------------------------------------------------------------
# Stage C: offline candidate-pair enumeration (no LLM call). Simulates the run-level
# dedup a real relations stage would apply, so the reported call count is exact, not
# an over-count from re-proposed pairs.
# ---------------------------------------------------------------------------


@dataclass
class SectionPairCounts:
    section_id: str
    chapter_num: int
    kept: int
    overflow: int
    new_pairs: int  # kept pairs not already resolved by an earlier section


@dataclass
class PairEnumerationResult:
    per_section: list[SectionPairCounts]
    total_new_pairs: int  # exact number of pairs that would need a family call


def enumerate_pairs_stage(
    registry: RelationRegistry,
    sections: list[SectionInput],  # book order
    concept_registry: ConceptRegistry,
    *,
    window: int = 0,
    max_pairs: int = 30,
) -> PairEnumerationResult:
    seen_pair_keys: set[frozenset[str]] = set()
    per_section: list[SectionPairCounts] = []

    for section in sections:
        kept, overflow = find_candidate_pairs(
            section.section_id,
            section.text,
            concept_registry.all(),
            registry,
            window=window,
            max_pairs=max_pairs,
        )
        new_pairs = 0
        for pair in kept:
            key = frozenset((pair.concept_x_id, pair.concept_y_id))
            if key not in seen_pair_keys:
                seen_pair_keys.add(key)
                new_pairs += 1
        per_section.append(
            SectionPairCounts(
                section_id=section.section_id,
                chapter_num=section.chapter_num,
                kept=len(kept),
                overflow=len(overflow),
                new_pairs=new_pairs,
            )
        )

    return PairEnumerationResult(per_section=per_section, total_new_pairs=len(seen_pair_keys))


# ---------------------------------------------------------------------------
# Stage D: relations (only when explicitly invoked).
# ---------------------------------------------------------------------------


def run_relations_stage(
    client: LLMClient,
    prompts: PromptSet,
    registry: RelationRegistry,
    sections: list[SectionInput],  # book order
    concept_registry: ConceptRegistry,
    run_dir: Path,
    checkpoint: Checkpoint,
    *,
    window: int = 0,
    max_pairs: int = 30,
) -> tuple[Checkpoint, PairRegistry]:
    pair_registry = _restore_pair_registry(checkpoint)

    for section in sections:
        if section.section_id in checkpoint.completed_section_ids:
            continue
        try:
            section_result = extract_relations_for_section(
                client,
                prompts.relation_family,
                prompts.relation_choice,
                prompts.relation_qualifiers,
                registry,
                pair_registry,
                section_id=section.section_id,
                section_text=section.text,
                concepts=concept_registry.all(),
                window=window,
                max_pairs=max_pairs,
            )
        except BudgetExceededError:
            checkpoint.pair_registry = [_pair_resolution_to_dict(p) for p in pair_registry.all()]
            save_checkpoint(checkpoint, run_dir)
            raise

        for c in section_result.classifications:
            if c.edge is None and not c.already_resolved:
                checkpoint.rejected_relations.append(
                    {
                        "section_id": section.section_id,
                        "pair_id": c.pair.pair_id,
                        "reason": c.reason,
                    }
                )
        checkpoint.completed_section_ids.append(section.section_id)
        checkpoint.pair_registry = [_pair_resolution_to_dict(p) for p in pair_registry.all()]
        save_checkpoint(checkpoint, run_dir)

    checkpoint.stage = "snapshots"
    checkpoint.completed_section_ids = []
    save_checkpoint(checkpoint, run_dir)
    return checkpoint, pair_registry


# ---------------------------------------------------------------------------
# Stage E: chapter snapshots, built from book-order state.
# ---------------------------------------------------------------------------


@dataclass
class ChapterResult:
    chapter_num: int
    snapshot: ChapterSnapshot
    structural_check: StructuralCheckResult


def build_snapshots_stage(
    registry: RelationRegistry,
    sections: list[SectionInput],  # book order
    concept_registry: ConceptRegistry,
    pair_registry: PairRegistry | None,
    snapshots_dir: Path,
    run_id: str,
    merges: list[dict] | None = None,
) -> list[ChapterResult]:
    merges = merges or []
    section_order = [s.section_id for s in sections]
    prereqs = find_prerequisite_candidates(concept_registry.all(), section_order)
    fwd_refs = find_forward_references(concept_registry.all(), section_order)

    concept_first_chapter: dict[str, int] = {}
    for section in sections:
        for concept in concept_registry.all():
            if concept.concept_id in concept_first_chapter:
                continue
            if any(m.section_id == section.section_id for m in concept.mentions):
                concept_first_chapter[concept.concept_id] = section.chapter_num

    edges: list[SnapshotEdge] = []
    if pair_registry is not None:
        for resolution in pair_registry.all():
            if resolution.edge is None:
                continue
            x_chapter = concept_first_chapter.get(resolution.concept_x_id, 0)
            y_chapter = concept_first_chapter.get(resolution.concept_y_id, 0)
            edges.append(
                SnapshotEdge(
                    edge_id=resolution.edge.pair.pair_id,
                    source_concept_id=resolution.concept_x_id,
                    relation=resolution.edge.relation,
                    target_concept_id=resolution.concept_y_id,
                    family=resolution.edge.family,
                    source_chapter=x_chapter,
                    target_chapter=y_chapter,
                    section_id=resolution.edge.pair.section_id,
                )
            )

    chapters = sorted({s.chapter_num for s in sections})
    results: list[ChapterResult] = []
    for chapter_num in chapters:
        chapter_section_ids = {s.section_id for s in sections if s.chapter_num == chapter_num}
        nodes = [
            SnapshotNode(
                concept_id=c.concept_id,
                canonical_name=c.canonical_name,
                node_type=c.node_type,
                first_introduced_chapter=concept_first_chapter.get(c.concept_id, chapter_num),
                aliases=list(c.aliases),
                mention_section_count=len(c.mentions),
            )
            for c in concept_registry.all()
            if any(m.section_id in chapter_section_ids for m in c.mentions)
        ]
        chapter_edges = [e for e in edges if e.section_id in chapter_section_ids]
        chapter_types = {c.concept_id: c.node_type for c in concept_registry.all()}
        structural_check = check_structure(
            [
                RelationEdgeCandidate(
                    pair=CandidatePair(
                        pair_id=e.edge_id,
                        section_id=e.section_id,
                        concept_x_id=e.source_concept_id,
                        concept_y_id=e.target_concept_id,
                        sentence="",
                    ),
                    family=e.family,
                    relation=e.relation,
                    direction="forward",
                    statement="",
                    evidence_quote="",
                    qualifiers=QualifiersLLM(
                        polarity="affirmed",
                        modality="always",
                        conditions=[],
                        part_type=None,
                        dimension=None,
                        surface_phrase="",
                    ),
                )
                for e in chapter_edges
            ],
            chapter_types,
            registry,
        )

        chapter_merges = [
            SnapshotMerge(concept_id=m["concept_id"], alias=m["alias"], section_id=m["section_id"])
            for m in merges
            if m["section_id"] in chapter_section_ids
        ]
        prereq_count = sum(1 for p in prereqs if p.used_section_id in chapter_section_ids)
        fwd_ref_count = sum(1 for r in fwd_refs if r.used_section_id in chapter_section_ids)

        snapshot = ChapterSnapshot(
            run_id=run_id,
            chapter_num=chapter_num,
            nodes=nodes,
            edges=chapter_edges,
            merges=chapter_merges,
            rejected=[],
            prerequisite_candidate_count=prereq_count,
            forward_reference_count=fwd_ref_count,
        )
        write_snapshot(snapshot, snapshots_dir)
        results.append(
            ChapterResult(
                chapter_num=chapter_num, snapshot=snapshot, structural_check=structural_check
            )
        )

    return results
