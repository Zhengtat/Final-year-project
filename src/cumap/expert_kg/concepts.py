"""M5 task 2: per-section concept extraction (roles defined/used/mentioned), plus a
gleaning pass. Same prompt family for P&D and IIR — only the `domain` string changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cumap.expert_kg.llm_schemas import build_concept_extraction_llm
from cumap.gold.validate import verify_quote
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate
from cumap.schemas.relations import RelationRegistry


@dataclass
class ConceptMentionCandidate:
    canonical_name: str
    node_type: str
    role: str
    definition: str | None
    evidence_quote: str
    section_id: str
    run_index: int = 0  # which extraction pass found it: 0 = main, 1 = gleaning


@dataclass
class ExtractionResult:
    mentions: list[ConceptMentionCandidate] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


def _run_pass(
    client: LLMClient,
    prompt_template: PromptTemplate,
    registry: RelationRegistry,
    *,
    task: str,
    section_id: str,
    section_text: str,
    heading_path: list[str],
    candidate_terms: list[str],
    domain: str,
    run_index: int,
    fixture_name: str,
    already_found: list[str] | None = None,
) -> ExtractionResult:
    rendered = prompt_template.render(
        domain=domain,
        heading_path=" > ".join(heading_path),
        section_text=section_text,
        candidate_terms=", ".join(candidate_terms) if candidate_terms else "(none)",
        already_found=", ".join(already_found) if already_found else "(none yet)",
    )
    schema = build_concept_extraction_llm(registry)
    result = client.parse(
        task=task,
        prompt_version=prompt_template.version,
        messages=[{"role": "user", "content": rendered}],
        schema=schema,
        model_tier="bulk",
        fixture_name=fixture_name,
    )

    out = ExtractionResult()
    for m in result.output.concepts:
        if not verify_quote(m.evidence_quote, section_text):
            out.rejected.append(
                {"section_id": section_id, "name": m.canonical_name, "reason": "evidence_quote not found in section text", "quote": m.evidence_quote}
            )
            continue
        out.mentions.append(
            ConceptMentionCandidate(
                canonical_name=m.canonical_name,
                node_type=m.node_type,
                role=m.role,
                definition=m.definition,
                evidence_quote=m.evidence_quote,
                section_id=section_id,
                run_index=run_index,
            )
        )
    return out


def extract_concepts_for_section(
    client: LLMClient,
    main_prompt: PromptTemplate,
    gleaning_prompt: PromptTemplate,
    registry: RelationRegistry,
    *,
    section_id: str,
    section_text: str,
    heading_path: list[str],
    candidate_terms: list[str],
    domain: str,
    fixture_name: str = "default",
    gleaning_fixture_name: str = "default",
) -> ExtractionResult:
    """Main pass + one gleaning pass ("list concepts you missed"), merged. Duplicate
    canonical_name (case-insensitive) mentions from the gleaning pass are dropped —
    canonicalisation (across sections) happens separately in canonicalize.py.
    """
    main = _run_pass(
        client, main_prompt, registry, task="concept_extraction",
        section_id=section_id, section_text=section_text, heading_path=heading_path,
        candidate_terms=candidate_terms, domain=domain, run_index=0, fixture_name=fixture_name,
    )
    already_found = [m.canonical_name for m in main.mentions]
    gleaning = _run_pass(
        client, gleaning_prompt, registry, task="concept_extraction_gleaning",
        section_id=section_id, section_text=section_text, heading_path=heading_path,
        candidate_terms=candidate_terms, domain=domain, run_index=1, fixture_name=gleaning_fixture_name,
        already_found=already_found,
    )

    seen_lower = {m.canonical_name.lower() for m in main.mentions}
    merged_mentions = list(main.mentions)
    for m in gleaning.mentions:
        if m.canonical_name.lower() in seen_lower:
            continue
        seen_lower.add(m.canonical_name.lower())
        merged_mentions.append(m)

    return ExtractionResult(mentions=merged_mentions, rejected=main.rejected + gleaning.rejected)
