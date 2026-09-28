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
from cumap.schemas.llm_schemas import StudentGraphSuggestionLLM
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
