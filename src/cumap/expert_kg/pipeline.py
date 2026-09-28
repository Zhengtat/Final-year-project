"""M5 pipeline orchestration (CR-005 §2): processes sections chapter by chapter over
a growing ConceptRegistry, writing a snapshot after each completed chapter, and
stopping *before* starting a new chapter if real spend (`spend_for_run`) is already
at or over `max_usd_per_command` -- a live runtime enforcement of the cap, not just
the pre-run estimate `cost_estimate.py` provides (CR-005 §2 step 5: no code enforced
this as a hard stop before now).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cumap.config import Settings
from cumap.expert_kg.canonicalize import ConceptRegistry, canonicalize_mention
from cumap.expert_kg.checks import StructuralCheckResult, check_structure
from cumap.expert_kg.concepts import extract_concepts_for_section
from cumap.expert_kg.cost_estimate import spend_for_run
from cumap.expert_kg.llm_schemas import QualifiersLLM
from cumap.expert_kg.prerequisites import find_forward_references, find_prerequisite_candidates
from cumap.expert_kg.relations import (
    CandidatePair,
    RelationEdgeCandidate,
    extract_relations_for_section,
)
from cumap.expert_kg.snapshots import (
    ChapterSnapshot,
    SnapshotEdge,
    SnapshotMerge,
    SnapshotNode,
    write_snapshot,
)
from cumap.expert_kg.stats import extract_candidate_terms
from cumap.llm.client import LLMClient
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
    def load(cls, prompts_dir: Path) -> PromptSet:
        return cls(
            concept_extraction=load_prompt(prompts_dir, "concept_extraction", "v1"),
            concept_extraction_gleaning=load_prompt(
                prompts_dir, "concept_extraction_gleaning", "v1"
            ),
            canonicalize=load_prompt(prompts_dir, "canonicalize", "v1"),
            relation_family=load_prompt(prompts_dir, "relation_family", "v1"),
            relation_choice=load_prompt(prompts_dir, "relation_choice", "v1"),
            relation_qualifiers=load_prompt(prompts_dir, "relation_qualifiers", "v1"),
        )


@dataclass
class ChapterResult:
    chapter_num: int
    snapshot: ChapterSnapshot
    structural_check: StructuralCheckResult


@dataclass
class PipelineRunResult:
    run_id: str
    chapters: list[ChapterResult] = field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str | None = None
    spend_usd: float = 0.0


def _group_by_chapter(sections: list[SectionInput]) -> dict[int, list[SectionInput]]:
    chapters: dict[int, list[SectionInput]] = {}
    for s in sections:
        chapters.setdefault(s.chapter_num, []).append(s)
    return chapters


def run_slice(
    client: LLMClient,
    settings: Settings,
    registry: RelationRegistry,
    prompts: PromptSet,
    embed_fn,
    sections: list[SectionInput],
    nlp,
    *,
    snapshots_dir: Path,
    max_usd_per_command: float | None = None,
) -> PipelineRunResult:
    """Processes `sections` chapter by chapter, in the order chapters first appear in
    the list (sections within a chapter may arrive in any order relative to other
    chapters, but the concept registry and prerequisite/forward-reference detection
    assume the *sections themselves* are already in book order within their chapter).
    """
    cap = (
        max_usd_per_command if max_usd_per_command is not None else settings.llm.max_usd_per_command
    )
    concept_registry = ConceptRegistry(embed_fn)
    concept_first_chapter: dict[str, int] = {}
    section_order = [s.section_id for s in sections]
    result = PipelineRunResult(run_id=client.run_id)

    chapters = _group_by_chapter(sections)
    for chapter_num in sorted(chapters):
        spend_so_far = spend_for_run(settings, client.run_id)
        if spend_so_far >= cap:
            result.stopped_early = True
            result.stop_reason = f"spend ${spend_so_far:.2f} already at/over cap ${cap:.2f} before chapter {chapter_num}"
            result.spend_usd = spend_so_far
            return result

        nodes: dict[str, SnapshotNode] = {}
        edges: list[SnapshotEdge] = []
        merges: list[SnapshotMerge] = []
        rejected: list[dict] = []

        for section in chapters[chapter_num]:
            candidate_terms = extract_candidate_terms(section.text, nlp)
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
            rejected.extend(extraction.rejected)

            for mention in extraction.mentions:
                outcome = canonicalize_mention(
                    client, prompts.canonicalize, concept_registry, mention
                )
                if outcome.decision == "same" and outcome.llm_called:
                    merges.append(
                        SnapshotMerge(
                            concept_id=outcome.concept_id,
                            alias=mention.canonical_name,
                            section_id=section.section_id,
                        )
                    )
                concept_first_chapter.setdefault(outcome.concept_id, chapter_num)
                concept = concept_registry.get(outcome.concept_id)
                nodes[concept.concept_id] = SnapshotNode(
                    concept_id=concept.concept_id,
                    canonical_name=concept.canonical_name,
                    node_type=concept.node_type,
                    first_introduced_chapter=concept_first_chapter[concept.concept_id],
                    aliases=list(concept.aliases),
                    mention_section_count=len(concept.mentions),
                )

            relation_results = extract_relations_for_section(
                client,
                prompts.relation_family,
                prompts.relation_choice,
                prompts.relation_qualifiers,
                registry,
                section_id=section.section_id,
                section_text=section.text,
                concepts=concept_registry.all(),
            )
            for r in relation_results:
                if r.edge is None:
                    rejected.append(
                        {
                            "section_id": section.section_id,
                            "pair_id": r.pair.pair_id,
                            "reason": r.reason,
                        }
                    )
                    continue
                edges.append(
                    SnapshotEdge(
                        edge_id=f"E-{section.section_id}-{r.pair.pair_id}",
                        source_concept_id=r.pair.concept_x_id,
                        relation=r.edge.relation,
                        target_concept_id=r.pair.concept_y_id,
                        family=r.edge.family,
                        source_chapter=concept_first_chapter[r.pair.concept_x_id],
                        target_chapter=concept_first_chapter[r.pair.concept_y_id],
                        section_id=section.section_id,
                    )
                )

        # An edge endpoint from an earlier chapter (how cross-chapter edges arise, per
        # CR-005 §2 task 4) may not have been freshly re-extracted as a "mention" this
        # chapter -- back-fill it into this chapter's node list so it's counted as
        # "reused" by compute_growth_metrics, not silently missing.
        for edge in edges:
            for concept_id in (edge.source_concept_id, edge.target_concept_id):
                if concept_id not in nodes:
                    concept = concept_registry.get(concept_id)
                    nodes[concept_id] = SnapshotNode(
                        concept_id=concept.concept_id,
                        canonical_name=concept.canonical_name,
                        node_type=concept.node_type,
                        first_introduced_chapter=concept_first_chapter[concept_id],
                        aliases=list(concept.aliases),
                        mention_section_count=len(concept.mentions),
                    )

        prereqs = find_prerequisite_candidates(concept_registry.all(), section_order)
        fwd_refs = find_forward_references(concept_registry.all(), section_order)
        this_chapter_section_ids = {s.section_id for s in chapters[chapter_num]}
        prereq_count = sum(1 for p in prereqs if p.used_section_id in this_chapter_section_ids)
        fwd_ref_count = sum(1 for r in fwd_refs if r.used_section_id in this_chapter_section_ids)

        concept_types = {c.concept_id: c.node_type for c in concept_registry.all()}
        structural_check = _check_chapter_structure(edges, concept_types, registry)

        snapshot = ChapterSnapshot(
            run_id=client.run_id,
            chapter_num=chapter_num,
            nodes=list(nodes.values()),
            edges=edges,
            merges=merges,
            rejected=rejected,
            prerequisite_candidate_count=prereq_count,
            forward_reference_count=fwd_ref_count,
        )
        write_snapshot(snapshot, snapshots_dir)
        result.chapters.append(
            ChapterResult(
                chapter_num=chapter_num, snapshot=snapshot, structural_check=structural_check
            )
        )

    result.spend_usd = spend_for_run(settings, client.run_id)
    return result


def _check_chapter_structure(
    edges: list[SnapshotEdge],
    concept_types: dict[str, str],
    registry: RelationRegistry,
) -> StructuralCheckResult:
    """Rebuilds RelationEdgeCandidate-shaped input for checks.check_structure from the
    chapter's own SnapshotEdges (direction is already resolved into source/target at
    snapshot-build time, so every edge here is treated as already-forward).
    """
    fake_edges = [
        RelationEdgeCandidate(
            pair=CandidatePair(
                pair_id=e.edge_id,
                section_id=e.section_id,
                concept_x_id=e.source_concept_id,
                concept_y_id=e.target_concept_id,
                paragraph="",
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
        for e in edges
    ]
    return check_structure(fake_edges, concept_types, registry)
