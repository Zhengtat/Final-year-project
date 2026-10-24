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


def adjudicator_tier(tiers) -> str:
    """CR-051 (owner, 2026-10-24): the tier the rejected-link adjudicator runs on, from `rejected_link_tier` in configs/concept_policy.yaml
    (default "strong"). Under the luna profile `escalate` is gpt-6-sol, the model the adjudicator was adopted with (CR-021); a profile
    without that tier (configs/default.yaml alone, where `strong` is already sol) falls back to "strong"."""
    import yaml

    from cumap.config import REPO_ROOT

    pol = yaml.safe_load((REPO_ROOT / "configs/concept_policy.yaml").read_text()) or {}
    tier = pol.get("rejected_link_tier", "strong")
    return tier if tier in tiers else "strong"
