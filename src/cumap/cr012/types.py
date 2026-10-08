"""CR-012 shared data types. Spans are half-open `(start, end)` in the unit's own coordinate system: token indices for SciNLP
(documents are pre-tokenised), character offsets for P&D-E2E sections."""

from __future__ import annotations

from dataclasses import dataclass, field

Span = tuple[int, int]


@dataclass(frozen=True)
class GoldMention:
    unit: str
    span: Span
    type: str
    concept_id: str | None = None  # None where the benchmark has no identity gold (SciNLP)


@dataclass(frozen=True)
class GoldConcept:
    concept_id: str
    unit: str
    name: str
    type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoldRelation:
    """Mention-level (SciNLP: src/tgt are mention spans) or concept-level (P&D: src/tgt concept ids)."""

    unit: str
    relation: str
    src_span: Span | None = None
    tgt_span: Span | None = None
    src_concept: str | None = None
    tgt_concept: str | None = None
    qualifiers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PredNode:
    node_id: str
    unit: str
    type: str
    name: str
    mentions: tuple[Span, ...]  # evidence-grounded mention spans of the canonical node


@dataclass(frozen=True)
class PredEdge:
    unit: str
    src: str
    tgt: str
    relation: str
    evidence_span: Span | None = (
        None  # where the supporting quote sits (used to project a node edge to mentions)
    )
    qualifiers: tuple[tuple[str, str], ...] = ()


@dataclass
class UnitGold:
    unit: str
    mentions: list[GoldMention] = field(default_factory=list)
    concepts: list[GoldConcept] = field(default_factory=list)
    relations: list[GoldRelation] = field(default_factory=list)
    not_same: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class PRF:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def to_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }
