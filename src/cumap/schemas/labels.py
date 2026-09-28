"""M4 silver-label schemas: Proposition, PropositionLabel, ExtraError, SilverAnswerLabel.

Built from SAF's `answer_feedback` (privileged, CLAUDE.md rule 10) — only the M4
labeller reads that column; these output schemas carry no feedback text themselves,
only quotes/labels derived from it, and are safe for the diagnosis pipeline to read.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cumap.schemas.enums import AnswerLabel3Way, Criticality, PropositionLabelValue


class PropositionTriple(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    relation: str
    target: str
    polarity: str
    conditions: list[str] = []


class Proposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prop_id: str
    question_id: str
    text: str
    triple: PropositionTriple | None = None
    criticality: Criticality
    weight: float


class PropositionLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_id: str
    prop_id: str
    label: PropositionLabelValue
    answer_quote: str | None = None
    feedback_quote: str | None = None


class ExtraError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_id: str
    description: str
    answer_quote: str | None = None
    feedback_quote: str | None = None


class SilverAnswerLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_id: str
    question_id: str
    proposition_labels: list[PropositionLabel]
    extra_errors: list[ExtraError] = []
    label_3way: AnswerLabel3Way
    run_id: str
