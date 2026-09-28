"""M5 task 5: prerequisite candidates from defined -> used later, rule-based (no LLM
call) over a concept's own mention history and the book's section order. Also detects
forward references (used before defined) as a sanity metric (CR-005 §3.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from cumap.expert_kg.canonicalize import RegisteredConcept


@dataclass
class PrerequisiteCandidate:
    concept_id: str
    defined_section_id: str
    used_section_id: str


@dataclass
class ForwardReference:
    concept_id: str
    used_section_id: str
    defined_section_id: str


def _earliest_defined_section(
    concept: RegisteredConcept, order_index: dict[str, int]
) -> str | None:
    defined = [m for m in concept.mentions if m.role == "defined" and m.section_id in order_index]
    if not defined:
        return None
    return min(defined, key=lambda m: order_index[m.section_id]).section_id


def find_prerequisite_candidates(
    concepts: list[RegisteredConcept], section_order: list[str]
) -> list[PrerequisiteCandidate]:
    """A concept defined in section D is a prerequisite candidate for every later
    section U (book order) that uses it. One candidate per (concept, used_section)
    pair, even if the concept is used more than once in that section.
    """
    order_index = {sid: i for i, sid in enumerate(section_order)}
    candidates: list[PrerequisiteCandidate] = []
    for concept in concepts:
        defined_section = _earliest_defined_section(concept, order_index)
        if defined_section is None:
            continue
        defined_idx = order_index[defined_section]
        seen_used_sections: set[str] = set()
        for mention in concept.mentions:
            if mention.role != "used" or mention.section_id not in order_index:
                continue
            if mention.section_id in seen_used_sections:
                continue
            used_idx = order_index[mention.section_id]
            if used_idx > defined_idx:
                seen_used_sections.add(mention.section_id)
                candidates.append(
                    PrerequisiteCandidate(
                        concept_id=concept.concept_id,
                        defined_section_id=defined_section,
                        used_section_id=mention.section_id,
                    )
                )
    return candidates


def find_forward_references(
    concepts: list[RegisteredConcept], section_order: list[str]
) -> list[ForwardReference]:
    """A concept used in section U before its earliest "defined" section D (book
    order) is a forward reference -- a sanity metric, not itself an error.
    """
    order_index = {sid: i for i, sid in enumerate(section_order)}
    refs: list[ForwardReference] = []
    for concept in concepts:
        defined_section = _earliest_defined_section(concept, order_index)
        if defined_section is None:
            continue
        defined_idx = order_index[defined_section]
        seen_used_sections: set[str] = set()
        for mention in concept.mentions:
            if mention.role != "used" or mention.section_id not in order_index:
                continue
            if mention.section_id in seen_used_sections:
                continue
            used_idx = order_index[mention.section_id]
            if used_idx < defined_idx:
                seen_used_sections.add(mention.section_id)
                refs.append(
                    ForwardReference(
                        concept_id=concept.concept_id,
                        used_section_id=mention.section_id,
                        defined_section_id=defined_section,
                    )
                )
    return refs
