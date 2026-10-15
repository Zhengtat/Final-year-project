"""CR-021 (adopted 2026-10-15): the LLM-facing schema and the adopted prompt version of the rejected-link adjudicator. Production code
imports from here; the measurement code (`cumap.cr021.adjudicator`) reuses the same schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ADOPTED_VERSION = "v2"  # chosen on dev (accuracy 0.861 vs v1 0.833); held-out passed both rules (DECISIONS 2026-10-15)


class AdjudicationLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["new_concept", "same_as_target", "not_a_concept"]
    evidence_quote: str
    reason: str
    confidence: float
