"""`cumap gold suggest-student --answer-id <id>`: LLM-drafts a student graph for a
sampled pilot answer (BUILD_PLAN M3 task 3). Writes ONLY to
data/interim/suggestions/student/ — never to data/gold/ (CLAUDE.md rule 2). Only
ever sees `provided_answer`, never `answer_feedback` (CLAUDE.md rule 10). Every
evidence quote is verified as an exact substring of the answer text before the
item is accepted (CLAUDE.md rule 3).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from cumap.gold.validate import verify_quote
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate
from cumap.schemas.chain_links import ChainLink
from cumap.schemas.edges import Evidence, Validation
from cumap.schemas.llm_schemas import StudentGraphSuggestionLLM, build_student_graph_suggestion_v2
from cumap.schemas.relations import RelationRegistry
from cumap.schemas.student import EvidenceSpan, StudentEdge


def known_concepts_block(concepts: list[dict]) -> str:
    if not concepts:
        return "(none drafted yet for this question)"
    return "\n".join(f"- {c['canonical_name']} ({c['node_type']})" for c in concepts)


def suggest_student_graph(
    client: LLMClient,
    prompt_template: PromptTemplate,
    registry: RelationRegistry,
    *,
    answer_id: str,
    question_id: str,
    question: str,
    answer_text: str,
    known_concepts: list[dict],  # [{canonical_name, node_type, concept_id}, ...]
) -> dict:
    """Returns {"edges": [...], "rejected": [...]} of plain dicts, ready to dump to YAML."""
    name_to_id = {c["canonical_name"]: c["concept_id"] for c in known_concepts}
    from cumap.gold.suggest_expert import relation_vocab_block

    rendered = prompt_template.render(
        question=question,
        known_concepts=known_concepts_block(known_concepts),
        answer_text=answer_text,
        relation_vocab=relation_vocab_block(registry),
    )
    result = client.parse(
        task="student_graph",
        prompt_version=prompt_template.version,
        messages=[{"role": "user", "content": rendered}],
        schema=StudentGraphSuggestionLLM,
        model_tier="strong",
    )
    draft: StudentGraphSuggestionLLM = result.output

    edges: list[StudentEdge] = []
    rejected: list[dict] = []

    for i, e in enumerate(draft.edges):
        if not verify_quote(e.evidence_quote, answer_text):
            rejected.append({"index": i, "reason": "evidence_quote not found in answer text", "edge": e.model_dump()})
            continue

        normalised_answer = answer_text
        start = normalised_answer.find(e.evidence_quote)
        if start == -1:  # fell back to whitespace-normalised match; find the closest literal span
            start = 0
        end = start + len(e.evidence_quote)

        source_id = name_to_id.get(e.source_concept_name) if e.source_concept_name else None
        target_id = name_to_id.get(e.target_concept_name) if e.target_concept_name else None

        relation = e.relation if e.relation in registry else "other"

        edges.append(
            StudentEdge(
                source_id=source_id or f"unlinked:{e.source_surface}",
                relation=relation,
                target_id=target_id or f"unlinked:{e.target_surface}",
                polarity=e.polarity,
                modality=e.modality,
                conditions=e.conditions,
                response_id=answer_id,
                question_id=question_id,
                evidence_span=EvidenceSpan(start=start, end=end, text=e.evidence_quote),
                stance=e.stance,
                extraction_confidence=e.extraction_confidence,
                link_confidence=0.0 if (source_id is None and target_id is None) else e.link_confidence,
            )
        )

    return {
        "edges": [edge.model_dump(mode="json") for edge in edges],
        "rejected": rejected,
    }


def write_student_suggestion(draft: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True))


def suggest_student_graph_v2(
    client: LLMClient,
    prompt_template: PromptTemplate,
    registry: RelationRegistry,
    *,
    answer_id: str,
    question_id: str,
    question: str,
    answer_text: str,
    known_concepts: list[dict],
    fixture_name: str = "default",
) -> dict:
    """CR-001 §7.2: v1-registry-aware version of suggest_student_graph. Returns
    {"edges": [...], "chain_links": [...], "rejected": [...]}. Student edges have no
    stable id (StudentEdge doesn't carry one), so chain_links address them by their
    final position in `edges` as "SE-<index>" — the same convention
    cumap.gold.validate uses when checking a saved student_pilot file.
    """
    from cumap.gold.suggest_expert import relation_guideline_block

    name_to_id = {c["canonical_name"]: c["concept_id"] for c in known_concepts}

    rendered = prompt_template.render(
        question=question,
        known_concepts=known_concepts_block(known_concepts),
        answer_text=answer_text,
        relation_guideline=relation_guideline_block(registry),
    )
    schema = build_student_graph_suggestion_v2(registry)
    result = client.parse(
        task="student_graph",
        prompt_version=prompt_template.version,
        messages=[{"role": "user", "content": rendered}],
        fixture_name=fixture_name,
        schema=schema,
        model_tier="strong",
    )
    draft = result.output

    edges: list[StudentEdge] = []
    rejected: list[dict] = []
    llm_index_to_synthetic_id: dict[int, str] = {}

    for i, e in enumerate(draft.edges):
        if not verify_quote(e.evidence_quote, answer_text):
            rejected.append({"index": i, "reason": "evidence_quote not found in answer text", "edge": e.model_dump()})
            continue

        start = answer_text.find(e.evidence_quote)
        if start == -1:
            start = 0
        end = start + len(e.evidence_quote)

        source_id = name_to_id.get(e.source_concept_name) if e.source_concept_name else None
        target_id = name_to_id.get(e.target_concept_name) if e.target_concept_name else None
        relation = e.relation if (e.relation in registry or e.relation == "other") else "other"

        edges.append(
            StudentEdge(
                source_id=source_id or f"unlinked:{e.source_surface}",
                relation=relation,
                target_id=target_id or f"unlinked:{e.target_surface}",
                polarity=e.polarity,
                modality=e.modality,
                conditions=e.conditions,
                part_type=e.part_type,
                dimension=e.dimension,
                surface_phrase=e.surface_phrase,
                relation_family=registry.family_of(relation) if relation in registry else None,
                registry_version=registry.version,
                response_id=answer_id,
                question_id=question_id,
                evidence_span=EvidenceSpan(start=start, end=end, text=e.evidence_quote),
                stance=e.stance,
                extraction_confidence=e.extraction_confidence,
                link_confidence=0.0 if (source_id is None and target_id is None) else e.link_confidence,
            )
        )
        llm_index_to_synthetic_id[i] = f"SE-{len(edges) - 1}"

    chain_links: list[ChainLink] = []
    for i, cl in enumerate(draft.chain_links):
        from_id = llm_index_to_synthetic_id.get(cl.from_edge_index)
        to_id = llm_index_to_synthetic_id.get(cl.to_edge_index)
        if from_id is None or to_id is None:
            rejected.append({"kind": "chain_link", "index": i, "reason": "from/to edge index was rejected or out of range", "chain_link": cl.model_dump()})
            continue
        if not verify_quote(cl.evidence_quote, answer_text):
            rejected.append({"kind": "chain_link", "index": i, "reason": "evidence_quote not found in answer text", "chain_link": cl.model_dump()})
            continue
        chain_links.append(
            ChainLink(
                link_id=f"CL-{answer_id}-{i:03d}",
                from_edge_id=from_id,
                to_edge_id=to_id,
                type=cl.type,
                statement=cl.statement,
                surface_phrase=cl.surface_phrase,
                evidence=[Evidence(source="student answer", answer_id=answer_id, quote=cl.evidence_quote)],
                origin="student",
                question_ids=[question_id],
                validation=Validation(status="unreviewed"),
            )
        )

    return {
        "registry_version": registry.version,
        "edges": [edge.model_dump(mode="json") for edge in edges],
        "chain_links": [c.model_dump(mode="json") for c in chain_links],
        "rejected": rejected,
    }
