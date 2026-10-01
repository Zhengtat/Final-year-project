"""CR-007 §4.2: first occurrence and role rules.

- `first_section` / `first_chapter` of a concept is the first section, in book order, containing a
  LONGEST-MATCH mention (mentions.py) of its name or alias. It replaces "first extracted", which
  produced the late-edge effect (an edge whose sentence is in ch2 but whose endpoint was first
  extracted in ch3).
- `defined` is kept ONLY on the first definition in book order. Later `defined` tags become
  `refined`, evidence kept. The canonical description is the first definition; every refinement is
  appended to `description_history` (section, quote, definition). Nothing is overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.relations import concept_vocab


@dataclass(frozen=True)
class SectionText:
    section_id: str
    chapter_num: int
    order_index: int
    text: str


def first_occurrences(
    concepts: list[RegisteredConcept], sections: list[SectionText]
) -> dict[str, SectionText]:
    """concept id -> the earliest section (book order) with a longest-match mention."""
    matcher = MentionMatcher(concept_vocab(concepts))
    found: dict[str, SectionText] = {}
    for sec in sorted(sections, key=lambda s: s.order_index):
        for cid in {m.concept_id for m in matcher.find(sec.text)}:
            found.setdefault(cid, sec)
    return found


def apply_role_rules(concept: RegisteredConcept, order: dict[str, int]) -> None:
    """Keep `defined` on the first definition in book order; later ones become `refined`."""
    ms = sorted(concept.mentions, key=lambda m: order.get(m.section_id, 10**9))
    seen_definition = False
    history = list(concept.description_history)
    known = {(h["section_id"], h["quote"]) for h in history}
    for m in ms:
        if m.role not in ("defined", "refined"):
            continue
        if not seen_definition:
            m.role = "defined"
            seen_definition = True
            if concept.definition is None and m.definition:
                concept.definition = m.definition  # the first definition is the canonical one
            continue
        m.role = "refined"
        if (m.section_id, m.quote) not in known:
            history.append(
                {"section_id": m.section_id, "quote": m.quote, "definition": m.definition}
            )
            known.add((m.section_id, m.quote))
    concept.description_history = history
    concept.mentions = ms


def apply_first_occurrence(
    concepts: list[RegisteredConcept], sections: list[SectionText]
) -> dict[str, int]:
    """Set `first_introduced` to the first longest-match occurrence; returns concept id -> chapter."""
    found = first_occurrences(concepts, sections)
    chapters: dict[str, int] = {}
    for c in concepts:
        sec = found.get(c.concept_id)
        if sec is not None:
            c.first_introduced = sec.section_id
            chapters[c.concept_id] = sec.chapter_num
    return chapters
