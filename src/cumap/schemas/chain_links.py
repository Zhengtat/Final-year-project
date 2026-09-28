"""CR-001 §4.2–4.3 — the reasoning layer: typed links BETWEEN edges (propositions),
modelled on PDTB-3's top-level senses. A ChainLink says *how* one proposition supports
another; a ChainLinkAlignment is the diagnosis verdict on a student's version of that link.

ChainLinks live at the top level of a gold file (a `chain_links:` list sibling to
`concepts:`/`edges:`), not nested inside individual ExpertEdge/StudentEdge objects —
see CR-001 §4.2: "Expert links live in data/gold/expert_pilot/<qid>.yaml under a new
top-level chain_links: list ... Student links live in the student graph file".
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cumap.schemas.edges import Evidence, Validation
from cumap.schemas.enums import ChainLinkMatchType, ChainLinkType, Verdict


class ChainLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: str
    from_edge_id: str  # the supported proposition (A)
    to_edge_id: str  # the supporting proposition (B)
    type: ChainLinkType
    statement: str
    surface_phrase: str | None = None  # the connective as written ("because", "so that", ...)
    evidence: list[Evidence] = []
    origin: str  # "textbook" | "reference_answer" | "manual" | "student"
    question_ids: list[str] = []  # expert links: questions where this link is expected
    validation: Validation | None = None


class ChainLinkAlignment(BaseModel):
    """Diagnosis verdict comparing a student's chain link against the matching expert
    ChainLink (if any). CR-001 §4.3 verdict mapping: wrong_link_type/reversed_link ->
    contradictory (a reasoning-misconception candidate); missing_link -> incomplete.
    """

    model_config = ConfigDict(extra="forbid")

    expert_link_id: str | None
    student_from_edge_id: str | None
    student_to_edge_id: str | None
    match_type: ChainLinkMatchType
    verdict: Verdict
    rationale: str


_CHAIN_LINK_VERDICT = {
    ChainLinkMatchType.EXACT: Verdict.CORRECT,
    ChainLinkMatchType.WRONG_LINK_TYPE: Verdict.CONTRADICTORY,
    ChainLinkMatchType.REVERSED_LINK: Verdict.CONTRADICTORY,
    # CR-001's text maps missing_link to the answer-level "incomplete" label, which is a
    # DiagnosisRecord.label_3way value, not a Verdict — the closest Verdict bucket is
    # inaccurate (a weaker/absent claim), same as StudentEdge's partial_relation default.
    ChainLinkMatchType.MISSING_LINK: Verdict.INACCURATE,
    # By analogy with StudentEdge.unsupported_extra's default mapping (inaccurate, unless
    # the aligner finds it conflicts with a KG edge, which is decided at align time, not here).
    ChainLinkMatchType.UNSUPPORTED_LINK: Verdict.INACCURATE,
}


def verdict_for_chain_link_match(match_type: ChainLinkMatchType) -> Verdict:
    return _CHAIN_LINK_VERDICT[match_type]
