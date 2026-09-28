"""`cumap gold suggest-expert --qid <id>`: LLM-drafts an expert subgraph for a pilot
question (BUILD_PLAN M3 task 1). Writes ONLY to data/interim/suggestions/expert/ —
never to data/gold/ (CLAUDE.md rule 2). Every evidence quote is verified as an exact
substring of the section text before the item is accepted into the draft; failures
are rejected and logged (CLAUDE.md rule 3).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from cumap.gold.validate import verify_quote
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate
from cumap.schemas.chain_links import ChainLink
from cumap.schemas.edges import Evidence, ExpertEdge, QuestionLink, Validation
from cumap.schemas.llm_schemas import (
    ExpertSubgraphSuggestionLLM,
    build_expert_subgraph_suggestion_v2,
)
from cumap.schemas.nodes import Concept, ConceptMention
from cumap.schemas.relations import RelationRegistry


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def relation_vocab_block(registry: RelationRegistry) -> str:
    """v1-prompt (flat) vocabulary block: name + one-line definition only."""
    return "\n".join(f"- {rel.name}: {rel.definition}" for rel in registry.all_relations())


def relation_guideline_block(registry: RelationRegistry) -> str:
    """v2-prompt (CR-001 §7.2) guideline block: family-grouped, with each relation's
    template, examples and near-miss negatives — the annotation-guideline pattern
    GoLLIE (ICLR 2024) and QA4RE (2023) found drives reliable zero-shot extraction.
    """
    lines = []
    by_family: dict[str, list] = {}
    for rel in registry.all_relations():
        if rel.family is None:
            continue  # v0-only relation with no guideline content; skip for v2 prompts
        by_family.setdefault(rel.family, []).append(rel)

    for family_name, rels in by_family.items():
        family = registry.families.get(family_name)
        lines.append(f"\n## {family.label if family else family_name}\n")
        for rel in rels:
            lines.append(f"- **{rel.name}** — {rel.definition}")
            lines.append(f"  Template: \"{rel.template}\"")
            lines.append(f"  Examples: {'; '.join(rel.examples)}")
            for nm in rel.near_misses:
                lines.append(f"  NOT {nm.relation} (e.g. \"{nm.example}\") — {nm.why}")

    lines.append("\n## Chain-link types (for connecting two edges into a reasoning step)\n")
    for cl in registry.chain_link_types.values():
        lines.append(f"- **{cl.name}** — \"{cl.template}\" — cue words: {', '.join(cl.cues)}")

    return "\n".join(lines)


def suggest_expert_subgraph(
    client: LLMClient,
    prompt_template: PromptTemplate,
    registry: RelationRegistry,
    *,
    question_id: str,
    question: str,
    reference_answer: str,
    section_ids: list[str],
    sections_by_id: dict[str, str],
) -> dict:
    """Returns {"concepts": [...], "edges": [...], "rejected": [...]} of plain dicts,
    ready to dump to YAML. `concepts`/`edges` are validated Concept/ExpertEdge
    instances (as dicts); `rejected` items failed evidence verification or
    referenced an unknown concept and were left out.
    """
    sections_block = "\n\n".join(
        f"[{sid}]\n{sections_by_id[sid]}" for sid in section_ids if sid in sections_by_id
    )
    combined_section_text = "\n\n".join(sections_by_id[sid] for sid in section_ids if sid in sections_by_id)

    rendered = prompt_template.render(
        question=question,
        reference_answer=reference_answer,
        sections_block=sections_block,
        relation_vocab=relation_vocab_block(registry),
    )
    result = client.parse(
        task="expert_subgraph",
        prompt_version=prompt_template.version,
        messages=[{"role": "user", "content": rendered}],
        schema=ExpertSubgraphSuggestionLLM,
        model_tier="strong",
    )
    draft: ExpertSubgraphSuggestionLLM = result.output

    rejected: list[dict] = []
    concepts: list[Concept] = []
    name_to_id: dict[str, str] = {}

    for c in draft.concepts:
        concept_id = "c_" + slugify(c.canonical_name)
        if not verify_quote(c.evidence_quote, combined_section_text):
            rejected.append({"kind": "concept", "name": c.canonical_name, "reason": "evidence_quote not found in section text", "quote": c.evidence_quote})
            continue
        source_section = next((sid for sid in section_ids if verify_quote(c.evidence_quote, sections_by_id.get(sid, ""))), section_ids[0])
        concepts.append(
            Concept(
                concept_id=concept_id,
                canonical_name=c.canonical_name,
                node_type=c.node_type if c.node_type in registry.node_types else "Concept",
                definition=c.definition,
                first_introduced=source_section,
                mentions=[ConceptMention(section_id=source_section, role="defined", quote=c.evidence_quote)],
                status="candidate",
                confidence=0.7,
                extracted_by={"model": result.model, "prompt_version": result.prompt_version, "run_id": result.run_id},
                validation=Validation(status="unreviewed"),
            )
        )
        name_to_id[c.canonical_name] = concept_id

    edges: list[ExpertEdge] = []
    for i, e in enumerate(draft.edges):
        if e.source_concept_name not in name_to_id or e.target_concept_name not in name_to_id:
            rejected.append({"kind": "edge", "index": i, "reason": "source/target concept not in accepted concepts list", "edge": e.model_dump()})
            continue
        if e.relation not in registry:
            rejected.append({"kind": "edge", "index": i, "reason": f"unknown relation {e.relation!r}", "edge": e.model_dump()})
            continue
        if not verify_quote(e.evidence_quote, combined_section_text):
            rejected.append({"kind": "edge", "index": i, "reason": "evidence_quote not found in section text", "edge": e.model_dump()})
            continue
        source_section = next((sid for sid in section_ids if verify_quote(e.evidence_quote, sections_by_id.get(sid, ""))), section_ids[0])
        edges.append(
            ExpertEdge(
                edge_id=f"E-{question_id[2:10]}-{i:03d}",
                source_id=name_to_id[e.source_concept_name],
                target_id=name_to_id[e.target_concept_name],
                relation=e.relation,
                layer=registry.get(e.relation).layer,
                polarity=e.polarity,
                modality=e.modality,
                conditions=e.conditions,
                statement=e.statement,
                criticality=e.criticality,
                question_links=[QuestionLink(question_id=question_id, role="required", weight=1.0, source="reference_answer")],
                chain_id=e.chain_id,
                chain_position=e.chain_position,
                introduced_in=source_section,
                evidence=[Evidence(source="Peterson & Davie 6e", section_id=source_section, quote=e.evidence_quote)],
                extracted_by={"model": result.model, "prompt_version": result.prompt_version, "run_id": result.run_id},
                confidence=0.7,
                validation=Validation(status="unreviewed"),
                origin="textbook",
            )
        )

    n_edges = len(edges) or 1
    for edge in edges:
        for link in edge.question_links:
            link.weight = round(1.0 / n_edges, 4)

    return {
        "concepts": [c.model_dump(mode="json") for c in concepts],
        "edges": [e.model_dump(mode="json") for e in edges],
        "rejected": rejected,
    }


def write_expert_suggestion(draft: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True))


def suggest_expert_subgraph_v2(
    client: LLMClient,
    prompt_template: PromptTemplate,
    registry: RelationRegistry,
    *,
    question_id: str,
    question: str,
    reference_answer: str,
    section_ids: list[str],
    sections_by_id: dict[str, str],
    fixture_name: str = "default",
) -> dict:
    """CR-001 §7.2: v1-registry-aware version of suggest_expert_subgraph — same
    contract, plus part_type/dimension/surface_phrase/relation_family/registry_version
    on every edge and a `chain_links` list. Returns
    {"concepts": [...], "edges": [...], "chain_links": [...], "rejected": [...]}.
    """
    sections_block = "\n\n".join(f"[{sid}]\n{sections_by_id[sid]}" for sid in section_ids if sid in sections_by_id)
    combined_section_text = "\n\n".join(sections_by_id[sid] for sid in section_ids if sid in sections_by_id)

    rendered = prompt_template.render(
        question=question,
        reference_answer=reference_answer,
        sections_block=sections_block,
        relation_guideline=relation_guideline_block(registry),
    )
    schema = build_expert_subgraph_suggestion_v2(registry)
    result = client.parse(
        task="expert_subgraph",
        prompt_version=prompt_template.version,
        messages=[{"role": "user", "content": rendered}],
        fixture_name=fixture_name,
        schema=schema,
        model_tier="strong",
    )
    draft = result.output

    rejected: list[dict] = []
    concepts: list[Concept] = []
    name_to_id: dict[str, str] = {}

    for c in draft.concepts:
        concept_id = "c_" + slugify(c.canonical_name)
        if not verify_quote(c.evidence_quote, combined_section_text):
            rejected.append({"kind": "concept", "name": c.canonical_name, "reason": "evidence_quote not found in section text", "quote": c.evidence_quote})
            continue
        source_section = next((sid for sid in section_ids if verify_quote(c.evidence_quote, sections_by_id.get(sid, ""))), section_ids[0])
        concepts.append(
            Concept(
                concept_id=concept_id,
                canonical_name=c.canonical_name,
                node_type=c.node_type if c.node_type in registry.node_types else "Concept",
                definition=c.definition,
                first_introduced=source_section,
                mentions=[ConceptMention(section_id=source_section, role="defined", quote=c.evidence_quote)],
                status="candidate",
                confidence=0.7,
                extracted_by={"model": result.model, "prompt_version": result.prompt_version, "run_id": result.run_id},
                validation=Validation(status="unreviewed"),
            )
        )
        name_to_id[c.canonical_name] = concept_id

    edges: list[ExpertEdge] = []
    edge_index_to_id: dict[int, str] = {}  # LLM's edge-list position -> assigned edge_id, for chain_links
    for i, e in enumerate(draft.edges):
        if e.source_concept_name not in name_to_id or e.target_concept_name not in name_to_id:
            rejected.append({"kind": "edge", "index": i, "reason": "source/target concept not in accepted concepts list", "edge": e.model_dump()})
            continue
        if e.relation not in registry and e.relation != "other":
            rejected.append({"kind": "edge", "index": i, "reason": f"unknown relation {e.relation!r}", "edge": e.model_dump()})
            continue
        if not verify_quote(e.evidence_quote, combined_section_text):
            rejected.append({"kind": "edge", "index": i, "reason": "evidence_quote not found in section text", "edge": e.model_dump()})
            continue
        source_section = next((sid for sid in section_ids if verify_quote(e.evidence_quote, sections_by_id.get(sid, ""))), section_ids[0])
        edge_id = f"E-{question_id[2:10]}-{i:03d}"
        edges.append(
            ExpertEdge(
                edge_id=edge_id,
                source_id=name_to_id[e.source_concept_name],
                target_id=name_to_id[e.target_concept_name],
                relation=e.relation,
                layer=registry.get(e.relation).layer if e.relation in registry else "semantic",
                polarity=e.polarity,
                modality=e.modality,
                conditions=e.conditions,
                part_type=e.part_type,
                dimension=e.dimension,
                surface_phrase=e.surface_phrase,
                relation_family=registry.family_of(e.relation) if e.relation in registry else None,
                registry_version=registry.version,
                statement=e.statement,
                criticality=e.criticality,
                question_links=[QuestionLink(question_id=question_id, role="required", weight=1.0, source="reference_answer")],
                chain_id=e.chain_id,
                chain_position=e.chain_position,
                introduced_in=source_section,
                evidence=[Evidence(source="Peterson & Davie 6e", section_id=source_section, quote=e.evidence_quote)],
                extracted_by={"model": result.model, "prompt_version": result.prompt_version, "run_id": result.run_id},
                confidence=0.7,
                validation=Validation(status="unreviewed"),
                origin="textbook",
            )
        )
        edge_index_to_id[i] = edge_id

    n_edges = len(edges) or 1
    for edge in edges:
        for link in edge.question_links:
            link.weight = round(1.0 / n_edges, 4)

    chain_links: list[ChainLink] = []
    for i, cl in enumerate(draft.chain_links):
        from_id = edge_index_to_id.get(cl.from_edge_index)
        to_id = edge_index_to_id.get(cl.to_edge_index)
        if from_id is None or to_id is None:
            rejected.append({"kind": "chain_link", "index": i, "reason": "from/to edge index was rejected or out of range", "chain_link": cl.model_dump()})
            continue
        if not verify_quote(cl.evidence_quote, combined_section_text):
            rejected.append({"kind": "chain_link", "index": i, "reason": "evidence_quote not found in section text", "chain_link": cl.model_dump()})
            continue
        source_section = next((sid for sid in section_ids if verify_quote(cl.evidence_quote, sections_by_id.get(sid, ""))), section_ids[0])
        chain_links.append(
            ChainLink(
                link_id=f"CL-{question_id[2:10]}-{i:03d}",
                from_edge_id=from_id,
                to_edge_id=to_id,
                type=cl.type,
                statement=cl.statement,
                surface_phrase=cl.surface_phrase,
                evidence=[Evidence(source="Peterson & Davie 6e", section_id=source_section, quote=cl.evidence_quote)],
                origin="textbook",
                question_ids=[question_id],
                validation=Validation(status="unreviewed"),
            )
        )

    return {
        "registry_version": registry.version,
        "concepts": [c.model_dump(mode="json") for c in concepts],
        "edges": [e.model_dump(mode="json") for e in edges],
        "chain_links": [c.model_dump(mode="json") for c in chain_links],
        "rejected": rejected,
    }
